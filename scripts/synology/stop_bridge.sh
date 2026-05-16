#!/usr/bin/env sh
set -eu

DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PIDFILE="$DIR/bridge.pid"

if [ ! -f "$PIDFILE" ]; then
  echo "Garmin Pet bridge is not running."
  exit 0
fi

PID="$(cat "$PIDFILE" 2>/dev/null || true)"
if [ "$PID" != "" ] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Garmin Pet bridge stopped."
else
  echo "Garmin Pet bridge pid was stale."
fi

rm -f "$PIDFILE"
