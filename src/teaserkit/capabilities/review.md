**Model-backed.** Reviews rendered frames with a vision model before publishing. Samples one
frame every `--every` seconds from each video (at most `--max-frames` per video), or takes still
images and contact sheets as given, and asks for structured findings in these categories:
`deny_list`, `real_person`, `personal_data`, `error_message`, `loading_state`,
`placeholder_text`, `broken_layout`, `other`, each rated high / medium / low.

Recording already scans the page text for deny-listed strings; review catches what only shows in
pixels (text inside images or canvas, clipped captions, spinners held on screen).

## Arguments

- `inputs...` -- videos and/or images.
- `--deny TERM` (repeatable), `--storyboard SB` (adds its deny list).
- `--every 2`, `--max-frames 24`.
- `--fail-on high|medium|low|never` (default high).
- `--context-file F`, `--json`.

## Example

```bash
teaserkit review /tmp/teaserkit-demo/acme-teaser-16x9.mp4 --storyboard examples/demo-app/storyboard.yaml --json
```

## Result

One line per finding plus a summary. JSON: `{ok, findings: [{frame, severity, category,
description, evidence}], summary, frames_reviewed, fail_on}`.

## Failures

Exit 7 when any finding is at or above `--fail-on`; exit 3 without a provider; exit 4 without
the `ai` extra.
