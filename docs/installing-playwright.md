# Installing Playwright's Chromium

teaserkit films apps and renders its graphics with headless Chromium driven by Playwright. The
Python package `playwright` is installed with teaserkit; the browser itself is a separate
download that teaserkit never triggers on its own. Install it once per environment:

```bash
# in the same environment teaserkit runs in
playwright install chromium

# with uv tool installs, run it through the tool's environment:
uv tool run --from teaserkit playwright install chromium
```

On Linux, Chromium also needs system libraries:

```bash
playwright install --with-deps chromium   # may ask for sudo
```

## Check

```bash
teaserkit doctor      # the chromium line should say ok
```

## Troubleshooting

- `Executable doesn't exist`: the browser for this Playwright version is not installed. Run
  `playwright install chromium` again from the environment teaserkit uses; each Playwright
  version pins its own browser build.
- Fonts look wrong in recordings: the app is rendered with the fonts installed on the machine
  (or its web fonts). Install the fonts your app expects, or rely on web fonts.
