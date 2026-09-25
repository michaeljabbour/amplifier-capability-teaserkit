"""Record raw takes: headless Chromium at high pixel density, filmed through the DevTools screencast.

Each take is one continuous browser session. The beats that share the take run in order; the
recorder marks where each beat starts, where its result hold begins, and where it ends, so the
compositor can cut the take into beats without hand-entered timecodes.

Frames arrive only when the page repaints, each with a timestamp. They are written as JPEGs and
turned into a constant 30 fps MP4 by ffmpeg's concat demuxer, which holds every frame until the
next one, so still moments cost nothing and timing stays true.

A fake cursor with a click ripple is injected into every page (headless Chromium draws none).
After every step the visible text is scanned for deny-listed strings; a hit fails the take.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

from . import prereqs
from .errors import LeakDetected, RecordingError
from .serve import serve_static
from .storyboard import Beat, Storyboard
from .rules import deny_pattern, deny_terms

Log = Callable[[str], None]

CURSOR_JS = r"""
(() => {
  const ACCENT = '__ACCENT__';
  const install = () => {
    if (document.getElementById('__tk_cursor')) return;
    const st = document.createElement('style');
    st.textContent = '::-webkit-scrollbar{width:0!important;height:0!important;display:none!important} *{scrollbar-width:none!important}' +
      '#__tk_cursor{position:fixed;left:0;top:0;width:30px;height:30px;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}' +
      '.__tk_ripple{position:fixed;z-index:2147483646;pointer-events:none;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;border:3px solid ' + ACCENT + ';background:' + ACCENT + '2e;animation:__tk_r .55s ease-out forwards}' +
      '@keyframes __tk_r{from{transform:scale(.4);opacity:1}to{transform:scale(3.4);opacity:0}}';
    document.documentElement.appendChild(st);
    const c = document.createElement('div');
    c.id = '__tk_cursor';
    c.innerHTML = '<svg width="30" height="30" viewBox="0 0 30 30"><path d="M4 2 L4 24 L10 18.5 L14 27 L18 25.2 L14 17 L22 17 Z" fill="#111" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(c);
    const p = window.__tkPos || [-100, -100];
    c.style.transform = 'translate(' + (p[0] - 4) + 'px,' + (p[1] - 2) + 'px)';
  };
  window.__tkSet = (x, y) => { window.__tkPos = [x, y]; install(); const c = document.getElementById('__tk_cursor'); if (c) c.style.transform = 'translate(' + (x - 4) + 'px,' + (y - 2) + 'px)'; };
  window.__tkRipple = (x, y) => { const r = document.createElement('div'); r.className = '__tk_ripple'; r.style.left = x + 'px'; r.style.top = y + 'px'; document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();
"""

VISIBLE_TEXT_JS = """() => {
  const vals = [...document.querySelectorAll('input,textarea,select')].map(e => e.value || '').join('\\n');
  return (document.title || '') + '\\n' + (document.body ? document.body.innerText : '') + '\\n' + vals;
}"""

ENV_REF = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")


def ease(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def resolve_env(s: str) -> str:
    def sub(m):
        v = os.environ.get(m.group(1))
        if v is None:
            raise RecordingError(f"Environment variable {m.group(1)} is referenced by the storyboard but not set.",
                                 f"Export {m.group(1)} before recording.")
        return v

    return ENV_REF.sub(sub, s)


@dataclass
class TakeResult:
    take: str
    video: Path
    marks: Path
    frames: int
    seconds: float


def locator_for(page, spec: dict):
    """Turn a storyboard locator into a Playwright locator (works with the sync and async APIs)."""
    exact = bool(spec.get("exact", False))
    if "selector" in spec:
        loc = page.locator(spec["selector"])
    elif "role" in spec:
        loc = page.get_by_role(spec["role"], name=resolve_env(spec["name"]), exact=exact) if spec.get("name") else page.get_by_role(spec["role"])
    elif "label" in spec:
        loc = page.get_by_label(resolve_env(spec["label"]), exact=exact)
    elif "placeholder" in spec:
        loc = page.get_by_placeholder(resolve_env(spec["placeholder"]), exact=exact)
    else:
        loc = page.get_by_text(resolve_env(spec["text"]), exact=exact)
    return loc.nth(int(spec["nth"])) if "nth" in spec else loc.first


class _Actor:
    """Drives one page like a person: eased cursor moves, clicks with a ripple, human-speed typing."""

    def __init__(self, page, base_url: str, viewport: tuple[int, int], deny: re.Pattern | None, log: Log):
        self.page = page
        self.base = base_url.rstrip("/") + "/"
        self.pos = (viewport[0] * 0.6, viewport[1] * 0.55)
        self.deny = deny
        self.log = log

    async def set_cursor(self, x: float, y: float):
        self.pos = (x, y)
        try:
            await self.page.evaluate("([a, b]) => window.__tkSet && window.__tkSet(a, b)", [x, y])
        except Exception:  # noqa: BLE001 - page may be navigating
            pass

    async def move_to(self, x: float, y: float, ms: float = 700):
        x0, y0 = self.pos
        n = max(8, round(ms / 16))
        for i in range(1, n + 1):
            t = ease(i / n)
            cx, cy = x0 + (x - x0) * t, y0 + (y - y0) * t
            await self.page.mouse.move(cx, cy)
            await self.set_cursor(cx, cy)
            await self.page.wait_for_timeout(8)

    def locator(self, spec: dict):
        return locator_for(self.page, spec)

    async def center(self, loc) -> tuple[float, float]:
        await loc.wait_for(state="visible", timeout=15_000)
        try:
            await loc.scroll_into_view_if_needed(timeout=5_000)
        except Exception:  # noqa: BLE001
            pass
        b = await loc.bounding_box()
        if not b:
            raise RecordingError("Element has no box on screen.", "Check the locator matches a visible element.")
        return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2

    async def settle(self, ms: float = 600):
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=15_000)
            await self.page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:  # noqa: BLE001 - long-polling apps never go idle; that is fine
            pass
        await self.page.wait_for_timeout(ms)
        await self.set_cursor(*self.pos)

    async def scan(self, where: str):
        if not self.deny:
            return
        try:
            text = await self.page.evaluate(VISIBLE_TEXT_JS)
        except Exception:  # noqa: BLE001
            return
        m = self.deny.search(text or "")
        if m:
            raise LeakDetected(f"Deny-listed text '{m.group(0)}' was on screen at {where}.",
                               "Change the demo data or the steps so it never appears, then record again.",
                               details={"where": where, "term": m.group(0)})

    async def step(self, st: dict):
        p = self.page
        if "goto" in st:
            url = urljoin(self.base, resolve_env(st["goto"]).lstrip("/")) if not re.match(r"^https?://", st["goto"]) else resolve_env(st["goto"])
            await p.goto(url, wait_until="domcontentloaded", timeout=45_000)
            await self.settle(float(st.get("settle_ms", 700)))
        elif "click" in st:
            loc = self.locator(st["click"])
            x, y = await self.center(loc)
            await self.move_to(x, y, float(st.get("ms", 700)))
            await p.wait_for_timeout(float(st.get("before_ms", 250)))
            await p.evaluate("([a, b]) => window.__tkRipple && window.__tkRipple(a, b)", [x, y])
            await p.mouse.down()
            await p.wait_for_timeout(60)
            await p.mouse.up()
            await p.wait_for_timeout(float(st.get("after_ms", 400)))
            await self.settle(200)
        elif "hover" in st:
            x, y = await self.center(self.locator(st["hover"]))
            await self.move_to(x, y, float(st.get("ms", 700)))
        elif "type" in st:
            t = st["type"]
            if "into" in t:
                await self.step({"click": t["into"]})
            text = resolve_env(t["text"])
            delay = float(t.get("delay", 55))
            rng = random.Random(len(text))  # deterministic jitter
            for ch in text:
                await p.keyboard.type(ch)
                await p.wait_for_timeout(delay + rng.random() * delay * 0.6)
        elif "press" in st:
            await p.keyboard.press(st["press"])
            await self.settle(300)
        elif "scroll" in st:
            dy, ms = st["scroll"]["dy"], st["scroll"]["ms"]
            await p.mouse.move(*self.pos)
            n = max(10, round(ms / 16))
            done = 0
            for i in range(1, n + 1):
                target = round(dy * ease(i / n))
                await p.mouse.wheel(0, target - done)
                done = target
                await p.wait_for_timeout(14)
        elif "wait_for" in st:
            await self.locator(st["wait_for"]).wait_for(state=st.get("state", "visible"), timeout=float(st.get("timeout", 20)) * 1000)
        elif "hold" in st:
            await p.wait_for_timeout(float(st["hold"]) * 1000)
        elif "move" in st:
            m = st["move"]
            await self.move_to(m["x"], m["y"], m["ms"])

    async def box(self, selector: str) -> list[float] | None:
        try:
            b = await self.page.locator(selector).first.bounding_box(timeout=3_000)
        except Exception:  # noqa: BLE001
            return None
        return [b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]] if b else None


class _Screencast:
    def __init__(self, page, frames_dir: Path, viewport, dpr):
        self.page, self.dir, self.viewport, self.dpr = page, frames_dir, viewport, dpr
        self.frames: list[tuple[Path, float]] = []
        self.cdp = None

    async def start(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        self.cdp = await self.page.context.new_cdp_session(self.page)

        def on_frame(ev):
            f = self.dir / f"{len(self.frames):06d}.jpg"
            f.write_bytes(base64.b64decode(ev["data"]))
            self.frames.append((f, float(ev["metadata"]["timestamp"])))
            asyncio.ensure_future(self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]}))

        self.cdp.on("Page.screencastFrame", on_frame)
        await self.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": 92, "everyNthFrame": 1,
            "maxWidth": self.viewport[0] * self.dpr, "maxHeight": self.viewport[1] * self.dpr,
        })

    async def stop(self) -> float:
        await self.page.wait_for_timeout(300)
        await self.cdp.send("Page.stopScreencast")
        end = time.time()
        await self.page.wait_for_timeout(200)
        return end


def _encode(frames: list[tuple[Path, float]], end_wall: float, out: Path, size: tuple[int, int]) -> None:
    if not frames:
        raise RecordingError("The screencast produced no frames.", "Check the page renders; try recording again.")
    lines = []
    for i, (f, t) in enumerate(frames):
        nxt = frames[i + 1][1] if i + 1 < len(frames) else max(end_wall, t + 0.1)
        lines += [f"file '{f}'", f"duration {max(0.001, nxt - t):.4f}"]
    lines.append(f"file '{frames[-1][0]}'")
    lst = frames[0][0].parent / "list.txt"
    lst.write_text("\n".join(lines))
    cmd = [prereqs.ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-vf", f"fps=30,scale={size[0]}:{size[1]}:flags=lanczos,format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", "14", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RecordingError(f"ffmpeg could not encode the take: {r.stderr.strip()[-400:]}", "Check ffmpeg works: `ffmpeg -version`.")


async def _record_take(ctx, sb: Storyboard, base_url: str, take: str, beats: list[Beat], raw_dir: Path, log: Log) -> TakeResult:
    proj = sb.project
    page = await ctx.new_page()
    actor = _Actor(page, base_url, proj.viewport, deny_pattern(deny_terms(sb)), log)
    steps0 = list(beats[0].steps)
    pre = []
    while steps0 and "goto" in steps0[0]:
        pre.append(steps0.pop(0))
    try:
        for st in pre or [{"goto": "/"}]:
            await actor.step(st)
        await actor.scan(f"take {take} (opening page)")
        cast = _Screencast(page, raw_dir / f"{take}.frames", proj.viewport, proj.dpr)
        await cast.start()
        await page.wait_for_timeout(250)
        marks: dict[str, dict] = {}
        for bi, b in enumerate(beats):
            start = time.time()
            steps = steps0 if bi == 0 else b.steps
            log(f"  beat {b.id}: {len(steps)} step(s)")
            for si, st in enumerate(steps):
                try:
                    await actor.step(st)
                except (LeakDetected, RecordingError):
                    raise
                except Exception as e:  # noqa: BLE001
                    raise RecordingError(f"Beat '{b.id}' step {si + 1} ({next(iter(st))}) failed: {str(e).splitlines()[0]}",
                                         "Fix the step's locator or add a wait_for step; `teaserkit explore` can propose working steps.",
                                         details={"beat": b.id, "step": si}) from e
                await actor.scan(f"beat {b.id} step {si + 1}")
            hold_start = time.time()
            boxes = {}
            for sel in b.selectors():
                bx = await actor.box(sel)
                if bx is None:
                    log(f"  warning: roi selector {sel!r} not found in beat {b.id}; using the full frame")
                boxes[sel] = bx
            await page.wait_for_timeout(b.hold * 1000)
            await actor.scan(f"beat {b.id} (result hold)")
            marks[b.id] = {"start": start, "hold_start": hold_start, "end": time.time(), "boxes": boxes}
        end_wall = await cast.stop()
    finally:
        await page.close()
    if not cast.frames:
        raise RecordingError(f"Take '{take}' captured no frames.", "Check the page renders in headless Chromium.")
    t0 = cast.frames[0][1]
    vw, vh = proj.viewport
    out = raw_dir / f"{take}.mp4"
    _encode(cast.frames, end_wall, out, (vw * proj.dpr, vh * proj.dpr))
    duration = end_wall - t0
    beats_json = {}
    for bid, m in marks.items():
        beats_json[bid] = {
            "start": round(max(0.0, m["start"] - t0), 3),
            "hold_start": round(max(0.0, m["hold_start"] - t0), 3),
            "end": round(min(duration, max(0.0, m["end"] - t0)), 3),
            "boxes": m["boxes"],
        }
    meta = {"take": take, "video": out.name, "viewport": [vw, vh], "dpr": proj.dpr, "frames": len(cast.frames),
            "seconds": round(duration, 3), "beats": beats_json}
    marks_path = raw_dir / f"{take}.json"
    marks_path.write_text(json.dumps(meta, indent=1))
    shutil.rmtree(raw_dir / f"{take}.frames", ignore_errors=True)
    log(f"  recorded {take}: {len(cast.frames)} frames, {duration:.1f} s -> {out}")
    return TakeResult(take, out, marks_path, len(cast.frames), round(duration, 2))


async def _record_async(sb: Storyboard, raw_dir: Path, takes: list[str] | None, log: Log) -> list[TakeResult]:
    from playwright.async_api import async_playwright

    proj = sb.project
    groups = sb.takes()
    wanted = takes or list(groups)
    for t in wanted:
        if t not in groups:
            raise RecordingError(f"No take named '{t}'.", f"Known takes: {', '.join(groups)}")
    results = []
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(headless=True, args=["--hide-scrollbars", "--force-color-profile=srgb"])
        except Exception as e:  # noqa: BLE001
            raise (prereqs.chromium_missing(e) or RecordingError(f"Could not launch Chromium: {e}", "See docs/installing-playwright.md.")) from e
        try:
            base = proj.base_url
            with (serve_static(proj.serve_dir, proj.serve_port) if proj.serve_dir else _nullctx(base)) as served:
                base = proj.base_url or served
                kw = dict(viewport={"width": proj.viewport[0], "height": proj.viewport[1]}, device_scale_factor=proj.dpr,
                          locale=proj.locale, timezone_id=proj.timezone)
                if proj.auth.kind == "storage_state":
                    if not proj.auth.storage_state or not proj.auth.storage_state.exists():
                        raise RecordingError(f"Storage state file not found: {proj.auth.storage_state}",
                                             "Create it by signing in once and saving the context's storage state.")
                    kw["storage_state"] = str(proj.auth.storage_state)
                for take in wanted:
                    log(f"recording take {take} ({len(groups[take])} beat(s)) from {base}")
                    ctx = await browser.new_context(**kw)
                    ctx.set_default_timeout(30_000)
                    await ctx.add_init_script(CURSOR_JS.replace("__ACCENT__", proj.brand.color("accent")))
                    if proj.auth.kind == "script":
                        ap = await ctx.new_page()
                        a = _Actor(ap, base, proj.viewport, None, log)
                        for st in proj.auth.steps:
                            await a.step(st)
                        await ap.close()
                    try:
                        results.append(await _record_take(ctx, sb, base, take, groups[take], raw_dir, log))
                    finally:
                        await ctx.close()
        finally:
            await browser.close()
    return results


class _nullctx:
    def __init__(self, v):
        self.v = v

    def __enter__(self):
        return self.v

    def __exit__(self, *a):
        return False


def record(sb: Storyboard, raw_dir: str | Path, *, takes: list[str] | None = None, log: Log | None = None) -> list[TakeResult]:
    """Record every take in the storyboard (or only `takes`) into `raw_dir` as <take>.mp4 + <take>.json.

    Raises LeakDetected if a deny-listed string appears on screen, RecordingError if a step fails,
    MissingPrerequisite if Chromium or ffmpeg is absent.
    """
    prereqs.ffmpeg()
    raw = Path(raw_dir)
    raw.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_record_async(sb, raw, takes, log or (lambda s: None)))


def load_take(raw_dir: str | Path, take: str) -> dict:
    p = Path(raw_dir) / f"{take}.json"
    if not p.exists():
        raise RecordingError(f"Take '{take}' has not been recorded (no {p}).", "Run `teaserkit record <storyboard>` first.")
    meta = json.loads(p.read_text())
    meta["path"] = str(Path(raw_dir) / meta["video"])
    return meta


__all__ = ["record", "load_take", "TakeResult", "ease"]
