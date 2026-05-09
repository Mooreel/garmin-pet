#!/usr/bin/env python3
"""Validate the local Garmin Pet project without requiring the Connect IQ SDK."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(path: str) -> Path:
    target = ROOT / path
    if not target.exists():
        raise AssertionError(f"Missing {path}")
    return target


def main() -> None:
    for path in [
        "manifest.xml",
        "monkey.jungle",
        "source/CodexPetApp.mc",
        "source/CodexStateModel.mc",
        "source/DashboardView.mc",
        "source/DashboardDelegate.mc",
        "source/CodexTheme.mc",
        "source/CodexSettings.mc",
        "source/CodexBuildConfig.mc",
        "source/CodexPetSprites.mc",
        "resources/strings/strings.xml",
        "resources/drawables/drawables.xml",
        "resources/properties/properties.xml",
        "resources/settings/settings.xml",
        "samples/latest.json",
        "scripts/export_pet_frames.py",
        "scripts/build.sh",
        "scripts/setup_mac.sh",
        "scripts/start.sh",
        "scripts/install_to_watch.sh",
        "scripts/install_pipeline_launch_agent.sh",
        "scripts/configured_build.py",
        "scripts/security_check.py",
        "scripts/mtp_send_to_folder.c",
        "config/devices.json",
        "pipeline/local.example.json",
        "pipeline/server.py",
        "pipeline/app/bridge.py",
        "pipeline/web/index.html",
        "pipeline/web/styles.css",
        "pipeline/web/app.js",
    ]:
        require(path)

    ET.parse(require("manifest.xml"))
    ET.parse(require("resources/strings/strings.xml"))
    ET.parse(require("resources/drawables/drawables.xml"))
    ET.parse(require("resources/properties/properties.xml"))
    ET.parse(require("resources/settings/settings.xml"))

    payload = json.loads(require("samples/latest.json").read_text(encoding="utf-8"))
    for key in ["updatedAt", "summary", "status", "mood", "progress", "pet", "messages"]:
        if key not in payload:
            raise AssertionError(f"samples/latest.json missing {key}")
    if not payload["messages"]:
        raise AssertionError("samples/latest.json must contain at least one message")

    devices = json.loads(require("config/devices.json").read_text(encoding="utf-8"))
    if "devices" not in devices or not devices["devices"]:
        raise AssertionError("config/devices.json must define at least one watch")
    manifest_text = require("manifest.xml").read_text(encoding="utf-8")
    default_device = devices.get("default")
    if not default_device or f'id="{default_device}"' not in manifest_text:
        raise AssertionError("manifest.xml must include the default build target")
    for device in devices["devices"]:
        if device.get("buildEnabled") and f'id="{device["id"]}"' not in manifest_text:
            raise AssertionError(f"manifest.xml missing build-enabled device {device['id']}")

    for index in range(8):
        for state in ["idle", "waving", "jumping", "failed", "review", "sleeping"]:
            require(f"resources/images/pet_large_{state}_{index}.png")
    require("resources/images/launcher_icon.png")

    sys.path.insert(0, str(ROOT))
    from pipeline.app.bridge import latest_payload

    live_payload = latest_payload()
    if "messages" not in live_payload or "pet" not in live_payload:
        raise AssertionError("Bridge payload does not match watch contract")

    print("OK: project files, resources, sample payload, and bridge contract are present.")


if __name__ == "__main__":
    main()
