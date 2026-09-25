---
smart_tool_format: 1
name: teaserkit
version: 0.1.0
description: >
  Makes short product teaser videos from a live web app: it films scripted clicks and typing in
  headless Chromium, adds slow eased camera moves, captions, title and end cards, and an
  original synthesized soundtrack, and exports 16:9, 9:16 and 1:1 MP4s with posters. Reach for
  it for "make a teaser / demo video / feature clip of our app" or "re-shoot one beat after a
  UI change". AI capabilities draft a storyboard, find the clicks for a beat, and review frames
  for leaks. Not for voiceover, stock footage, live-action or generated video.
use_cases:
  - Turn a running web app into a 60-90 second teaser and 30-40 second feature clips
  - Export the same edit as landscape, vertical and square videos with posters
  - Re-shoot a single beat after the UI changes without redoing the whole video
  - Draft a storyboard that already follows a calm, readable house style
  - Check every frame for real names, internal strings, errors and spinners before publishing
platforms:
  - macos
requires:
  - name: ffmpeg
    purpose: Encodes takes and renders, muxes the soundtrack, normalizes loudness and grabs posters.
    install: docs/installing-ffmpeg.md
  - name: playwright-chromium
    purpose: >
      The headless browser that films the app and renders captions and cards. Installed with
      `playwright install chromium` in the environment teaserkit runs in; teaserkit never
      installs it itself.
    install: docs/installing-playwright.md
  - name: anthropic-provider
    purpose: >
      Credentials for Anthropic's API (ANTHROPIC_API_KEY or an `ant auth login` profile) plus
      the `ai` extra. Only plan, explore and review use it; without it those three fail and say
      so, and every deterministic capability, including a full build, keeps working.
    optional: true
    install: docs/configuring-ai.md
---

teaserkit is a library with a thin CLI. `teaserkit` (the Python package) does all the work;
the `teaserkit` command parses arguments and prints what the library returns. To chain steps,
import the library and call its functions (results are typed values), rather than piping CLI
output from one command into the next.

## When to reach for it

- You have a web app running somewhere a headless browser can reach (a URL, or a static build
  on disk) and want a polished, captioned teaser of real screens, not a mock-up.
- You need the same edit in several shapes: 16:9 (1920x1080), 9:16 (1080x1920), 1:1 (1080x1080).
- The UI changed and one beat needs re-filming: edit that beat's steps, record its take, and
  re-compose; everything else is reused from the work directory.

## When not to

- Narrated explainers, talking heads, stock footage or AI-generated video. There is no
  voiceover and no text-to-speech.
- Apps that only run natively (desktop, mobile) or behind hardware tokens a headless browser
  cannot pass.
- Licensed music. The soundtrack is always synthesized from scratch; if you want a licensed
  track, use the no-audio exports and mix it elsewhere.

## Install

```bash
uv tool install 'teaserkit @ git+https://github.com/michaeljabbour/teaserkit'
uv tool install 'teaserkit[ai] @ git+https://github.com/michaeljabbour/teaserkit'   # adds plan / explore / review
uv tool run --from teaserkit playwright install chromium     # the browser, once per environment
teaserkit doctor                                             # confirms ffmpeg, Chromium, AI provider
```

ffmpeg must be on PATH (docs/installing-ffmpeg.md). AI capabilities read ANTHROPIC_API_KEY and
use `claude-sonnet-5` unless TEASERKIT_MODEL says otherwise (docs/configuring-ai.md).

## How a video is made

1. A **storyboard** (`storyboard.yaml`) names the app, the brand, and a list of **beats**. A beat
   is one feature: declarative steps (goto, click, type, press, scroll, hover, wait_for, hold,
   move), a hold on the result, a caption, a planned duration, and a region of interest (ROI).
2. `record` drives headless Chromium at 1440x810 CSS pixels and 2x density, films it through
   the DevTools screencast, draws a visible cursor with click ripples, and marks where each beat
   starts, where its result hold begins, and where it ends. Beats that share a `take` are filmed
   in one continuous session. Every step is followed by a scan of the visible text for
   deny-listed strings; a hit fails the take.
