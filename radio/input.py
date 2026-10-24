"""Lectura no bloqueante de teclado (secuencias ANSI)."""
from __future__ import annotations

import os
import select
import sys
import time

_ESCAPE_MAP = {
    b"[A": "UP",
    b"[B": "DOWN",
    b"[C": "RIGHT",
    b"[D": "LEFT",
    b"OA": "UP",
    b"OB": "DOWN",
    b"OC": "RIGHT",
    b"OD": "LEFT",
    b"[H": "HOME",
    b"[F": "END",
    b"[5~": "PAGEUP",
    b"[6~": "PAGEDOWN",
}


def _read_byte(timeout: float) -> bytes:
    if not select.select([sys.stdin], [], [], max(0.0, timeout))[0]:
        return b""
    try:
        return os.read(sys.stdin.fileno(), 1)
    except OSError:
        return b""


def read_key_nonblocking() -> str | None:
    first = _read_byte(0)
    if not first:
        return None

    if first == b"\x1b":
        seq = b""
        deadline = time.monotonic() + 0.03
        while len(seq) < 6:
            nxt = _read_byte(deadline - time.monotonic())
            if not nxt:
                break
            seq += nxt
            if nxt.isalpha() or nxt == b"~":
                break
        return _ESCAPE_MAP.get(seq, "ESC")

    try:
        char = first.decode("utf-8", errors="ignore")
    except Exception:
        return None
    if char in ("\r", "\n"):
        return "ENTER"
    if char == " ":
        return "SPACE"
    if char == "\x03":
        return "CTRL_C"
    return char
