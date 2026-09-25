"""Where teaserkit reads and writes.

- Output artifacts go where the caller asks (`out_dir`).
- Intermediate work (raw takes, rendered graphics, silent renders, audio) goes to a per-project
  work directory under the user's cache directory unless the caller passes `work_dir`.
- Scratch files go to the system temp directory and are removed.
Nothing is ever written next to the installed package.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from platformdirs import user_cache_dir

APP = "teaserkit"


def cache_root() -> Path:
    return Path(user_cache_dir(APP, appauthor=False))


def default_work_dir(storyboard_path: Path | str, project_name: str) -> Path:
    """A stable per-storyboard work directory: <cache>/work/<slug>-<hash of absolute path>."""
    p = Path(storyboard_path).resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-") or "project"
    digest = hashlib.sha1(str(p).encode()).hexdigest()[:8]
    return cache_root() / "work" / f"{slug}-{digest}"


def work_layout(work_dir: Path) -> dict[str, Path]:
    d = {
        "root": work_dir,
        "raw": work_dir / "raw",
        "gfx": work_dir / "gfx",
        "silent": work_dir / "silent",
        "audio": work_dir / "audio",
    }
    for v in d.values():
        v.mkdir(parents=True, exist_ok=True)
    return d
