Prints the tool's manifest: name, version, description, use cases, platforms, prerequisites, and
the capability list with which ones need an AI provider. Deterministic; reads the copy of
SMART_TOOL.md shipped in the package, so it answers the same way wherever teaserkit is installed.

## Arguments

- `--json` -- JSON on stdout (the default output is already JSON unless `--body` is given alone).
- `--body` -- also include the Markdown guide (`body`); without `--json`, print only the guide.

## Example

```bash
teaserkit manifest --json | jq '.version, [.capabilities[] | select(.needs_ai_provider) | .name]'
```

## Result

`{smart_tool_format, name, version, description, use_cases, platforms, requires, capabilities[, body]}`.
Library: `teaserkit.manifest()` returns the frontmatter fields plus `body`.

## Failures

None in practice; exit 0.
