"""Manual and Petdex pet import flows."""

from __future__ import annotations

import base64
import binascii
import json
import re
import shutil
import zipfile
from pathlib import Path

from .core import PYTHON, ROOT, WORK, read_json, run_step, slug, write_json
from .petdex import MAX_REMOTE_ASSET_BYTES, MAX_REMOTE_JSON_BYTES, PETDEX_BASE, fetch_remote_bytes


def safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    base = target.resolve()
    for member in archive.infolist():
        destination = (target / member.filename).resolve()
        if base != destination and base not in destination.parents:
            raise ValueError(f"Unsafe ZIP path: {member.filename}")
    archive.extractall(target)


def decode_data_url(data_url: str) -> bytes:
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    return base64.b64decode(data_url)


def safe_upload_path(raw_path: str) -> Path:
    normalized = raw_path.replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"Unsafe upload path: {raw_path}")
    return Path(*parts)


def find_pet_dir(upload_root: Path) -> Path | None:
    candidates = sorted(
        (path.parent for path in upload_root.rglob("pet.json") if (path.parent / "spritesheet.webp").exists()),
        key=lambda path: (len(path.parts), str(path)),
    )
    return candidates[0] if candidates else None


def exported_pet_manifest() -> dict:
    return read_json(ROOT / "resources" / "images" / "pet_export_manifest.json", {})


def exported_pet_files(manifest: dict) -> list[Path]:
    images_dir = ROOT / "resources" / "images"
    files: list[str] = ["launcher_icon.png", "pet_export_manifest.json"]
    for key in ["frames", "miniFrames", "largeFrames"]:
        value = manifest.get(key)
        if isinstance(value, list):
            files.extend(str(item) for item in value)
    state_frames = manifest.get("stateLargeFrames")
    if isinstance(state_frames, dict):
        for value in state_frames.values():
            if isinstance(value, list):
                files.extend(str(item) for item in value)

    paths: list[Path] = []
    seen: set[Path] = set()
    for item in files:
        path = ROOT / item if item.startswith("resources/") else images_dir / item
        try:
            resolved = path.resolve()
        except Exception:
            continue
        if images_dir.resolve() in resolved.parents or resolved == images_dir.resolve():
            if resolved.exists() and resolved not in seen:
                seen.add(resolved)
                paths.append(resolved)
    return paths


def current_pet_identity() -> dict:
    manifest = exported_pet_manifest()
    return {
        "pet": str(manifest.get("pet") or ""),
        "displayName": str(manifest.get("displayName") or ""),
        "source": str(manifest.get("source") or ""),
    }


def snapshot_current_pet(recipe_id: str) -> dict | None:
    manifest = exported_pet_manifest()
    files = exported_pet_files(manifest)
    if not files:
        return None

    snapshot_dir = WORK / "recipe_pets" / slug(recipe_id)
    images_dir = snapshot_dir / "images"
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    root_images = (ROOT / "resources" / "images").resolve()
    copied = 0
    for source in files:
        relative = source.relative_to(root_images)
        destination = images_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1

    return {
        "id": slug(recipe_id),
        "pet": str(manifest.get("pet") or ""),
        "displayName": str(manifest.get("displayName") or ""),
        "source": str(manifest.get("source") or ""),
        "fileCount": copied,
        "previewUrl": f"/api/config-history/{recipe_id}/pet-preview",
    }


def pet_snapshot_preview_path(recipe_id: str) -> Path | None:
    path = WORK / "recipe_pets" / slug(recipe_id) / "images" / "pet_large_idle_0.png"
    return path if path.exists() else None


