# The self-teaser

`storyboard.yaml` here films teaserkit being asked, by an Amplifier agent, to make a teaser of
the demo app — then cuts in the result. It's how
[the project's own teaser](../../docs/images/teaser.gif) was made.

```bash
examples/self-teaser/setup.sh
.venv/bin/teaserkit build examples/self-teaser/storyboard.yaml --out /tmp/teaserkit-teaser
```

`setup.sh` starts a private [Forge](https://github.com/microsoft/amplifier-skill-forge) terminal
daemon on port 3199 — separate from any Forge dashboard already running on this machine — with
one Amplifier session, `--bundle foundation`, sat in a fresh copy of the demo app. The build then
types the request into that session, films it working, and cuts to `gallery/index.html`, a small
page that plays back the three videos it made.

Needs, beyond teaserkit's own prerequisites: this repo's dev venv (`uv venv && uv pip install -e
'.[dev]'`), the `amplifier-skill-forge` skill installed, the `amplifier` CLI on PATH, and a
configured model provider. The whole shoot, including the agent's build, takes 4-6 minutes.

`setup.sh` writes everything it needs under `.shoot/` (gitignored) and always starts clean, so
re-running it is how you re-shoot. It never touches this machine's real Forge dashboard: it
closes only sessions on its own private daemon.

## Reading the storyboard

- `ask` / `think` / `done`: one take of the Forge dashboard at `http://127.0.0.1:3199/`, cut into
  three beats. `think` covers the agent's real build (recorded at whatever it actually takes,
  including a `wait_for` beat left out of the video) and plays back at up to `max_speedup` (4x by
  default; this cut uses about 3x).
- `shapes`: a second take of `gallery/index.html`, served from this same directory.
- `deny_list` covers home-directory paths. The filming wrappers in `setup.sh` (`bin/teaserkit`,
  `bin/ls`) keep this machine's actual home directory and file ownership out of anything typed
  or listed on screen; the deny list is the backstop that fails the take if one leaks anyway.

## Troubleshooting

- `too many open files` in `.shoot/forge.log`: the private daemon's config-file watcher hit this
  machine's file-descriptor limit. Raise it first: `ulimit -n 65536` in the shell that runs
  `setup.sh`.
- A stale session on port 3199 from a previous shoot: `setup.sh` closes every session on that
  daemon before starting a new one, so just re-run it.
