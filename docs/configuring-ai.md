# Configuring the AI capabilities

`plan`, `explore` and `review` call Anthropic's API. Everything else, including a full
`build`, runs without any provider.

1. Install the extra: `uv tool install 'teaserkit[ai] @ git+https://github.com/michaeljabbour/teaserkit'`
   (or `pip install -e '.[ai]'` in a checkout).
2. Provide credentials, one of:
   - `export ANTHROPIC_API_KEY=...`
   - `ant auth login` (the Anthropic CLI stores a profile the SDK picks up)
3. Optional: `export TEASERKIT_MODEL=<model id>` (default `claude-sonnet-5`).

`teaserkit doctor` reports whether the SDK and credentials are present.

## What each capability sends

- `plan`: your description, feature list and optional context file.
- `explore`: screenshots of the pages it visits and a list of visible elements, one step at a
  time. It drives a fresh headless browser context; it only receives a signed-in session if you
  pass `--storage-state`. The model can only choose declarative steps.
- `review`: sampled frames (JPEG, about 1024 px wide) or the images you pass, plus the deny list.

Without credentials each of these fails immediately with exit code 3 and says what to set; none
of them falls back to a lesser non-AI answer.