def restore_pet_snapshot(snapshot: dict | None) -> dict:
    if not isinstance(snapshot, dict) or not snapshot.get("id"):
        return {"ok": True, "restored": False, "message": "Saved recipe has no pet snapshot."}

    images_dir = WORK / "recipe_pets" / slug(str(snapshot["id"])) / "images"
    if not images_dir.exists():
        return {"ok": False, "restored": False, "message": "Saved pet snapshot is missing."}

    target = ROOT / "resources" / "images"
    copied = 0
    for source in images_dir.rglob("*"):
        if not source.is_file():
            continue
        destination = target / source.relative_to(images_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1

    return {
        "ok": True,
        "restored": True,
        "fileCount": copied,
        "displayName": str(snapshot.get("displayName") or ""),
    }


def export_pet_dir(pet_dir: Path) -> dict:
    export = run_step(
        [
            PYTHON,
            "scripts/export_pet_frames.py",
            "--pet-dir",
            str(pet_dir),
            "--output-dir",
            str(ROOT),
            "--all-states",
        ],
        timeout=120,
    )
    if not export["ok"]:
        return {"ok": False, "message": "Pet export failed.", "output": export["output"]}
    meta = {}
    try:
        loaded = json.loads((pet_dir / "pet.json").read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            meta = loaded
    except Exception:
        meta = {}
    return {
        "ok": True,
        "petDir": str(pet_dir),
        "output": export["output"],
        "pet": {
            "id": str(meta.get("id") or pet_dir.name),
            "displayName": str(meta.get("displayName") or pet_dir.name),
        },
    }


def save_upload_files(payload: dict) -> dict:
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        return {"ok": False, "message": "Drop a folder containing pet.json and spritesheet.webp."}

    display_name = payload.get("displayName") or payload.get("name") or "uploaded-pet"
    pet_dir = WORK / "pets" / slug(display_name)
    if pet_dir.exists():
        shutil.rmtree(pet_dir)
    pet_dir.mkdir(parents=True, exist_ok=True)

    try:
        for item in files:
            if not isinstance(item, dict):
                continue
            rel_path = safe_upload_path(str(item.get("path") or item.get("name") or ""))
            destination = (pet_dir / rel_path).resolve()
            if pet_dir.resolve() not in destination.parents:
                raise ValueError(f"Unsafe upload path: {rel_path}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(decode_data_url(str(item.get("dataUrl") or "")))
    except (ValueError, binascii.Error) as exc:
        return {"ok": False, "message": str(exc)}

    source_dir = find_pet_dir(pet_dir)
    if source_dir is None:
        return {"ok": False, "message": "Folder must contain pet.json and spritesheet.webp in the same directory."}

    if source_dir != pet_dir:
        final_dir = WORK / "pets" / slug(display_name + "-folder")
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.copytree(source_dir, final_dir)
        pet_dir = final_dir

    return export_pet_dir(pet_dir)


def save_upload(payload: dict) -> dict:
    if payload.get("files"):
        return save_upload_files(payload)

    file_name = payload.get("name") or "pet.zip"
    data_url = payload.get("dataUrl") or ""
    display_name = payload.get("displayName") or Path(file_name).stem

    raw = decode_data_url(data_url)
    upload_dir = WORK / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / Path(file_name).name
    upload_path.write_bytes(raw)

    pet_dir = WORK / "pets" / slug(display_name)
    if pet_dir.exists():
        shutil.rmtree(pet_dir)
    pet_dir.mkdir(parents=True, exist_ok=True)

    suffix = upload_path.suffix.lower()
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(upload_path) as archive:
                safe_extract(archive, pet_dir)
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}
        source_dir = find_pet_dir(pet_dir)
        if source_dir is None:
            return {"ok": False, "message": "ZIP must contain pet.json and spritesheet.webp."}
        if source_dir != pet_dir:
            final_dir = WORK / "pets" / slug(display_name + "-package")
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(source_dir, final_dir)
            pet_dir = final_dir
    elif suffix == ".webp":
        shutil.copy2(upload_path, pet_dir / "spritesheet.webp")
        write_json(
            pet_dir / "pet.json",
            {"id": slug(display_name), "displayName": display_name, "spritesheetPath": "spritesheet.webp"},
        )
    else:
        return {"ok": False, "message": "Upload a Codex pet ZIP or spritesheet.webp."}

    return export_pet_dir(pet_dir)


def import_petdex_pet(payload: dict) -> dict:
    pet = payload.get("pet")
    if not isinstance(pet, dict):
        return {"ok": False, "message": "Choose a Petdex pet before importing."}

    petdex_slug = str(pet.get("slug") or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,90}", petdex_slug):
        return {"ok": False, "message": "Petdex result is missing a valid slug."}

    display_name = str(pet.get("displayName") or petdex_slug).strip()[:80] or petdex_slug
    pet_json_url = str(pet.get("petJsonPath") or "").strip()
    spritesheet_url = str(pet.get("spritesheetPath") or "").strip()
    if not pet_json_url or not spritesheet_url:
        return {"ok": False, "message": "Petdex result is missing pet.json or spritesheet URLs."}

    try:
        pet_json_bytes = fetch_remote_bytes(pet_json_url, MAX_REMOTE_JSON_BYTES)
        spritesheet_bytes = fetch_remote_bytes(spritesheet_url, MAX_REMOTE_ASSET_BYTES)
        meta = json.loads(pet_json_bytes.decode("utf-8"))
        if not isinstance(meta, dict):
            meta = {}
    except (RuntimeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "message": str(exc)}

    pet_dir = WORK / "pets" / f"petdex-{petdex_slug}"
    if pet_dir.exists():
        shutil.rmtree(pet_dir)
    pet_dir.mkdir(parents=True, exist_ok=True)

    meta["id"] = str(meta.get("id") or petdex_slug)
    meta["displayName"] = str(meta.get("displayName") or display_name)
    meta["spritesheetPath"] = "spritesheet.webp"
    meta["petdex"] = {
        "slug": petdex_slug,
        "url": f"{PETDEX_BASE}/pets/{petdex_slug}",
        "petJsonPath": pet_json_url,
        "spritesheetPath": spritesheet_url,
    }

    write_json(pet_dir / "pet.json", meta)
    (pet_dir / "spritesheet.webp").write_bytes(spritesheet_bytes)

    result = export_pet_dir(pet_dir)
    result["pet"] = {
        "slug": petdex_slug,
        "displayName": display_name,
        "kind": pet.get("kind"),
        "vibes": pet.get("vibes") if isinstance(pet.get("vibes"), list) else [],
        "url": f"{PETDEX_BASE}/pets/{petdex_slug}",
    }
    if result.get("ok"):
        result["message"] = f"Imported {display_name} from Petdex."
    return result
