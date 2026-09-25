# Installing ffmpeg

teaserkit calls `ffmpeg` and `ffprobe` to encode takes and renders, mux audio, normalize
loudness and grab posters. It needs a build with `libx264` and the `loudnorm` filter, which
every mainstream package includes. `drawtext` is not required.

## macOS

```bash
brew install ffmpeg
```

## Debian / Ubuntu

```bash
sudo apt update && sudo apt install ffmpeg
```

## Fedora

```bash
sudo dnf install ffmpeg   # from RPM Fusion
```

## Check

```bash
ffmpeg -version | head -1
ffmpeg -hide_banner -encoders | grep libx264
teaserkit doctor
```

If ffmpeg lives somewhere unusual, point teaserkit at it with `TEASERKIT_FFMPEG=/path/to/ffmpeg`
and `TEASERKIT_FFPROBE=/path/to/ffprobe`.
