"""Captions, frame chrome, and title/end cards, designed as small HTML pages and rendered to
transparent PNGs by headless Chromium, one set per aspect.

The brand (fonts, colors, logo) comes from the storyboard. Defaults use the system UI font
stack and a neutral palette, so no proprietary font or artwork ships with teaserkit.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import mimetypes
from pathlib import Path
from typing import Callable

from . import prereqs
from .errors import RenderError
from .storyboard import Brand
from .style import ASPECTS

Log = Callable[[str], None]


def gfx_id(kind: str, aspect: str, brand: Brand, **params) -> str:
    key = json.dumps({"k": kind, "p": params, "b": _brand_key(brand)}, sort_keys=True, default=str)
    return f"{kind}-{aspect}-{hashlib.sha1(key.encode()).hexdigest()[:10]}"


def _brand_key(b: Brand) -> dict:
    return {"h": b.heading_font, "b": b.body_font, "c": b.colors, "l": str(b.logo or ""), "ld": str(b.logo_on_dark or ""), "w": b.wordmark,
            "f": [str(f["path"]) for f in b.font_files]}


def caption_item(aspect: str, brand: Brand, text: str, sub: str | None) -> dict:
    return {"id": gfx_id("caption", aspect, brand, text=text, sub=sub), "kind": "caption", "aspect": aspect, "text": text, "sub": sub}


def chrome_item(aspect: str, brand: Brand, name: str) -> dict:
    return {"id": gfx_id("chrome", aspect, brand, name=name), "kind": "chrome", "aspect": aspect, "name": name}


def card_item(kind: str, aspect: str, brand: Brand, params: dict, name: str) -> dict:
    return {"id": gfx_id(kind, aspect, brand, name=name, **params), "kind": kind, "aspect": aspect, "name": name, **params}


# ─────────────────────────────── HTML ───────────────────────────────

e = html.escape


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or ("image/svg+xml" if path.suffix == ".svg" else "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _css(b: Brand) -> str:
    faces = "".join(
        f"@font-face{{font-family:'{f['family']}';src:url({_data_url(Path(f['path']))});font-weight:{f.get('weight', '100 900')}}}"
        for f in b.font_files
    )
    return faces + f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100%;background:transparent;-webkit-font-smoothing:antialiased}}
.h{{font-family:{b.heading_font};font-weight:800;letter-spacing:-0.02em}}
.b{{font-family:{b.body_font};font-weight:500}}
"""


def _lines(text: str) -> str:
    return "<br>".join(e(x) for x in text.split("\n"))


def _stripe(b: Brand, height: int) -> str:
    cols = b.stripe()
    n = len(cols)
    stops = ",".join(f"{c} {i * 100 / n:.1f}% {(i + 1) * 100 / n:.1f}%" for i, c in enumerate(cols))
    return f"height:{height}px;background:linear-gradient(90deg,{stops})"


def _logo(b: Brand, name: str, width: int, color: str, *, on_dark: bool = False) -> str:
    logo = b.logo_on_dark if on_dark else b.logo
    if logo:
        return f'<img src="{_data_url(logo)}" style="width:{width}px;max-height:{int(width * 0.4)}px;object-fit:contain">'
    word = b.wordmark or name
    return f'<div class="h" style="color:{color};font-size:{int(width * 0.14)}px">{e(word)}</div>'


def caption_html(aspect: str, b: Brand, text: str, sub: str | None) -> str:
    ink, hi, fg, fg2 = b.color("ink"), b.color("highlight"), b.color("caption_text"), b.color("caption_sub")
    if aspect == "16x9":
        return f"""<div style="position:absolute;left:72px;bottom:64px;max-width:1300px;background:{ink};border-radius:26px;padding:24px 38px 26px 44px;box-shadow:0 18px 50px rgba(0,0,0,.35);overflow:hidden">
          <div style="position:absolute;left:0;top:0;bottom:0;width:12px;background:{hi}"></div>
          <div class="h" style="color:{fg};font-size:50px;line-height:1.1">{_lines(text)}</div>
          {f'<div class="b" style="color:{fg2};font-size:30px;margin-top:8px">{e(sub)}</div>' if sub else ''}</div>"""
    band = 250 if aspect == "9x16" else 180
    fs = 60 if aspect == "9x16" else 46
    return f"""<div style="position:absolute;left:0;right:0;bottom:0;height:{band}px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 60px">
        <div class="h" style="color:{fg};font-size:{fs}px;line-height:1.08">{_lines(text)}</div>
        {f'<div class="b" style="color:{fg2};font-size:{round(fs * 0.55)}px;margin-top:10px">{e(sub)}</div>' if sub else ''}</div>"""


