"""Petdex search and asset download helpers."""

from __future__ import annotations

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from .core import parse_int


PETDEX_BASE = "https://petdex.crafter.run"
PETDEX_SORTS = {"curated", "popular", "installed", "alpha", "recent"}
PETDEX_ALLOWED_HOSTS = ("petdex.crafter.run", "r2.dev", "ufs.sh")
MAX_REMOTE_JSON_BYTES = 512 * 1024
MAX_REMOTE_ASSET_BYTES = 16 * 1024 * 1024

try:
    import certifi

    HTTPS_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    HTTPS_CONTEXT = ssl.create_default_context()


def safe_remote_url(raw_url: str) -> str:
    parsed = urlparse(str(raw_url or ""))
    host = (parsed.hostname or "").lower()
    allowed = any(host == allowed_host or host.endswith(f".{allowed_host}") for allowed_host in PETDEX_ALLOWED_HOSTS)
    if parsed.scheme != "https" or not allowed or parsed.username or parsed.password:
        raise ValueError("Petdex asset URL is not from an allowed host.")
    return parsed.geturl()


def fetch_remote_bytes(raw_url: str, max_bytes: int, timeout: int = 16, accept: str = "*/*") -> bytes:
    url = safe_remote_url(raw_url)
    request = Request(url, headers={"User-Agent": "garmin-pet-pipeline/1.0", "Accept": accept})
    try:
        with urlopen(request, timeout=timeout, context=HTTPS_CONTEXT) as response:
            safe_remote_url(response.geturl())
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    too_large = int(content_length) > max_bytes
                except ValueError:
                    too_large = False
                if too_large:
                    raise ValueError("Petdex asset is larger than the local import limit.")
            data = response.read(max_bytes + 1)
    except HTTPError as exc:
        raise RuntimeError(f"Petdex request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Petdex request failed: {exc.reason}") from exc
    if len(data) > max_bytes:
        raise ValueError("Petdex asset is larger than the local import limit.")
    return data


def fetch_remote_json(raw_url: str, max_bytes: int = MAX_REMOTE_JSON_BYTES):
    data = fetch_remote_bytes(raw_url, max_bytes=max_bytes, accept="application/json")
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Petdex API returned data that is not UTF-8 JSON.") from exc
    try:
        return json.loads(decoded)
    except json.JSONDecodeError as exc:
        preview = decoded.lstrip()[:120].replace("\n", " ")
        if preview.startswith("<"):
            raise RuntimeError("Petdex API returned an HTML page instead of JSON. The upstream search endpoint may be unavailable.") from exc
        raise RuntimeError("Petdex API returned invalid JSON.") from exc


def search(query: str) -> tuple[dict, int]:
    params = parse_qs(query, keep_blank_values=False)

    def first(name: str, default: str = "") -> str:
        values = params.get(name)
        return str(values[0]) if values else default

    sort = first("sort", "popular").lower()
    if sort not in PETDEX_SORTS:
        sort = "popular"
    limit = parse_int(first("limit"), 12, 1, 24)
    cursor = parse_int(first("cursor"), 0, 0, 10000)

    forwarded: dict[str, str] = {
        "sort": sort,
        "limit": str(limit),
        "cursor": str(cursor),
    }
    for key in ("q", "kinds", "vibes", "colors", "batches"):
        value = first(key).strip()
        if value:
            forwarded[key] = value[:160]

    url = f"{PETDEX_BASE}/api/pets/search?{urlencode(forwarded)}"
    try:
        payload = fetch_remote_json(url)
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "message": str(exc)}, 502
    payload["ok"] = True
    return payload, 200
