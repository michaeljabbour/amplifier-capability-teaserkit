"""Finishing: mux the soundtrack (AAC 192k, EBU R128 loudness normalization), web fast-start,
a no-audio copy, and a poster frame."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import prereqs
from .errors import RenderError


def _run(cmd: list[str], what: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RenderError(f"ffmpeg failed while {what}: {r.stderr.strip()[-400:]}", "Check the input files exist and ffmpeg works.")


def probe(path: str | Path) -> dict:
    """ffprobe summary: duration, codecs, size, fps."""
    r = subprocess.run([prereqs.ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True)
    if r.returncode:
        raise RenderError(f"ffprobe could not read {path}: {r.stderr.strip()}", "Check the file is a complete MP4.")
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    return {
        "seconds": round(float(d["format"]["duration"]), 2),
        "video_codec": v.get("codec_name"),
        "width": v.get("width"),
        "height": v.get("height"),
        "fps": round(float(num) / float(den or 1), 2) if num else None,
        "audio_codec": a.get("codec_name") if a else None,
    }


def mux(silent: str | Path, wav: str | Path | None, out: str | Path, *, lufs: float = -18.0, tp: float = -2.0, lra: float = 7.0) -> Path:
    """Add the soundtrack (or copy video-only when `wav` is None) with fast-start."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ff = prereqs.ffmpeg()
    if wav is None:
        _run([ff, "-v", "error", "-y", "-i", str(silent), "-c", "copy", "-an", "-movflags", "+faststart", str(out)], "copying the silent video")
    else:
        _run([ff, "-v", "error", "-y", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
              "-c:a", "aac", "-b:a", "192k", "-af", f"loudnorm=I={lufs}:TP={tp}:LRA={lra}", "-ar", "48000", "-shortest",
              "-movflags", "+faststart", str(out)], "adding the soundtrack")
    return out


def poster(video: str | Path, at: float, out: str | Path) -> Path:
    out = Path(out)
    _run([prereqs.ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0.0, at):.2f}", "-i", str(video), "-frames:v", "1", str(out)], "grabbing the poster frame")
    return out


def finalize(silent: str | Path, wav: str | Path | None, out_dir: str | Path, name: str, *, poster_at: float | None,
             no_audio: bool, lufs: float = -18.0, tp: float = -2.0, lra: float = 7.0) -> dict:
    """Write <name>.mp4 (+ <name>-no-audio.mp4, <name>-poster.png) into `out_dir`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    res: dict = {"video": str(mux(silent, wav, out_dir / f"{name}.mp4", lufs=lufs, tp=tp, lra=lra))}
    if no_audio and wav is not None:
        res["no_audio"] = str(mux(silent, None, out_dir / f"{name}-no-audio.mp4"))
    if poster_at is not None:
        res["poster"] = str(poster(silent, poster_at, out_dir / f"{name}-poster.png"))
    return res


__all__ = ["finalize", "mux", "poster", "probe"]
