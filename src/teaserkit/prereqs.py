"""Detect what the environment must provide. Each check fails with a named remedy."""

from __future__ import annotations

import os
import shutil

from .errors import MissingPrerequisite

FFMPEG_DOC = "docs/installing-ffmpeg.md"
CHROMIUM_DOC = "docs/installing-playwright.md"


def ffmpeg() -> str:
    exe = os.environ.get("TEASERKIT_FFMPEG") or shutil.which("ffmpeg")
    if not exe:
        raise MissingPrerequisite(
            "ffmpeg was not found on PATH.",
            f"Install ffmpeg (macOS: `brew install ffmpeg`; Debian/Ubuntu: `sudo apt install ffmpeg`) or set TEASERKIT_FFMPEG. See {FFMPEG_DOC}.",
        )
    return exe


def ffprobe() -> str:
    exe = os.environ.get("TEASERKIT_FFPROBE") or shutil.which("ffprobe")
    if not exe:
        raise MissingPrerequisite("ffprobe was not found on PATH (it ships with ffmpeg).", f"Install ffmpeg. See {FFMPEG_DOC}.")
    return exe


def chromium_missing(exc: BaseException) -> MissingPrerequisite | None:
    """Translate Playwright's 'browser not installed' failure into a named prerequisite."""
    msg = str(exc)
    if "Executable doesn't exist" in msg or "playwright install" in msg:
        return MissingPrerequisite(
            "Playwright's Chromium browser is not installed.",
            f"Run `playwright install chromium` in the environment teaserkit runs in. See {CHROMIUM_DOC}.",
        )
    return None


def doctor() -> dict:
    """Report every prerequisite without raising. Used by `teaserkit doctor`."""
    out: dict = {}
    for name, fn in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)):
        try:
            out[name] = {"ok": True, "path": fn()}
        except MissingPrerequisite as e:
            out[name] = {"ok": False, "remedy": e.remedy}
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            path = pw.chromium.executable_path
        out["chromium"] = {"ok": os.path.exists(path), "path": path}
        if not out["chromium"]["ok"]:
            out["chromium"]["remedy"] = f"Run `playwright install chromium`. See {CHROMIUM_DOC}."
    except Exception as e:  # noqa: BLE001
        out["chromium"] = {"ok": False, "remedy": f"Playwright is unavailable ({e}). See {CHROMIUM_DOC}."}
    try:
        import anthropic  # noqa: F401

        sdk = True
    except ImportError:
        sdk = False
    from . import _provider

    out["ai"] = {
        "ok": sdk and _provider.configured(),
        "sdk_installed": sdk,
        "credentials": _provider.configured(),
        "model": _provider.model(),
        "note": "Only plan, explore and review need this.",
    }
    return out
