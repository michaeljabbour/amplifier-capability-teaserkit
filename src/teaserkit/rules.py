"""Style-rule checks. Deterministic, no browser, no network.

Because every beat has a planned duration (its `duration`, or the style default), a video's
length is known before anything is recorded, so pacing rules are checked up front.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .storyboard import Beat, Storyboard, Video
from .style import DEFAULT_DENY

CAPTION_FADE_IN_AT = 0.3   # captions appear this far into a beat...
CAPTION_FADE_OUT_BEFORE = 0.4  # ...and leave this long before its end


@dataclass
class Issue:
    rule: str
    where: str
    message: str
    severity: str  # "error" | "warning"


@dataclass
class Report:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    videos: dict[str, float] = field(default_factory=dict)  # planned seconds per video

    @property
    def ok(self) -> bool:
        return not self.errors

    def clean(self) -> bool:
        return not self.errors and not self.warnings

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [asdict(i) for i in self.errors],
            "warnings": [asdict(i) for i in self.warnings],
            "planned_seconds": self.videos,
        }

    def text(self) -> str:
        lines = []
        for i in self.errors + self.warnings:
            lines.append(f"{i.severity.upper():7} {i.rule:18} {i.where}: {i.message}")
        for vid, secs in self.videos.items():
            lines.append(f"video   {vid}: {secs:.1f} s planned")
        lines.append("OK" if self.ok else f"FAILED: {len(self.errors)} error(s)")
        return "\n".join(lines)


def words(line: str) -> int:
    return len([w for w in re.split(r"\s+", line.strip()) if re.search(r"[\w\d]", w)])


def deny_terms(sb: Storyboard) -> list[str]:
    terms = list(sb.project.deny_list)
    if sb.project.deny_defaults:
        terms += [t for t in DEFAULT_DENY if t not in terms]
    return terms


def deny_pattern(terms: list[str]) -> re.Pattern | None:
    """Case-insensitive; alphanumeric edges match on word boundaries so 'NaN' does not hit 'Finance'."""
    parts = []
    for t in terms:
        if not t:
            continue
        e = re.escape(t)
        if t[0].isalnum():
            e = r"\b" + e
        if t[-1].isalnum():
            e = e + r"\b"
        parts.append(e)
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


def caption_visible(duration: float) -> float:
    return max(0.0, duration - CAPTION_FADE_IN_AT - CAPTION_FADE_OUT_BEFORE)


def segments(video: Video, style: dict) -> list[tuple[str, float]]:
    segs: list[tuple[str, float]] = []
    if video.title:
        segs.append(("title", float(video.title.get("seconds", style["title_seconds"]))))
    segs += [(b.id, b.planned(style)) for b in video.beats]
    if video.end:
        segs.append(("end", float(video.end.get("seconds", style["end_seconds"]))))
    return segs


def planned_seconds(video: Video, style: dict) -> float:
    segs = segments(video, style)
    xf = style["crossfade_seconds"]
    return sum(d for _, d in segs) - xf * max(0, len(segs) - 1)


def _beat_rules(b: Beat, sb: Storyboard, add) -> None:
    st = sb.style
    where = f"beats.{b.id}"
    lines = b.caption_lines()
    maxw = st["caption_max_words_per_line"]
    for ln in lines:
        n = words(ln)
        if n > maxw:
            add("error", "caption-words", where, f"'{ln}' has {n} words; the limit is {maxw} per line. Shorten it or split it with a subtitle.")
    if len(lines) > st["caption_max_lines"]:
        add("error", "caption-lines", where, f"{len(lines)} caption lines; the limit is {st['caption_max_lines']} (caption + subtitle).")
    d = b.planned(st)
    if lines:
        vis = caption_visible(d)
        if vis + 1e-6 < st["caption_min_seconds"]:
            need = st["caption_min_seconds"] + CAPTION_FADE_IN_AT + CAPTION_FADE_OUT_BEFORE
            add("error", "caption-time", where, f"caption readable for {vis:.1f} s; needs {st['caption_min_seconds']:.1f} s. Make the beat at least {need:.1f} s.")
        if b.hold < st["result_hold_min_seconds"]:
            add("warning", "result-hold", where, f"hold is {b.hold:.1f} s; rest at least {st['result_hold_min_seconds']:.1f} s on the result so viewers can take it in.")
    lo, hi = st["beat_seconds"]
    if not (lo - 1e-6 <= d <= hi + 1e-6):
        add("warning", "beat-length", where, f"beat lasts {d:.1f} s; features read best held {lo:g}-{hi:g} s.")
    vw, vh = sb.project.viewport
    for aspect, kfs in [("*", b.roi), *b.roi_per_aspect.items()]:
        for k in kfs:
            if k.roi:
                x0, y0, x1, y1 = k.roi
                if x0 < 0 or y0 < 0 or x1 > vw or y1 > vh:
                    add("error", "roi-bounds", where, f"roi {k.roi} ({aspect}) falls outside the {vw}x{vh} viewport.")
            if k.at > d:
                add("warning", "roi-timing", where, f"keyframe at {k.at:.1f} s ({aspect}) is after the beat ends ({d:.1f} s).")
        for k in kfs[1:]:
            mv = k.move if k.move is not None else st["move_seconds"]
            if mv < st["min_move_seconds"]:
                add("warning", "camera-speed", where, f"camera move of {mv:.1f} s at {k.at:.1f} s ({aspect}); use at least {st['min_move_seconds']:.1f} s so it reads as a slow ease.")


def validate(sb: Storyboard, *, strict: bool = False) -> Report:
    """Check every style rule. With `strict`, warnings count as errors (used by `plan`)."""
    rep = Report()
    st = sb.style

    def add(sev, rule, where, msg):
        if strict and sev == "warning":
            sev = "error"
        (rep.errors if sev == "error" else rep.warnings).append(Issue(rule, where, msg, sev))

    if st.get("music") not in ("synth", "none"):
        add("error", "music", "style.music", f"'{st.get('music')}' is not allowed; only original synthesized music ('synth') or 'none'.")
    seen: set[str] = set()
    for v in sb.videos:
        for b in v.beats:
            if b.id not in seen:
                seen.add(b.id)
                _beat_rules(b, sb, add)
    for v in sb.videos:
        secs = planned_seconds(v, st)
        rep.videos[v.id] = round(secs, 2)
        rng = st["lengths"].get(v.kind)
        if rng:
            tol = st["length_tolerance_seconds"]
            if not (rng[0] - tol <= secs <= rng[1] + tol):
                add("warning", "video-length", f"videos.{v.id}", f"{v.kind} video plans {secs:.1f} s; aim for {rng[0]:g}-{rng[1]:g} s.")
        per_min = len(v.beats) / max(secs / 60.0, 1e-6)
        if per_min > 60.0 / st["beat_seconds"][0] + 0.5:
            add("warning", "cut-rate", f"videos.{v.id}", f"{per_min:.0f} beats per minute; fewer, longer beats are easier to follow.")
    pat = deny_pattern(deny_terms(sb))
    if pat:
        for where, text in sb.texts():
            m = pat.search(text or "")
            if m:
                add("error", "deny-list", where, f"contains deny-listed '{m.group(0)}'. Use fictional demo content only.")
    return rep
