#!/usr/bin/env sh
set -eu

DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ALIAS_NAME="${GARMIN_MDNS_ALIAS:-pet.local}"
ADDRESS="${GARMIN_MDNS_ADDRESS:-192.168.0.246}"
PIDFILE="$DIR/mdns-alias.pid"
LOGFILE="$DIR/mdns-alias.log"

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ "$PID" != "" ] && kill -0 "$PID" 2>/dev/null; then
    echo "$ALIAS_NAME mDNS alias already running with pid $PID."
    exit 0
  fi
  rm -f "$PIDFILE"
fi

cd "$DIR"
nohup python3 mdns_alias.py --name "$ALIAS_NAME" --address "$ADDRESS" >"$LOGFILE" 2>&1 &
PID="$!"
echo "$PID" >"$PIDFILE"
chmod 600 "$PIDFILE" "$LOGFILE" 2>/dev/null || true
sleep 1

if kill -0 "$PID" 2>/dev/null; then
  echo "Started $ALIAS_NAME mDNS alias for $ADDRESS with pid $PID."
else
  echo "Failed to start $ALIAS_NAME mDNS alias. See $LOGFILE." >&2
  exit 1
fi
