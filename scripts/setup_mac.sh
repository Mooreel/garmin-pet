#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

INSTALL_DEPS=false
for arg in "$@"; do
  case "$arg" in
    --install-deps)
      INSTALL_DEPS=true
      ;;
    -h|--help)
      echo "Usage: scripts/setup_mac.sh [--install-deps]"
      echo
      echo "Checks and creates local Garmin Pet files. With --install-deps, installs"
      echo "Homebrew packages that can be automated safely: openjdk and libmtp."
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

mkdir -p build pipeline/work

echo "Checking local Mac setup..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required." >&2
  exit 1
fi

SYSTEM_HAS_PILLOW=false
if python3 - <<'PY' >/dev/null 2>&1
from PIL import Image
assert hasattr(Image, "Resampling")
PY
then
  SYSTEM_HAS_PILLOW=true
fi

if [ ! -x .venv/bin/python ]; then
  echo "Creating local Python environment: .venv"
  if [ "$SYSTEM_HAS_PILLOW" = true ]; then
    python3 -m venv --system-site-packages .venv
  else
    python3 -m venv .venv
  fi
fi

PYTHON_BIN="$ROOT/.venv/bin/python"
PYTHON_READY_MESSAGE=""

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from PIL import Image
assert hasattr(Image, "Resampling")
PY
then
  if [ "$SYSTEM_HAS_PILLOW" = true ] && [ -f .venv/pyvenv.cfg ]; then
    python3 - <<'PY'
from pathlib import Path

path = Path(".venv/pyvenv.cfg")
lines = path.read_text(encoding="utf-8").splitlines()
updated = []
seen = False
for line in lines:
    if line.startswith("include-system-site-packages"):
        updated.append("include-system-site-packages = true")
        seen = True
    else:
        updated.append(line)
if not seen:
    updated.append("include-system-site-packages = true")
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
    PYTHON_READY_MESSAGE="Python packages ready: using compatible system Pillow through .venv"
  fi
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from PIL import Image
assert hasattr(Image, "Resampling")
PY
then
  echo "Installing Python packages from requirements.txt..."
  "$PYTHON_BIN" -m pip install --disable-pip-version-check -r requirements.txt
else
  if [ "$PYTHON_READY_MESSAGE" != "" ]; then
    echo "$PYTHON_READY_MESSAGE"
  else
    echo "Python packages ready: requirements.txt"
  fi
fi

"$PYTHON_BIN" - <<'PY'
from pipeline.app.bridge import bridge_status

status = bridge_status(None, ("0.0.0.0", 8790))
print(f"Bridge token ready: {status['tokenRequired']}")
display_url = status["url"].split("token=", 1)[0] + "token=..."
print(f"Generated watch bridge: {display_url}")
PY

if [ ! -f pipeline/local.json ]; then
  cp pipeline/local.example.json pipeline/local.json
  echo "Created local config: pipeline/local.json"
else
  echo "Local config ready: pipeline/local.json"
fi

if [ ! -f build/developer_key.der ]; then
  if command -v openssl >/dev/null 2>&1; then
    echo "Creating local Garmin developer key at build/developer_key.der..."
    openssl genrsa -out build/developer_key.pem 4096 >/dev/null 2>&1
    openssl pkcs8 -topk8 -inform PEM -outform DER -in build/developer_key.pem -out build/developer_key.der -nocrypt >/dev/null 2>&1
    rm -f build/developer_key.pem
  else
    echo "WARN: openssl not found; create build/developer_key.der before building."
  fi
else
  echo "Developer key ready: build/developer_key.der"
fi

if [ "$INSTALL_DEPS" = true ]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "WARN: Homebrew not found; skipping automatic package install."
  else
    if ! [ -x /opt/homebrew/opt/openjdk/bin/java ] && ! java -version >/dev/null 2>&1; then
      echo "Installing OpenJDK with Homebrew..."
      brew install openjdk
    fi
    if ! command -v mtp-detect >/dev/null 2>&1; then
      echo "Installing libmtp with Homebrew..."
      brew install libmtp
    fi
  fi
fi

if command -v monkeyc >/dev/null 2>&1; then
  echo "Garmin compiler ready: $(command -v monkeyc)"
elif [ -x build/connectiq-sdk-9.1.0/bin/monkeyc ]; then
  echo "Garmin compiler ready: build/connectiq-sdk-9.1.0/bin/monkeyc"
else
  echo "WARN: Garmin monkeyc was not found. Install Garmin Connect IQ SDK Manager before building."
fi

if command -v java >/dev/null 2>&1 && JAVA_VERSION="$(java -version 2>&1 | head -n 1)"; then
  echo "Java ready: $JAVA_VERSION"
elif [ -x /opt/homebrew/opt/openjdk/bin/java ]; then
  JAVA_VERSION="$(/opt/homebrew/opt/openjdk/bin/java -version 2>&1 | head -n 1)"
  echo "Java ready: $JAVA_VERSION"
else
  echo "WARN: Java was not found. Install a JDK before building with Garmin SDK."
fi

if command -v mtp-detect >/dev/null 2>&1; then
  echo "MTP tools ready: $(command -v mtp-detect)"
else
  echo "WARN: libmtp tools were not found. Install with 'brew install libmtp' if USB deploy needs MTP."
fi

echo
echo "Start the app with:"
echo "  scripts/start.sh"
echo
echo "Then open:"
echo "  http://127.0.0.1:8790"
