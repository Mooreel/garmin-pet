"""Local configuration, saved recipes, and build/deploy orchestration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlparse

from .core import (
    CONFIG_HISTORY,
    DEVICES_PATH,
    EXAMPLE_CONFIG,
    LOCAL_CONFIG,
    MAX_CONFIG_HISTORY,
    PYTHON,
    read_json,
    run_step,
    slug,
    write_json,
)
from .pets import current_pet_identity, restore_pet_snapshot, snapshot_current_pet


def merge_config(overrides: dict | None) -> dict:
    config = read_json(EXAMPLE_CONFIG, {})
    overrides = overrides or {}
    merged = dict(config)
    merged.update({key: value for key, value in overrides.items() if key != "theme"})
    merged["bridgeMode"] = str(merged.get("bridgeMode") or "auto")
    merged["theme"] = dict(config.get("theme", {}))
    if isinstance(overrides.get("theme"), dict):
        merged["theme"].update(overrides.get("theme", {}))
    return merged


def current_config() -> dict:
    return merge_config(read_json(LOCAL_CONFIG, {}))


def device_by_id(device_id: str) -> dict | None:
    devices = read_json(DEVICES_PATH, {}).get("devices", [])
    for device in devices:
        if device.get("id") == device_id:
            return device
    return None


def read_config_history() -> list[dict]:
    history = read_json(CONFIG_HISTORY, [])
    if not isinstance(history, list):
        return []
    deduped: list[dict] = []
    seen: set[str] = set()
    for entry in history:
        if not isinstance(entry, dict):
            continue
        key = recipe_key(entry.get("config", {}), entry.get("petSnapshot") or entry.get("pet") or {})
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped[:MAX_CONFIG_HISTORY]


def write_config_history(history: list[dict]) -> None:
    write_json(CONFIG_HISTORY, history[:MAX_CONFIG_HISTORY])


def recipe_key(config: dict, pet: dict | None = None) -> str:
    normalized = merge_config(config)
    pet_name = str(normalized.get("petDisplayName") or "Codex Pet").strip().lower() or "codex pet"
    device = str(normalized.get("device") or "fr265s").strip().lower() or "fr265s"
    pet_identity = pet or {}
    pet_id = str(pet_identity.get("pet") or pet_identity.get("id") or "").strip().lower()
    pet_source = str(pet_identity.get("source") or "").strip().lower()
    return json.dumps(
        {"device": device, "pet": pet_name, "petId": pet_id, "petSource": pet_source},
        sort_keys=True,
        separators=(",", ":"),
    )


def config_label(config: dict) -> str:
    device_id = str(config.get("device") or "fr265s")
    device = device_by_id(device_id) or {}
    pet_name = str(config.get("petDisplayName") or "Codex Pet").strip() or "Codex Pet"
    bridge_url = str(config.get("bridgeUrl") or "").strip()
    host = "no bridge"
    if bridge_url:
        parsed = urlparse(bridge_url)
        host = parsed.netloc or parsed.path or "bridge set"
    return f"{pet_name} / {device.get('name') or device_id} / {host}"


def record_config(config: dict, source: str) -> list[dict]:
    normalized = merge_config(config)
    pet_identity = current_pet_identity()
    key = recipe_key(normalized, pet_identity)
    history = [
        entry for entry in read_config_history()
        if recipe_key(entry.get("config", {}), entry.get("petSnapshot") or entry.get("pet") or {}) != key
    ]
    created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    entry_id = f"{created_at.replace(':', '').replace('-', '').replace('.', '')}-{slug(config_label(normalized))}"
    pet_snapshot = snapshot_current_pet(entry_id)
    history.insert(
        0,
        {
            "id": entry_id,
            "createdAt": created_at,
            "source": source,
            "label": config_label(normalized),
            "petSnapshot": pet_snapshot,
            "config": normalized,
        },
    )
    write_config_history(history)
    return history[:MAX_CONFIG_HISTORY]


def write_local_config(config: dict, source: str = "saved") -> dict:
    normalized = merge_config(config)
    write_json(LOCAL_CONFIG, normalized)
    record_config(normalized, source)
    return normalized


def history_entry(history_id: str) -> dict | None:
    for entry in read_config_history():
        if str(entry.get("id")) == history_id and isinstance(entry.get("config"), dict):
            return entry
    return None


def restore_history_pet(history_id: str) -> dict:
    entry = history_entry(history_id)
    if entry is None:
        return {"ok": False, "restored": False, "message": f"Saved configuration not found: {history_id}"}
    return restore_pet_snapshot(entry.get("petSnapshot"))


def history_config(history_id: str, restore_pet: bool = True) -> dict | None:
    entry = history_entry(history_id)
    if entry is not None:
        if restore_pet:
            restore_history_pet(history_id)
        return merge_config(entry["config"])
    return None


def delete_config_history(history_id: str) -> bool:
    history = read_config_history()
    updated = [entry for entry in history if str(entry.get("id")) != history_id]
    if len(updated) == len(history):
        return False
    write_config_history(updated)
    return True


def config_from_payload(payload: dict) -> dict:
    if payload.get("historyId"):
        config = history_config(str(payload.get("historyId")))
        if config is None:
            raise KeyError(f"Saved configuration not found: {payload.get('historyId')}")
        return config
    if isinstance(payload.get("config"), dict):
        config = merge_config(payload["config"])
    else:
        config = current_config()
    if payload.get("device"):
        config["device"] = str(payload.get("device"))
    return config


def security_check() -> dict:
    return run_step([PYTHON, "scripts/security_check.py"], timeout=30)


def build_config(config: dict, source: str = "build") -> tuple[dict, int]:
    saved = write_local_config(config, source)
    security = security_check()
    if not security["ok"]:
        return (
            {
                "ok": False,
                "message": "Security check must pass before building.",
                "security": security,
                "config": saved,
                "configHistory": read_config_history(),
            },
            400,
        )

    device = str(saved.get("device") or "fr265s")
    profile = device_by_id(device)
    if profile is None:
        return {"ok": False, "message": f"Unknown Garmin device profile: {device}", "config": saved, "configHistory": read_config_history()}, 400
    if not profile.get("buildEnabled"):
        return (
            {
                "ok": False,
                "message": f"{profile.get('name', device)} is preview-only. Add it to manifest.xml and set buildEnabled after monkeyc verifies the target.",
                "config": saved,
                "configHistory": read_config_history(),
            },
            400,
        )
    result = run_step([PYTHON, "scripts/configured_build.py", "--config", str(LOCAL_CONFIG), "--device", device], timeout=180)
    result["security"] = security
    result["config"] = current_config()
    result["configHistory"] = read_config_history()
    return result, 200 if result["ok"] else 500


def build_and_deploy_config(config: dict) -> tuple[dict, int]:
    build_result, build_status = build_config(config, "build-deploy")
    if not build_result.get("ok"):
        return build_result, build_status

    deploy_result = run_step(["scripts/install_to_watch.sh"], timeout=120)
    output = "\n\n".join(part for part in [build_result.get("output", ""), deploy_result.get("output", "")] if part)
    return (
        {
            "ok": deploy_result["ok"],
            "code": deploy_result["code"],
            "output": output,
            "build": build_result,
            "deploy": deploy_result,
            "config": current_config(),
            "configHistory": read_config_history(),
        },
        200 if deploy_result["ok"] else 500,
    )
