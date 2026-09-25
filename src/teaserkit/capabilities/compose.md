Composites the recorded takes and graphics into one silent MP4 per video per aspect.
Deterministic. Renders any missing graphics first.

For each beat: cut the take at the recorder's marks; retime to the planned duration (the action
plays up to `max_speedup` times real speed, the result hold plays at real speed and freezes on
the last frame if the beat outlasts the footage); fit a crop of the aspect's panel shape around
the ROI (at least `min_crop` of the recording wide, padded by `roi_pad`) and ease between
keyframes over `move` seconds; overlay the caption with a short fade. Segments (title card,
beats, end card) crossfade for `crossfade_seconds`. Frames are piped to ffmpeg (H.264,
yuv420p, 30 fps, fast-start).

## Arguments

- `storyboard`, `--work DIR`, `--video ID`, `--aspect A` (repeatable)
- `--preview` -- half resolution and a fast encode, for checking framing.
- `--json` -- `{renders: [{video, aspect, path, seconds, timeline: [{id, start, seconds}]}]}`.

## Example

```bash
teaserkit compose examples/demo-app/storyboard.yaml --aspect 9x16 --preview
```

## Result

`<work>/silent/<video>-<aspect>[-preview].mp4` and its length.

## Failures

Exit 1 `recording_failed` if a take was not recorded yet; `render_failed` if ffmpeg fails.
