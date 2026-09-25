import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo-app" / "storyboard.yaml"


def minimal(**over) -> dict:
    """A small valid storyboard as data."""
    beat = {"id": "b1", "take": "t", "steps": [{"goto": "/"}], "hold": 1.5, "duration": 5, "caption": "Short and plain caption"}
    beat.update(over.pop("beat", {}))
    data = {
        "project": {"name": "Demo", "base_url": "https://app.example.com"},
        "beats": [beat],
        "videos": [{"id": "v", "kind": "free", "beats": ["b1"]}],
    }
    for k, v in over.items():
        data[k] = v
    return data


@pytest.fixture
def ffmpeg_ok():
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")


def make_clip(path: Path, seconds: float = 3.0, size=(288, 162)) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={size[0]}x{size[1]}:rate=30:duration={seconds}",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
