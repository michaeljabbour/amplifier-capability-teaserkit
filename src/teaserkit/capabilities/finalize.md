Finishes the silent renders: muxes each video's soundtrack as AAC 192k with ffmpeg `loudnorm`
(I=-18 LUFS, TP=-2 dB, LRA=7 by default), adds fast-start for web playback, writes a no-audio
copy (main videos by default; `outputs.no_audio: all|main|none`) and a poster PNG
(`poster_at` per video, else 40% in). Deterministic.

## Arguments

- `storyboard`, `--work DIR`, `--video ID`, `--aspect A`
- `--out DIR` -- required; where the finished files go.
- `--json`

## Example

```bash
teaserkit finalize examples/demo-app/storyboard.yaml --out /tmp/teaserkit-demo
```

## Result

`<out>/<video>-<aspect>.mp4`, `-no-audio.mp4`, `-poster.png`.

## Failures

Exit 1 if a silent render or soundtrack is missing (run `compose`, then `music`).
