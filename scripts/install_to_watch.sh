#!/usr/bin/env bash
set -euo pipefail

APP="${1:-build/CodexPet.prg}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/build/mtp_send_to_folder"
APP_FOLDER="GARMIN/APPS"
MTP_APP_FOLDER="GARMIN/Apps"

if [ ! -f "$APP" ]; then
  echo "Missing app binary: $APP" >&2
  echo "Use Save & Build in the browser or run scripts/configured_build.py first." >&2
  exit 2
fi

target=""
for volume in /Volumes/*; do
  if [ -d "$volume/$APP_FOLDER" ]; then
    target="$volume/$APP_FOLDER/CODEXPET.PRG"
    break
  fi
done

if [ "$target" = "" ]; then
  if command -v mtp-filetree >/dev/null 2>&1; then
    if [ ! -x "$HELPER" ]; then
      clang "$ROOT/scripts/mtp_send_to_folder.c" -o "$HELPER" -I/opt/homebrew/include -L/opt/homebrew/lib -lmtp
    fi
    "$HELPER" "$APP" CODEXPET.PRG "$MTP_APP_FOLDER" --replace
    exit 0
  fi

  echo "No Garmin watch storage found. Connect the Forerunner 265S over USB or install libmtp for MTP access." >&2
  exit 3
fi

cp "$APP" "$target"
echo "Installed $APP to $target"
