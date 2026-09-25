# teaserkit: status

Version 0.1.0. First complete scaffold. The deterministic pipeline runs end to end, and the three
AI capabilities have each been exercised once against the real API.

## What it is

teaserkit turns a live web app into short product teaser videos. It films scripted clicks and
typing in headless Chromium, then adds eased camera moves, captions, title and end cards and an
original synthesized soundtrack. It exports 16:9, 9:16 and 1:1 MP4s with posters, no-audio
copies, contact sheets and a storyboard timing table.

It follows the Amplifier Smart Tools format:

- `smart-tool.json` at the root: `{"manifest": "src/teaserkit/SMART_TOOL.md", "cli_argv": ["teaserkit"], "deterministic_smoke": ["manifest"]}`.
- `src/teaserkit/SMART_TOOL.md` is the one manifest. Its frontmatter has `smart_tool_format`,
  name, version, description, use_cases, `platforms: [macos]` and `requires` (ffmpeg,
  playwright-chromium, and an optional anthropic-provider). Its body is the guide that `--help`
  prints.
- The library holds every capability. `cli.py` only parses arguments and prints results.
  `teaserkit.manifest()` reads the copy of the manifest shipped in the package.
- `teaserkit -h` prints a terse list. `teaserkit --help` prints the full guide (a
  `<skill_content>` block). `teaserkit <capability> --help` prints one capability's guide from
  `src/teaserkit/capabilities/<name>.md`. `teaserkit manifest --json` prints identity plus the
  capability list, with `needs_ai_provider` on each entry.

## Repository layout

```
smart-tool.json  pyproject.toml  README.md  AGENTS.md  LICENSE  .gitignore
docs/            GUIDE.md (production guide), STATUS.md, images/, installing-ffmpeg.md, installing-playwright.md, configuring-ai.md
examples/demo-app/  site/ (fictional "Acme Planner" static app), storyboard.yaml, brand.yaml, logo.svg
scripts/         check-generic.sh + check_generic.py (deny-list check over files and git history)
src/teaserkit/   SMART_TOOL.md, capabilities/*.md, templates/*.yaml, and the modules:
                 _manifest, storyboard, rules, recorder, graphics, compose, music, finishing, sheets,
                 pipeline, project, serve, prereqs, paths, style, errors, cli,
                 planner, explorer, reviewer, _provider (AI)
tests/           test_validate, test_manifest, test_generic, test_music, test_compose, test_cli (+ opt-in e2e)
```

## Capabilities

| Capability | Kind | Status |
|---|---|---|
| manifest | deterministic | working |
| doctor | deterministic | working |
| init | deterministic | working. The template storyboard validates cleanly. |
| validate | deterministic | working: 11 rules, strict mode, exact planned lengths |
| record | deterministic | working: CDP screencast at 2x, cursor and ripple, per-beat marks, selector boxes, DOM deny-list scan, env interpolation, static `serve`, auth none/storage_state/script |
| captions | deterministic | working: HTML to transparent PNG, brand colors, logo or wordmark, embedded font files |
| compose | deterministic | working: retiming, ROI fit per aspect, eased keyframes, crossfades, caption fades, preview mode |
| music | deterministic | working: deterministic, duration-exact, three progressions |
| finalize | deterministic | working: AAC 192k, loudnorm (-18 LUFS measured), faststart, no-audio copy, poster |
| sheet | deterministic | working: timestamped contact sheets, CSS-pixel ROI grid |
| build | deterministic | working end to end. Writes build.json and STORYBOARD.md. |
| plan | AI | working. Ran once: a valid clip draft on attempt 2, with validate-and-repair loop. |
| explore | AI | working, minimal. Ran once on the demo and reached the goal in 2 steps. |
| review | AI | working, minimal. Ran once on the demo: 2 findings, and the prompt was tuned afterwards. |

The AI capabilities use Anthropic's API through the optional `[ai]` extra. The default model is
`claude-sonnet-5`, overridable with `TEASERKIT_MODEL`. They return structured JSON via
`output_config.format`. Without a provider they fail immediately with exit 3 (or exit 4 if the
SDK is missing).

## Install and run

