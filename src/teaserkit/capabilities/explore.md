**Model-backed.** Finds the steps for one beat by trying them in a real headless browser. Each
turn the model sees a screenshot and the visible interactive elements (with CSS-pixel boxes),
proposes one declarative step, and teaserkit runs it; failures go back to the model. Only steps
that actually ran are returned, with a suggested ROI and caption, as a ready-to-paste beat.

The model can only choose declarative steps (click, type, press, scroll, hover, wait_for, goto,
done); it cannot run scripts. The browser context is fresh unless `--storage-state` is given.

## Arguments

- `--intent TEXT` -- required; what the beat should show.
- `--base-url URL` or `--storyboard SB` (uses its base_url, or serves its static site).
- `--start /path` (default `/`), `--max-steps 8`, `--storage-state F`.
- `--screenshots DIR` -- keep the screenshots the model saw.
- `--context-file F`, `--json`.

## Example

```bash
teaserkit explore --storyboard examples/demo-app/storyboard.yaml --start /board.html \
  --intent "open the details of the 'Order name badges' card"
```

## Result

A YAML beat (`steps`, `roi`, `caption`). JSON: `{steps, roi, roi_selector, caption, beat_yaml,
transcript, final_screenshot}`.

## Failures

Exit 3 without a provider (checked before the browser starts); exit 1 if the goal was not
reached in `--max-steps` (the steps that ran are in the error details); exit 4 if Chromium or
the `ai` extra is missing.
