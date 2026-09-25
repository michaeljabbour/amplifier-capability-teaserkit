"""[AI] Check rendered frames for things that must never ship in a teaser.

Frames are sampled from each video (or contact-sheet / still images are used as given) and sent
to a vision model with the deny list. It returns structured findings: real-looking names or
personal data, deny-listed strings, error toasts, loading spinners, placeholder text, broken
layouts. Recording already scans the DOM for deny-listed text; this catches what only shows
up in pixels (images, canvas, cropped captions).
"""

from __future__ import annotations

import base64
from pathlib import Path

import cv2

from . import _provider, sheets
from .errors import TeaserkitError
from .style import DEFAULT_DENY

SEVERITIES = ["low", "medium", "high"]
CATEGORIES = ["deny_list", "real_person", "personal_data", "error_message", "loading_state", "placeholder_text", "broken_layout", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "frame": {"type": "string", "description": "The frame label as given, e.g. 'teaser.mp4 @ 12.0s'."},
                    "severity": {"type": "string", "enum": SEVERITIES},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "description": {"type": "string"},
                    "evidence": {"type": "string", "description": "The exact text or a short description of what is visible."},
                },
                "required": ["frame", "severity", "category", "description", "evidence"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["findings", "summary"],
    "additionalProperties": False,
}

SYSTEM = """You are the last check before a product teaser video is published. You see labelled
frames. Report anything that must not ship:
- deny_list: any of the deny-listed strings, in any case, anywhere in the frame;
- real_person / personal_data: names, faces, emails, phone numbers or addresses that look real
  rather than obviously fictional demo content;
- error_message: error toasts, stack traces, 404/500 pages, failed-to-load notices;
- loading_state: spinners, skeleton screens, half-loaded content held on screen;
- placeholder_text: lorem ipsum, 'undefined', 'NaN', '[object Object]', template braces;
- broken_layout: overlapping or clipped text, captions cut off, elements off-screen, blank panels.
Severity: high = must fix before publishing; medium = likely noticed; low = polish.
Videos crossfade between segments over about half a second, so a frame may show two shots
dissolving into each other; that is a transition, not a defect, unless it is held. Vertical and
square versions crop into the page on purpose; report clipping only when it hides the caption or
the element the frame is clearly about.
Do not report ordinary fictional demo data. If nothing is wrong, return no findings."""


def _encode(img, width: int = 1024) -> str:
    h, w = img.shape[:2]
    if w > width:
        img = cv2.resize(img, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise TeaserkitError("Could not encode a frame.", "Check the input files are readable images or videos.")
    return base64.standard_b64encode(buf.tobytes()).decode()


def collect_frames(inputs: list[str | Path], every: float = 2.0, max_frames: int = 24) -> list[tuple[str, str]]:
    """(label, base64 jpeg) for every frame to review. Deterministic; no model involved."""
    out = []
    for inp in inputs:
        p = Path(inp)
        if not p.exists():
            raise TeaserkitError(f"Input not found: {p}", "Pass video or image paths that exist.")
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            img = cv2.imread(str(p))
            if img is None:
                raise TeaserkitError(f"Cannot read image {p}.", "Pass PNG or JPEG files.")
            out.append((p.name, _encode(img, 1568)))
        else:
            for t, f in sheets.sample_frames(p, every, max_frames):
                out.append((f"{p.name} @ {t:.1f}s", _encode(f)))
    return out


def review(inputs: list[str | Path], *, deny_list: list[str] | None = None, every: float = 2.0, max_frames: int = 24,
           context: str | None = None, fail_on: str = "high", batch: int = 12, log=None) -> dict:
    """Review videos/images for leaks and defects. Model-backed.

    Returns {"ok", "findings", "summary", "frames_reviewed"}; `ok` is False when any finding is at
    or above `fail_on` (high | medium | low | never).
    """
    log = log or (lambda s: None)
    _provider.client()
    frames = collect_frames(inputs, every, max_frames)
    deny = list(dict.fromkeys((deny_list or []) + DEFAULT_DENY))
    findings, summaries = [], []
    for i in range(0, len(frames), batch):
        chunk = frames[i:i + batch]
        content: list = []
        for label, data in chunk:
            content.append({"type": "text", "text": f"Frame: {label}"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
        text = f"Deny list: {deny}"
        if context:
            text += f"\nContext from the caller:\n{context}"
        content.append({"type": "text", "text": text})
        log(f"  reviewing frames {i + 1}-{i + len(chunk)} of {len(frames)}")
        r = _provider.ask_json(SYSTEM, content, SCHEMA, max_tokens=8000)
        findings += r["findings"]
        summaries.append(r["summary"])
    threshold = None if fail_on == "never" else SEVERITIES.index(fail_on)
    bad = [f for f in findings if threshold is not None and SEVERITIES.index(f["severity"]) >= threshold]
    return {"ok": not bad, "findings": findings, "summary": " ".join(summaries), "frames_reviewed": len(frames), "fail_on": fail_on}
