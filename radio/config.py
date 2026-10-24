"""Estaciones, constantes de audio y persistencia de recientes."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

MAX_RECENT = 5
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_BYTES = 8192
RENDER_FPS = 20
MAX_VISIBLE = 12
NUM_BANDS = 7
FFT_FRAMES = 1024

_recent_env = os.environ.get("RADIO_RECENT_FILE")
RECENT_FILE = Path(_recent_env).expanduser() if _recent_env else Path.home() / ".radio_agent_recent.json"

# (nombre, url, género, ciudad)
DEFAULT_STATIONS = [
    ("SmoothJazz 320k", "https://smoothjazz.cdnstream1.com/2585_320.mp3", "Smooth Jazz", "USA"),
    ("MUGEN Radio", "https://mugenradio.com/hls/live.m3u8", "Lofi", ""),
    ("Hunter.FM Lo-Fi", "https://hls.hunter.fm/lofi/192.m3u8", "Lofi", "BR"),
    ("LofiRadio24", "https://stream.zeno.fm/0r0xa792kwzuv", "Lofi", ""),
    ("laut.fm/lofi", "http://stream.laut.fm/lofi", "Lofi", "DE"),
    ("Delta 90.3", "https://cdn.instream.audio/:9069/stream", "FM", "Buenos Aires"),
    ("Radio con Vos 89.9", "https://server1.stweb.tv/rcvos/live/playlist.m3u8", "FM", "Buenos Aires"),
    ("Rock & Pop 95.9", "https://playerservices.streamtheworld.com/api/livestream-redirect/ROCKANDPOP.mp3", "Rock", "Buenos Aires"),
    ("Metro 95.1", "https://playerservices.streamtheworld.com/api/livestream-redirect/METRO_FM.mp3", "Pop", "Buenos Aires"),
    ("Pop Radio 101.5", "https://popradio.stweb.tv/popradio/live/playlist.m3u8", "Pop", "Buenos Aires"),
    ("Aspen 102.3", "https://playerservices.streamtheworld.com/api/livestream-redirect/ASPEN.mp3", "Clásicos", "Buenos Aires"),
    ("Blue 100.7", "http://playerservices.streamtheworld.com/api/livestream-redirect/BLUE_FM_100_7.mp3", "Rock", "Buenos Aires"),
]


def _station_paths(project_dir=None):
    env = os.environ.get("RADIO_STATIONS_FILE")
    if env:
        yield Path(env).expanduser()
    if project_dir:
        yield Path(project_dir) / "stations.json"
    yield Path.cwd() / "stations.json"
    yield Path.home() / ".config" / "radio-agent" / "stations.json"
    yield Path(__file__).resolve().parent / "stations.json"


def _normalize_station(item):
    if isinstance(item, dict):
        name = item.get("name") or item.get("title") or item.get("station")
        url = item.get("url") or item.get("stream") or item.get("href")
        genre = item.get("genre", "") or item.get("style", "")
        city = item.get("city", "") or item.get("location", "")
    elif isinstance(item, (list, tuple)):
        if len(item) < 2:
            return None
        name = item[0]
        url = item[1]
        genre = item[2] if len(item) > 2 else ""
        city = item[3] if len(item) > 3 else ""
    else:
        return None
    if not name or not url:
        return None
    return (str(name), str(url), str(genre), str(city))


def load_stations(project_dir=None):
    for path in _station_paths(project_dir):
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data = data.get("stations") or data.get("items") or []
                if isinstance(data, list):
                    stations = [s for s in (_normalize_station(x) for x in data) if s]
                    if stations:
                        return stations
        except Exception:
            continue
    return list(DEFAULT_STATIONS)


STATIONS = load_stations()


def station_info(st) -> tuple[str, str, str, str]:
    """Normaliza una estación a (nombre, url, género, ciudad)."""
    name = str(st[0])
    url = str(st[1])
    genre = str(st[2]) if len(st) > 2 else ""
    city = str(st[3]) if len(st) > 3 else ""
    return name, url, genre, city


def ordered_stations(stations, recents) -> list:
    """Recientes primero (en su orden), luego el resto del catálogo."""
    by_name = {st[0]: st for st in stations}
    ordered: list = []
    seen: set[str] = set()
    for name in recents:
        st = by_name.get(name)
        if st is not None and name not in seen:
            ordered.append(st)
            seen.add(name)
    for st in stations:
        if st[0] not in seen:
            ordered.append(st)
            seen.add(st[0])
    return ordered


def load_recents() -> list[str]:
    try:
        if RECENT_FILE.exists():
            data = json.loads(RECENT_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(x) for x in data][:MAX_RECENT]
    except Exception:
        pass
    return []


def save_recents(recents: list[str]) -> None:
    """Escritura atómica para no dejar el archivo a medias."""
    try:
        RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(recents[:MAX_RECENT], ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=RECENT_FILE.parent, prefix=".radio-recent-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, RECENT_FILE)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except Exception:
        pass


def add_recent(recents: list[str], name: str) -> None:
    if name in recents:
        recents.remove(name)
    recents.insert(0, name)
    del recents[MAX_RECENT:]
    save_recents(recents)
