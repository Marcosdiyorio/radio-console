"""Metadata 'Now Playing' vía ICY/SHOUTcast."""
from __future__ import annotations

import re
import ssl
import threading
import urllib.request
from typing import Callable

_QUOTED = r"(?:'([^']*)'|\"([^\"]*)\")"


def _last_quoted(meta: str, key: str) -> str:
    matches = re.findall(key + r"=" + _QUOTED, meta)
    value = ""
    for single, double in matches:
        current = (single or double).strip()
        if current:
            value = current
    return value


def _parse_title(meta: str) -> tuple[str, str, str, str]:
    """Devuelve (artista, tema, url, artwork) desde un bloque ICY."""
    title = _last_quoted(meta, "StreamTitle")
    artist, track = "", title
    if " - " in title:
        artist, track = title.split(" - ", 1)
    url = _last_quoted(meta, "StreamUrl")
    art = _last_quoted(meta, "StreamArtwork")
    return artist.strip(), track.strip(), url, art


class IcyMetadataFetcher:
    """Hilo que mantiene actualizada la metadata sin cortar el audio."""

    def __init__(self, on_update: Callable[[dict], None]):
        self.on_update = on_update
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._generation = 0
        self._thread: threading.Thread | None = None
        self.current_url: str | None = None

    def _emit(self, generation: int, info: dict) -> None:
        with self._lock:
            if generation != self._generation:
                return
        self.on_update(info)

    def start(self, url: str, station_name: str = "") -> None:
        self.stop()
        with self._lock:
            self._generation += 1
            generation = self._generation
        self.current_url = url
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(url, station_name, generation),
            daemon=True,
            name="icy-meta",
        )
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._generation += 1
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)
        self._thread = None
        self.current_url = None

    def _run(self, url: str, station_name: str, generation: int) -> None:
        base = {
            "station": station_name,
            "genre": "",
            "url": "",
            "artist": "",
            "track": "",
            "artwork": "",
        }
        # Los HLS no exponen ICY; evitamos descargar el playlist entero.
        if ".m3u8" in url.lower():
            self._emit(generation, base)
            return

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (RadioAgent/1.0)",
                    "Icy-MetaData": "1",
                },
            )
            with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
                metaint = response.headers.get("icy-metaint")
                info = dict(base)
                info.update(
                    {
                        "station": response.headers.get("icy-name", "") or station_name,
                        "genre": response.headers.get("icy-genre", ""),
                        "url": response.headers.get("icy-url", ""),
                    }
                )
                self._emit(generation, info)
                if not metaint:
                    return
                metaint = int(metaint)
                while not self._stop.is_set():
                    remaining = metaint
                    while remaining > 0 and not self._stop.is_set():
                        chunk = response.read(min(remaining, 8192))
                        if not chunk:
                            return
                        remaining -= len(chunk)
                    if self._stop.is_set():
                        break
                    length_byte = response.read(1)
                    if not length_byte:
                        return
                    length = length_byte[0] * 16
                    if length == 0:
                        continue
                    block = response.read(length)
                    if not block:
                        return
                    meta = block.decode("latin-1", errors="ignore").rstrip("\x00")
                    artist, track, stream_url, artwork = _parse_title(meta)
                    if not (artist or track):
                        continue
                    info = dict(base)
                    info.update(
                        {
                            "station": response.headers.get("icy-name", "") or station_name,
                            "genre": response.headers.get("icy-genre", ""),
                            "url": stream_url or response.headers.get("icy-url", ""),
                            "artist": artist,
                            "track": track,
                            "artwork": artwork,
                        }
                    )
                    self._emit(generation, info)
        except Exception as exc:  # red caída, timeout, stream cerrado...
            if not self._stop.is_set():
                self._emit(generation, {**base, "error": str(exc)})
