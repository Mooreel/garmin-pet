"""Shared paths and small helpers for the local pipeline backend."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "pipeline" / "web"
WORK = ROOT / "pipeline" / "work"
LOCAL_CONFIG = ROOT / "pipeline" / "local.json"
CONFIG_HISTORY = WORK / "config_history.json"
EXAMPLE_CONFIG = ROOT / "pipeline" / "local.example.json"
DEVICES_PATH = ROOT / "config" / "devices.json"
MAX_CONFIG_HISTORY = 24
PYTHON = sys.executable or "python3"


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_step(command: list[str], timeout: int = 120) -> dict:
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "code": 124, "output": str(exc)}
    output = (result.stdout + result.stderr).strip()
    return {"ok": result.returncode == 0, "code": result.returncode, "output": output[-8000:]}


def parse_int(value: str | None, fallback: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value or "")
    except ValueError:
        number = fallback
    return max(minimum, min(number, maximum))


def slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return text or "uploaded-pet"
