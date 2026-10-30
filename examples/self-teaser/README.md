# The self-teaser

`storyboard.yaml` here films teaserkit being asked, by an Amplifier agent, to make a teaser of
the demo app — then cuts in the result. It's how
[the project's own teaser](../../docs/images/teaser.gif) was made.

```bash
examples/self-teaser/setup.sh
# Run the staged build command printed by setup.sh.
# After filming, run its printed --cleanup command.
```

`setup.sh` starts a private [Forge](https://github.com/microsoft/amplifier-skill-forge) terminal
daemon on port 3199 — separate from any Forge dashboard already running on this machine — with
one Amplifier session, `--bundle foundation`, sat in a fresh copy of the demo app. The build then
types the request into that session, films it working, and cuts to `gallery/index.html`, a small
page that plays back the three videos it made.

Needs, beyond teaserkit's own prerequisites: this repo's dev venv (`uv venv && uv pip install -e
'.[dev]'`), the `amplifier-skill-forge` skill installed, the `amplifier` CLI on PATH, and a
configured model provider. The whole shoot, including the agent's build, takes 4-6 minutes.

`setup.sh` creates a private scratch directory under `/tmp` and prints its path and the exact
staged build command. It refuses an occupied port 3199, including a previous shoot; it never
reuses a healthy HTTP service or assumes that a private HOME proves port ownership. Keep the
printed scratch directory until cleanup is complete.

The controller launches Forge in the foreground as its recorded child, with a scratch HOME
and no launchd registration. Before every client call it verifies the child's PID, private
Forge PID file, listening PID and process start identity. It records only the session ID
returned by this shoot's successful creation. An invalid or timed-out creation remains
uncertain; the controller retains the daemon for inspection instead of guessing which session
to close. A startup retry is allowed only after its exact child has exited and the port is free.

After filming, run the printed command, or:

```bash
examples/self-teaser/setup.sh --cleanup /tmp/teaserkit-self-teaser-EXAMPLE
```

Cleanup closes only the recorded session IDs. It refuses to stop the daemon if other sessions
are observed, or if current process/port ownership no longer matches the receipt. It never
invokes a global Forge stop or closes every ID from a dashboard listing. The scratch files
are retained for review. This is a cooperative local shoot, not authentication or isolation
from another process that deliberately joins the new local dashboard.

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

- `too many open files` in the printed scratch directory's `forge.log`: the private daemon's config-file watcher hit this
  machine's file-descriptor limit. Raise it first: `ulimit -n 65536` in the shell that runs
  `setup.sh`.
- A previous shoot still occupies port 3199: use that shoot's retained `shoot-owner.json` and
  printed `--cleanup` command. If ownership cannot be proven or another session is present,
  cleanup stops with a specific error. Inspect the named process/session yourself; do not
  substitute a list-and-close-all command.
- `lsof` and `ps` are required for process ownership checks. A missing tool, failed startup or
  mismatch is a setup failure, not a ready dashboard. No configured provider or live Forge
  acceptance is inferred from the offline regression tests.
