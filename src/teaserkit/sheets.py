"""Contact sheets for checking a render by eye, and a pixel grid for picking regions of interest."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from .errors import RenderError


def sample_frames(video: str | Path, every: float = 2.0, max_frames: int | None = None) -> list[tuple[float, np.ndarray]]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RenderError(f"Cannot open {video}.", "Check the path points at a video file.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = n / fps
    times = [t for t in np.arange(0, dur, every)] or [0.0]
    if max_frames and len(times) > max_frames:
        times = list(np.linspace(0, dur - 1 / fps, max_frames))
    out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, f = cap.read()
        if ok:
            out.append((float(t), f))
    cap.release()
    return out


def _label(img: np.ndarray, text: str) -> None:
    cv2.rectangle(img, (0, 0), (12 + 13 * len(text), 30), (0, 0, 0), -1)
    cv2.putText(img, text, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)


def contact_sheet(video: str | Path, out: str | Path, *, every: float = 2.0, cols: int = 6, tile_width: int = 480) -> dict:
    """Tile one frame every `every` seconds, each stamped with its time, into a PNG."""
    frames = sample_frames(video, every)
    if not frames:
        raise RenderError(f"No frames could be read from {video}.", "Check the video is complete.")
    h0, w0 = frames[0][1].shape[:2]
    th = int(round(tile_width * h0 / w0))
    tiles = []
    for t, f in frames:
        tile = cv2.resize(f, (tile_width, th), interpolation=cv2.INTER_AREA)
        _label(tile, f"{int(t // 60)}:{t % 60:04.1f}")
        tiles.append(tile)
    rows = math.ceil(len(tiles) / cols)
    pad = 4
    sheet = np.full((rows * (th + pad) + pad, cols * (tile_width + pad) + pad, 3), 255, np.uint8)
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        y, x = pad + r * (th + pad), pad + c * (tile_width + pad)
        sheet[y:y + th, x:x + tile_width] = tile
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet)
    return {"path": str(out), "frames": len(tiles), "every": every}


def roi_grid(take: str | Path, times: list[float], out: str | Path, *, viewport_width: int = 1440, step: int = 120) -> dict:
    """Overlay a CSS-pixel grid on frames of a raw take so ROIs can be read off directly."""
    cap = cv2.VideoCapture(str(take))
    if not cap.isOpened():
        raise RenderError(f"Cannot open {take}.", "Check the path points at a recorded take.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tiles = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, f = cap.read()
        if not ok:
            continue
        h, w = f.shape[:2]
        s = w / viewport_width
        for css in range(0, viewport_width + 1, step):
            x = int(css * s)
            cv2.line(f, (x, 0), (x, h), (0, 0, 255), 2)
            cv2.putText(f, str(css), (x + 4, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3)
        for css in range(0, int(h / s) + 1, step):
            y = int(css * s)
            cv2.line(f, (0, y), (w, y), (255, 0, 0), 2)
            cv2.putText(f, str(css), (4, y + 34), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 0, 0), 3)
        cv2.putText(f, f"t={t:g}s", (w // 2 - 80, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 140, 0), 5)
        tiles.append(cv2.resize(f, (960, int(960 * h / w)), interpolation=cv2.INTER_AREA))
    cap.release()
    if not tiles:
        raise RenderError("None of the requested times could be read.", "Pass times inside the take's duration.")
    blank = np.zeros_like(tiles[0])
    rows = [np.hstack(tiles[i:i + 2] + [blank] * (2 - len(tiles[i:i + 2]))) for i in range(0, len(tiles), 2)]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), np.vstack(rows))
    return {"path": str(out), "frames": len(tiles)}
