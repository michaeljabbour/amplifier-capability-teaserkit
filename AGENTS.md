# AGENTS.md

Guidance for coding agents using or changing teaserkit.

## Using it

1. `teaserkit --help` first (the full guide), then `teaserkit <capability> --help` before calling
   a capability. Do not call from memory.
2. Prefer the library when chaining steps: `import teaserkit as tk; sb = tk.load_storyboard(p);
   tk.validate(sb); tk.build(sb, out)`. Results are typed values; CLI text is for people.
3. Pass `--json` when a result feeds code. Results are on stdout, progress on stderr. A non-zero
   exit is a failure; the message names the remedy. Act on it or relay it verbatim.
4. `plan`, `explore` and `review` are model-backed (cost tokens, may vary between runs). Without
   a provider they exit 3; configure it or report it, do not do their work yourself silently.
5. Always look at the contact sheets (`out/sheets/*.png`) before calling a video done, and run
   `validate` before `record`.
6. Film fictional demo data only. Put every real name and internal string that could appear on
   screen into `project.deny_list`.

## Layout

```
smart-tool.json                 descriptor: manifest path, CLI argv, deterministic smoke
src/teaserkit/
  SMART_TOOL.md                 the one manifest (frontmatter + the guide --help prints)
  capabilities/<name>.md        one guide per capability (<name> --help)
  _manifest.py                  manifest(), skill(), capability_skill(), CAPABILITIES table
  storyboard.py                 YAML schema -> dataclasses (Storyboard, Beat, Keyframe, ...)
  rules.py                      style checks (validate)
  recorder.py                   Playwright + CDP screencast recorder, cursor, leak scan
  graphics.py                   HTML -> PNG captions, chrome, cards
  compose.py                    retiming, ROI fitting, eased camera, crossfades, ffmpeg pipe
  music.py, finishing.py, sheets.py, pipeline.py, project.py, serve.py, prereqs.py, paths.py
  planner.py, explorer.py, reviewer.py, _provider.py    AI capabilities (anthropic SDK, optional extra)
  cli.py                        argparse wrapper only
examples/demo-app/              fictional static app + storyboard used by the e2e test
scripts/check-generic.sh        deny-list check over files and git history
```

## Changing it

- **Capability lives in the library.** The CLI parses arguments and prints; if you need logic
  in `cli.py`, move it into a module and call it.
- **New capability:** add the function, a row in `_manifest.CAPABILITIES` (name, deterministic or
  model-backed, summary), `capabilities/<name>.md` (arguments, example, result, failures), a
  subparser in `cli.py`, a lazy export in `__init__.py`, and tests.
- **New step kind:** `storyboard.STEP_KINDS` + `_parse_step`, `recorder._Actor.step`, the
  `explorer` action list if the model should use it, `capabilities/record.md`.
- **New style rule:** default in `style.DEFAULT_STYLE`, check in `rules.py` (error for hard
  rules, warning for taste), a test, and a line in `capabilities/validate.md` and docs/GUIDE.md.
- **Deterministic paths never import the AI SDK.** Import `_provider` lazily inside AI functions;
  `import teaserkit` must work without `anthropic` installed and without credentials.
- **Files:** artifacts only where the caller asks; work files under the user cache directory
  (`paths.py`); scratch in the temp directory; never beside the package.
- **Version:** bump `version` in `pyproject.toml`, `__version__` in `src/teaserkit/__init__.py` and
  `version:` in `SMART_TOOL.md` together (a test enforces it). Update `platforms:` only for systems you have
  actually run the demo build on.
- **Tests:** `.venv/bin/pytest`; `TEASERKIT_E2E=1 .venv/bin/pytest -m e2e` for a real film + render.

## Open-source hygiene (enforced)

- No personal data or references to any particular company, product or person other than the
  fictional demo: no real names, no email addresses (only `example.com`-style placeholders), no
  home-directory paths, no internal codenames. `scripts/check-generic.sh` scans every file and
  the git history (authors, committers, messages) and runs in the test suite. It always checks
  paths and email addresses; names and codenames you must never publish go one per line in
  `.check-generic.local`, which is gitignored so the list itself stays private. The project's
  own GitHub URL is the one allowed exception.
- Commit with the repository-local neutral identity (`git config user.name teaserkit`,
  `git config user.email noreply@example.com`), never a personal one.
- Never commit recordings or renders (`*.mp4`, `*.wav` are ignored) or screenshots of real products.

## Market research upkeep

Local-only market research lives in `.research/market/` (gitignored; never commit it).

At session start, check `.research/market/last_updated`:
- If the file is missing, seed it from authorized local market research for this repository, retaining source URLs and retrieval dates, or start fresh. Do not invent a review or copy private working content into public files.
- If it is older than 30 days, or before any positioning, launch or naming work, refresh it with cited primary sources (URL + retrieved date).
- Keep it local. Never commit it and never copy private research into public docs.
- Log every change in `.research/market/CHANGELOG.md`.

## Capability identity

Public capability identity: `amplifier-capability-teaserkit`. Preserve the existing portable method folder, native interfaces and legacy installation routes across the approved repository rename.
