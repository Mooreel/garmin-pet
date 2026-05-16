"""Shared Garmin bridge payload and endpoint helpers.

The browser pipeline serves the watch bridge directly, so users run one local
server and one port for both the web UI and Garmin requests.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
from typing import Any
from urllib.parse import parse_qs, urlparse

from .core import ROOT


CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
HISTORY_PATH = CODEX_HOME / "history.jsonl"
STATE_PATH = CODEX_HOME / ".codex-global-state.json"
PETS_PATH = CODEX_HOME / "pets"
SESSIONS_PATH = CODEX_HOME / "sessions"
TOKEN_PATH = Path(os.environ.get("GARMIN_BRIDGE_TOKEN_PATH", ROOT / "bridge_token.txt"))

MESSAGE_BODY_LIMIT = 480
PROMPT_BODY_LIMIT = 360
BRIDGE_PATH = "/garmin/latest"


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def ensure_bridge_token() -> str:
    env_token = os.environ.get("GARMIN_BRIDGE_TOKEN", "").strip()
    if env_token:
        return env_token

    try:
        existing = TOKEN_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        existing = ""
    if existing:
        return existing

    token = secrets.token_hex(16)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(f"{token}\n", encoding="utf-8")
    return token


def bridge_token() -> str:
    return ensure_bridge_token()


def is_authorized(query: str) -> bool:
    token = bridge_token()
    if not token:
        return True
    values = parse_qs(query).get("token", [])
    return bool(values and values[0] == token)


def _is_usable_lan_host(value: str) -> bool:
    host = value.strip().split("%", 1)[0]
    if not host or host in {"0.0.0.0", "127.0.0.1", "::1", "localhost"}:
        return False
    if host.startswith("169.254.") or host.startswith("10.211.") or host.startswith("10.37."):
        return False
    return True


def _interface_ip(name: str) -> str:
    try:
        result = subprocess.run(["ipconfig", "getifaddr", name], text=True, capture_output=True, timeout=2)
    except Exception:
        result = None
    if result is not None and result.returncode == 0:
        return result.stdout.strip()

    try:
        fallback = subprocess.run(["ifconfig", name], text=True, capture_output=True, timeout=2)
    except Exception:
        return ""
    if fallback.returncode != 0:
        return ""
    for line in fallback.stdout.splitlines():
        text = line.strip()
        if text.startswith("inet "):
            return text.split()[1]
    return ""


def _networksetup_devices(port_names: tuple[str, ...]) -> list[str]:
    try:
        result = subprocess.run(["networksetup", "-listallhardwareports"], text=True, capture_output=True, timeout=2)
    except Exception:
        return []
    if result.returncode != 0:
        return []

    devices: list[str] = []
    current_port = ""
    normalized_names = tuple(name.lower() for name in port_names)
    for line in result.stdout.splitlines():
        text = line.strip()
        if text.startswith("Hardware Port:"):
            current_port = text.split(":", 1)[1].strip().lower()
        elif text.startswith("Device:") and current_port:
            device = text.split(":", 1)[1].strip()
            if device and any(name in current_port for name in normalized_names):
                devices.append(device)
    return devices


def _ifconfig_interface_ips() -> list[tuple[str, str, bool]]:
    try:
        result = subprocess.run(["ifconfig"], text=True, capture_output=True, timeout=2)
    except Exception:
        return []
    if result.returncode != 0:
        return []

    interfaces: list[tuple[str, str, bool]] = []
    blocks: list[tuple[str, list[str]]] = []
    name = ""
    block: list[str] = []
    for line in result.stdout.splitlines():
        if line and not line.startswith(("\t", " ")):
            if name:
                blocks.append((name, block))
            name = line.split(":", 1)[0]
            block = [line]
            continue
        if name:
            block.append(line)
    if name:
        blocks.append((name, block))

    for interface, lines in blocks:
        text = "\n".join(lines)
        is_wired = "VLAN_HWTAGGING" in text
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("inet "):
                interfaces.append((interface, stripped.split()[1], is_wired))
    return interfaces


def _route_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.2)
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except Exception:
        return ""
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _host_header_host(headers: Any) -> str:
    raw = ""
    try:
        raw = str(headers.get("Host") or "")
    except Exception:
        raw = ""
    if not raw:
        return ""
    if raw.startswith("["):
        return raw.split("]", 1)[0].strip("[]")
    return raw.rsplit(":", 1)[0]


def candidate_lan_hosts(headers: Any | None = None) -> list[str]:
    wifi_devices = _networksetup_devices(("wi-fi", "airport"))
    wired_devices = _networksetup_devices(("ethernet", "thunderbolt"))
    discovered_interfaces = _ifconfig_interface_ips()
    wifi_fallback = [
        ip for name, ip, is_wired in discovered_interfaces
        if name.startswith("en") and name not in wired_devices and not is_wired
    ]
    wired_fallback = [
        ip for name, ip, is_wired in discovered_interfaces
        if name.startswith("en") and (name in wired_devices or is_wired)
    ]
    candidates = [
        os.environ.get("GARMIN_PET_HOST", ""),
        os.environ.get("GARMIN_BRIDGE_HOST", ""),
        _host_header_host(headers),
        *(_interface_ip(name) for name in wifi_devices),
        *wifi_fallback,
        *(_interface_ip(name) for name in wired_devices),
        *wired_fallback,
        _route_ip(),
    ]

    seen: set[str] = set()
    usable: list[str] = []
    for candidate in candidates:
        host = str(candidate or "").strip()
        if host and host not in seen and _is_usable_lan_host(host):
            seen.add(host)
            usable.append(host)
    return usable


def preferred_lan_host(headers: Any | None = None) -> str:
    return (candidate_lan_hosts(headers) or ["127.0.0.1"])[0]


def _server_port(server_address: Any, fallback: int = 8790) -> int:
    try:
        return int(server_address[1])
    except Exception:
        return fallback


def bridge_url(headers: Any | None, server_address: Any, scheme: str = "http") -> str:
    token = bridge_token()
    host = preferred_lan_host(headers)
    port = _server_port(server_address)
    return f"{scheme}://{host}:{port}{BRIDGE_PATH}?token={token}"


def _is_remote_bridge_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    return _is_usable_lan_host(parsed.hostname)


def apply_pipeline_bridge(config: dict, headers: Any | None, server_address: Any) -> dict:
    resolved = dict(config)
    mode = str(resolved.get("bridgeMode") or "auto").strip().lower()
    if mode == "manual" and _is_remote_bridge_url(str(resolved.get("bridgeUrl") or "")):
        resolved["bridgeMode"] = "manual"
        return resolved

    resolved["bridgeMode"] = "auto"
    resolved["bridgeUrl"] = bridge_url(headers, server_address)
    return resolved


def _tcp_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except Exception:
        return False


def _server_allows_lan(server_address: Any) -> bool:
    try:
        bind_host = str(server_address[0] or "")
    except Exception:
        bind_host = ""
    return bind_host in {"", "0.0.0.0", "::"} or _is_usable_lan_host(bind_host)


def bridge_status(headers: Any | None, server_address: Any, config: dict | None = None) -> dict:
    config = config or {}
    manual_url = str(config.get("bridgeUrl") or "").strip()
    if str(config.get("bridgeMode") or "").strip().lower() == "manual" and _is_remote_bridge_url(manual_url):
        parsed = urlparse(manual_url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        reachable = _tcp_reachable(parsed.hostname or "", port)
        return {
            "ok": reachable,
            "samePort": False,
            "path": parsed.path or BRIDGE_PATH,
            "host": parsed.hostname or "",
            "port": port,
            "url": manual_url,
            "tokenRequired": bool(parse_qs(parsed.query).get("token")),
            "lanCandidates": candidate_lan_hosts(headers),
            "lanReachableFromMac": reachable,
            "message": (
                f"Manual watch bridge is configured on {parsed.hostname}:{port}."
                if reachable
                else f"Manual watch bridge is configured on {parsed.hostname}:{port}, but this Mac cannot reach it."
            ),
        }

    host = preferred_lan_host(headers)
    port = _server_port(server_address)
    lan_host = _is_usable_lan_host(host)
    reachable = lan_host and (_server_allows_lan(server_address) or _tcp_reachable(host, port))
    if not lan_host:
        message = "No Mac LAN bridge address was detected. Set GARMIN_PET_HOST to the Mac LAN IP."
    elif reachable:
        message = f"Watch bridge is served by this pipeline on {host}:{port}."
    else:
        message = (
            f"Pipeline is running, but {host}:{port} is not reachable as a LAN bridge. "
            "Restart with scripts/start.sh or set GARMIN_PET_HOST to the Mac LAN IP."
        )
    return {
        "ok": reachable,
        "samePort": True,
        "path": BRIDGE_PATH,
        "host": host,
        "port": port,
        "url": bridge_url(headers, server_address),
        "tokenRequired": bool(bridge_token()),
        "lanCandidates": candidate_lan_hosts(headers),
        "lanReachableFromMac": reachable,
        "message": message,
    }


def recent_history(limit: int = 2) -> list[dict[str, str]]:
    if not HISTORY_PATH.exists():
        return []

    lines = HISTORY_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    messages: list[dict[str, str]] = []
    for line in reversed(lines[-250:]):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        text = str(item.get("text", "")).strip()
        if not is_meaningful_prompt(text):
            continue

        ts = item.get("ts")
        time_label = ""
        if isinstance(ts, (int, float)):
            time_label = datetime.fromtimestamp(ts).strftime("%H:%M")

        messages.append(
            {
                "title": "You",
                "body": collapse(text, PROMPT_BODY_LIMIT),
                "tone": tone_for(text),
                "time": time_label,
                "eventType": "prompt",
                "alert": False,
                "alertId": "",
            }
        )
        if len(messages) >= limit:
            break

    return messages


def recent_lines(path: Path, limit: int = 500) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return list(deque(handle, maxlen=limit))
    except Exception:
        return []


def latest_session_id() -> str | None:
    if not HISTORY_PATH.exists():
        return None

    for line in reversed(recent_lines(HISTORY_PATH, 300)):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = item.get("session_id")
        if session_id:
            return str(session_id)
    return None


def session_file_for(session_id: str | None) -> Path | None:
    if not SESSIONS_PATH.exists():
        return None

    matches: list[Path] = []
    if session_id:
        matches = list(SESSIONS_PATH.rglob(f"*{session_id}.jsonl"))

    if not matches:
        matches = list(SESSIONS_PATH.rglob("rollout-*.jsonl"))

    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def is_internal_review_text(text: str) -> bool:
    return str(text or "").startswith("The following is the Codex agent history added since your last approval assessment.")


def is_internal_review_session(path: Path) -> bool:
    user_messages = 0
    internal_messages = 0
    for line in recent_lines(path, 140):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") != "event_msg":
            continue
        payload = item.get("payload", {})
        if payload.get("type") != "user_message":
            continue
        user_messages += 1
        if is_internal_review_text(str(payload.get("message") or "")):
            internal_messages += 1
    return user_messages > 0 and user_messages == internal_messages


def newest_session_file() -> Path | None:
    if not SESSIONS_PATH.exists():
        return None

    matches = sorted(SESSIONS_PATH.rglob("rollout-*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in matches[:24]:
        if not is_internal_review_session(path):
            return path
    return matches[0] if matches else None


def active_session_file() -> Path | None:
    current = newest_session_file()
    if current is not None:
        return current
    return session_file_for(latest_session_id())


def message_time(item: dict[str, Any]) -> str:
    value = item.get("timestamp")
    if not isinstance(value, str):
        return ""
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone().strftime("%H:%M")
    except ValueError:
        return ""


def message_alert_id(item: dict[str, Any], payload_type: str, title: str, body: str) -> str:
    timestamp = str(item.get("timestamp") or "")
    session_id = str(item.get("session_id") or "")
    return collapse(f"{session_id}:{timestamp}:{payload_type}:{title}:{body}", 180)


def recent_codex_messages(limit: int = 4) -> list[dict[str, str]]:
    path = active_session_file()
    if path is None:
        return []

    lines = recent_lines(path, 700)
    parsed_items: list[tuple[int, dict[str, Any]]] = []
    task_result_by_line: dict[int, str] = {}
    latest_final_answer = ""
    for index, line in enumerate(lines):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        parsed_items.append((index, item))
        if item.get("type") != "event_msg":
            continue

        payload = item.get("payload", {})
        payload_type = payload.get("type")
        if payload_type == "agent_message" and payload.get("phase") == "final_answer":
            body = str(payload.get("message", "")).strip()
            if body:
                latest_final_answer = body
        elif payload_type == "task_complete" and latest_final_answer:
            task_result_by_line[index] = latest_final_answer
            latest_final_answer = ""

    messages: list[dict[str, str]] = []
    seen: set[str] = set()
    last_user_message_by_turn: dict[str, str] = {}
    latest_user_message = ""
    for line_index, item in reversed(parsed_items):
        if item.get("type") != "event_msg":
            continue

        payload = item.get("payload", {})
        payload_type = payload.get("type")
        turn_id = str(payload.get("turn_id") or item.get("turn_id") or "")
        title = ""
        body = ""
        tone = "info"
        alert = False
        event_type = payload_type

        if payload_type == "user_message":
            body = str(payload.get("message", "")).strip()
            if body and not is_internal_review_text(body):
                latest_user_message = collapse(body, PROMPT_BODY_LIMIT)
                if turn_id:
                    last_user_message_by_turn.setdefault(turn_id, latest_user_message)
            continue

        if payload_type == "agent_message":
            body = str(payload.get("message", "")).strip()
            phase = payload.get("phase")
            title = "Codex done" if phase == "final_answer" else "Codex"
            tone = tone_for(body)
            if phase == "final_answer":
                tone = "success"
                alert = True
                event_type = "final_answer"
        elif payload_type == "task_started":
            title = "Codex"
            body = last_user_message_by_turn.get(turn_id) or latest_user_message or "Task started"
            tone = "review"
            alert = True
        elif payload_type == "task_complete":
            title = "Codex done"
            body = task_result_by_line.get(line_index) or "Task complete"
            tone = "success"
            alert = True
        else:
            continue

        body = collapse(body, MESSAGE_BODY_LIMIT)
        key = f"{title}:{body}"
        if not body or key in seen:
            continue

        seen.add(key)
        messages.append(
            {
                "title": title,
                "body": body,
                "tone": tone,
                "time": message_time(item),
                "eventType": event_type,
                "alert": alert,
                "alertId": message_alert_id(item, str(event_type), title, body),
            }
        )
        if len(messages) >= limit:
            break

    return messages


def is_meaningful_prompt(text: str) -> bool:
    if not text:
        return False

    compact = " ".join(text.lower().split())
    if compact in {"ok", "yes", "no", "exit", "done", "approve", "aprove"}:
        return False
    if len(compact) < 8:
        return False
    return True


def selected_pet(pet_state: str) -> dict[str, str]:
    state = read_json(STATE_PATH, {})
    selected = str(state.get("selected-pet-id") or state.get("selected-avatar-id") or "guybrush")
    candidate = PETS_PATH / selected / "pet.json"
    if not candidate.exists() or selected == "codex":
        candidate = PETS_PATH / "guybrush" / "pet.json"

    pet = read_json(candidate, {})
    pet_id = str(pet.get("id") or candidate.parent.name)
    display = str(pet.get("displayName") or pet_id.replace("-", " ").title())
    return {"id": pet_id, "displayName": display, "state": pet_state}


def watch_text(text: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }
    cleaned = str(text)
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.replace("`", "")
    return cleaned.encode("ascii", "ignore").decode("ascii")


def collapse(text: str, max_chars: int) -> str:
    compact = " ".join(watch_text(text).split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."


def tone_for(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("error", "broken", "failed to", "missing", "wrong")):
        return "warning"
    if any(word in lowered for word in ("review", "check", "verify")):
        return "review"
    if any(word in lowered for word in ("done", "deploy", "commit", "push")):
        return "success"
    return "info"


def pet_state_for(messages: list[dict[str, str]]) -> str:
    if not messages:
        return "idle"

    latest = messages[0]
    tone = latest.get("tone", "info")
    title = latest.get("title", "")
    body = latest.get("body", "").lower()

    if tone == "warning":
        return "failed"
    if tone == "success" or title == "Codex done":
        return "waving"
    if tone == "review" or "review" in body or "verify" in body or "check" in body:
        return "review"
    if "started" in body or "running" in body or "working" in body:
        return "review"
    return "review"


def latest_payload() -> dict[str, Any]:
    now = datetime.now().astimezone()
    messages = recent_codex_messages()
    for message in recent_history():
        if len(messages) >= 4:
            break
        if all(existing["body"] != message["body"] for existing in messages):
            messages.append(message)

    if not messages:
        messages = [
            {
                "title": "Codex",
                "body": "No recent prompts found. Codex bridge is running.",
                "tone": "info",
                "time": now.strftime("%H:%M"),
                "eventType": "idle",
                "alert": False,
                "alertId": "",
            }
        ]

    pet_state = pet_state_for(messages)
    progress = 100 if messages[0]["tone"] == "success" else min(96, max(18, 36 + len(messages) * 14))
    return {
        "generatedAt": now.isoformat(timespec="seconds"),
        "updatedAt": now.strftime("%H:%M"),
        "summary": messages[0]["body"],
        "status": "Live from Codex",
        "mood": "idle" if pet_state == "idle" else "working",
        "progress": progress,
        "pet": selected_pet(pet_state),
        "messages": messages,
    }


def _send_json(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def handle_bridge_get(handler: BaseHTTPRequestHandler, path: str, query: str) -> bool:
    if path != BRIDGE_PATH:
        return False
    if not is_authorized(query):
        handler.send_error(403)
        return True

    _send_json(handler, latest_payload())
    return True


class BridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        bridge_path = BRIDGE_PATH if parsed.path == "/" else parsed.path
        if not handle_bridge_get(self, bridge_path, parsed.query):
            self.send_error(404)

    def log_message(self, fmt: str, *args: Any) -> None:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        print("%s %s - %s" % (timestamp, self.address_string(), fmt % args), flush=True)
