#!/usr/bin/env bash
# macOS installer: build (if needed), copy the .app to /Applications, seed the
# config, and put an alias on the Desktop.
#
#     bash packaging/install.sh
#
set -euo pipefail

APP_NAME="ZLibraryWrapper"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_BUNDLE="$ROOT/dist/$APP_NAME.app"

# 1. Build with PyInstaller if the .app isn't there yet.
if [ ! -d "$APP_BUNDLE" ]; then
  echo "Build output not found. Building with PyInstaller..."
  # Generate a crisp native .icns first (falls back gracefully off macOS).
  if [ -f "$ROOT/assets/icon.png" ]; then
    bash "$ROOT/packaging/make_icns.sh" || true
  fi
  ( cd "$ROOT" && python3 -m PyInstaller "packaging/app.spec" --noconfirm )
fi
if [ ! -d "$APP_BUNDLE" ]; then
  echo "Error: build did not produce $APP_BUNDLE" >&2
  exit 1
fi

# 2. Install into /Applications (fall back to ~/Applications without sudo).
DEST="/Applications"
if [ ! -w "$DEST" ]; then
  DEST="$HOME/Applications"
  mkdir -p "$DEST"
fi
echo "Installing to $DEST ..."
rm -rf "$DEST/$APP_NAME.app"
cp -R "$APP_BUNDLE" "$DEST/"

# Clear the quarantine flag so Gatekeeper doesn't block the first launch.
xattr -dr com.apple.quarantine "$DEST/$APP_NAME.app" 2>/dev/null || true

# 3. Desktop alias (symlink).
ln -sfn "$DEST/$APP_NAME.app" "$HOME/Desktop/Z-Library.app"
echo "Created Desktop alias."

# 4. Seed a config template if none exists.
CONFIG_DIR="$HOME/Library/Application Support/$APP_NAME"
CONFIG_FILE="$CONFIG_DIR/config.ini"
if [ ! -f "$CONFIG_FILE" ]; then
  mkdir -p "$CONFIG_DIR"
  cp "$ROOT/config.ini.example" "$CONFIG_FILE"
  chmod 600 "$CONFIG_FILE" || true
  echo ""
  echo "A config file was created at:"
  echo "    $CONFIG_FILE"
  echo "Open it and enter your Z-Library email and password before first launch."
fi

echo ""
echo "Done. Launch 'Z-Library' from your Desktop or Applications."
