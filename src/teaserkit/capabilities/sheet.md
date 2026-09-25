Contact sheets for checking a render by eye: one frame every N seconds, each stamped with its
time, tiled into one PNG. With `--grid`, overlays a CSS-pixel grid on frames of a raw take
instead, so ROIs can be read straight off the picture. Deterministic.

## Arguments

- `video` -- a finished video, or a raw take for `--grid`.
- `--out FILE.png` -- required.
- `--every 2` and `--cols 6` -- contact sheet spacing and layout.
- `--grid --times 1,4.5 [--viewport-width 1440]` -- ROI grid mode.
- `--json`

## Example

```bash
teaserkit sheet /tmp/teaserkit-demo/acme-teaser-16x9.mp4 --out /tmp/sheet.png --every 2
```

## Result

The PNG path and the number of frames.

## Failures

Exit 1 if the video cannot be read.
