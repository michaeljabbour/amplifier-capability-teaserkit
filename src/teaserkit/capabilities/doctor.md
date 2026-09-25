Checks the prerequisites and says how to fix each missing one: ffmpeg and ffprobe on PATH,
Playwright's Chromium, and (optional) the AI extra plus credentials. Deterministic; it launches
nothing and changes nothing.

## Arguments

- `--json` -- the report as JSON.

## Example

```bash
teaserkit doctor
```

## Result

One line per prerequisite (`ok` or `MISSING` with the remedy). JSON:
`{ffmpeg: {ok, path|remedy}, ffprobe: {...}, chromium: {...}, ai: {ok, sdk_installed, credentials, model}}`.

## Failures

Exit 4 when ffmpeg, ffprobe or Chromium is missing. A missing AI provider does not fail doctor,
since only plan, explore and review need it.
