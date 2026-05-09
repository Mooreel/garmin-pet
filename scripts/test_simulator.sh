#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEVICE="${1:-fr265s}"
KEY="${2:-build/developer_key.der}"
TEST_APP="build/CodexPet-test.prg"
SDK_HOME="${GARMIN_SDK_HOME:-}"

if [ "$SDK_HOME" = "" ] && [ -x "build/connectiq-sdk-9.1.0/bin/monkeyc" ]; then
  SDK_HOME="$ROOT/build/connectiq-sdk-9.1.0"
fi

if [ "$SDK_HOME" = "" ]; then
  echo "GARMIN_SDK_HOME is not set and build/connectiq-sdk-9.1.0 is missing." >&2
  exit 2
fi

export PATH="$SDK_HOME/bin:${PATH}"
if [ -d "/opt/homebrew/opt/openjdk" ]; then
  export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk}"
  export PATH="/opt/homebrew/opt/openjdk/bin:${PATH}"
fi

mkdir -p build
monkeyc -t -f monkey.jungle -d "$DEVICE" -o "$TEST_APP" -y "$KEY"

if ! lsof -nP -iTCP:1234 -sTCP:LISTEN >/dev/null 2>&1; then
  open -n "$SDK_HOME/bin/ConnectIQ.app"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if lsof -nP -iTCP:1234 -sTCP:LISTEN >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! lsof -nP -iTCP:1234 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Connect IQ simulator is not listening on TCP 1234." >&2
  exit 3
fi

out="$(mktemp -t codex-pet-sim-tests.XXXXXX)"
set +e
monkeydo "$TEST_APP" "$DEVICE" -t >"$out" 2>&1
status=$?
set -e
cat "$out"

if grep -q "PASSED (passed=" "$out" && ! grep -q "FAILED" "$out"; then
  rm -f "$out"
  exit 0
fi

rm -f "$out"
exit "$status"
