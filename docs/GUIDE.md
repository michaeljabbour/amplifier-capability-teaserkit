# Making product teaser videos from a live web app

A production guide: what the pipeline does, the house style, how to make a new video or
re-shoot one beat, and how to check the result before it ships. Every step here is a teaserkit
capability; the same guide applies if you drive it from a script or an agent.

## At a glance

- **What the videos are:** real screen recordings of the running product, not mock-ups and not
  AI-generated video.
- **How they are filmed:** a script drives an invisible (headless) browser. Nobody's screen or
  mouse is involved, so filming can run anywhere, repeatably.
- **How they are finished:** the compositor adds slow camera moves, captions, title and end
  cards and an original synthesized soundtrack, then exports every video in three shapes.
- **What is on screen:** a demo workspace full of made-up people and projects. Real customers,
  colleagues and internal codenames never appear.

Every video comes out as 16:9 (1920x1080), 9:16 (1080x1920) and 1:1 (1080x1080), each with a
poster PNG, and main videos also get a no-audio copy. `build` writes a `STORYBOARD.md` timing
table and a `build.json` summary beside them.

## 1. What is used

No video generator or special video service is involved. It is ordinary, reproducible tooling:

| Piece | Used for |
|---|---|
| Playwright + headless Chromium | Clicking through the app like a person: typing, scrolling, hovering. Also renders captions and cards. |
| DevTools screencast | Capturing the browser at 2x density (2880x1620 for a 1440x810 viewport), so zooms stay sharp. |
| Injected cursor | A visible pointer with a click ripple; headless browsers draw none. |
| Python + OpenCV + NumPy | The compositor: cuts, crossfades, eased zooms and pans, per-shape reframing, captions. |
| Python + NumPy (audio) | The soundtrack, synthesized from sine waves: pad, plucked arpeggio, sub bass. No samples. |
| ffmpeg | H.264 at 30 fps, AAC audio, loudness levelling to -18 LUFS, posters. |
| HTML + your brand | Captions and cards are small web pages (brand fonts and colors) rendered to transparent PNGs. |
| A vision model (optional) | `review` looks at frames for names, internal strings, errors, spinners and broken layouts. |
| A language model (optional) | `plan` drafts storyboards; `explore` finds the clicks for a beat. |

Not used: voiceover or text-to-speech, stock footage, stock music, generated imagery.

## 2. The pipeline

```
demo data --> storyboard.yaml --> record --> captions --> compose --> music --> finalize --> out/
 (yours)       (plan: AI)        (takes)     (PNGs)     (silent MP4s)  (WAV)   (MP4, posters)
                                    ^                                            |
                               explore: AI                              sheet / review: AI
```

**Demo data.** Seed a demo account through the product's own normal actions: a couple of
friendly projects, a few dozen tasks, invented teammates. Backdate history if charts need weeks
of data. Keep it as a marketing asset; you will re-shoot from it.

**Storyboard.** One YAML file: the project (URL or local static site, sign-in method, brand,
deny list) and a list of beats. A beat is one feature: steps, a result hold, a planned duration,
a caption, and a region of interest (ROI). Videos list beats. `teaserkit init` writes a
commented starting point; `teaserkit plan` (AI) drafts one from a description.

**Record.** `teaserkit record` opens a fresh browser per take at 1440x810 CSS pixels and 2x
density, injects the cursor, and films through the screencast. Frames arrive only when the page
repaints, each timestamped, and ffmpeg turns them into a constant 30 fps MP4, so waiting costs
nothing and timing stays true. The recorder marks each beat's start, the start of its result
hold, and its end, and notes the on-screen box of any ROI selector. After every step it reads
the visible text and fails the take if a deny-listed string is there.

**Captions and cards.** `teaserkit captions` renders each caption for all three shapes, plus the
frame chrome (a brand band and caption band for vertical and square) and the title and end
cards.

**Compose.** `teaserkit compose` cuts every beat out of its take at the marks and fits it to the
beat's planned duration: the action may play faster than real time (up to 4x), the result hold
plays at real speed and freezes on its last frame if needed. For each shape it fits a crop
around the ROI and eases between framings, so vertical and square versions follow the action
instead of shrinking the whole screen. Beats crossfade; captions fade in and out.

