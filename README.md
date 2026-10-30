# TeaserKit

Change the interface. Re-shoot the same story.

Watch the [71-second film](https://michaeljabbour.github.io/amplifier-smart-tool-teaserkit/#film): one moved button, and how a written storyboard re-shoots all three versions. The example in it is fictional.

For people producing repeatable product videos of web apps. TeaserKit writes the clicks, framing, captions and timing into a storyboard, then builds landscape, vertical and square outputs from that shared source.

[Explore the site](https://michaeljabbour.github.io/amplifier-smart-tool-teaserkit/)

## What you get

- **Keep the edit repeatable.** Update a beat after the UI changes instead of reconstructing the entire capture by hand.
- **Frame each shape deliberately.** Give vertical and square their own regions of interest rather than relying on a crop of the landscape edit.
- **Review the whole output.** Use validation, contact sheets, posters and build records to inspect timing, framing and accidental leaks.

## Start here

```sh
git clone https://github.com/michaeljabbour/amplifier-smart-tool-teaserkit.git
cd amplifier-smart-tool-teaserkit
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/teaserkit --help
```

The package is installed into the project virtual environment. The native guide below explains configuration and actual operations. Start by inspecting help; no provider or GitHub operation is needed to do that.

## What you need

- The quickstart uses macOS/Linux virtual-environment paths. On Windows, use the corresponding `.venv\Scripts` executables.
- Python 3.11+, ffmpeg and Playwright Chromium are required for a full build.
- The deterministic library/CLI works without an AI provider. Optional plan, explore and review use the separately configured ai extra.
- Install the package first, inspect teaserkit doctor, then install any missing browser or renderer prerequisites deliberately.

## Evidence and limits

Deterministic and mocked checks plus installed storyboard validation passed. The full capture/render end-to-end check is separate; this update generated no new video.

The worked examples on the site are fictional. They illustrate the output and decisions; they are not user results or measured benefit. See [consolidation and runtime boundaries](docs/CONSOLIDATION.md) for retained interfaces and acceptance scope.

---

## Retained native guide

### teaserkit

Turn a live web app into short product teaser videos.

teaserkit films scripted clicks and typing in headless Chromium, then adds slow eased camera
moves, captions, title and end cards and an original synthesized soundtrack. One storyboard
produces landscape, vertical and square MP4s, each with a poster, a no-audio copy and a contact
sheet.

![A few seconds of the demo teaser: a task is typed, added and ticked off](docs/images/hero.gif)

<sub>Rendered from [`examples/demo-app`](examples/demo-app), a fictional app included in this
repository.</sub>

## Why

Product videos go stale every time the UI changes, and re-recording by hand is slow and
inconsistent. With teaserkit the video is a YAML file: the clicks, the framing, the captions and
the timing are all written down, so a re-shoot after a UI change is one command, and every
shape stays in sync.

## One storyboard, three shapes

![Frames from the demo teaser at 16:9, 9:16 and 1:1](docs/images/shapes.png)

Each beat can set its own framing per aspect ratio, so the vertical cut is framed for vertical
rather than cropped from the landscape one.

## Install

teaserkit needs Python 3.11+, [ffmpeg](docs/installing-ffmpeg.md) and Playwright's
[Chromium](docs/installing-playwright.md).

```bash
uv tool install "teaserkit[ai] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-teaserkit"
uv tool run --from teaserkit playwright install chromium
brew install ffmpeg            # or: sudo apt install ffmpeg
teaserkit doctor
```

Drop `[ai]` if you only want the deterministic pipeline. It runs with no model provider and no
network access beyond the app being filmed.

## Quickstart

Build the included demo:

```bash
git clone https://github.com/michaeljabbour/amplifier-smart-tool-teaserkit
cd amplifier-smart-tool-teaserkit
teaserkit validate examples/demo-app/storyboard.yaml
teaserkit build examples/demo-app/storyboard.yaml --out /tmp/teaserkit-demo
```

A full build writes outputs like these; elapsed time depends on the machine and app:

```
acme-teaser-16x9.mp4   acme-teaser-9x16.mp4   acme-teaser-1x1.mp4     1920x1080 / 1080x1920 / 1080x1080, 35 s
*-no-audio.mp4         *-poster.png           sheets/*.png            STORYBOARD.md   build.json
```

Start your own:

```bash
teaserkit init teasers/myapp --name "My App"
$EDITOR teasers/myapp/storyboard.yaml
teaserkit build teasers/myapp/storyboard.yaml --out teasers/myapp/out
```

## The storyboard

A beat is a few browser steps, a hold, a caption and a region of interest to frame:

```yaml
beats:
  - id: add-task
    take: tour
    steps:
      - click: {placeholder: "Add a task"}
      - type: {text: "Book the venue walkthrough", delay: 45}
      - press: Enter
    hold: 1.8
    duration: 6
    caption: Add a task in seconds
    roi: {selector: "#today-card", pad: 20}

videos:
  - id: acme-teaser
    kind: clip
    title: {title: Acme Planner, sub: Plan the week without the busywork.}
    beats: [today, add-task, complete, board, card, insights]
```

`validate` checks it against the house style before anything is filmed: short captions held
long enough to read, a few calm cuts rather than many fast ones, and planned lengths that fit
the video kind. Every build writes contact sheets, so you can review the whole edit at a
glance:

![Contact sheet of the 16:9 demo teaser](docs/images/contact-sheet.png)

[docs/GUIDE.md](docs/GUIDE.md) is the production guide. `teaserkit --help` and
`teaserkit <capability> --help` cover every field and step kind.

## How it works

![Pipeline: storyboard, validate, record, captions, compose and music, finalize, outputs](docs/images/pipeline.svg)

| Capability | Kind | What it does |
|---|---|---|
| `manifest` | deterministic | Identity, platforms, prerequisites and capabilities as JSON |
| `doctor` | deterministic | Checks ffmpeg, Chromium and the optional AI provider |
| `init` | deterministic | Scaffolds `storyboard.yaml` and `brand.yaml` |
| `validate` | deterministic | Style rules and planned lengths, before filming |
| `record` | deterministic | Films raw takes at 2x density, with an injected cursor and a leak scan |
| `captions` | deterministic | Renders captions, frame chrome and cards as transparent PNGs |
| `compose` | deterministic | Crops, eases and crossfades each aspect into a silent MP4 |
| `music` | deterministic | Synthesizes an original track exactly as long as the video |
| `finalize` | deterministic | Muxes audio at -18 LUFS; writes posters and no-audio copies |
| `sheet` | deterministic | Contact sheets, or a CSS-pixel grid over a raw take for picking crops |
| `build` | deterministic | The whole pipeline end to end |
| `plan` | AI | Drafts a storyboard that already passes `validate` |
| `explore` | AI | Drives the live app to find working steps, a crop and a caption for one beat |
| `review` | AI | Flags leaked names, errors, spinners and broken layouts in rendered frames |

The AI capabilities use Anthropic's API through the `ai` extra (`ANTHROPIC_API_KEY`; see
[docs/configuring-ai.md](docs/configuring-ai.md)). Without a provider they exit with code 3
and a message naming the fix. They never fall back to guessing.

## Watch it build its own teaser

![An Amplifier agent asked to make a teaser of this app with teaserkit](docs/images/teaser.gif)

Asked for nothing but "make a teaser of this app with teaserkit," an [Amplifier](https://github.com/microsoft/amplifier)
agent finds the CLI through its own `--help`, builds the video, and gets a working result.
[Watch the full clip](https://github.com/michaeljabbour/amplifier-smart-tool-teaserkit/releases/tag/v0.1.1) (28s,
with sound), or reproduce it yourself: [`examples/self-teaser`](examples/self-teaser).

## Use it from an agent

teaserkit is an [Amplifier Smart Tool](https://github.com/microsoft/amplifier-smart-tools): a
library with a thin CLI that describes itself, so any agent or harness that can run a command
can discover and drive it without a custom integration.

```bash
teaserkit -h                # terse capability list
teaserkit --help            # the full guide, written for an agent
teaserkit build --help      # one capability: arguments, result, failures
teaserkit manifest --json   # machine-readable identity and capabilities
```

Pass `--json` to any capability for structured results on stdout. Progress goes to stderr.
A non-zero exit is a failure, and its message names the remedy. The manifest lives at
[`src/teaserkit/SMART_TOOL.md`](src/teaserkit/SMART_TOOL.md) and the descriptor at
[`smart-tool.json`](smart-tool.json). The repository passes the Smart Tools conformance kit
(16/16 rules).

From Python, the same capabilities return typed values:

```python
import teaserkit as tk

sb = tk.load_storyboard("examples/demo-app/storyboard.yaml")
print(tk.validate(sb).text())
result = tk.build(sb, "/tmp/teaserkit-demo")
```

## Privacy

Film fictional demo data. Every string that must never appear on screen, such as real names,
internal domains or codenames, goes in the storyboard's `deny_list`. `record` scans the visible
page text after every step and stops if one appears, and `review` checks the rendered frames,
including text inside images.

## Status

Version 0.1.0. The full pipeline has been run on macOS (Apple silicon); Linux should work (Playwright,
ffmpeg and OpenCV all support it) but has not been run yet. Known limitations and next steps are in [docs/STATUS.md](docs/STATUS.md).

## Development

```bash
uv venv && uv pip install -e '.[ai,dev]'
.venv/bin/playwright install chromium
.venv/bin/pytest                          # unit tests and the privacy check
TEASERKIT_E2E=1 .venv/bin/pytest -m e2e   # films and renders the demo
```

[AGENTS.md](AGENTS.md) explains how capabilities, step kinds and style rules are added.
Contributions must keep the repository free of personal and company-specific data;
`scripts/check-generic.sh` enforces this over files and git history.

## License

[MIT](LICENSE)

## Repository migration

This repository was renamed from `amplifier-smart-tool-teaserkit` to `amplifier-capability-teaserkit`. Existing installed method names, bundle aliases and native interfaces stay the same. See the [migration guide](https://michaeljabbour.github.io/migration/) and [repository map](https://michaeljabbour.github.io/migration/mapping.json) for source URL updates.
