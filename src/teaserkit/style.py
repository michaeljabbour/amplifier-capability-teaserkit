"""The default house style. Every value can be overridden per storyboard under `style:`."""

from __future__ import annotations

import copy

FPS = 30

# Output canvases. `panel` is the rectangle the screen recording occupies; the rest is chrome
# (brand band, caption band). Values are output pixels: (x, y, width, height).
ASPECTS: dict[str, dict] = {
    "16x9": {"size": (1920, 1080), "panel": (0, 0, 1920, 1080)},
    "9x16": {"size": (1080, 1920), "panel": (0, 170, 1080, 1500)},
    "1x1": {"size": (1080, 1080), "panel": (0, 0, 1080, 900)},
}

DEFAULT_STYLE: dict = {
    # captions
    "caption_max_words_per_line": 7,
    "caption_max_lines": 2,          # caption lines + subtitle line
    "caption_min_seconds": 2.5,      # time a caption is fully readable
    # pacing
    "beat_seconds": [4.0, 6.0],      # each feature is held about this long
    "beat_default_seconds": 5.0,     # used when a beat gives no `duration`
    "result_hold_min_seconds": 1.0,  # pause on the result at the end of a captioned beat
    "crossfade_seconds": 0.5,
    "title_seconds": 2.8,
    "end_seconds": 3.4,
    "max_speedup": 4.0,              # how much faster than real time the action part may play
    # camera
    "move_seconds": 1.4,             # default ease between framings
    "min_move_seconds": 1.2,         # anything faster reads as a jump cut
    "min_crop": {"16x9": 0.55, "9x16": 0.22, "1x1": 0.34},  # smallest crop, as a fraction of the recording width
    "roi_pad": 1.06,
    # lengths per video kind, seconds
    "lengths": {"main": [60.0, 90.0], "clip": [30.0, 40.0]},
    "length_tolerance_seconds": 2.0,
    # sound
    "music": "synth",                # synth | none. Only original synthesized music is supported.
    "music_bpm": 96,
    "loudness_lufs": -18.0,
    "true_peak_db": -2.0,
    "loudness_range": 7.0,
}

# Strings that should never be on screen in a teaser, whatever the product.
DEFAULT_DENY = ["undefined", "[object Object]", "NaN", "lorem ipsum", "Traceback (most recent call last)"]


def merged_style(overrides: dict | None) -> dict:
    out = copy.deepcopy(DEFAULT_STYLE)
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out
