import json

import cv2
import numpy as np
import pytest

from teaserkit import compose
from teaserkit.finishing import probe
from teaserkit.storyboard import parse

from conftest import make_clip, minimal


def test_fit_keeps_aspect_and_stays_in_frame():
    x, y, w, h = compose.fit((100, 100, 400, 300), 16 / 9, 200, 1000, 600)
    assert w / h == pytest.approx(16 / 9)
    assert x >= 0 and y >= 0 and x + w <= 1000 + 1e-6 and y + h <= 600 + 1e-6


def test_retime_speeds_action_and_keeps_hold():
    m, speed = compose.retime(0.0, 8.0, 10.0, 5.0, 4.0)
    assert speed > 1
    assert m(0) == 0
    assert m(4.99) <= 10.0
    m2, speed2 = compose.retime(0.0, 1.0, 2.0, 5.0, 4.0)  # short footage: freeze on the last frame
    assert speed2 == 1 and m2(4.9) == 2.0


def test_compose_smoke(tmp_path, ffmpeg_ok):
    raw, gfx = tmp_path / "raw", tmp_path / "gfx"
    raw.mkdir()
    gfx.mkdir()
    make_clip(raw / "t.mp4", 3.0)
    (raw / "t.json").write_text(json.dumps({"take": "t", "video": "t.mp4", "viewport": [144, 81], "dpr": 2, "frames": 90, "seconds": 3.0,
                                            "beats": {"b1": {"start": 0.2, "hold_start": 2.0, "end": 3.0, "boxes": {}}}}))
    data = minimal(beat={"duration": 3.5, "roi": [{"at": 0, "roi": [0, 0, 144, 81]}, {"at": 1.0, "roi": [20, 10, 100, 60], "move": 1.2}]})
    data["project"]["viewport"] = [144, 81]
    data["videos"][0]["end"] = {"tagline": "Bye", "seconds": 1.0}
    sb = parse(data)
    v = sb.videos[0]
    for aspect in ("16x9", "9x16"):
        for it in compose.graphics_needed(sb, v, aspect):  # stand-in PNGs: no browser needed
            w, h = compose.ASPECTS[aspect]["size"]
            img = np.zeros((h, w, 4), np.uint8)
            img[h - 60:, :, :] = (40, 40, 40, 200)
            cv2.imwrite(str(gfx / f"{it['id']}.png"), img)
        out = tmp_path / f"v-{aspect}.mp4"
        r = compose.render_video(sb, v, aspect, raw, gfx, out, preview=True)
        assert r["seconds"] == pytest.approx(3.5 + 1.0 - 0.5, abs=0.05)
        p = probe(out)
        assert p["video_codec"] == "h264" and p["fps"] == 30
        assert (p["width"], p["height"]) == tuple(s // 2 for s in compose.ASPECTS[aspect]["size"])
        assert [s["id"] for s in r["timeline"]] == ["b1", "end"]
