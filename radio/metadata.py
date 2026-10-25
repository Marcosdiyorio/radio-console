"""Metadata 'Now Playing': ICY/SHOUTcast para streams directos y ID3 para HLS."""
from __future__ import annotations

import re
import ssl
import threading
import urllib.request
from typing import Callable
from urllib.parse import urljoin

_QUOTED = r"(?:'([^']*)'|\"([^\"]*)\")"

RETRY_SECONDS = 10
NO_META_RETRY_SECONDS = 60
HLS_POLL_SECONDS = 8
HLS_HEAD_BYTES = 65536
PLAYLIST_LIMIT = 262144
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


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


def _is_hls(url: str) -> bool:
    return ".m3u8" in url.lower()


def _http_get(url: str, limit: int | None = None, timeout: float = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RadioAgent/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as response:
        return response.read(limit) if limit else response.read()


def _hls_last_segment(url: str, depth: int = 0) -> str | None:
    """Último segmento del playlist; sigue playlists anidadas (variantes)."""
    body = _http_get(url, limit=PLAYLIST_LIMIT).decode("utf-8", errors="ignore")
    entries = [line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#")]
    if not entries:
        return None
    target = urljoin(url, entries[-1])
    if _is_hls(target) and depth < 2:
        return _hls_last_segment(target, depth + 1)
    return target


def _syncsafe(data: bytes) -> int:
    return (data[0] << 21) | (data[1] << 14) | (data[2] << 7) | data[3]


def _decode_id3_text(body: bytes) -> str:
    encoding, raw = body[0], body[1:]
    codec = {0: "latin-1", 1: "utf-16", 2: "utf-16-be", 3: "utf-8"}.get(encoding, "utf-8")
    return raw.decode(codec, errors="ignore").replace("\x00", "").strip()


def _parse_id3(data: bytes) -> dict[str, str]:
    """Lee TPE1 (artista) y TIT2 (título) de un tag ID3v2 al inicio de data."""
    start = data.find(b"ID3")
    if start < 0 or len(data) < start + 10:
        return {}
    major = data[start + 3]
    pos = start + 10
    end = min(len(data), pos + _syncsafe(data[start + 6:start + 10]))
    tags: dict[str, str] = {}
    while pos + 10 <= end:
        frame_id = data[pos:pos + 4].decode("latin-1")
        if not frame_id.strip("\x00"):
            break
        size_bytes = data[pos + 4:pos + 8]
        size = _syncsafe(size_bytes) if major == 4 else int.from_bytes(size_bytes, "big")
        body = data[pos + 10:pos + 10 + size]
        pos += 10 + size
        if frame_id in ("TPE1", "TIT2") and body:
            text = _decode_id3_text(body)
            if text:
                tags[frame_id] = text
    return tags


class IcyMetadataFetcher:
    """Hilo que mantiene actualizada la metadata y reintenta si se pierde."""

    def __init__(self, on_update: Callable[[dict], None]):
        self.on_update = on_update
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._generation = 0
        self._thread: threading.Thread | None = None
        self.current_url: str | None = None

    def _active(self, generation: int, stop: threading.Event) -> bool:
        with self._lock:
            return generation == self._generation and not stop.is_set()

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
            args=(url, station_name, generation, self._stop),
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

    def _run(self, url: str, station_name: str, generation: int, stop: threading.Event) -> None:
        base = {
            "station": station_name,
            "genre": "",
            "url": "",
            "artist": "",
            "track": "",
            "artwork": "",
        }
        self._emit(generation, base)
        hls = _is_hls(url)
        while self._active(generation, stop):
            wait = RETRY_SECONDS
            try:
                if hls:
                    self._poll_hls(url, base, generation, stop)
                    wait = HLS_POLL_SECONDS
                elif not self._read_icy(url, station_name, base, generation, stop):
                    wait = NO_META_RETRY_SECONDS
            except Exception as exc:  # red caída, timeout, stream cerrado...
                if self._active(generation, stop):
                    self._emit(generation, {**base, "error": str(exc)})
            if stop.wait(wait):
                break

    def _poll_hls(self, url: str, base: dict, generation: int, stop: threading.Event) -> None:
        segment = _hls_last_segment(url)
        if not segment:
            raise RuntimeError("playlist sin segmentos")
        tags = _parse_id3(_http_get(segment, limit=HLS_HEAD_BYTES))
        if not tags:
            return
        artist = tags.get("TPE1", "")
        track = tags.get("TIT2", "")
        if not (artist or track):
            return
        if track and artist and track.startswith(artist + " - "):
            track = track[len(artist) + 3:]
        self._emit(generation, {**base, "artist": artist, "track": track})

    def _read_icy(
        self,
        url: str,
        station_name: str,
        base: dict,
        generation: int,
        stop: threading.Event,
    ) -> bool:
        """Lee ICY hasta que el stream termina. Devuelve False si no hay ICY."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (RadioAgent/1.0)",
                "Icy-MetaData": "1",
            },
        )
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CONTEXT) as response:
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
                return False
            metaint = int(metaint)
            while self._active(generation, stop):
                remaining = metaint
                while remaining > 0 and self._active(generation, stop):
                    chunk = response.read(min(remaining, 8192))
                    if not chunk:
                        return True
                    remaining -= len(chunk)
                if not self._active(generation, stop):
                    break
                length_byte = response.read(1)
                if not length_byte:
                    return True
                length = length_byte[0] * 16
                if length == 0:
                    continue
                block = response.read(length)
                if not block:
                    return True
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
        return True
