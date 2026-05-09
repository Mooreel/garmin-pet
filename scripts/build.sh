#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: scripts/build.sh /path/to/developer-key.der [device]" >&2
  exit 2
fi

DEVICE="${2:-fr265s}"
BRIDGE_URL="$(awk -F'"' '/CODEX_BRIDGE_URL/ {print $2; exit}' source/CodexBuildConfig.mc 2>/dev/null || true)"

if [[ "$BRIDGE_URL" =~ ^https?://(127\.0\.0\.1|localhost|0\.0\.0\.0)(:|/) ]] && [ "${GARMIN_ALLOW_LOCALHOST_BRIDGE:-}" != "1" ]; then
  echo "Refusing to build a real-watch app with loopback bridge URL: $BRIDGE_URL" >&2
  echo "Use the web Save & Build flow or run scripts/configured_build.py so the Mac LAN bridge URL is injected." >&2
  echo "For the Garmin simulator only, rerun with GARMIN_ALLOW_LOCALHOST_BRIDGE=1." >&2
  exit 2
fi

SDK_HOME="${GARMIN_SDK_HOME:-}"
if [ "$SDK_HOME" = "" ] && [ -x "build/connectiq-sdk-9.1.0/bin/monkeyc" ]; then
  SDK_HOME="$PWD/build/connectiq-sdk-9.1.0"
fi

if [ "$SDK_HOME" != "" ]; then
  export PATH="$SDK_HOME/bin:${PATH}"
fi

if [ -d "/opt/homebrew/opt/openjdk" ]; then
  export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk}"
  export PATH="/opt/homebrew/opt/openjdk/bin:${PATH}"
fi

if [[ "${JAVA_TOOL_OPTIONS:-}" != *"-Djava.awt.headless=true"* ]]; then
  export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:-} -Djava.awt.headless=true"
fi

if ! command -v monkeyc >/dev/null 2>&1; then
  echo "monkeyc is not on PATH. Install Garmin Connect IQ SDK and set GARMIN_SDK_HOME=/path/to/sdk." >&2
  exit 127
fi

mkdir -p build
monkeyc -f monkey.jungle -d "$DEVICE" -o build/CodexPet.prg -y "$1"
