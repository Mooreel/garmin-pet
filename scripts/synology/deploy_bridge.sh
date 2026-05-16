#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REMOTE="${GARMIN_SYNOLOGY_HOST:-synology}"
REMOTE_DIR="${GARMIN_SYNOLOGY_DIR:-/volume1/homes/nico/development/garmin-pet-bridge}"
PORT="${GARMIN_BRIDGE_PORT:-8790}"
PUBLIC_HOST="${GARMIN_PUBLIC_BRIDGE_HOST:-synology.local}"
BRIDGE_URL="http://$PUBLIC_HOST:$PORT/garmin/latest"
MDNS_ALIAS="${GARMIN_MDNS_ALIAS:-pet.local}"
MDNS_ADDRESS="${GARMIN_MDNS_ADDRESS:-192.168.0.246}"
WEB_ROOT="${GARMIN_SYNOLOGY_WEB_ROOT:-/volume2/web}"

TOKEN="$(cd "$ROOT" && GARMIN_BRIDGE_TOKEN_PATH="$ROOT/bridge_token.txt" python3 - <<'PY'
from pathlib import Path
import sys

root = Path.cwd()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
from pipeline.app.bridge import bridge_token

print(bridge_token())
PY
)"
BRIDGE_URL="$BRIDGE_URL?token=$TOKEN"

TMP_TOKEN="$(mktemp "${TMPDIR:-/tmp}/garmin-pet-token.XXXXXX")"
trap 'rm -f "$TMP_TOKEN"' EXIT
printf '%s\n' "$TOKEN" >"$TMP_TOKEN"

ssh -o BatchMode=yes "$REMOTE" "mkdir -p '$REMOTE_DIR'"
scp -O -q \
  "$ROOT/scripts/synology_bridge_server.py" \
  "$ROOT/scripts/synology/start_bridge.sh" \
  "$ROOT/scripts/synology/stop_bridge.sh" \
  "$ROOT/scripts/synology/mdns_alias.py" \
  "$ROOT/scripts/synology/start_mdns_alias.sh" \
  "$ROOT/scripts/synology/stop_mdns_alias.sh" \
  "$TMP_TOKEN" \
  "$REMOTE:$REMOTE_DIR/"
ssh -o BatchMode=yes "$REMOTE" "mv '$REMOTE_DIR/$(basename "$TMP_TOKEN")' '$REMOTE_DIR/bridge_token.txt' && chmod 700 '$REMOTE_DIR' && chmod 755 '$REMOTE_DIR/start_bridge.sh' '$REMOTE_DIR/stop_bridge.sh' '$REMOTE_DIR/synology_bridge_server.py' '$REMOTE_DIR/mdns_alias.py' '$REMOTE_DIR/start_mdns_alias.sh' '$REMOTE_DIR/stop_mdns_alias.sh' && chmod 600 '$REMOTE_DIR/bridge_token.txt'"

GARMIN_SYNOLOGY_HOST="$REMOTE" \
GARMIN_SYNOLOGY_DIR="$REMOTE_DIR" \
GARMIN_BRIDGE_PORT="$PORT" \
GARMIN_PUBLIC_BRIDGE_HOST="$PUBLIC_HOST" \
"$ROOT/scripts/synology/publish_payload.sh"

ssh -o BatchMode=yes "$REMOTE" "cd '$REMOTE_DIR' && GARMIN_BRIDGE_PORT='$PORT' ./start_bridge.sh"
ssh -o BatchMode=yes "$REMOTE" "cd '$REMOTE_DIR' && GARMIN_MDNS_ALIAS='$MDNS_ALIAS' GARMIN_MDNS_ADDRESS='$MDNS_ADDRESS' ./start_mdns_alias.sh"
scp -O -q "$ROOT/scripts/synology/web_landing.html" "$REMOTE:$WEB_ROOT/index.html"

python3 - "$ROOT" "$BRIDGE_URL" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
bridge_url = sys.argv[2]
config_path = root / "pipeline" / "local.json"
example_path = root / "pipeline" / "local.example.json"
base = json.loads(example_path.read_text(encoding="utf-8"))
if config_path.exists():
    base.update(json.loads(config_path.read_text(encoding="utf-8")))
base["bridgeMode"] = "manual"
base["bridgeUrl"] = bridge_url
config_path.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "Configured local builds to use: http://$PUBLIC_HOST:$PORT/garmin/latest?token=..."
echo "Open bridge health: http://$PUBLIC_HOST:$PORT/health"
