#!/usr/bin/env python3
"""Build with local bridge/theme settings without committing those settings."""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PROPERTIES_PATH = ROOT / "resources" / "properties" / "properties.xml"
BUILD_CONFIG_PATH = ROOT / "source" / "CodexBuildConfig.mc"
DEFAULT_CONFIG = ROOT / "pipeline" / "local.example.json"


def allow_loopback_bridge() -> bool:
    return os.environ.get("GARMIN_ALLOW_LOCALHOST_BRIDGE") == "1"


def is_loopback_bridge(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return (parsed.hostname or "").lower() in {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


def generated_bridge_url() -> str:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from pipeline.app.bridge import bridge_url

    return bridge_url(None, ("0.0.0.0", 8790))


def env_bridge_url() -> str:
    raw = os.environ.get("GARMIN_BRIDGE_URL", "").strip()
    if raw and (allow_loopback_bridge() or not is_loopback_bridge(raw)):
        return raw
    return ""


def resolved_bridge_url(config: dict) -> str:
    override = env_bridge_url()
    if override:
        return override
    if str(config.get("bridgeMode") or "auto").strip().lower() == "auto":
        return generated_bridge_url()
    raw = str(config.get("bridgeUrl") or "").strip()
    if raw and (allow_loopback_bridge() or not is_loopback_bridge(raw)):
        return raw
    return generated_bridge_url()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def color_to_number(value: str, fallback: str) -> int:
    text = str(value or fallback).strip()
    if text.startswith("#"):
        text = text[1:]
    return int(text, 16)


def render_properties(config: dict) -> str:
    theme = config.get("theme", {})
    bridge_url = html.escape(resolved_bridge_url(config), quote=False)
    pet_name = html.escape(str(config.get("petDisplayName") or "Codex Pet"), quote=False)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<resources>
  <property id="bridgeUrl" type="string">{bridge_url}</property>
  <property id="autoRefresh" type="boolean">true</property>
  <property id="hapticAlerts" type="boolean">true</property>
  <property id="petDisplayName" type="string">{pet_name}</property>
  <property id="themeSurface" type="number">{color_to_number(theme.get("surface"), "#000000")}</property>
  <property id="themePanel" type="number">{color_to_number(theme.get("panel"), "#111216")}</property>
  <property id="themeSelection" type="number">{color_to_number(theme.get("selection"), "#251B5F")}</property>
  <property id="themeInk" type="number">{color_to_number(theme.get("ink"), "#FFFFFF")}</property>
  <property id="themeSubtle" type="number">{color_to_number(theme.get("subtle"), "#A8A6B6")}</property>
  <property id="themeAccent" type="number">{color_to_number(theme.get("accent"), "#9A6CFF")}</property>
  <property id="themeReview" type="number">{color_to_number(theme.get("review"), "#32C8FF")}</property>
  <property id="themeGood" type="number">{color_to_number(theme.get("good"), "#42E76F")}</property>
  <property id="themeWarn" type="number">{color_to_number(theme.get("warn"), "#FFA754")}</property>
</resources>
"""


def render_build_config(config: dict) -> str:
    theme = config.get("theme", {})
    bridge_url = resolved_bridge_url(config).replace("\\", "\\\\").replace('"', '\\"')
    pet_name = str(config.get("petDisplayName") or "Codex Pet").replace("\\", "\\\\").replace('"', '\\"')
    return f"""const CODEX_BRIDGE_URL = "{bridge_url}";
const CODEX_PET_DISPLAY_NAME = "{pet_name}";
const CODEX_AUTO_REFRESH = true;
const CODEX_HAPTIC_ALERTS = true;
const CODEX_THEME_SURFACE = {color_to_number(theme.get("surface"), "#000000")};
const CODEX_THEME_PANEL = {color_to_number(theme.get("panel"), "#111216")};
const CODEX_THEME_SELECTION = {color_to_number(theme.get("selection"), "#251B5F")};
const CODEX_THEME_INK = {color_to_number(theme.get("ink"), "#FFFFFF")};
const CODEX_THEME_SUBTLE = {color_to_number(theme.get("subtle"), "#A8A6B6")};
const CODEX_THEME_ACCENT = {color_to_number(theme.get("accent"), "#9A6CFF")};
const CODEX_THEME_REVIEW = {color_to_number(theme.get("review"), "#32C8FF")};
const CODEX_THEME_GOOD = {color_to_number(theme.get("good"), "#42E76F")};
const CODEX_THEME_WARN = {color_to_number(theme.get("warn"), "#FFA754")};
"""


def build(config_path: Path, device: str | None = None, key: str | None = None) -> None:
    config = read_json(config_path)
    device_id = device or str(config.get("device") or "fr265s")
    key_path = key or str(config.get("developerKey") or "build/developer_key.der")
    original_properties = PROPERTIES_PATH.read_text(encoding="utf-8")
    original_build_config = BUILD_CONFIG_PATH.read_text(encoding="utf-8")
    try:
        PROPERTIES_PATH.write_text(render_properties(config), encoding="utf-8")
        BUILD_CONFIG_PATH.write_text(render_build_config(config), encoding="utf-8")
        subprocess.run([str(ROOT / "scripts" / "build.sh"), key_path, device_id], cwd=ROOT, check=True)
    finally:
        PROPERTIES_PATH.write_text(original_properties, encoding="utf-8")
        BUILD_CONFIG_PATH.write_text(original_build_config, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "pipeline" / "local.json"))
    parser.add_argument("--device")
    parser.add_argument("--key")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        config_path = DEFAULT_CONFIG
    build(config_path, args.device, args.key)


if __name__ == "__main__":
    main()
