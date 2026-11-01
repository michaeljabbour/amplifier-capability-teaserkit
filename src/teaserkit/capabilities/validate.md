Checks a storyboard against the house style before anything is filmed. Deterministic: no
browser, no network, no model. Because every beat has a planned duration (`duration`, or the
style's `beat_default_seconds`), each video's final length is known here.

Checks are errors unless noted. Style defaults may be overridden under `style:`;
the viewport requirement is structural.

- `viewport` -- exactly two positive integer CSS-pixel dimensions. This structural
  requirement is fixed rather than a style override. It is also checked for manually
  constructed or mutated library storyboards before ROI rules run.
- `caption-words` -- at most 7 words per caption line.
- `caption-lines` -- at most 2 lines, counting `sub`.
- `caption-time` -- each caption readable at least 2.5 s (beat duration minus fades).
- `result-hold` (warning) -- captioned beats rest at least 1 s on the result (`hold`).
- `beat-length` (warning) -- each beat 4-6 s.
- `camera-speed` (warning) -- keyframe moves at least 1.2 s.
- `roi-bounds` / `roi-timing` -- ROIs inside the viewport and inside the beat.
- `video-length` (warning) -- main 60-90 s, clip 30-40 s (plus/minus 2 s); `free` is unchecked.
- `cut-rate` (warning) -- no more beats per minute than the minimum beat length allows.
- `deny-list` -- no caption, card or typed text contains a deny-listed string (project
  `deny_list` plus built-ins such as "undefined", "NaN", "lorem ipsum").
- `music` -- only `synth` (original synthesized) or `none`.

Schema problems (unknown step, missing id, bad ROI shape or viewport) fail during parsing
as `storyboard_invalid`. `project.viewport` accepts a list or tuple of two positive
integers, defaulting to `[1440, 810]`. Booleans, numeric strings, floats (including
non-finite values), nonpositive dimensions and other shapes are rejected instead of
being truncated or coerced. If a library caller changes the viewport after parsing,
`validate` preserves its `Report` return contract and returns a hard `viewport` error.

## Arguments

- `storyboard` -- path to the YAML file.
- `--strict` -- warnings count as errors.
- `--json` -- `{ok, errors[], warnings[], planned_seconds{video: s}}`.

## Example

```bash
teaserkit validate examples/demo-app/storyboard.yaml
```

## Result

One line per problem (`SEVERITY rule where: message`), then planned seconds per video, then
`OK` or `FAILED`.

## Failures

Exit 5 on any error (or any warning with `--strict`), and on schema problems.
