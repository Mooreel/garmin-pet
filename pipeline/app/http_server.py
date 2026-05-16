"""HTTP routes and static file serving for the local pipeline UI."""

from __future__ import annotations

import json
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
from urllib.parse import urlparse

from . import bridge, petdex, watch
from .configuration import (
    build_and_deploy_config,
    build_config,
    config_from_payload,
    current_config,
    delete_config_history,
    history_config,
    read_config_history,
    restore_history_pet,
    security_check,
    write_local_config,
)
from .core import DEVICES_PATH, ROOT, WEB, WORK, read_json, run_step
from .pets import import_petdex_pet, pet_snapshot_preview_path, save_upload


def json_response(handler: BaseHTTPRequestHandler, payload, status: int = 200) -> None:
    encoded = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def static_content_type(path) -> str:
    if path.suffix == ".html":
        return "text/html; charset=utf-8"
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    if path.suffix == ".js":
        return "application/javascript; charset=utf-8"
    if path.suffix == ".png":
        return "image/png"
    if path.suffix == ".webp":
        return "image/webp"
    if path.suffix == ".json":
        return "application/json; charset=utf-8"
    return "application/octet-stream"


def static_cache_control(path) -> str:
    resolved = path.resolve()
    cacheable_roots = (
        ROOT / "resources" / "images",
        WEB / "assets" / "devices",
    )
    if any(root in resolved.parents for root in cacheable_roots):
        return "public, max-age=300"
    return "no-store"


def send_static(handler: BaseHTTPRequestHandler, path, root) -> bool:
    if not path.exists() or root not in path.resolve().parents:
        return False
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", static_content_type(path))
    handler.send_header("Cache-Control", static_cache_control(path))
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
    return True


