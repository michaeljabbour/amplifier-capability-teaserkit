"""Scaffold a new teaser project directory."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from .errors import TeaserkitError


class ProjectExists(TeaserkitError):
    code = "project_exists"
    exit_code = 1


def init_project(directory: str | Path, name: str = "My Product", *, force: bool = False) -> dict:
    """Write storyboard.yaml and brand.yaml into `directory` (created if needed). Never overwrites unless `force`."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    written = []
    for fname in ("storyboard.yaml", "brand.yaml"):
        target = d / fname
        if target.exists() and not force:
            raise ProjectExists(f"{target} already exists.", "Choose an empty directory or pass --force to overwrite.")
        text = resources.files("teaserkit").joinpath("templates", fname).read_text().replace("__NAME__", name)
        target.write_text(text)
        written.append(str(target.resolve()))
    return {"directory": str(d.resolve()), "files": written,
            "next": [f"edit {d / 'storyboard.yaml'}", f"teaserkit validate {d / 'storyboard.yaml'}",
                     f"teaserkit build {d / 'storyboard.yaml'} --out {d / 'out'}"]}
