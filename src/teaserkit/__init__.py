"""teaserkit: product teaser videos from a live web app.

The library is the tool; the `teaserkit` CLI is a thin wrapper over it.

Deterministic (no model provider needed):
    manifest, skill, capability_skill, capabilities, doctor, init_project, load_storyboard,
    parse_storyboard, validate, record, render_captions, compose_videos, render_video,
    make_track, finalize, contact_sheet, roi_grid, build, serve_static
Model-backed (need the `ai` extra and ANTHROPIC_API_KEY):
    plan, explore, review

Heavy modules (OpenCV, Playwright) load on first use, so `import teaserkit` is cheap.
"""

from __future__ import annotations

__version__ = "0.1.0"

from ._manifest import capabilities, capability_skill, manifest, skill  # noqa: E402
from .errors import (  # noqa: E402
    LeakDetected,
    MissingPrerequisite,
    NoProvider,
    RecordingError,
    RenderError,
    StoryboardError,
    StyleViolation,
    TeaserkitError,
)

_LAZY = {
    "load_storyboard": ("storyboard", "load"),
    "parse_storyboard": ("storyboard", "loads"),
    "Storyboard": ("storyboard", "Storyboard"),
    "validate": ("rules", "validate"),
    "record": ("recorder", "record"),
    "render_captions": ("pipeline", "render_captions"),
    "compose_videos": ("pipeline", "compose_videos"),
    "render_video": ("compose", "render_video"),
    "make_track": ("music", "make_track"),
    "synthesize": ("music", "synthesize"),
    "finalize": ("finishing", "finalize"),
    "probe": ("finishing", "probe"),
    "contact_sheet": ("sheets", "contact_sheet"),
    "roi_grid": ("sheets", "roi_grid"),
    "build": ("pipeline", "build"),
    "work_for": ("pipeline", "work_for"),
    "init_project": ("project", "init_project"),
    "serve_static": ("serve", "serve_static"),
    "doctor": ("prereqs", "doctor"),
    "plan": ("planner", "plan"),
    "explore": ("explorer", "explore"),
    "review": ("reviewer", "review"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        mod, attr = _LAZY[name]
        return getattr(importlib.import_module(f".{mod}", __name__), attr)
    raise AttributeError(f"module 'teaserkit' has no attribute {name!r}")


__all__ = ["__version__", "manifest", "skill", "capability_skill", "capabilities", *_LAZY,
           "TeaserkitError", "StoryboardError", "StyleViolation", "MissingPrerequisite", "NoProvider",
           "LeakDetected", "RecordingError", "RenderError"]
