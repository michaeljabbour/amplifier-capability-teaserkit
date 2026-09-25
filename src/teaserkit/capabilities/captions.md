Renders every graphic the chosen videos need, per aspect, as transparent PNGs: caption plates,
frame chrome (the brand band and caption band for 9:16 and 1:1), title cards and end cards.
Deterministic. Designed as HTML with the storyboard's brand (fonts, colors, logo or wordmark)
and rendered by headless Chromium. Files are content-addressed, so unchanged graphics are reused.

## Arguments

- `storyboard`, `--work DIR`
- `--video ID`, `--aspect 16x9|9x16|1x1` -- limit the set (repeatable).
- `--force` -- re-render even if the PNG exists.
- `--json` -- `{gfx_dir, files[]}`.

## Example

```bash
teaserkit captions examples/demo-app/storyboard.yaml --aspect 9x16
```

## Result

PNG paths under `<work>/gfx/`.

## Failures

Exit 4 if Chromium is missing; exit 5 if the storyboard is invalid.
