"""Resuelve playlists .pls/.m3u a la URL real del stream."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from .metadata import PLAYLIST_LIMIT, _http_get

_MAX_DEPTH = 3


def _is_playlist(url: str) -> bool:
    return urlparse(url).path.lower().endswith((".pls", ".m3u"))


def _first_entry(base: str, body: str) -> str | None:
    if "[playlist]" in body.lower():
        match = re.search(r"^\s*File\d+\s*=\s*(\S+)", body, re.MULTILINE | re.IGNORECASE)
        return urljoin(base, match.group(1)) if match else None
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return urljoin(base, line)
    return None


def resolve_stream_url(url: str, timeout: float = 5) -> str:
    """Devuelve la primera URL de stream de una playlist; si falla, la URL original."""
    current = url
    for _ in range(_MAX_DEPTH):
        if not _is_playlist(current):
            return current
        try:
            body = _http_get(current, limit=PLAYLIST_LIMIT, timeout=timeout).decode(
                "utf-8", errors="ignore"
            )
        except Exception:
            return current
        target = _first_entry(current, body)
        if not target:
            return current
        current = target
    return current
