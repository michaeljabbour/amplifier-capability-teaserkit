Scaffolds a new teaser project directory with a commented `storyboard.yaml` and `brand.yaml`.
Deterministic. Never overwrites existing files unless `--force`.

## Arguments

- `directory` -- where to write (created if missing).
- `--name` -- product name to put in the templates (default "My Product").
- `--force` -- overwrite existing files.
- `--json` -- `{directory, files, next}` as JSON.

## Example

```bash
teaserkit init teasers/acme --name "Acme Planner"
```

## Result

The paths written and the next commands to run.

## Failures

Exit 1 with `project_exists` if a file is already there (pass `--force` or pick another directory).
