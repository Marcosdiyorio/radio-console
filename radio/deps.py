"""Verificación de dependencias del sistema."""
from __future__ import annotations

import shutil

from .config import CHANNELS, SAMPLE_RATE


def find_sink() -> list[str] | None:
    """Primer sink de audio disponible, con PCM s16le por stdin."""
    if shutil.which("pw-cat"):
        return [
            "pw-cat", "--playback",
            "--media-type", "Audio", "--media-role", "Music",
            "--format=s16", f"--rate={SAMPLE_RATE}", f"--channels={CHANNELS}", "-",        ]
    if shutil.which("pacat"):
        return [
            "pacat", "--playback",
            f"--format=s16le", f"--rate={SAMPLE_RATE}", f"--channels={CHANNELS}",
        ]
    if shutil.which("aplay"):
        return [
            "aplay", "-f", "S16_LE", "-r", str(SAMPLE_RATE),
            "-c", str(CHANNELS), "-q",
        ]
    if shutil.which("ffplay"):
        return [
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
            "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS), "pipe:0",
        ]
    return None


def check_deps() -> list[str]:
    problems: list[str] = []
    if not shutil.which("ffmpeg"):
        problems.append("ffmpeg → sudo apt install ffmpeg")
    if find_sink() is None:
        problems.append(
            "sink de audio → sudo apt install pipewire-bin "
            "(o pulseaudio-utils / alsa-utils)"
        )
    return problems
