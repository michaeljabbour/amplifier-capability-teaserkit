Films the raw takes. Deterministic (no model), but it drives a real browser, so it depends on
the app behaving the same way each time.

For each take: a fresh headless Chromium context at the project viewport (1440x810 CSS px by
default) and pixel density (2x), a fake cursor with click ripples, and the DevTools screencast.
Leading `goto` steps of the first beat run before filming starts so the take opens on a loaded
page. Beats run in order; the recorder marks each beat's start, the start of its result hold,
and its end, and records the on-screen box of every ROI selector. After every step the visible
text (plus input values and the page title) is scanned for deny-listed strings.

Steps: `goto` (path or URL), `click` / `hover` / `wait_for` (locator), `type` (`text`, `delay`,
optional `into` locator), `press` (key), `scroll` (`dy`, `ms`), `hold` (seconds), `move` (`x`,
`y`, `ms`). Locators: a string (visible text), or one of `{text}`, `{role, name}`, `{label}`,
`{placeholder}`, `{selector}`, each with optional `exact` and `nth`. `${env:NAME}` in any
string is read from the environment at run time.

Auth: `none`; `storage_state` (`path` to a saved session JSON); `script` (`steps` run in the
same context before filming, never recorded). `project.serve` serves a static directory on a
local port for the duration of the recording.

## Arguments

- `storyboard`
- `--take NAME` -- only this take (repeatable); default all.
- `--work DIR` -- work directory (default: per-storyboard under the user cache directory).
- `--json` -- `{work_dir, takes: [{take, video, marks, frames, seconds}]}`.

## Example

```bash
teaserkit record examples/demo-app/storyboard.yaml --take tour
```

## Result

`<work>/raw/<take>.mp4` (30 fps H.264 at viewport x density) and `<take>.json` (marks, boxes).

## Failures

- Exit 5: the storyboard breaks a style rule (checked first).
- Exit 6 `leak_detected`: a deny-listed string was on screen; names the beat, step and string.
- Exit 1 `recording_failed`: a step failed (locator not found, timeout); names beat and step.
- Exit 4 `missing_prerequisite`: Chromium (`playwright install chromium`) or ffmpeg is absent.
