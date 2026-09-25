Runs the whole deterministic pipeline: validate, record, captions, compose (every video x
aspect), music, finalize, contact sheets, and a storyboard timing table. No model provider is
involved at any point.

## Arguments

- `storyboard`
- `--out DIR` -- required; finished videos, posters, sheets, `build.json`, `STORYBOARD.md`.
- `--work DIR` -- work directory (default: per-storyboard under the user cache directory).
- `--video ID`, `--aspect A` -- limit the set (repeatable).
- `--preview` -- half-resolution renders.
- `--skip-record` -- reuse the takes already recorded (after editing captions or ROIs).
- `--json` -- the full summary (also written to `<out>/build.json`).

## Example

```bash
teaserkit build examples/demo-app/storyboard.yaml --out /tmp/teaserkit-demo
```

## Result

For every video and aspect: the MP4 with its ffprobe summary (length, codec, size, fps), the
no-audio copy, the poster and the contact sheet; plus the work directory and elapsed time.

## Failures

Same as the individual steps: exit 5 style violation (before filming), 6 leak detected, 4
missing prerequisite, 1 recording or render failure. Partial results are not reported as
success; files already written stay in `--out` and the work directory.
