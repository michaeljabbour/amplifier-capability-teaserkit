Synthesizes an original soundtrack: a warm detuned pad, a soft plucked eighth-note arpeggio, sub
bass and a small delay room, 96 bpm by default, faded in and out, peaking at -4 dBFS. No samples
are used, so there is nothing to license. Deterministic: the same length, bpm, seed and
progression always produce the same audio.

Two modes:

- **Storyboard**: one track per video, exactly as long as its silent render, written to
  `<work>/audio/<video>.wav`. Uses `style.music_bpm`, `music_seed`, `music_progression`.
  Does nothing when `style.music` is `none`.
- **Standalone**: `--seconds S --out file.wav`.

## Arguments

- `storyboard` (optional), `--work DIR`
- `--seconds`, `--out` -- standalone mode.
- `--bpm` (96), `--seed` (7), `--progression warm|bright|calm`.
- `--json`

## Example

```bash
teaserkit music --seconds 35 --out /tmp/track.wav --progression calm
```

## Result

WAV path(s), 48 kHz 16-bit stereo, and lengths.

## Failures

Exit 1 if the storyboard has no silent renders yet (run `compose` first).

Nobody listens during a build: the track is checked for length and loudness, not by ear.
