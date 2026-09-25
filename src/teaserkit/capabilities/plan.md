**Model-backed.** Drafts a storyboard from a product description and an ordered feature list.
The draft is parsed and validated in strict mode (warnings count as errors); failures are sent
back to the model to fix, up to `--attempts` times. Only a draft that passes is returned. It
costs tokens and may differ between runs.

Selectors and exact labels in the draft are guesses from the description; the `notes` field
lists what to verify. `explore` can then find working steps for each beat against the real app.

## Arguments

- `--description TEXT` or `--description-file F` -- what the product does.
- `--feature TEXT` (repeatable) or `--features-file F` -- features to show, in order.
- `--name`, `--base-url`, `--kind main|clip|free` (default main).
- `--context-file F` -- extra material (page text, notes) passed to the model verbatim.
- `--attempts 3`, `--out FILE.yaml`, `--json`.

## Example

```bash
teaserkit plan --name "Acme Planner" --description "A weekly planner for small teams" \
  --feature "add a task" --feature "tick it off" --feature "board view" --kind clip --out draft.yaml
```

## Result

The storyboard YAML (or its path with `--out`), notes, attempts used, and the validation
report. JSON: `{storyboard_yaml, notes, attempts, report[, path]}`.

## Failures

- Exit 3 `no_provider`: set ANTHROPIC_API_KEY (or `ant auth login`).
- Exit 4 `missing_prerequisite`: install the `ai` extra.
- Exit 5 `style_violation`: no draft passed; the last draft and problems are in the error details.