```bash
cd teaserkit
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e '.[ai,dev]'
.venv/bin/playwright install chromium          # browser; teaserkit never installs it itself
brew install ffmpeg                            # or apt install ffmpeg
.venv/bin/teaserkit doctor
.venv/bin/teaserkit validate examples/demo-app/storyboard.yaml
.venv/bin/teaserkit build examples/demo-app/storyboard.yaml --out /tmp/teaserkit-demo
```

Demo build result (macOS, Apple silicon): about 2.5 minutes. It produced `acme-teaser-{16x9,9x16,1x1}.mp4`
(H.264 30 fps + AAC, 35.2 s each, 1920x1080 / 1080x1920 / 1080x1080), the matching
`-no-audio.mp4` and `-poster.png`, `sheets/*.png`, `STORYBOARD.md` and `build.json`. Integrated
loudness measured -18.0 LUFS.

## Check results

- **Tests:** `.venv/bin/pytest`: 41 passed, 1 skipped. The skipped one is the opt-in e2e test;
  `TEASERKIT_E2E=1 .venv/bin/pytest -m e2e` passed too (it films and renders the demo, about 1 minute).
- **Smart Tools conformance kit** (run from its spec repository against this root, with the CLI
  on PATH): 16 pass, 0 fail, 0 skip. VERDICT: PASS.
- **Deny-list check:** `scripts/check-generic.sh` reported 0 findings. It scans every tracked and
  untracked file plus the git log (authors, committers, messages).

## Known issues and limitations

- `platforms` lists macOS only, because the demo build has only been run there. Linux should
  work (Playwright, ffmpeg and OpenCV all support it) but has not been run, so it is not listed.
- Wide layouts clip in 9:16: a vertical crop of a 1440 px page can show only about 580 CSS px.
  Give vertical beats narrower `roi_per_aspect` targets.
- `compose` centres every crop on its ROI. When the aspect ratio or the 16:9 minimum crop needs a
  wider box than the ROI, the extra width is added evenly on both sides and can pull in
  neighbouring UI. The demo works around this with explicit boxes; an anchor option (keep the
  ROI's top-left, or its heading, in frame) would fix it in the library.
- In the demo's Insights beat, the summary line under the chart is wider than a 9:16 or 1:1 crop
  can hold, so it shows part-way through the pan before the crop settles on the chart.
- Compose runs single-threaded, frame by frame in Python: about one CPU-minute per 35 s
  aspect on this machine. Rendering aspects in parallel is an easy win.
- The DOM deny-list scan sees text only, not text inside images or canvas. `review` and the
  contact sheets cover that.
- `explore` and `review` have been run once each. They need more real-world testing (sign-in
  flows, long pages, `max_steps` exhaustion).
- Nobody has listened to the synthesized music. It is checked only for length and loudness.
- There is no MCP server or other optional surface. The spec does not require one.

## Next, in priority order

1. Run the demo build and tests on Linux, then add `linux` to `platforms`.
2. Render aspects in parallel (a process per aspect) to cut build time.
3. Add a crop anchor option to `compose`, and a 60-90 s `main` example video.
4. Add an `auth` walkthrough doc plus a helper to save a storage-state file from a one-off
   sign-in (explicitly run by the user, never automatic).
5. `review`: add an optional deterministic OCR pass (no model) for deny-listed strings in pixels.
6. `explore`: verify the proposed ROI by re-rendering a still with the crop, and support
   continuing from an existing take's state.
7. Optional: an Agent Skill file (`skills/teaserkit/SKILL.md`) for hosts that discover skills,
   and an MCP adapter.
8. Publish to PyPI.

## Rules for contributors

- The project is open source. It must contain no personal data and no references to any real
  company, product or person other than the fictional demo: no real names, no email addresses
  beyond `example.com`-style placeholders, no home-directory paths, no internal codenames.
  `scripts/check-generic.sh` enforces this over files and git history and runs in the tests.
- Commit with the repository-local neutral identity only: `git config user.name teaserkit`,
  `git config user.email noreply@example.com`.
- The repository is public at https://github.com/michaeljabbour/teaserkit. Changes land through
  pull requests.
- Keep the Smart Tools shape: capabilities live in the library, the CLI stays thin, there is one
  manifest, and its version stays in sync with `pyproject.toml` and `__init__.py` (tests enforce
  both). Run the conformance kit after changing the manifest, descriptor or CLI.
- Never commit recordings, renders or screenshots of real products. `*.mp4` and `*.wav` are
  ignored.
