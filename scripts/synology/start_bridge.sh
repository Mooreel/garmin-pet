#!/usr/bin/env sh
set -eu

DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PORT="${GARMIN_BRIDGE_PORT:-8790}"
HOST="${GARMIN_BRIDGE_BIND:-0.0.0.0}"
PIPELINE_URL="${GARMIN_PIPELINE_URL:-}"
PIDFILE="$DIR/bridge.pid"
LOGFILE="$DIR/bridge.log"

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ "$PID" != "" ] && kill -0 "$PID" 2>/dev/null; then
    echo "Garmin Pet bridge already running on port $PORT with pid $PID."
    exit 0
  fi
  rm -f "$PIDFILE"
fi

cd "$DIR"
nohup python3 synology_bridge_server.py --host "$HOST" --port "$PORT" --state-dir "$DIR" --pipeline-url "$PIPELINE_URL" >"$LOGFILE" 2>&1 &
PID="$!"
echo "$PID" >"$PIDFILE"
chmod 600 "$PIDFILE" "$LOGFILE" 2>/dev/null || true
sleep 1

if kill -0 "$PID" 2>/dev/null; then
  echo "Garmin Pet bridge started on port $PORT with pid $PID."
else
  echo "Garmin Pet bridge failed to start. See $LOGFILE." >&2
  exit 1
fi