def chrome_html(aspect: str, b: Brand, name: str) -> str:
    ink = b.color("ink")
    if aspect == "9x16":
        return f"""<div style="position:absolute;inset:0;background:{ink}"></div>
          <div style="position:absolute;left:0;right:0;top:0;height:170px;display:flex;align-items:center;justify-content:center">{_logo(b, name, 380, b.color('caption_text'), on_dark=True)}</div>
          <div style="position:absolute;left:0;right:0;bottom:250px;{_stripe(b, 6)}"></div>"""
    if aspect == "1x1":
        return f"""<div style="position:absolute;inset:0;background:{ink}"></div>
          <div style="position:absolute;left:0;right:0;bottom:180px;{_stripe(b, 5)}"></div>"""
    return ""


def title_html(aspect: str, b: Brand, o: dict) -> str:
    big = {"16x9": 150, "9x16": 132, "1x1": 118}[aspect]
    left = aspect == "16x9"
    return f"""<div style="position:absolute;inset:0;background:{b.color('paper')}"></div>
      <div style="position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:{'flex-start' if left else 'center'};padding:0 {150 if left else 80}px;text-align:{'left' if left else 'center'}">
        {f'<div style="margin-bottom:44px">{_logo(b, o.get("name", ""), 520, b.color("ink"))}</div>' if (b.logo and o.get("logo")) else ''}
        <div class="h" style="font-size:{big}px;line-height:.98;color:{b.color('ink')}">{_lines(o.get('title', ''))}</div>
        {f'<div class="b" style="font-size:{round(big * 0.3)}px;margin-top:36px;color:{b.color("muted")};max-width:1200px;line-height:1.3">{e(o["sub"])}</div>' if o.get('sub') else ''}
        <div style="margin-top:48px;display:flex;gap:14px">{''.join(f'<div style="width:64px;height:14px;border-radius:7px;background:{c}"></div>' for c in b.stripe())}</div>
      </div>"""


def end_html(aspect: str, b: Brand, o: dict) -> str:
    u = 54 if aspect == "16x9" else 50
    url = o.get("url")
    return f"""<div style="position:absolute;inset:0;background:{b.color('paper')}"></div>
      <div style="position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 60px">
        {_logo(b, o.get('name', ''), 900 if aspect == '16x9' else 760, b.color('ink'))}
        <div class="h" style="font-size:{round(u * 1.05)}px;margin-top:{56 if aspect == '16x9' else 70}px;color:{b.color('ink')}">{e(o.get('tagline', ''))}</div>
        {f'<div class="b" style="font-size:{round(u * 0.58)}px;margin-top:22px;color:{b.color("muted")}">{e(o["sub"])}</div>' if o.get('sub') else ''}
        {f'<div class="h" style="margin-top:{54 if aspect == "16x9" else 70}px;background:{b.color("accent")};color:#fff;font-size:{u}px;padding:22px 46px;border-radius:999px">{e(url)}</div>' if url else ''}
      </div>"""


def item_html(item: dict, b: Brand) -> str:
    k, a = item["kind"], item["aspect"]
    if k == "caption":
        body = caption_html(a, b, item["text"], item.get("sub"))
    elif k == "chrome":
        body = chrome_html(a, b, item["name"])
    elif k == "title":
        body = title_html(a, b, item)
    elif k == "end":
        body = end_html(a, b, item)
    else:
        raise RenderError(f"Unknown graphic kind {k!r}.", "Use caption, chrome, title or end.")
    w, h = ASPECTS[a]["size"]
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{_css(b)}</style></head>'
            f'<body><div style="position:relative;width:{w}px;height:{h}px">{body}</div></body></html>')


def render(items: list[dict], brand: Brand, out_dir: str | Path, *, force: bool = False, log: Log | None = None) -> list[Path]:
    """Render graphics to `<out_dir>/<id>.png` (transparent). Existing files are reused unless `force`."""
    log = log or (lambda s: None)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    uniq, seen = [], set()
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            uniq.append(it)
    todo = [it for it in uniq if force or not (out / f"{it['id']}.png").exists()]
    if todo:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as ex:  # noqa: BLE001
                raise (prereqs.chromium_missing(ex) or RenderError(f"Could not launch Chromium: {ex}", "See docs/installing-playwright.md.")) from ex
            try:
                for it in todo:
                    w, h = ASPECTS[it["aspect"]]["size"]
                    page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                    page.set_content(item_html(it, brand))
                    page.evaluate("document.fonts.ready.then(() => true)")
                    page.wait_for_timeout(100)
                    page.screenshot(path=str(out / f"{it['id']}.png"), omit_background=True)
                    page.close()
            finally:
                browser.close()
        log(f"rendered {len(todo)} graphic(s) into {out}")
    return [out / f"{it['id']}.png" for it in uniq]
