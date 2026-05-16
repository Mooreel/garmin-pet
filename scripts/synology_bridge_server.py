#!/usr/bin/env python3
"""Small always-on Garmin bridge for a Synology NAS.

The local Mac pipeline still builds and deploys the Connect IQ app. This server
only keeps the watch-facing `/garmin/latest` endpoint available on the LAN.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BRIDGE_PATH = "/garmin/latest"
MAX_BODY_BYTES = 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def read_json(path: Path, fallback: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback
    return value if isinstance(value, dict) else fallback


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def fallback_payload() -> dict:
    return {
        "generatedAt": utc_now(),
        "pet": {"id": "monk", "displayName": "Monk", "state": "idle"},
        "messages": [
            {
                "title": "Codex",
                "body": "Synology bridge is online. Publish from the Mac pipeline to show live Codex updates.",
                "tone": "info",
                "time": "",
                "eventType": "idle",
                "alert": False,
                "alertId": "",
            }
        ],
    }


class BridgeState:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.payload_path = state_dir / "latest.json"
        self.token_path = state_dir / "bridge_token.txt"

    @property
    def token(self) -> str:
        return read_text(self.token_path)

    def latest_payload(self) -> dict:
        return read_json(self.payload_path, fallback_payload())

    def publish(self, payload: dict) -> None:
        payload = dict(payload)
        payload.setdefault("generatedAt", utc_now())
        write_json(self.payload_path, payload)


class Handler(BaseHTTPRequestHandler):
    state: BridgeState

    def send_json(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def authorized(self, parsed) -> bool:
        token = self.state.token
        if not token:
            return True
        values = parse_qs(parsed.query).get("token", [])
        header_token = self.headers.get("X-Garmin-Pet-Token", "")
        return header_token == token or bool(values and values[0] == token)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            payload = self.state.latest_payload()
            self.send_json(
                {
                    "ok": True,
                    "bridgePath": BRIDGE_PATH,
                    "payloadGeneratedAt": payload.get("generatedAt", ""),
                    "tokenRequired": bool(self.state.token),
                }
            )
            return

        if parsed.path == BRIDGE_PATH:
            if not self.authorized(parsed):
                self.send_json({"ok": False, "message": "Unauthorized bridge token."}, 401)
                return
            self.send_json(self.state.latest_payload())
            return

        if parsed.path in {"", "/"}:
            body = (
                "<!doctype html><meta charset='utf-8'>"
                "<title>Garmin Pet Bridge</title>"
                "<style>body{font:16px system-ui;margin:3rem;max-width:42rem;line-height:1.45}</style>"
                "<h1>Garmin Pet Bridge</h1>"
                "<p>The Synology watch bridge is online.</p>"
                f"<p>Endpoint: <code>{BRIDGE_PATH}</code></p>"
                "<p>Publish updates from the Mac pipeline with <code>scripts/synology/publish_payload.sh</code>.</p>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_json({"ok": False, "message": f"Unknown route: {parsed.path}"}, 404)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/payload":
            self.send_json({"ok": False, "message": f"Unknown route: {parsed.path}"}, 404)
            return
        if not self.authorized(parsed):
            self.send_json({"ok": False, "message": "Unauthorized bridge token."}, 401)
            return

        length = min(int(self.headers.get("Content-Length", "0")), MAX_BODY_BYTES)
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            self.send_json({"ok": False, "message": "Invalid JSON payload."}, 400)
            return
        if not isinstance(payload, dict):
            self.send_json({"ok": False, "message": "Payload must be a JSON object."}, 400)
            return

        self.state.publish(payload)
        self.send_json({"ok": True, "payloadGeneratedAt": self.state.latest_payload().get("generatedAt", "")})

    def log_message(self, fmt: str, *args) -> None:
        print(fmt % args, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--state-dir", default=".")
    args = parser.parse_args()

    state_dir = Path(args.state_dir).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    Handler.state = BridgeState(state_dir)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Garmin Pet Synology bridge: http://{args.host}:{args.port}{BRIDGE_PATH}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
