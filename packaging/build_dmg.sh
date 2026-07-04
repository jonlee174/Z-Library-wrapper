#!/usr/bin/env bash
# One-click macOS DMG builder.
#
#   bash packaging/build_dmg.sh
#
# Produces dist/ZLibraryWrapper.dmg — a drag-to-Applications installer disk
# image. Must be run ON macOS (PyInstaller + hdiutil are macOS-only here).
#
# Uses `create-dmg` for a nicely laid-out window if it's installed
# (brew install create-dmg); otherwise falls back to plain `hdiutil`, which
# still yields a working drag-to-Applications DMG.
set -euo pipefail

APP_NAME="ZLibraryWrapper"
VOL_NAME="Z-Library"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/$APP_NAME.app"
DMG="$DIST/$APP_NAME.dmg"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "Error: build the DMG on macOS (this is $(uname))." >&2
  exit 1
fi

# 1. Build the .app if it isn't there.
if [ ! -d "$APP" ]; then
  echo "==> Building the app bundle first..."
  if [ -f "$ROOT/assets/icon.png" ]; then
    bash "$ROOT/packaging/make_icns.sh" || true
  fi
  ( cd "$ROOT" && python3 -m PyInstaller "packaging/app.spec" --noconfirm )
fi
[ -d "$APP" ] || { echo "Error: $APP not found after build." >&2; exit 1; }

# Clear quarantine so the DMG's copy launches without extra friction.
xattr -cr "$APP" 2>/dev/null || true

rm -f "$DMG"

# 2a. Preferred path: create-dmg (styled window, app + Applications shortcut).
if command -v create-dmg >/dev/null 2>&1; then
  echo "==> Building styled DMG with create-dmg..."
  ICON_ARG=()
  [ -f "$ROOT/assets/icon.icns" ] && ICON_ARG=(--volicon "$ROOT/assets/icon.icns")
  create-dmg \
    --volname "$VOL_NAME" \
    "${ICON_ARG[@]}" \
    --window-pos 200 120 \
    --window-size 640 400 \
    --icon-size 128 \
    --icon "$APP_NAME.app" 160 190 \
    --hide-extension "$APP_NAME.app" \
    --app-drop-link 480 190 \
    "$DMG" \
    "$APP" \
  || { echo "create-dmg failed; falling back to hdiutil."; HDIUTIL_FALLBACK=1; }
else
  HDIUTIL_FALLBACK=1
fi

# 2b. Fallback: assemble a staging folder and build with hdiutil.
if [ "${HDIUTIL_FALLBACK:-0}" = "1" ]; then
  echo "==> Building DMG with hdiutil (install create-dmg for a prettier window)..."
  STAGE="$(mktemp -d)/dmg"
  mkdir -p "$STAGE"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create \
    -volname "$VOL_NAME" \
    -srcfolder "$STAGE" \
    -ov -format UDZO \
    "$DMG"
fi

echo ""
echo "Done -> $DMG"
echo "Open it and drag Z-Library into Applications."
