#!/usr/bin/env bash
# One-click build on macOS/Linux. On macOS this produces the DMG.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/build.py" "$@"