3. `captions` renders captions, frame chrome and title/end cards as transparent PNGs.
4. `compose` cuts each take at the marks, retimes each beat to its planned duration (action sped
   up if needed, result hold at real speed), fits a crop around the ROI for each aspect with
   eased moves, crossfades beats and overlays captions.
5. `music` synthesizes a duration-matched original track; `finalize` muxes it at -18 LUFS and
   writes posters and no-audio copies. `build` runs all of it.

## House style (defaults; override under `style:` in the storyboard)

- Captions: at most 7 words per line, at most 2 lines (caption + subtitle), readable at least 2.5 s.
- Each feature is held about 4-6 s; fewer cuts; rest at least 1 s on each result.
- Camera moves are slow eases (1.4 s default, 1.2 s minimum) with a settle before and after.
- Main videos run 60-90 s, clips 30-40 s. Crossfades are 0.5 s.
- Outputs: 16:9, 9:16 and 1:1, a poster per video, a no-audio copy of main videos.
- Original synthesized music only; no voiceover; fictional demo data only.
- `validate` checks all of this before anything is filmed, because planned durations make each
  video's length known in advance.

## Worked invocations

```bash
teaserkit init my-teaser --name "Acme Planner"         # storyboard.yaml + brand.yaml
teaserkit validate my-teaser/storyboard.yaml            # style rules, planned lengths
teaserkit build my-teaser/storyboard.yaml --out out     # record -> ... -> out/*.mp4
teaserkit record my-teaser/storyboard.yaml --take main  # re-film one take
teaserkit compose my-teaser/storyboard.yaml --aspect 9x16 --preview
teaserkit sheet out/teaser-16x9.mp4 --out sheet.png     # contact sheet for checking
teaserkit plan --name "Acme Planner" --description "A planner for small teams" \
  --feature "add a task" --feature "board view" --kind clip --out draft.yaml   # AI
teaserkit explore --base-url http://127.0.0.1:8000 --intent "open a card's details"  # AI
teaserkit review out/teaser-16x9.mp4 --storyboard my-teaser/storyboard.yaml         # AI
```

In Python:

```python
import teaserkit as tk
sb = tk.load_storyboard("my-teaser/storyboard.yaml")
report = tk.validate(sb)             # Report(errors, warnings, videos)
summary = tk.build(sb, "out")        # dict of every artifact and its ffprobe summary
```

## Where files go

Artifacts go where you point `--out`. Raw takes, graphics, silent renders and audio go to a
per-storyboard work directory under the user cache directory (reported in every result;
override with `--work`). Scratch files go to the system temp directory. Nothing is written
next to the installed package. `build` writes `build.json` and `STORYBOARD.md` (a timing
table) beside the videos.

## Sharp edges

- Locators follow what the page shows (text, roles, labels, placeholders). A redesign can break
  them; `explore` proposes new ones, and `validate` cannot know until you record.
- ROIs are CSS pixels of the 1440x810 viewport. `teaserkit sheet <take.mp4> --grid --times 2,5`
  overlays a CSS-pixel grid on a raw take to read them off; `selector` keyframes avoid the
  arithmetic entirely.
- Nobody listens to the music during a build. It is levelled to a standard loudness and checked
  technically, not by ear. Listen before publishing, or use the no-audio copies.
- Filming a signed-in app needs a demo account and fictional data. Use `auth: storage_state`
  with a saved session, or `auth: script` steps (credentials via `${env:NAME}`), and a
  deny list of every real name and internal string that could appear.
- `project.serve` starts a local static file server for the duration of a recording, only when
  the storyboard asks for it.
- The DOM scan sees text, not pixels. Run `review` (AI) or look at the contact sheets for text
  inside images and canvases.

More: docs/GUIDE.md (the full production guide) and AGENTS.md (extending teaserkit).
