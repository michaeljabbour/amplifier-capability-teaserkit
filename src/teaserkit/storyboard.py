"""Storyboard schema: one YAML file describes the product, the look, and every video.

```yaml
project:
  name: Acme Planner
  base_url: https://app.example.com      # or omit and use `serve` for a local static site
  serve: {dir: site, port: 0}             # optional: serve a static directory while recording
  auth: {kind: none}                      # none | storage_state | script
  brand: brand.yaml                       # or an inline mapping (fonts, colors, logo)
  deny_list: ["Internal", "staging"]      # strings that must never be on screen
  viewport: [1440, 810]
  dpr: 2
outputs:
  aspects: [16x9, 9x16, 1x1]
  no_audio: main                          # main | all | none
  posters: true
  sheets: true
style: {caption_max_words_per_line: 7}    # overrides of the house style
beats:                                    # reusable beats, referenced by id from videos
  - id: add-task
    take: tour                            # beats sharing a take are recorded in one continuous take
    steps:
      - click: {placeholder: "Add a task"}
      - type: {text: "Book the venue walkthrough"}
      - press: Enter
    hold: 1.5                             # seconds to rest on the result
    duration: 5                           # seconds this beat lasts in the edit
    caption: Add a task in seconds
    sub: Optional second line
    roi: {selector: "#tasks"}             # or [x0, y0, x1, y1] in CSS pixels, or keyframes
    roi_per_aspect: {9x16: [0, 100, 720, 700]}
videos:
  - id: teaser
    kind: clip                            # main | clip | free
    title: {title: Acme Planner, sub: Plan the week without the busywork.}
    end: {tagline: Plan less. Do more., sub: Free for small teams., url: acme.example}
    beats: [add-task]                     # ids or inline beat mappings
```

Paths are relative to the storyboard file. Strings may reference environment variables as
`${env:NAME}`; they are resolved at record time, never stored.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import StoryboardError
from .style import ASPECTS, merged_style

STEP_KINDS = ("goto", "click", "type", "press", "scroll", "hover", "wait_for", "hold", "move")
LOCATOR_KEYS = ("text", "role", "selector", "label", "placeholder")
VIDEO_KINDS = ("main", "clip", "free")
AUTH_KINDS = ("none", "storage_state", "script")


@dataclass
class Brand:
    heading_font: str = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    body_font: str = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    font_files: list[dict] = field(default_factory=list)  # [{family, path, weight?}] embedded into graphics
    colors: dict[str, str] = field(default_factory=dict)
    logo: Path | None = None  # SVG or PNG, for light backgrounds (cards)
    logo_on_dark: Path | None = None  # for the dark brand band; without it the wordmark is set as text
    wordmark: str | None = None  # text shown where a logo would go when no logo is given

    DEFAULT_COLORS = {
        "ink": "#1E2230",        # caption plates, dark bands, headings
        "paper": "#FFFFFF",      # card backgrounds
        "accent": "#3B5BDB",     # cursor ripple, buttons, highlights
        "highlight": "#F2B84B",  # caption plate edge
        "muted": "#5B6272",      # secondary text on cards
        "caption_text": "#FFFFFF",
        "caption_sub": "#C8CCD8",
    }

    def color(self, key: str) -> str:
        return self.colors.get(key) or self.DEFAULT_COLORS[key]

    def stripe(self) -> list[str]:
        s = self.colors.get("stripe")
        if isinstance(s, list) and s:
            return s
        return [self.color("accent"), self.color("highlight")]


@dataclass
class Auth:
    kind: str = "none"
    storage_state: Path | None = None  # JSON: {"cookies": [...], "origins": [{"origin", "localStorage": [{name, value}]}]}
    steps: list[dict] = field(default_factory=list)  # run before recording, never filmed


@dataclass
class Project:
    name: str
    base_url: str | None
    auth: Auth
    brand: Brand
    deny_list: list[str]
    deny_defaults: bool = True
    viewport: tuple[int, int] = (1440, 810)
    dpr: int = 2
    locale: str = "en-US"
    timezone: str = "UTC"
    serve_dir: Path | None = None
    serve_port: int = 0


@dataclass
class Keyframe:
    at: float                 # seconds into the beat, output time
    roi: list[float] | None   # CSS pixels [x0, y0, x1, y1]
    selector: str | None      # resolved to the element's box at record time
    pad: float = 24.0
    move: float | None = None  # ease duration into this framing; None = style default


@dataclass
class Beat:
    id: str
    take: str
    steps: list[dict]
    hold: float = 1.5
    duration: float | None = None
    caption: str | None = None
    sub: str | None = None
    roi: list[Keyframe] = field(default_factory=list)
    roi_per_aspect: dict[str, list[Keyframe]] = field(default_factory=dict)

    def planned(self, style: dict) -> float:
        return float(self.duration if self.duration is not None else style["beat_default_seconds"])

    def keyframes(self, aspect: str) -> list[Keyframe]:
        return self.roi_per_aspect.get(aspect) or self.roi

    def selectors(self) -> list[str]:
        out = []
        for kfs in [self.roi, *self.roi_per_aspect.values()]:
            for k in kfs:
                if k.selector and k.selector not in out:
                    out.append(k.selector)
        return out

    def caption_lines(self) -> list[str]:
        lines = [ln.strip() for ln in (self.caption or "").split("\n") if ln.strip()]
        if self.sub:
            lines.append(self.sub.strip())
        return lines


@dataclass
class Video:
    id: str
    kind: str
    beats: list[Beat]
    title: dict | None = None
    end: dict | None = None
    poster_at: float | None = None


@dataclass
class Outputs:
    aspects: list[str] = field(default_factory=lambda: list(ASPECTS))
    no_audio: str = "main"
    posters: bool = True
    sheets: bool = True


@dataclass
class Storyboard:
    path: Path | None
    project: Project
    outputs: Outputs
    style: dict
    beats: dict[str, Beat]
    videos: list[Video]
    raw: dict = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return self.path.parent if self.path else Path.cwd()

    def takes(self) -> dict[str, list[Beat]]:
        """Beats grouped by take, in first-appearance order (library order, then video order)."""
        out: dict[str, list[Beat]] = {}
        seen: set[str] = set()
        order = list(self.beats.values()) + [b for v in self.videos for b in v.beats]
        for b in order:
            if b.id in seen:
                continue
            seen.add(b.id)
            out.setdefault(b.take, []).append(b)
        return out

    def video(self, vid: str) -> Video:
        for v in self.videos:
            if v.id == vid:
                return v
        raise StoryboardError(f"No video with id '{vid}'.", f"Known videos: {', '.join(v.id for v in self.videos)}")

    def texts(self) -> list[tuple[str, str]]:
        """Every human-visible string the storyboard puts on screen, with where it came from."""
        out: list[tuple[str, str]] = []
        for v in self.videos:
            for key in ("title", "end"):
                for k, s in (getattr(v, key) or {}).items():
                    if isinstance(s, str):
                        out.append((f"videos.{v.id}.{key}.{k}", s))
        for b in self._all_beats():
            for i, ln in enumerate(b.caption_lines()):
                out.append((f"beats.{b.id}.caption[{i}]", ln))
            for i, st in enumerate(b.steps):
                if "type" in st:
                    t = st["type"]
                    out.append((f"beats.{b.id}.steps[{i}].type", t if isinstance(t, str) else str(t.get("text", ""))))
        return out

    def _all_beats(self) -> list[Beat]:
        seen, out = set(), []
        for b in list(self.beats.values()) + [b for v in self.videos for b in v.beats]:
            if b.id not in seen:
                seen.add(b.id)
                out.append(b)
        return out


# ─────────────────────────────── parsing ───────────────────────────────


def _err(where: str, msg: str, remedy: str = "") -> StoryboardError:
    return StoryboardError(f"{where}: {msg}", remedy or "Fix the storyboard; run `teaserkit validate <storyboard>` to re-check.")


def _num(v: Any, where: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise _err(where, f"expected a number, got {v!r}")
    return float(v)


def _parse_locator(v: Any, where: str) -> dict:
    if isinstance(v, str):
        return {"text": v}
    if isinstance(v, dict) and any(k in v for k in LOCATOR_KEYS):
        return dict(v)
    raise _err(where, f"expected a locator (a string, or a mapping with one of {', '.join(LOCATOR_KEYS)}), got {v!r}")


def _parse_step(s: Any, where: str) -> dict:
    if isinstance(s, str) and s in ("hold",):
        return {"hold": 1.0}
    if not isinstance(s, dict) or len([k for k in s if k in STEP_KINDS]) != 1:
        raise _err(where, f"a step is a mapping with exactly one of {', '.join(STEP_KINDS)}; got {s!r}")
    kind = next(k for k in s if k in STEP_KINDS)
    v = s[kind]
    opts = {k: val for k, val in s.items() if k != kind}
    if kind == "goto":
        if isinstance(v, dict):
            v = v.get("url") or v.get("path")
        if not isinstance(v, str) or not v:
            raise _err(where, "goto needs a path or URL")
        return {"goto": v, **opts}
    if kind in ("click", "hover", "wait_for"):
        return {kind: _parse_locator(v, where), **opts}
    if kind == "type":
        if isinstance(v, str):
            v = {"text": v}
        if not isinstance(v, dict) or not isinstance(v.get("text"), str):
            raise _err(where, "type needs `text` (a string)")
        if "into" in v:
            v = {**v, "into": _parse_locator(v["into"], where + ".into")}
        return {"type": v, **opts}
    if kind == "press":
        if not isinstance(v, str):
            raise _err(where, "press needs a key name such as Enter")
        return {"press": v, **opts}
    if kind == "scroll":
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            v = {"dy": v}
        if not isinstance(v, dict) or "dy" not in v:
            raise _err(where, "scroll needs `dy` (pixels, positive scrolls down)")
        return {"scroll": {"dy": _num(v["dy"], where), "ms": _num(v.get("ms", 900), where)}, **opts}
    if kind == "hold":
        return {"hold": _num(v, where), **opts}
    if kind == "move":
        if not isinstance(v, dict) or "x" not in v or "y" not in v:
            raise _err(where, "move needs `x` and `y` (CSS pixels)")
        return {"move": {"x": _num(v["x"], where), "y": _num(v["y"], where), "ms": _num(v.get("ms", 700), where)}, **opts}
    raise _err(where, f"unknown step {kind}")  # pragma: no cover


def _parse_roi(v: Any, where: str) -> list[Keyframe]:
    if v is None:
        return []
    if isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        v = [{"at": 0, "roi": list(v)}]
    if isinstance(v, dict):
        v = [dict(v, at=v.get("at", 0))]
    if not isinstance(v, list):
        raise _err(where, "roi is [x0, y0, x1, y1], {selector: ...}, or a list of keyframes {at, roi|selector, move}")
    out = []
    for i, k in enumerate(v):
        w = f"{where}[{i}]"
        if not isinstance(k, dict):
            raise _err(w, "a keyframe is a mapping {at, roi|selector, move}")
        roi = k.get("roi")
        sel = k.get("selector")
        if (roi is None) == (sel is None):
            raise _err(w, "a keyframe needs exactly one of `roi` or `selector`")
        if roi is not None:
            if not (isinstance(roi, list) and len(roi) == 4):
                raise _err(w, "roi must be [x0, y0, x1, y1]")
            roi = [_num(x, w) for x in roi]
            if roi[2] <= roi[0] or roi[3] <= roi[1]:
                raise _err(w, f"roi {roi} has no area (x1 must exceed x0 and y1 exceed y0)")
        out.append(Keyframe(at=_num(k.get("at", 0), w), roi=roi, selector=sel,
                            pad=_num(k.get("pad", 24), w), move=_num(k["move"], w) if "move" in k else None))
    out.sort(key=lambda k: k.at)
    return out


def _parse_beat(b: Any, where: str) -> Beat:
    if not isinstance(b, dict):
        raise _err(where, "a beat is a mapping")
    bid = b.get("id")
    if not isinstance(bid, str) or not bid:
        raise _err(where, "every beat needs an `id`")
    where = f"beats.{bid}"
    steps = b.get("steps") or []
    if not isinstance(steps, list):
        raise _err(where, "steps must be a list")
    rpa = b.get("roi_per_aspect") or {}
    if not isinstance(rpa, dict):
        raise _err(where, "roi_per_aspect maps an aspect (16x9, 9x16, 1x1) to a roi")
    for a in rpa:
        if a not in ASPECTS:
            raise _err(where, f"roi_per_aspect has unknown aspect {a!r}", f"Use one of {', '.join(ASPECTS)}.")
    cap = b.get("caption")
    if cap is not None and not isinstance(cap, str):
        raise _err(where, "caption must be a string (use \\n for a second line)")
    return Beat(
        id=bid,
        take=str(b.get("take") or "main"),
        steps=[_parse_step(s, f"{where}.steps[{i}]") for i, s in enumerate(steps)],
        hold=_num(b.get("hold", 1.5), where + ".hold"),
        duration=_num(b["duration"], where + ".duration") if b.get("duration") is not None else None,
        caption=cap,
        sub=b.get("sub"),
        roi=_parse_roi(b.get("roi"), where + ".roi"),
        roi_per_aspect={a: _parse_roi(r, f"{where}.roi_per_aspect.{a}") for a, r in rpa.items()},
    )


def _parse_brand(v: Any, root: Path) -> Brand:
    if v is None:
        return Brand()
    if isinstance(v, str):
        p = (root / v).resolve()
        if not p.exists():
            raise _err("project.brand", f"brand file {v!r} not found (looked in {p.parent})")
        v = yaml.safe_load(p.read_text()) or {}
        root = p.parent
    if not isinstance(v, dict):
        raise _err("project.brand", "brand is a file path or a mapping")
    fonts = v.get("fonts") or {}
    br = Brand()
    if isinstance(fonts, dict):
        br.heading_font = fonts.get("heading", br.heading_font)
        br.body_font = fonts.get("body", br.body_font)
        files = fonts.get("files") or []
        for f in files:
            if not isinstance(f, dict) or "family" not in f or "path" not in f:
                raise _err("project.brand.fonts.files", "each font file is {family, path, weight?}")
            fp = (root / f["path"]).resolve()
            if not fp.exists():
                raise _err("project.brand.fonts.files", f"font file {f['path']!r} not found")
            br.font_files.append({**f, "path": fp})
    br.colors = dict(v.get("colors") or {})
    if v.get("logo"):
        lp = (root / v["logo"]).resolve()
        if not lp.exists():
            raise _err("project.brand.logo", f"logo {v['logo']!r} not found")
        br.logo = lp
    if v.get("logo_on_dark"):
        lp = (root / v["logo_on_dark"]).resolve()
        if not lp.exists():
            raise _err("project.brand.logo_on_dark", f"logo {v['logo_on_dark']!r} not found")
        br.logo_on_dark = lp
    br.wordmark = v.get("wordmark")
    return br


def _parse_project(p: Any, root: Path) -> Project:
    if not isinstance(p, dict) or not p.get("name"):
        raise _err("project", "needs at least `name`")
    auth_raw = p.get("auth") or {"kind": "none"}
    kind = auth_raw.get("kind", "none")
    if kind not in AUTH_KINDS:
        raise _err("project.auth", f"kind must be one of {', '.join(AUTH_KINDS)}")
    auth = Auth(kind=kind)
    if kind == "storage_state":
        sp = auth_raw.get("path")
        if not sp:
            raise _err("project.auth", "storage_state needs `path` to a JSON file of cookies/localStorage")
        auth.storage_state = (root / sp).resolve()
    elif kind == "script":
        auth.steps = [_parse_step(s, f"project.auth.steps[{i}]") for i, s in enumerate(auth_raw.get("steps") or [])]
        if not auth.steps:
            raise _err("project.auth", "script auth needs `steps` (run before recording, never filmed)")
    serve = p.get("serve")
    serve_dir, serve_port = None, 0
    if serve:
        if not isinstance(serve, dict) or "dir" not in serve:
            raise _err("project.serve", "serve is {dir, port?}")
        serve_dir = (root / serve["dir"]).resolve()
        serve_port = int(serve.get("port", 0))
        if not serve_dir.is_dir():
            raise _err("project.serve", f"directory {serve['dir']!r} not found")
    base = p.get("base_url")
    if not base and not serve_dir:
        raise _err("project", "needs `base_url`, or `serve` to film a local static site")
    vp = p.get("viewport", [1440, 810])
    deny = p.get("deny_list") or []
    if not isinstance(deny, list) or not all(isinstance(x, str) for x in deny):
        raise _err("project.deny_list", "deny_list is a list of strings")
    return Project(
        name=str(p["name"]),
        base_url=base.rstrip("/") if base else None,
        auth=auth,
        brand=_parse_brand(p.get("brand"), root),
        deny_list=list(deny),
        deny_defaults=bool(p.get("deny_defaults", True)),
        viewport=(int(vp[0]), int(vp[1])),
        dpr=int(p.get("dpr", 2)),
        locale=str(p.get("locale", "en-US")),
        timezone=str(p.get("timezone", "UTC")),
        serve_dir=serve_dir,
        serve_port=serve_port,
    )


def parse(data: dict, path: Path | None = None) -> Storyboard:
    """Build a Storyboard from already-loaded YAML data. Raises StoryboardError with the location of the problem."""
    if not isinstance(data, dict):
        raise _err("storyboard", "top level must be a mapping with project, videos (and optionally beats, outputs, style)")
    raw = copy.deepcopy(data)
    root = path.parent if path else Path.cwd()
    project = _parse_project(data.get("project"), root)
    o = data.get("outputs") or {}
    aspects = o.get("aspects", list(ASPECTS))
    for a in aspects:
        if a not in ASPECTS:
            raise _err("outputs.aspects", f"unknown aspect {a!r}", f"Use any of {', '.join(ASPECTS)}.")
    no_audio = o.get("no_audio", "main")
    if no_audio not in ("main", "all", "none"):
        raise _err("outputs.no_audio", "must be main, all or none")
    outputs = Outputs(aspects=list(aspects), no_audio=no_audio, posters=bool(o.get("posters", True)), sheets=bool(o.get("sheets", True)))
    style = merged_style(data.get("style"))
    beats: dict[str, Beat] = {}
    for i, b in enumerate(data.get("beats") or []):
        beat = _parse_beat(b, f"beats[{i}]")
        if beat.id in beats:
            raise _err(f"beats.{beat.id}", "duplicate beat id")
        beats[beat.id] = beat
    videos: list[Video] = []
    vids = data.get("videos")
    if not isinstance(vids, list) or not vids:
        raise _err("videos", "needs at least one video")
    inline_ids: set[str] = set()
    for i, v in enumerate(vids):
        if not isinstance(v, dict) or not v.get("id"):
            raise _err(f"videos[{i}]", "every video needs an `id`")
        where = f"videos.{v['id']}"
        kind = v.get("kind", "main")
        if kind not in VIDEO_KINDS:
            raise _err(where, f"kind must be one of {', '.join(VIDEO_KINDS)}")
        vb: list[Beat] = []
        for j, ref in enumerate(v.get("beats") or []):
            if isinstance(ref, str):
                if ref not in beats:
                    raise _err(f"{where}.beats[{j}]", f"no beat with id {ref!r}")
                vb.append(beats[ref])
            else:
                beat = _parse_beat(ref, f"{where}.beats[{j}]")
                if beat.id in beats or beat.id in inline_ids:
                    raise _err(f"{where}.beats[{j}]", f"beat id {beat.id!r} is already used; inline beats need unique ids")
                inline_ids.add(beat.id)
                vb.append(beat)
        if not vb:
            raise _err(where, "a video needs at least one beat")
        for key in ("title", "end"):
            if v.get(key) is not None and not isinstance(v.get(key), dict):
                raise _err(f"{where}.{key}", "must be a mapping")
        videos.append(Video(id=str(v["id"]), kind=kind, beats=vb, title=v.get("title"), end=v.get("end"),
                            poster_at=_num(v["poster_at"], where + ".poster_at") if v.get("poster_at") is not None else None))
    if len({v.id for v in videos}) != len(videos):
        raise _err("videos", "video ids must be unique")
    return Storyboard(path=path, project=project, outputs=outputs, style=style, beats=beats, videos=videos, raw=raw)


def load(path: str | Path) -> Storyboard:
    """Read and parse a storyboard file."""
    p = Path(path).resolve()
    if not p.exists():
        raise StoryboardError(f"Storyboard not found: {p}", "Pass the path to a storyboard.yaml, or create one with `teaserkit init <dir>`.")
    try:
        data = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise StoryboardError(f"{p.name} is not valid YAML: {e}", "Fix the YAML syntax.") from e
    return parse(data, p)


def loads(text: str, base_dir: str | Path | None = None) -> Storyboard:
    """Parse storyboard YAML from a string. Relative paths resolve against `base_dir` (default: cwd)."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise StoryboardError(f"Not valid YAML: {e}", "Fix the YAML syntax.") from e
    fake = (Path(base_dir) / "storyboard.yaml").resolve() if base_dir else None
    sb = parse(data, fake)
    return sb
