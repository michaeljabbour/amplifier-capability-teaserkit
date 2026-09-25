"""[AI] Find the steps for one beat by trying them in a real browser.

Given a base URL and what the beat should show ("add a task and see it appear"), a model looks
at a screenshot plus a list of the page's interactive elements, proposes one declarative step
at a time, and teaserkit executes it. Failed steps are reported back so the model can recover.
Only steps that actually ran make it into the result, with a suggested ROI and caption.

The browser is headless and isolated (fresh context, no stored credentials unless you pass a
storage-state file). The model can only choose among the declarative step kinds; it cannot run
scripts or reach outside the page it is on.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import yaml

from . import _provider, prereqs
from .errors import RecordingError, TeaserkitError
from .recorder import locator_for

ELEMENTS_JS = """() => {
  const out = [];
  const sel = 'a,button,input,textarea,select,[role],[onclick],label,summary,[tabindex],h1,h2,h3,li,[id]';
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
    const text = (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 70);
    out.push({tag: el.tagName.toLowerCase(), id: el.id || undefined, role: el.getAttribute('role') || undefined,
      text: text || undefined, label: el.getAttribute('aria-label') || undefined, placeholder: el.getAttribute('placeholder') || undefined,
      box: [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]});
    if (out.length >= 90) break;
  }
  return out;
}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "action": {"type": "string", "enum": ["click", "type", "press", "scroll", "hover", "wait_for", "goto", "done"]},
        "locator_kind": {"type": "string", "enum": ["text", "role", "selector", "label", "placeholder", "none"]},
        "locator_value": {"type": "string", "description": "The text/selector/label/placeholder, or the ARIA role for kind=role."},
        "role_name": {"type": "string", "description": "Accessible name when locator_kind=role, else empty."},
        "text": {"type": "string", "description": "Text to type, key to press, or path for goto. Empty otherwise."},
        "dy": {"type": "integer", "description": "Scroll distance in CSS pixels for scroll, else 0."},
        "roi": {"type": "array", "items": {"type": "number"}, "description": "When done: [x0, y0, x1, y1] CSS pixels framing the result."},
        "roi_selector": {"type": "string", "description": "When done: a CSS selector framing the result, or empty."},
        "caption": {"type": "string", "description": "When done: a caption of at most 7 words."},
    },
    "required": ["thought", "action", "locator_kind", "locator_value", "role_name", "text", "dy", "roi", "roi_selector", "caption"],
    "additionalProperties": False,
}

SYSTEM = """You drive a web app one step at a time to film a single beat of a product teaser.
Each turn you get the goal, the steps already run (and any that failed, with the error), a
screenshot, and a list of visible elements with their CSS-pixel boxes. Reply with exactly one
next step, or action=done once the goal's result is on screen.

Prefer locators a person would read: visible text, roles with accessible names, labels, and
placeholders. Use CSS selectors only when nothing else is unique. Type realistic, friendly,
fictional content. Never enter real personal data or credentials. When done, give an ROI that
frames the result with a little margin, and a plain caption of at most 7 words."""


def _step_from(r: dict) -> dict:
    a = r["action"]
    loc = None
    if r["locator_kind"] != "none" and r["locator_value"]:
        loc = {r["locator_kind"]: r["locator_value"]}
        if r["locator_kind"] == "role" and r["role_name"]:
            loc["name"] = r["role_name"]
    if a in ("click", "hover", "wait_for"):
        if not loc:
            raise RecordingError(f"{a} needs a locator", "Give locator_kind and locator_value.")
        return {a: loc}
    if a == "type":
        t = {"text": r["text"], "delay": 45}
        if loc:
            t["into"] = loc
        return {"type": t}
    if a == "press":
        return {"press": r["text"] or "Enter"}
    if a == "scroll":
        return {"scroll": {"dy": int(r["dy"] or 400), "ms": 900}}
    if a == "goto":
        return {"goto": r["text"] or "/"}
    raise RecordingError(f"unknown action {a}", "Use one of the listed actions.")


