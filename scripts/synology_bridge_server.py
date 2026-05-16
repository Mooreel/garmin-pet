#!/usr/bin/env python3
"""Small always-on Garmin bridge for a Synology NAS.

The local Mac pipeline still builds and deploys the Connect IQ app. This server
only keeps the watch-facing `/garmin/latest` endpoint available on the LAN.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import http.client
import json
from pathlib import Path
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
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
    def __init__(self, state_dir: Path, pipeline_url: str) -> None:
        self.state_dir = state_dir
        self.payload_path = state_dir / "latest.json"
        self.token_path = state_dir / "bridge_token.txt"
        self.pipeline_url = pipeline_url.rstrip("/")

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

    def send_bytes(self, data: bytes, status: int, headers: dict[str, str]) -> None:
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() in {"connection", "content-length", "transfer-encoding", "content-encoding"}:
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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

        if self.proxy_to_pipeline("GET"):
            return

        if parsed.path in {"", "/"}:
            self.send_dashboard()
            return

        self.send_json({"ok": False, "message": f"Unknown route: {parsed.path}"}, 404)

    def send_dashboard(self) -> None:
        payload = self.state.latest_payload()
        pet = payload.get("pet", {}) if isinstance(payload.get("pet"), dict) else {}
        messages = payload.get("messages", [])
        top = messages[0] if isinstance(messages, list) and messages and isinstance(messages[0], dict) else {}
        pet_name = html.escape(str(pet.get("displayName") or "Codex Pet"))
        pet_state = html.escape(str(pet.get("state") or "idle"))
        updated = html.escape(str(payload.get("updatedAt") or payload.get("generatedAt") or ""))
        latest = html.escape(str(top.get("body") or payload.get("summary") or "No payload published yet."))
        body = (
            "<!doctype html><meta charset='utf-8'>"
            "<title>Garmin Pet Dashboard</title>"
            "<style>"
            "body{font:16px system-ui;margin:0;min-height:100vh;background:#eef4ef;color:#102018;display:grid;place-items:center}"
            "main{width:min(680px,calc(100vw - 36px));background:#fff;border:1px solid #cddbd1;border-radius:18px;padding:28px;box-shadow:0 18px 60px #17352220}"
            "h1{margin:0 0 10px;font-size:28px} p{line-height:1.5} code{background:#eef4ef;border-radius:6px;padding:2px 6px}"
            ".status{display:inline-flex;gap:8px;align-items:center;background:#d9fbe2;color:#0d5f28;border-radius:999px;padding:7px 11px;font-weight:800}"
            ".grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}.card{border:1px solid #dbe7df;border-radius:12px;padding:14px;background:#fbfdfb}"
            "strong{display:block;margin-bottom:6px}.muted{color:#587060}"
            "</style>"
            "<main>"
            "<span class='status'>Online</span>"
            "<h1>Garmin Pet Dashboard</h1>"
            "<p>The Synology watch bridge is serving the latest payload for your Garmin app.</p>"
            "<div class='grid'>"
            f"<section class='card'><strong>Pet</strong><span>{pet_name}</span></section>"
            f"<section class='card'><strong>State</strong><span>{pet_state}</span></section>"
            f"<section class='card'><strong>Updated</strong><span>{updated}</span></section>"
            f"<section class='card'><strong>Endpoint</strong><code>{BRIDGE_PATH}</code></section>"
            "</div>"
            f"<p><strong>Latest</strong>{latest}</p>"
            "<p class='muted'>Publish updates from the Mac with <code>scripts/synology/publish_payload.sh</code>.</p>"
            "</main>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

    def do_POST(self) -> None:
        if self.proxy_to_pipeline("POST"):
            return
        self.send_json({"ok": False, "message": f"Unknown route: {urlparse(self.path).path}"}, 404)

    def proxy_to_pipeline(self, method: str) -> bool:
        if not self.state.pipeline_url:
            return False

        parsed = urlparse(self.path)
        if parsed.path in {"/health", BRIDGE_PATH, "/api/payload"}:
            return False

        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else None
        target = f"{self.state.pipeline_url}{self.path}"
        target_host = urlparse(self.state.pipeline_url).netloc
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in {"host", "connection", "content-length", "accept-encoding"}
        }
        headers["Host"] = target_host

        try:
            with urlopen(Request(target, data=body, headers=headers, method=method), timeout=8) as response:
                self.send_bytes(response.read(), response.status, dict(response.headers.items()))
                return True
        except HTTPError as exc:
            self.send_bytes(exc.read(), exc.code, dict(exc.headers.items()))
            return True
        except (OSError, URLError, socket.timeout, http.client.HTTPException):
            if method == "GET" and parsed.path in {"", "/"}:
                return False
            self.send_json(
                {
                    "ok": False,
                    "message": "Mac pipeline is not reachable from Synology right now.",
                    "pipelineUrl": self.state.pipeline_url,
                },
                503,
            )
            return True

    def log_message(self, fmt: str, *args) -> None:
        print(fmt % args, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--state-dir", default=".")
    parser.add_argument("--pipeline-url", default="")
    args = parser.parse_args()

    state_dir = Path(args.state_dir).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    Handler.state = BridgeState(state_dir, args.pipeline_url)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Garmin Pet Synology bridge: http://{args.host}:{args.port}{BRIDGE_PATH}", flush=True)
    if args.pipeline_url:
        print(f"Mac pipeline proxy: {args.pipeline_url}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
