"""The compositor: raw takes + graphics -> one silent H.264 MP4 per video per aspect.

For every beat it cuts the take at the recorder's marks and retimes it to the beat's planned
duration: the action plays (sped up if it must be, never beyond `max_speedup`) and the result
hold plays at real speed, freezing on the last frame if the beat is longer than the footage.

Framing is driven by regions of interest (ROIs) in CSS pixels. Each aspect fits its own crop
around the ROI, with an eased move between keyframes, so vertical and square versions follow
the action instead of shrinking the whole screen. Beats crossfade; captions fade in and out.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import cv2
import numpy as np

from . import graphics, prereqs
from .errors import RenderError
from .recorder import ease, load_take
from .storyboard import Beat, Keyframe, Storyboard, Video
from .style import ASPECTS, FPS
from .rules import CAPTION_FADE_IN_AT, CAPTION_FADE_OUT_BEFORE

Log = Callable[[str], None]


# ─────────────────────────────── helpers ───────────────────────────────


class Source:
    """Random access to frames of a take by time, reading forward when it can."""

    def __init__(self, path: str | Path):
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise RenderError(f"Cannot open take {path}.", "Record it again with `teaserkit record`.")
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.pos = -1
        self.frame: np.ndarray | None = None

    def at(self, t: float) -> np.ndarray:
        idx = min(self.n - 1, max(0, int(round(t * FPS))))
        if idx != self.pos:
            if idx < self.pos or idx > self.pos + 90:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                self.pos = idx - 1
            while self.pos < idx:
                if not self.cap.grab():
                    break
                self.pos += 1
            ok, f = self.cap.retrieve()
            if ok:
                self.frame = f
        if self.frame is None:
            raise RenderError("Could not decode a frame from the take.", "Record the take again.")
        return self.frame


def fit(roi, ar: float, minw: float, sw: float, sh: float, pad: float = 1.06) -> tuple[float, float, float, float]:
    """Smallest crop of aspect ratio `ar` (>= minw wide) containing the padded ROI, kept inside the frame."""
    x0, y0, x1, y1 = roi
    rw, rh = (x1 - x0) * pad, (y1 - y0) * pad
    w = max(rw, rh * ar, minw)
    w = min(w, sw, sh * ar)
    h = w / ar
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if rw > w:  # wider than we can show: keep the reading start (left edge)
        cx = x0 + w / 2 - (rw - (x1 - x0)) / 2
    if rh > h:  # taller than we can show: keep the top
        cy = y0 + h / 2
    cx = min(max(cx, w / 2), sw - w / 2)
    cy = min(max(cy, h / 2), sh - h / 2)
    return (cx - w / 2, cy - h / 2, w, h)


def over(dst: np.ndarray, rgba: np.ndarray | None, alpha: float = 1.0) -> np.ndarray:
    """Alpha-composite an RGBA (or BGR) image onto `dst` in place."""
    if rgba is None or alpha <= 0:
        return dst
    if rgba.ndim == 2:
        rgba = cv2.cvtColor(rgba, cv2.COLOR_GRAY2BGR)
    if rgba.shape[2] == 3:
        dst[:] = rgba if alpha >= 1 else cv2.addWeighted(dst, 1 - alpha, rgba, alpha, 0)
        return dst
    a = rgba[:, :, 3:4].astype(np.float32) / 255.0 * alpha
    dst[:] = (dst.astype(np.float32) * (1 - a) + rgba[:, :, :3].astype(np.float32) * a).astype(np.uint8)
    return dst


def retime(start: float, hold_start: float, end: float, d: float, max_speedup: float) -> tuple[Callable[[float], float], float]:
    """Map beat output time -> take time. Returns (mapping, action speed factor)."""
    a = max(0.0, hold_start - start)
    hld = max(0.0, end - hold_start)
    if a == 0:
        act_out = 0.0
    elif a + hld <= d:
        act_out = a  # everything fits at real speed; the hold stretches (last frame freezes)
    else:
        act_out = d - min(hld, 0.45 * d)  # keep up to 45% of the beat for the result, at real speed
        if a / act_out > max_speedup:
            act_out = min(d, a / max_speedup)  # borrow from the hold rather than play too fast
    speed = a / act_out if act_out > 0 else 1.0

    def m(tau: float) -> float:
        if tau < act_out:
            return start + tau * speed
        return min(end, hold_start + (tau - act_out))

    return m, speed


# ─────────────────────────────── segments ───────────────────────────────


@dataclass
class Segment:
    id: str
    dur: float

    def frames(self, aspect: str, base: np.ndarray) -> Iterator[np.ndarray]:  # pragma: no cover - interface
        raise NotImplementedError


class BeatSegment(Segment):
    def __init__(self, beat: Beat, take: dict, sb: Storyboard, gfx_dir: Path, log: Log):
        super().__init__(beat.id, beat.planned(sb.style))
        self.beat, self.take, self.sb, self.gfx_dir, self.log = beat, take, sb, gfx_dir, log
        m = take["beats"].get(beat.id)
        if not m:
            raise RenderError(f"Beat '{beat.id}' is missing from take '{take['take']}'.", "Record the take again after adding the beat.")
        self.map, speed = retime(m["start"], m["hold_start"], m["end"], self.dur, sb.style["max_speedup"])
        if speed > sb.style["max_speedup"] + 1e-6:
            log(f"  warning: beat {beat.id} plays {speed:.1f}x real time; give it a longer duration or fewer steps")
        self.boxes = m.get("boxes", {})

    def _kf_css(self, k: Keyframe) -> list[float]:
        vw, vh = self.take["viewport"]
        if k.roi:
            return k.roi
        b = self.boxes.get(k.selector)
        if not b:
            return [0, 0, vw, vh]
        return [max(0, b[0] - k.pad), max(0, b[1] - k.pad), min(vw, b[2] + k.pad), min(vh, b[3] + k.pad)]

    def rects(self, aspect: str, src: Source) -> list[tuple[float, tuple, float]]:
        st = self.sb.style
        _, _, pw, ph = ASPECTS[aspect]["panel"]
        ar = pw / ph
        scale = src.w / self.take["viewport"][0]
        kfs = self.beat.keyframes(aspect) or [Keyframe(at=0.0, roi=[0, 0, *self.take["viewport"]], selector=None)]
        out = []
        for k in kfs:
            css = self._kf_css(k)
            roi = [c * scale for c in css]
            rect = fit(roi, ar, st["min_crop"][aspect] * src.w, src.w, src.h, st["roi_pad"])
            out.append((k.at, rect, k.move if k.move is not None else st["move_seconds"]))
        return out

    def frames(self, aspect: str, base: np.ndarray) -> Iterator[np.ndarray]:
        px, py, pw, ph = ASPECTS[aspect]["panel"]
        src = Source(self.take["path"])
        rects = self.rects(aspect, src)
        cap_png = None
        lines = self.beat.caption_lines()
        if self.beat.caption:
            it = graphics.caption_item(aspect, self.sb.project.brand, self.beat.caption, self.beat.sub)
            cap_png = cv2.imread(str(self.gfx_dir / f"{it['id']}.png"), cv2.IMREAD_UNCHANGED)
            if cap_png is None:
                raise RenderError(f"Caption graphic for beat '{self.beat.id}' is missing.", "Run `teaserkit captions <storyboard>` first.")
        n = int(round(self.dur * FPS))
        t0, t1 = CAPTION_FADE_IN_AT, self.dur - CAPTION_FADE_OUT_BEFORE
        for k in range(n):
            tau = k / FPS
            f = src.at(self.map(tau))
            cur = rects[0][1]
            for at, rc, mv in rects[1:]:
                if tau < at:
                    break
                u = ease((tau - at) / mv) if mv > 0 else 1.0
                cur = tuple(cur[i] + (rc[i] - cur[i]) * u for i in range(4))
            x, y, w, h = (int(round(v)) for v in cur)
            crop = f[max(0, y):y + h, max(0, x):x + w]
            panel = cv2.resize(crop, (pw, ph), interpolation=cv2.INTER_AREA if w > pw else cv2.INTER_CUBIC)
            out = base.copy()
            out[py:py + ph, px:px + pw] = panel
            if cap_png is not None and lines and t0 - 0.01 <= tau <= t1:
                over(out, cap_png, max(0.0, min(1.0, (tau - t0) / 0.25, (t1 - tau) / 0.25)))
            yield out


class CardSegment(Segment):
    def __init__(self, kind: str, params: dict, dur: float, sb: Storyboard, gfx_dir: Path):
        super().__init__(kind, dur)
        self.kind, self.params, self.sb, self.gfx_dir = kind, params, sb, gfx_dir

    def frames(self, aspect: str, base: np.ndarray) -> Iterator[np.ndarray]:
        it = graphics.card_item(self.kind, aspect, self.sb.project.brand, self.params, self.sb.project.name)
        im = cv2.imread(str(self.gfx_dir / f"{it['id']}.png"), cv2.IMREAD_UNCHANGED)
        if im is None:
            raise RenderError(f"The {self.kind} card graphic is missing.", "Run `teaserkit captions <storyboard>` first.")
        W, H = ASPECTS[aspect]["size"]
        card = over(np.full((H, W, 3), 255, np.uint8), im)
        n = int(round(self.dur * FPS))
        for k in range(n):
            s = 1.0 + 0.035 * ease(k / max(1, n - 1))  # slow push-in
            M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
            yield cv2.warpAffine(card, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ─────────────────────────────── public API ───────────────────────────────


def _card_params(o: dict) -> dict:
    return {k: v for k, v in o.items() if k != "seconds"}


def graphics_needed(sb: Storyboard, video: Video, aspect: str) -> list[dict]:
    """Every graphic `render_video` will read for this video and aspect."""
    b = sb.project.brand
    items = [graphics.chrome_item(aspect, b, sb.project.name)]
    if video.title:
        items.append(graphics.card_item("title", aspect, b, _card_params(video.title), sb.project.name))
    for beat in video.beats:
        if beat.caption:
            items.append(graphics.caption_item(aspect, b, beat.caption, beat.sub))
    if video.end:
        items.append(graphics.card_item("end", aspect, b, _card_params(video.end), sb.project.name))
    return items


def segments_for(sb: Storyboard, video: Video, raw_dir: Path, gfx_dir: Path, log: Log) -> list[Segment]:
    st = sb.style
    segs: list[Segment] = []
    if video.title:
        segs.append(CardSegment("title", _card_params(video.title), float(video.title.get("seconds", st["title_seconds"])), sb, gfx_dir))
    takes: dict[str, dict] = {}
    for beat in video.beats:
        if beat.take not in takes:
            takes[beat.take] = load_take(raw_dir, beat.take)
        segs.append(BeatSegment(beat, takes[beat.take], sb, gfx_dir, log))
    if video.end:
        segs.append(CardSegment("end", _card_params(video.end), float(video.end.get("seconds", st["end_seconds"])), sb, gfx_dir))
    return segs


def encode_frames(segs: list[Segment], aspect: str, base: np.ndarray, out: Path, crossfade: float, preview: bool = False) -> tuple[float, list[dict]]:
    """Crossfade segments into an ffmpeg pipe. Returns (seconds, timeline)."""
    W, H = ASPECTS[aspect]["size"]
    ow, oh = (W // 2, H // 2) if preview else (W, H)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [prereqs.ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ow}x{oh}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast" if preview else "medium", "-crf", "23" if preview else "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    xf = int(round(crossfade * FPS))
    total = 0
    timeline = []

    def emit(fr):
        nonlocal total
        if preview:
            fr = cv2.resize(fr, (ow, oh), interpolation=cv2.INTER_AREA)
        ff.stdin.write(fr.tobytes())
        total += 1

    tail: list[np.ndarray] = []
    try:
        for s in segs:
            timeline.append({"id": s.id, "seconds": s.dur})
            gen = s.frames(aspect, base)
            if tail:
                n = len(tail)
                for j in range(n):
                    fr = next(gen, None)
                    if fr is None:
                        break
                    a = (j + 1) / (n + 1)
                    emit(cv2.addWeighted(tail[j], 1 - a, fr, a, 0))
            tail = []
            for fr in gen:
                tail.append(fr)
                if len(tail) > xf:
                    emit(tail.pop(0))
        for fr in tail:
            emit(fr)
    except BrokenPipeError as e:
        raise RenderError(f"ffmpeg stopped accepting frames: {ff.stderr.read().decode()[-400:]}", "Check ffmpeg has libx264.") from e
    finally:
        if ff.stdin:
            ff.stdin.close()
        ff.wait()
    if ff.returncode:
        raise RenderError(f"ffmpeg failed encoding {out.name}: {ff.stderr.read().decode()[-400:]}", "Check ffmpeg has libx264: `ffmpeg -encoders | grep x264`.")
    # the start of each segment is where its first (crossfading-in) frame lands
    t = 0.0
    for i, item in enumerate(timeline):
        item["start"] = round(t, 2)
        t += item["seconds"] - (crossfade if i < len(timeline) - 1 else 0)
    return total / FPS, timeline


def render_video(sb: Storyboard, video: Video | str, aspect: str, raw_dir: str | Path, gfx_dir: str | Path, out: str | Path,
                 *, preview: bool = False, log: Log | None = None) -> dict:
    """Compose one silent MP4. Needs the takes (`record`) and graphics (`graphics.render`) first."""
    log = log or (lambda s: None)
    if isinstance(video, str):
        video = sb.video(video)
    if aspect not in ASPECTS:
        raise RenderError(f"Unknown aspect {aspect!r}.", f"Use one of {', '.join(ASPECTS)}.")
    gfx_dir, raw_dir, out = Path(gfx_dir), Path(raw_dir), Path(out)
    W, H = ASPECTS[aspect]["size"]
    base = np.zeros((H, W, 3), np.uint8)
    chrome = graphics.chrome_item(aspect, sb.project.brand, sb.project.name)
    cp = cv2.imread(str(gfx_dir / f"{chrome['id']}.png"), cv2.IMREAD_UNCHANGED)
    if cp is None:
        raise RenderError("Frame chrome graphic is missing.", "Run `teaserkit captions <storyboard>` first.")
    over(base, cp)
    segs = segments_for(sb, video, raw_dir, gfx_dir, log)
    secs, timeline = encode_frames(segs, aspect, base, out, sb.style["crossfade_seconds"], preview)
    log(f"composed {video.id} {aspect}: {secs:.2f} s -> {out}")
    return {"video": video.id, "aspect": aspect, "path": str(out), "seconds": round(secs, 2), "timeline": timeline}
