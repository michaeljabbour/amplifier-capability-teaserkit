#!/bin/sh
# Prepare the "teaserkit films itself" shoot: a private Forge terminal daemon on port 3199 (so
# its dashboard shows nothing but this one session) running an Amplifier agent, cwd'd at a fresh
# copy of the demo app -- and a private daemon on the default port shows this machine's home
# directory in the agent's own tool-call output, which the storyboard's deny_list would (rightly)
# fail on. So the whole shoot -- storyboard, brand, gallery and the demo-app copy -- is staged
# into a scratch temp directory outside the home directory, printed at the end, and left in
# place for you to build from and to inspect.
#
#   examples/self-teaser/setup.sh
#   # then run the `teaserkit build ...` command it prints
#
# Needs: this repo's dev venv (`uv venv && uv pip install -e '.[dev]'`), the amplifier-skill-forge
# skill installed (ships forge.py; see its SKILL.md), the `amplifier` CLI on PATH, and a
# configured model provider. Re-run this script for a re-shoot; it always starts clean.
set -e
SELF=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$SELF/../.." && pwd)
FORGE="${FORGE:-$HOME/.amplifier/skills/amplifier-skill-forge/tools/forge.py}"
[ -f "$FORGE" ] || { echo "setup.sh: forge.py not found at $FORGE (install the amplifier-skill-forge skill, or set FORGE=)." >&2; exit 1; }

STAGE=$(mktemp -d -t teaserkit-self-teaser)
cp "$SELF/storyboard.yaml" "$SELF/brand.yaml" "$STAGE/"
cp -R "$SELF/gallery" "$STAGE/gallery"
cp -R "$REPO/examples/demo-app" "$STAGE/acme"
mkdir -p "$STAGE/bin" "$STAGE/tkhome" "$STAGE/forgehome"
ln -s "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/Library/Caches/ms-playwright}" "$STAGE/browsers"

cat > "$STAGE/bin/teaserkit" <<EOF
#!/bin/sh
# Filming wrapper: a fake HOME and a symlinked browser cache keep this machine's real home
# directory out of anything teaserkit or the recorded page prints.
export HOME="$STAGE/tkhome" PLAYWRIGHT_BROWSERS_PATH="$STAGE/browsers"
exec "$REPO/.venv/bin/teaserkit" "\$@"
EOF
cat > "$STAGE/bin/ls" <<'EOF'
#!/bin/sh
# Filming wrapper: -g drops the file-owner column from long listings.
exec /bin/ls -g "$@"
EOF
chmod +x "$STAGE/bin/teaserkit" "$STAGE/bin/ls"
# The private Forge daemon below runs under a scratch HOME (so it can't be mistaken for the
# shared one on the default port) and every session it spawns inherits that HOME. Restore the
# real one here so the Amplifier session in it stays the one you already have configured.
printf "export HOME='%s' PATH='%s:%s' PS1='acme %%%% '\n" "$HOME" "$STAGE/bin" "$PATH" > "$STAGE/env.sh"

export FORGE_URL=http://127.0.0.1:3199/mcp
if ! curl -s -o /dev/null "http://127.0.0.1:3199/"; then
  # Forge hot-reloads ~/.forge/settings.json with fs.watch(); on some machines that alone hits
  # EMFILE before the daemon is even up. It never needs to for a throwaway, private daemon, so
  # the second attempt disables it.
  cat > "$STAGE/nowatch.cjs" <<'JS'
const fs = require("fs"); const { EventEmitter } = require("events");
fs.watch = () => { const w = new EventEmitter(); w.close = () => {}; w.unref = () => w; return w; };
JS
  start_forge() {
    ( cd "$STAGE" && ulimit -n 65536 2>/dev/null; HOME="$STAGE/forgehome" FORGE_LAUNCHD=1 NODE_OPTIONS="$1" \
      nohup forge start --port 3199 --idle-timeout 7200000 > forge.log 2>&1 & )
    for i in 1 2 3 4 5 6 7 8 9 10; do curl -s -o /dev/null "http://127.0.0.1:3199/" && return 0; sleep 1; done
    return 1
  }
  start_forge "" || start_forge "--require $STAGE/nowatch.cjs"
fi
for id in $(python3 "$FORGE" list | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ".join(s["id"] for s in d) if isinstance(d, list) else "")' 2>/dev/null); do
  python3 "$FORGE" close "$id" >/dev/null
done

SID=$(python3 "$FORGE" new --name acme --cwd "$STAGE/acme"); sleep 2
python3 "$FORGE" run "$SID" ". $STAGE/env.sh; clear" --wait 1 >/dev/null
python3 "$FORGE" type "$SID" "amplifier run --bundle foundation --mode chat"; python3 "$FORGE" key "$SID" enter
ok=""
for i in 1 2 3 4 5 6 7 8; do python3 "$FORGE" wait "$SID" "Interactive Session" --timeout 29000 >/dev/null && { ok=1; break; }; done
if [ -z "$ok" ]; then
  echo "setup.sh: Amplifier never reached its interactive prompt. Last screen:" >&2
  python3 "$FORGE" screen "$SID" >&2
  exit 1
fi
sleep 4; python3 "$FORGE" key "$SID" ctrl+l; sleep 1

echo "Ready. Session $SID at http://127.0.0.1:3199/ ; now run:"
echo "  $REPO/.venv/bin/teaserkit build $STAGE/storyboard.yaml --out /tmp/teaserkit-teaser"
