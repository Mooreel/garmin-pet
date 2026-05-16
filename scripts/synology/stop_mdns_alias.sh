#!/usr/bin/env sh
set -eu

DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PIDFILE="$DIR/mdns-alias.pid"

if [ ! -f "$PIDFILE" ]; then
  echo "mDNS alias is not running."
  exit 0
fi

PID="$(cat "$PIDFILE" 2>/dev/null || true)"
if [ "$PID" != "" ] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "mDNS alias stopped."
else
  echo "mDNS alias pid was stale."
fi

rm -f "$PIDFILE"
