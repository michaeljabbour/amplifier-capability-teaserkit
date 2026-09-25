#!/usr/bin/env sh
# Deny-list check for files and git history. See check_generic.py.
exec python3 "$(dirname "$0")/check_generic.py" "$@"
