#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REMOTE="${GARMIN_SYNOLOGY_HOST:-synology}"
REMOTE_DIR="${GARMIN_SYNOLOGY_DIR:-/volume1/homes/nico/development/garmin-pet-bridge}"
PORT="${GARMIN_BRIDGE_PORT:-8790}"
PUBLIC_HOST="${GARMIN_PUBLIC_BRIDGE_HOST:-synology.local}"

TMP_JSON="$(mktemp "${TMPDIR:-/tmp}/garmin-pet-payload.XXXXXX.json")"
trap 'rm -f "$TMP_JSON"' EXIT

python3 "$ROOT/scripts/synology/publish_payload.py" >"$TMP_JSON"
ssh -o BatchMode=yes "$REMOTE" "mkdir -p '$REMOTE_DIR'"
scp -O -q "$TMP_JSON" "$REMOTE:$REMOTE_DIR/latest.json.next"
ssh -o BatchMode=yes "$REMOTE" "mv '$REMOTE_DIR/latest.json.next' '$REMOTE_DIR/latest.json' && chmod 600 '$REMOTE_DIR/latest.json'"

echo "Published current Codex payload to $REMOTE:$REMOTE_DIR/latest.json"
echo "Watch bridge URL: http://$PUBLIC_HOST:$PORT/garmin/latest?token=..."
