#!/usr/bin/env python3
"""Export Garmin-sized frames from a Codex 8x9 pet spritesheet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


ROWS = {
    "idle": 0,
    "waving": 3,
    "jumping": 4,
    "failed": 5,
    "review": 8,
    "sleeping": 6,
}

GARMIN_STATES = [
    "idle",
    "waving",
    "jumping",
    "failed",
    "review",
    "sleeping",
]


def clean_watch_artifacts(image: Image.Image) -> Image.Image:
    """Remove chroma-key halo/shadow pixels that render as rings on-device."""
    cleaned = image.copy()
    pixels = cleaned.load()
    for y in range(cleaned.height):
        for x in range(cleaned.width):
            r, g, b, a = pixels[x, y]
            purple_halo = r > 45 and b > 45 and g < 70 and abs(r - b) < 120
            if a < 160 or purple_halo:
                pixels[x, y] = (0, 0, 0, 0)
            elif a < 255:
                pixels[x, y] = (r, g, b, 255)
    return cleaned


def trim_alpha(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return image
    return image.crop(bbox)


def export_frame_set(sheet: Image.Image, row: int, output_dir: Path, size: int, prefix: str) -> list[str]:
    cell_w = sheet.width // 8
    cell_h = sheet.height // 9
    images_dir = output_dir / "resources" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    frame_files: list[str] = []
    last_visible: Image.Image | None = None
    for col in range(8):
        cell = sheet.crop((col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h))
        if cell.getchannel("A").getbbox() is None and last_visible is not None:
            cell = last_visible.copy()

        trimmed = trim_alpha(cell)
        trimmed.thumbnail((size, size), Image.Resampling.LANCZOS)
        if trimmed.getchannel("A").getbbox() is not None:
            last_visible = cell

        frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        frame.alpha_composite(trimmed, ((size - trimmed.width) // 2, (size - trimmed.height) // 2))
        frame = clean_watch_artifacts(frame)
        path = images_dir / f"{prefix}_{col}.png"
        frame.save(path)
        frame_files.append(str(path.relative_to(output_dir)))

    return frame_files


def export_frames(
    pet_dir: Path,
    output_dir: Path,
    state: str,
    large_size: int,
    all_states: bool,
) -> dict[str, object]:
    meta = json.loads((pet_dir / "pet.json").read_text(encoding="utf-8"))
    sheet_path = pet_dir / meta.get("spritesheetPath", "spritesheet.webp")
    sheet = Image.open(sheet_path).convert("RGBA")
    cell_w = sheet.width // 8
    cell_h = sheet.height // 9

    images_dir = output_dir / "resources" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    state_frame_files: dict[str, list[str]] = {}
    if all_states:
        for state_name in GARMIN_STATES:
            state_frame_files[state_name] = export_frame_set(
                sheet,
                ROWS[state_name],
                output_dir,
                large_size,
                "pet_large_" + state_name.replace("-", "_"),
            )
    else:
        state_frame_files[state] = export_frame_set(
            sheet,
            ROWS[state],
            output_dir,
            large_size,
            "pet_large_" + state.replace("-", "_"),
        )

    icon_path = images_dir / "pet_large_idle_0.png"
    if not icon_path.exists():
        icon_path = images_dir / f"pet_large_{state.replace('-', '_')}_0.png"
    icon_source = Image.open(icon_path).convert("RGBA")
    icon_bg = Image.new("RGBA", (60, 60), (18, 20, 24, 255))
    icon_source.thumbnail((50, 50), Image.Resampling.LANCZOS)
    icon_bg.alpha_composite(icon_source, ((60 - icon_source.width) // 2, (60 - icon_source.height) // 2))
    icon_bg.save(images_dir / "launcher_icon.png")

    return {
        "pet": meta.get("id", pet_dir.name),
        "displayName": meta.get("displayName", pet_dir.name),
        "state": state,
        "source": str(sheet_path),
        "cell": {"width": cell_w, "height": cell_h},
        "largeExportedSize": large_size,
        "stateLargeFrames": state_frame_files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pet-dir", default=str(Path.home() / ".codex" / "pets" / "retro"))
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--state", choices=sorted(ROWS), default="idle")
    parser.add_argument("--large-size", type=int, default=160)
    parser.add_argument("--all-states", action="store_true")
    args = parser.parse_args()

    manifest = export_frames(
        Path(args.pet_dir),
        Path(args.output_dir),
        args.state,
        args.large_size,
        args.all_states,
    )
    out = Path(args.output_dir) / "resources" / "images" / "pet_export_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