def _run(page, base: str, st: dict) -> None:
    if "goto" in st:
        url = st["goto"] if re.match(r"^https?://", st["goto"]) else urljoin(base.rstrip("/") + "/", st["goto"].lstrip("/"))
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    elif "click" in st:
        locator_for(page, st["click"]).click(timeout=8_000)
    elif "hover" in st:
        locator_for(page, st["hover"]).hover(timeout=8_000)
    elif "wait_for" in st:
        locator_for(page, st["wait_for"]).wait_for(state="visible", timeout=8_000)
    elif "type" in st:
        if "into" in st["type"]:
            locator_for(page, st["type"]["into"]).click(timeout=8_000)
        page.keyboard.type(st["type"]["text"], delay=15)
    elif "press" in st:
        page.keyboard.press(st["press"])
    elif "scroll" in st:
        page.mouse.wheel(0, st["scroll"]["dy"])
    try:
        page.wait_for_load_state("networkidle", timeout=4_000)
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(400)


def explore(base_url: str, intent: str, *, start: str = "/", max_steps: int = 8, viewport: tuple[int, int] = (1440, 810),
            storage_state: str | Path | None = None, context: str | None = None, screenshots_dir: str | Path | None = None,
            log=None) -> dict:
    """Propose working steps, an ROI and a caption for one beat. Model-backed.

    Returns {"steps", "roi", "roi_selector", "caption", "beat_yaml", "transcript", "final_screenshot"}.
    Raises NoProvider without credentials, TeaserkitError if the goal was not reached in `max_steps`.
    """
    from playwright.sync_api import sync_playwright

    log = log or (lambda s: None)
    _provider.client()  # fail before launching a browser if there is no provider
    history: list[dict] = []
    ok_steps: list[dict] = []
    shots = Path(screenshots_dir) if screenshots_dir else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:  # noqa: BLE001
            raise (prereqs.chromium_missing(e) or RecordingError(f"Could not launch Chromium: {e}", "See docs/installing-playwright.md.")) from e
        try:
            kw = {"viewport": {"width": viewport[0], "height": viewport[1]}}
            if storage_state:
                kw["storage_state"] = str(storage_state)
            page = browser.new_context(**kw).new_page()
            first = {"goto": start}
            _run(page, base_url, first)
            ok_steps.append(first)
            for i in range(max_steps):
                png = page.screenshot(type="jpeg", quality=80)
                if shots:
                    (shots / f"explore-{i:02d}.jpg").write_bytes(png)
                elements = page.evaluate(ELEMENTS_JS)
                text = (f"Goal: {intent}\nViewport: {viewport[0]}x{viewport[1]} CSS px\nCurrent URL: {page.url}\n"
                        f"Steps so far (JSON): {json.dumps(history)}\nVisible elements (JSON): {json.dumps(elements)}")
                if context:
                    text += f"\nContext from the caller:\n{context}"
                content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(png).decode()}},
                           {"type": "text", "text": text}]
                r = _provider.ask_json(SYSTEM, content, SCHEMA, max_tokens=4000)
                log(f"  explore step {i + 1}: {r['action']} {r['locator_kind']}={r['locator_value']!r} ({r['thought'][:80]})")
                if r["action"] == "done":
                    final = None
                    if shots:
                        final = str(shots / "explore-final.png")
                        page.screenshot(path=final)
                    roi = [float(x) for x in r["roi"]][:4] if len(r["roi"]) >= 4 else None
                    beat = {"id": "new-beat", "take": "main", "steps": ok_steps, "hold": 2.0, "duration": 5.0, "caption": r["caption"]}
                    if r["roi_selector"]:
                        beat["roi"] = {"selector": r["roi_selector"]}
                    elif roi:
                        beat["roi"] = roi
                    return {"steps": ok_steps, "roi": roi, "roi_selector": r["roi_selector"] or None, "caption": r["caption"],
                            "beat_yaml": yaml.safe_dump([beat], sort_keys=False), "transcript": history, "final_screenshot": final}
                try:
                    st = _step_from(r)
                    _run(page, base_url, st)
                    ok_steps.append(st)
                    history.append({"step": st, "ok": True})
                except Exception as e:  # noqa: BLE001
                    history.append({"proposal": {k: r[k] for k in ("action", "locator_kind", "locator_value", "role_name", "text")},
                                    "ok": False, "error": str(e).splitlines()[0][:200]})
        finally:
            browser.close()
    raise TeaserkitError(f"The goal was not reached in {max_steps} steps.", "Raise --max-steps, make the intent more specific, or start closer with --start.",
                         details={"steps_that_ran": ok_steps, "transcript": history})
