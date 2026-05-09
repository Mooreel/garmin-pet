"""Garmin watch recognition and accessibility checks."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .core import run_step


def mounted_garmin_app_folder() -> Path | None:
    for volume in sorted(Path("/Volumes").glob("*")):
        app_folder = volume / "GARMIN" / "APPS"
        if app_folder.is_dir():
            return app_folder
    return None


def status() -> dict:
    app_folder = mounted_garmin_app_folder()
    if app_folder is not None:
        writable = os.access(app_folder, os.W_OK)
        return {
            "visible": True,
            "recognized": True,
            "accessible": writable,
            "method": "mounted-volume",
            "headline": "Garmin storage accessible" if writable else "Garmin storage recognized, but not writable",
            "message": f"Deploy will copy CODEXPET.PRG to {app_folder}." if writable else f"{app_folder} exists, but this process cannot write to it.",
            "detail": str(app_folder),
        }

    mtp_detect = shutil.which("mtp-detect")
    mtp_filetree = shutil.which("mtp-filetree")
    if mtp_detect is None:
        return {
            "visible": False,
            "recognized": False,
            "accessible": False,
            "method": "none",
            "headline": "No Garmin watch detected",
            "message": "No mounted Garmin storage was found, and libmtp detection tools are not installed.",
            "detail": "Install libmtp tools or connect the watch so it appears under /Volumes.",
        }

    result = run_step(["mtp-detect"], timeout=8)
    text = result["output"]
    recognized = "No raw devices found" not in text and ("VID=" in text or "Garmin" in text or "Forerunner" in text)
    accessible = recognized and mtp_filetree is not None
    if accessible:
        headline = "Garmin watch recognized over MTP"
        message = "The watch is reachable through libmtp and can receive a deploy."
        method = "mtp"
    elif recognized:
        headline = "Garmin watch recognized, but not deployable yet"
        message = "The USB device is visible, but mtp-filetree/libmtp deploy tooling is missing."
        method = "mtp-detected"
    else:
        headline = "No Garmin watch detected"
        message = "Connect the watch over USB. Detection updates automatically once macOS has noticed it."
        method = "none"
    return {
        "visible": recognized,
        "recognized": recognized,
        "accessible": accessible,
        "method": method,
        "headline": headline,
        "message": message,
        "detail": text[-1200:],
    }
