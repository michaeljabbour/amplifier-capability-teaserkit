"""[AI] Draft a storyboard from a product description and a feature list.

The draft is validated against the style rules in strict mode (warnings count). If it fails,
the problems are sent back to the model to repair, up to `attempts` times. A draft that still
breaks a rule is a failure, not a partial result.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

import yaml

from . import _provider
from .errors import StoryboardError, StyleViolation
from .style import merged_style
from .rules import validate

SCHEMA = {
    "type": "object",
    "properties": {
        "storyboard_yaml": {"type": "string", "description": "The complete storyboard as YAML."},
        "notes": {"type": "string", "description": "What the author must still check: selectors guessed, data to seed."},
    },
    "required": ["storyboard_yaml", "notes"],
    "additionalProperties": False,
}


@dataclass
class PlanResult:
    storyboard_yaml: str
    notes: str
    attempts: int
    report: dict


def _system(style: dict) -> str:
    from . import storyboard as sbmod

    example = (resources.files("teaserkit").joinpath("templates", "storyboard.yaml").read_text())
    lengths = style["lengths"]
    return f"""You write storyboards for short product teaser videos filmed from a live web app.

The storyboard format (YAML), documented:
{sbmod.__doc__}

A minimal example:
{example}

House style you MUST satisfy (the draft is machine-checked):
- Captions: plain language, at most {style['caption_max_words_per_line']} words per line, at most {style['caption_max_lines']} lines counting `sub`.
- Every beat lasts between {style['beat_seconds'][0]:g} and {style['beat_seconds'][1]:g} seconds (`duration`), so its caption is readable for at least {style['caption_min_seconds']:g} s.
- Every captioned beat ends with `hold` >= {style['result_hold_min_seconds']:g} s on the result.
- Camera keyframes after the first use `move` >= {style['min_move_seconds']:g} s. Prefer one or two framings per beat.
- Video length: main {lengths['main'][0]:g}-{lengths['main'][1]:g} s, clip {lengths['clip'][0]:g}-{lengths['clip'][1]:g} s. Length = title {style['title_seconds']:g} s + beats + end {style['end_seconds']:g} s - {style['crossfade_seconds']:g} s per crossfade between segments.
- One feature per beat. Fewer cuts. Show each result, then rest on it.
- Fictional demo content only: invented people, projects and companies. No voiceover. Music is synthesized automatically.
- ROIs are CSS pixels inside the viewport; prefer `selector` keyframes when you know an element, otherwise omit roi.
- Beats that share a `take` are filmed in one continuous browser session, in order. Use one take
  for a flow that continues from screen to screen; only the first beat of a take needs a `goto`.
- Brand: `fonts` is a mapping {{heading, body}} of CSS font stacks; colors use the keys ink, paper,
  accent, highlight, muted. Do not reference logo or font files that may not exist.
- Locators: prefer visible text, roles with names, labels and placeholders over CSS selectors.
Return the whole storyboard as YAML in `storyboard_yaml` and list guesses the author must verify in `notes`."""


def _parse_draft(text: str):
    """Parse a draft for checking. File references (brand, serve dir) cannot exist yet, so they are
    neutralized for validation only; the returned YAML text is untouched."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise StoryboardError(f"Not valid YAML: {e}", "Return valid YAML.") from e
    if isinstance(data, dict) and isinstance(data.get("project"), dict):
        p = data["project"]
        if isinstance(p.get("brand"), str):
            p["brand"] = {}
        elif isinstance(p.get("brand"), dict):
            b = p["brand"]
            for k in ("logo", "logo_on_dark"):
                b.pop(k, None)
            if isinstance(b.get("fonts"), dict):
                b["fonts"].pop("files", None)
        if p.get("serve"):
            p.pop("serve")
            p.setdefault("base_url", "https://app.example.com")
        if isinstance(p.get("auth"), dict) and p["auth"].get("kind") == "storage_state":
            p["auth"] = {"kind": "none"}
    from .storyboard import parse

    return parse(data)


def plan(description: str, features: list[str], *, base_url: str | None = None, kind: str = "main", name: str | None = None,
         style: dict | None = None, context: str | None = None, attempts: int = 3) -> PlanResult:
    """Draft a storyboard (YAML text) that already passes `validate(strict=True)`.

    `context` is optional extra material (notes, a sitemap, page text) passed verbatim to the model.
    Model-backed: needs a provider (see `_provider`). Raises StyleViolation if no valid draft was produced.
    """
    _provider.client()  # fail fast, before any work, when no provider is configured
    st = merged_style(style)
    ask = [f"Product: {name or 'the product'}", f"What it does: {description}", f"Video kind: {kind}",
           f"Base URL: {base_url or 'https://app.example.com'}", "Features to show, in order:"]
    ask += [f"- {f}" for f in features]
    if style:
        ask.append(f"Style overrides to include under `style:`: {yaml.safe_dump(style)}")
    if context:
        ask.append(f"Context from the caller:\n{context}")
    content = "\n".join(ask)
    system = _system(st)
    last_err = ""
    draft = {"storyboard_yaml": "", "notes": ""}
    for i in range(1, attempts + 1):
        msg = content if not last_err else f"{content}\n\nYour previous draft:\n{draft['storyboard_yaml']}\n\nIt failed these checks; fix all of them:\n{last_err}"
        draft = _provider.ask_json(system, msg, SCHEMA)
        try:
            sb = _parse_draft(draft["storyboard_yaml"])
        except StoryboardError as e:
            last_err = f"{e.message}"
            continue
        rep = validate(sb, strict=True)
        if rep.ok:
            return PlanResult(draft["storyboard_yaml"], draft["notes"], i, rep.to_dict())
        last_err = "\n".join(f"- {x.where}: {x.message}" for x in rep.errors)
    raise StyleViolation(f"No draft passed the style rules after {attempts} attempt(s).",
                         "Retry, simplify the feature list, or edit the last draft by hand.",
                         details={"last_draft": draft.get("storyboard_yaml", ""), "problems": last_err})
