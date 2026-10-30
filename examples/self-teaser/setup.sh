#!/bin/sh
# Optional live shoot: configured Forge/Amplifier/provider access is required.
# The controller refuses occupied ports and records the exact process/session
# ownership it creates. Cleanup never targets a shared dashboard or unknown ID.
set -eu
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec python3 "$SELF/setup.py" "$@"
