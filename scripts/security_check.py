#!/usr/bin/env python3
"""Fail when files tracked by git contain local secrets or build credentials."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DENY_PATH_PARTS = {
    "bridge_token.txt",
    "local_certs/",
    "build/",
    "developer_key",
}
PATTERNS = [
    re.compile(r"token=[0-9a-fA-F]{16,}"),
    re.compile(r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"),
    re.compile(r"GARMIN_BRIDGE_TOKEN\s*=\s*['\"]?[0-9a-fA-F]{16,}"),
]
FALLBACK_SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "local_certs",
    "pipeline/work",
}


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files"], cwd=ROOT, text=True, capture_output=True)
    if result.returncode == 0:
        return [line for line in result.stdout.splitlines() if line]

    files: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        parts = rel.split("/")
        if any(skip == parts[0] or rel.startswith(skip + "/") for skip in FALLBACK_SKIP_DIRS):
            continue
        if rel == "bridge_token.txt" or rel == "pipeline/local.json":
            continue
        files.append(rel)
    return sorted(files)


def main() -> int:
    failures: list[str] = []
    for rel in tracked_files():
        normalized = rel.replace("\\", "/")
        for part in DENY_PATH_PARTS:
            if part in normalized:
                failures.append(f"tracked forbidden path: {rel}")

        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            continue

        for pattern in PATTERNS:
            if pattern.search(text):
                failures.append(f"secret-like content in {rel}: {pattern.pattern}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("OK: no tracked local tokens, private keys, local certs, or build credentials found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