**Music and finishing.** `teaserkit music` synthesizes a track exactly as long as each video.
`teaserkit finalize` adds it as AAC 192k, levels it to -18 LUFS (true peak -2 dB), adds fast-start,
writes the no-audio copy and the poster.

`teaserkit build` runs all of the above. Each step reads what the previous one left in the work
directory, so after editing a caption you can `build --skip-record`, and after a UI change you
can re-record one take.

## 3. House style

These are teaserkit's defaults. Change any of them under `style:` in the storyboard.

- **Captions:** short, plain language; **7 words or fewer per line**, at most two lines (caption
  and subtitle); each readable for **at least 2.5 s**. No voiceover.
- **Pacing:** each feature held **about 4-6 s**. Fewer cuts. Slow eased zooms (1.4 s) with a
  settle before and after. **Pause on each result**: the thing appearing, the answer, the
  confirmation.
- **Length:** main video about **60-90 s**, plus a tighter cut if needed; clips **30-40 s**.
- **Music:** original and synthesized; nothing licensed or sampled.
- **Formats:** all three shapes, posters, and a no-audio version of the main video.
- **Content:** fictional data only. Friendly, everyday examples rather than competitive
  comparisons.

`teaserkit validate` checks captions, beat lengths, holds, camera speeds, ROI bounds, video
lengths, cut rate, the deny list and the music setting before anything is filmed, because
planned durations make each video's length known in advance.

## 4. Making a new video, or re-shooting one beat

1. **Plan the beats.** Write the storyboard as a table first (time, picture, caption), then
   as beats. Or run `teaserkit plan --description ... --feature ... --out storyboard.yaml`.
2. **Find the steps.** For each beat, write steps with locators people can read (button text,
   roles, labels, placeholders). If you are unsure, `teaserkit explore --intent "..."` tries it
   in the live app and returns steps that actually ran.
3. **Sign in, only for filming.** Use a demo account. Save a signed-in session once and point
   `auth: storage_state` at it, or use `auth: script` steps with credentials from the
   environment (`${env:DEMO_PASSWORD}`). If the product needs a special sign-in route for
   automation, enable it only while filming and switch it off afterwards.
4. **Validate:** `teaserkit validate storyboard.yaml`.
5. **Preview:** `teaserkit build storyboard.yaml --out out --preview --aspect 16x9` renders half
   size, fast. Fix ROIs with `teaserkit sheet <work>/raw/<take>.mp4 --grid --times 2,6 --out
   grid.png`, which overlays a CSS-pixel grid, or use `selector` keyframes.
6. **Final:** `teaserkit build storyboard.yaml --out out`.
7. **Re-shoot one beat later:** edit its steps, `teaserkit record storyboard.yaml --take <take>`,
   then `teaserkit build storyboard.yaml --out out --skip-record`.

## 5. Checking

- **Contact sheets.** `build` writes `out/sheets/<video>-<aspect>.png`, a frame every 2 s with
  timestamps. Look at every one, in every shape, for real names, internal codenames, personal
  paths, error toasts, spinners and broken layouts.
- **Automated review (AI).** `teaserkit review out/*.mp4 --storyboard storyboard.yaml` returns
  structured findings and exits 7 if any are high severity.
- **Technical.** `build.json` includes an ffprobe summary for every file: codec, size, frame rate,
  duration, audio codec.
- **Product bugs.** Filming often exposes real bugs (fonts not loading, raw dates, raw markup).
  Fix them in the product and re-shoot; do not paper over them in the edit.

## 6. Good to know

- **Big redesigns move things.** Steps follow on-screen labels, so small changes are fine;
  after a redesign expect to update steps and ROIs.
- **AI features in the product may cost money on camera.** If a beat triggers the product's own
  paid features, budget for it in the demo account.
- **Nobody has listened to the music.** A build cannot hear audio. Tracks are levelled to a
  standard loudness and checked for length, not by ear. Listen before publishing; if a track
  does not suit, the no-audio versions are ready to pair with licensed music.
- **The leak scan reads text, not pixels.** Text inside images, video or canvas is invisible to
  it; that is what contact sheets and `review` are for.
- **Work files are large.** Raw takes, graphics and silent renders live in the work directory
  (reported by every command). Delete it once the exports are final.
