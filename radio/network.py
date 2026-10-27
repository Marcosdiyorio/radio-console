"""Chequeo de conectividad para decidir si conviene cambiar de emisora."""
from __future__ import annotations

import socket
import time

CHECK_ADDRESS = ("1.1.1.1", 443)
CACHE_SECONDS = 30.0

_cache: dict = {"at": None, "value": False}


def has_network(timeout: float = 3.0) -> bool:
    now = time.monotonic()
    at = _cache["at"]
    if at is not None and now - at < CACHE_SECONDS:
        return bool(_cache["value"])
    try:
        socket.create_connection(CHECK_ADDRESS, timeout=timeout).close()
        value = True
    except OSError:
        value = False
    _cache["at"] = now
    _cache["value"] = value
    return value