class Handler(BaseHTTPRequestHandler):
    def pipeline_config(self, config: dict) -> dict:
        return bridge.apply_pipeline_bridge(config, self.headers, self.server.server_address)

    def bridge_status(self, config: dict | None = None) -> dict:
        return bridge.bridge_status(self.headers, self.server.server_address, config or current_config())

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if bridge.handle_bridge_get(self, parsed.path, parsed.query):
            return
        if parsed.path == "/api/status":
            config = self.pipeline_config(current_config())
            json_response(
                self,
                {
                    "config": config,
                    "configHistory": read_config_history(),
                    "bridge": self.bridge_status(),
                    "devices": read_json(DEVICES_PATH, {}),
                    "watch": watch.status(),
                    "build": {"exists": (ROOT / "build" / "CodexPet.prg").exists()},
                    "git": run_step(["git", "status", "--short"], timeout=10),
                },
            )
            return
        if parsed.path == "/api/watch-status":
            json_response(
                self,
                {
                    "ok": True,
                    "watch": watch.status(),
                    "build": {"exists": (ROOT / "build" / "CodexPet.prg").exists()},
                },
            )
            return
        if parsed.path == "/api/bridge-status":
            json_response(self, {"ok": True, "bridge": self.bridge_status(), "payload": bridge.latest_payload()})
            return
        if parsed.path == "/api/devices":
            json_response(self, read_json(DEVICES_PATH, {}))
            return
        if parsed.path == "/api/config-history":
            json_response(self, {"ok": True, "configHistory": read_config_history()})
            return
        if parsed.path.startswith("/api/config-history/") and parsed.path.endswith("/pet-preview"):
            parts = parsed.path.strip("/").split("/")
            history_id = parts[2] if len(parts) == 4 else ""
            preview = pet_snapshot_preview_path(history_id)
            if preview is not None and send_static(self, preview, WORK):
                return
            fallback = ROOT / "resources" / "images" / "pet_large_idle_0.png"
            if send_static(self, fallback, ROOT):
                return
            self.send_error(404)
            return
        if parsed.path == "/api/petdex/search":
            payload, status = petdex.search(parsed.query)
            json_response(self, payload, status)
            return

        if parsed.path.startswith("/resources/"):
            asset = ROOT / parsed.path.lstrip("/")
            if not send_static(self, asset, ROOT):
                self.send_error(404)
            return
        if parsed.path.startswith("/api/"):
            json_response(self, {"ok": False, "message": f"Unknown API route: {parsed.path}"}, 404)
            return

        path = WEB / (parsed.path.lstrip("/") or "index.html")
        if path.is_dir():
            path = path / "index.html"
        if not send_static(self, path, WEB):
            self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8") or "{}")
        parsed = urlparse(self.path)

        if parsed.path == "/api/config":
            config = write_local_config(self.pipeline_config(payload), "saved")
            json_response(self, {"ok": True, "config": config, "configHistory": read_config_history(), "bridge": self.bridge_status()})
            return
        if parsed.path == "/api/config/restore":
            history_id = str(payload.get("id") or payload.get("historyId") or "")
            pet_restore = restore_history_pet(history_id)
            config = history_config(history_id, restore_pet=False)
            if config is None:
                json_response(self, {"ok": False, "message": "Saved configuration not found."}, 404)
                return
            config = write_local_config(self.pipeline_config(config), "restored")
            json_response(self, {"ok": True, "config": config, "configHistory": read_config_history(), "bridge": self.bridge_status(), "petRestore": pet_restore})
            return
        if parsed.path == "/api/config/delete":
            deleted = delete_config_history(str(payload.get("id") or payload.get("historyId") or ""))
            if not deleted:
                json_response(self, {"ok": False, "message": "Saved configuration not found."}, 404)
                return
            json_response(self, {"ok": True, "configHistory": read_config_history()})
            return
        if parsed.path == "/api/pet/upload":
            json_response(self, save_upload(payload))
            return
        if parsed.path == "/api/petdex/import":
            result = import_petdex_pet(payload)
            json_response(self, result, 200 if result.get("ok") else 400)
            return
        if parsed.path == "/api/build":
            try:
                config = self.pipeline_config(config_from_payload(payload))
            except KeyError as exc:
                json_response(self, {"ok": False, "message": str(exc)}, 404)
                return
            result, status = build_config(config, "build")
            result["bridge"] = self.bridge_status()
            json_response(self, result, status)
            return
        if parsed.path == "/api/build-deploy":
            try:
                config = self.pipeline_config(config_from_payload(payload))
            except KeyError as exc:
                json_response(self, {"ok": False, "message": str(exc)}, 404)
                return
            result, status = build_and_deploy_config(config)
            result["bridge"] = self.bridge_status()
            json_response(self, result, status)
            return
        if parsed.path == "/api/deploy":
            if payload.get("historyId"):
                try:
                    config = self.pipeline_config(config_from_payload(payload))
                except KeyError as exc:
                    json_response(self, {"ok": False, "message": str(exc)}, 404)
                    return
                result, status = build_and_deploy_config(config)
                result["bridge"] = self.bridge_status()
                json_response(self, result, status)
                return
            result = run_step(["scripts/install_to_watch.sh"], timeout=120)
            result["config"] = current_config()
            result["configHistory"] = read_config_history()
            result["bridge"] = self.bridge_status()
            json_response(self, result, 200 if result["ok"] else 500)
            return
        if parsed.path == "/api/security":
            result = security_check()
            json_response(self, result, 200 if result["ok"] else 500)
            return
        if parsed.path.startswith("/api/"):
            json_response(self, {"ok": False, "message": f"Unknown API route: {parsed.path}"}, 404)
            return

        self.send_error(404)

    def log_message(self, fmt: str, *args) -> None:
        print(fmt % args, flush=True)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Local web pipeline for configuring, previewing, building, and deploying pets.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()

    WORK.mkdir(parents=True, exist_ok=True)
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        if exc.errno in (errno.EADDRINUSE, 48):
            print(
                f"Garmin pet pipeline is already running or port {args.port} is in use.\n"
                f"Open http://127.0.0.1:{args.port} or start another copy with: "
                f"python3 pipeline/server.py --port {args.port + 1}",
                file=sys.stderr,
            )
            raise SystemExit(2) from None
        raise
    watch_url = bridge.bridge_url(None, server.server_address)
    print(f"Garmin pet pipeline UI: http://127.0.0.1:{args.port}")
    print(f"Garmin watch bridge: {watch_url}")
    server.serve_forever()
