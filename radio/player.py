"""Reproductor de audio: ffmpeg -> PCM -> sink del sistema."""
from __future__ import annotations

import array
import math
import shutil
import subprocess
import sys
import threading

from .config import CHANNELS, CHUNK_BYTES, FFT_FRAMES, NUM_BANDS, SAMPLE_RATE
from .deps import find_sink

# Cortes de banda en Hz (7 bandas).
_BAND_EDGES = [0, 120, 300, 700, 1500, 3000, 6000, 22050]


def _pcm_samples(data: bytes) -> array.array | None:
    """Convierte PCM s16le en un array nativo, descartando bytes impares."""
    if not data:
        return None
    if len(data) % 2:
        data = data[:-1]
    try:
        samples = array.array("h")
        samples.frombytes(data)
    except Exception:
        return None
    if sys.byteorder == "big":
        samples.byteswap()
    return samples


def compute_rms(data: bytes) -> tuple[float, float]:
    """Nivel RMS normalizado (0..1) por canal izquierdo/derecho."""
    samples = _pcm_samples(data)
    if samples is None or len(samples) < CHANNELS:
        return 0.0, 0.0
    left = samples[0::CHANNELS]
    right = samples[1::CHANNELS] if CHANNELS > 1 else left

    def _rms(channel) -> float:
        if not channel:
            return 0.0
        total = 0
        for value in channel:
            total += value * value
        return math.sqrt(total / len(channel)) / 32768.0

    return _rms(left), _rms(right)


def _fft_mag(samples: list[float]) -> list[float]:
    size = 1
    while size < len(samples):
        size <<= 1
    if size == 0:
        return []
    padded = samples + [0.0] * (size - len(samples))
    values = [complex(v) for v in padded]

    j = 0
    for i in range(1, size):
        bit = size >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            values[i], values[j] = values[j], values[i]

    length = 2
    while length <= size:
        angle = -2 * math.pi / length
        step = complex(math.cos(angle), math.sin(angle))
        half = length // 2
        for start in range(0, size, length):
            weight = complex(1, 0)
            for k in range(half):
                even = values[start + k]
                odd = values[start + k + half] * weight
                values[start + k] = even + odd
                values[start + k + half] = even - odd
                weight *= step
        length <<= 1
    return [abs(v) for v in values[: size // 2]]


def compute_bands(data: bytes, max_frames: int | None = None) -> list[float]:
    """Espectro aproximado en 7 bandas, normalizado 0..1."""
    samples = _pcm_samples(data)
    if samples is None:
        return [0.0] * NUM_BANDS

    frames = len(samples) // CHANNELS
    if frames < 32:
        return [0.0] * NUM_BANDS
    if max_frames is not None and frames > max_frames:
        # usamos la ventana más reciente para abaratar el cálculo
        samples = samples[-(max_frames * CHANNELS):]
        frames = max_frames

    mono = [0.0] * frames
    for i in range(frames):
        value = samples[i * CHANNELS]
        if CHANNELS > 1:
            value = (value + samples[i * CHANNELS + 1]) // 2
        mono[i] = value / 32768.0

    faded = [
        mono[i] * (0.5 - 0.5 * math.cos(2 * math.pi * i / max(1, frames - 1)))
        for i in range(frames)
    ]
    magnitudes = _fft_mag(faded)
    if not magnitudes:
        return [0.0] * NUM_BANDS

    fft_size = 1
    while fft_size < frames:
        fft_size <<= 1
    bin_hz = SAMPLE_RATE / fft_size

    power = [0.0] * NUM_BANDS
    counts = [0] * NUM_BANDS
    for index, magnitude in enumerate(magnitudes):
        hz = index * bin_hz
        for band in range(NUM_BANDS):
            if _BAND_EDGES[band] <= hz < _BAND_EDGES[band + 1]:
                power[band] += magnitude * magnitude
                counts[band] += 1
                break

    bands = [
        math.sqrt(power[b] / counts[b]) if counts[b] else 0.0
        for b in range(NUM_BANDS)
    ]
    peak = max(bands) if bands else 0.0
    if peak > 0:
        bands = [min(1.0, value / max(peak, 0.05)) for value in bands]
    return [min(1.0, value * 2.5) for value in bands]


class AudioPlayer:
    """Puentea ffmpeg con el sink de audio y expone niveles para la UI."""

    def __init__(self, on_error=None):
        self.proc_ffmpeg = None
        self.proc_sink = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.levels = {"left": 0.0, "right": 0.0}
        self.bands = [0.0] * NUM_BANDS
        self.peak_bands = [0.0] * NUM_BANDS
        self.peak_l = 0.0
        self.peak_r = 0.0
        self.playing = False
        self.current_name: str | None = None
        self.current_url: str | None = None
        self.error: str | None = None
        self.muted = False
        self.on_error = on_error
        self._retry_count = 0
        self._max_retries = 3
        self._band_decay = 0.92
        self._peak_hold = [0] * NUM_BANDS
        self._peak_timer_l = 0
        self._peak_timer_r = 0
        self._fatal = False

    # --- API pública --------------------------------------------------
    def play(self, name: str, url: str) -> None:
        self.stop()
        self.stop_event = threading.Event()
        self.error = None
        self._fatal = False
        self.current_name = name
        self.current_url = url
        self.playing = True
        self._retry_count = 0
        with self.lock:
            self._reset_levels_locked()
        self.thread = threading.Thread(target=self._run_with_retry, daemon=True, name="radio-player")
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        for proc in (self.proc_ffmpeg, self.proc_sink):
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=4)
        self.playing = False
        self.current_name = None
        self.current_url = None
        self.error = None
        self._retry_count = 0
        with self.lock:
            self._reset_levels_locked()

    def get_levels(self) -> dict:
        with self.lock:
            return {
                "left": self.levels["left"],
                "right": self.levels["right"],
                "peak_l": self.peak_l,
                "peak_r": self.peak_r,
                "bands": list(self.bands),
                "peak_bands": list(self.peak_bands),
            }

    def toggle_mute(self) -> bool:
        return self.set_muted(not self.muted)

    def set_muted(self, muted: bool) -> bool:
        self.muted = bool(muted)
        with self.lock:
            self._reset_levels_locked()
        return self.muted

    # --- internos -----------------------------------------------------
    def _reset_levels_locked(self) -> None:
        self.levels = {"left": 0.0, "right": 0.0}
        self.bands = [0.0] * NUM_BANDS
        self.peak_bands = [0.0] * NUM_BANDS
        self.peak_l = 0.0
        self.peak_r = 0.0
        self._peak_hold = [0] * NUM_BANDS
        self._peak_timer_l = 0
        self._peak_timer_r = 0

    def _run_with_retry(self) -> None:
        while not self.stop_event.is_set() and self._retry_count <= self._max_retries:
            self._run_pipeline_once()
            if self.stop_event.is_set() or self._fatal:
                break
            if self.error and self._retry_count < self._max_retries:
                self._retry_count += 1
                wait = min(2 ** self._retry_count, 8)
                self.stop_event.wait(wait)
                if not self.stop_event.is_set():
                    self.error = None
                    self.playing = True
                    continue
            break
        if not self.stop_event.is_set():
            self.playing = False
            if self.error and self.on_error:
                self.on_error(self.error)

    def _run_pipeline_once(self) -> None:
        sink_cmd = find_sink()
        if sink_cmd is None:
            self.error = "No hay sink de audio (pw-cat/pacat/aplay/ffplay)"
            self.playing = False
            self._fatal = True
            return
        if not shutil.which("ffmpeg"):
            self.error = "ffmpeg no está instalado"
            self.playing = False
            self._fatal = True
            return

        ffmpeg_cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "quiet", "-nostdin",
            "-reconnect", "1", "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-user_agent", "Mozilla/5.0 (RadioAgent/1.0)",
            "-i", self.current_url,
            "-vn", "-sn", "-dn",
            "-f", "s16le", "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE),
            "pipe:1",
        ]

        try:
            self.proc_ffmpeg = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            self.proc_sink = subprocess.Popen(
                sink_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            while not self.stop_event.is_set():
                data = self.proc_ffmpeg.stdout.read(CHUNK_BYTES)
                if not data:
                    if not self.stop_event.is_set():
                        self.error = "El stream se cortó inesperadamente"
                    break
                try:
                    output = b"\x00" * len(data) if self.muted else data
                    self.proc_sink.stdin.write(output)
                    self.proc_sink.stdin.flush()
                except (BrokenPipeError, OSError, ValueError):
                    self.error = "El sink de audio se cerró"
                    break
                if self.muted:
                    self._update_levels(0.0, 0.0, [0.0] * NUM_BANDS)
                else:
                    left, right = compute_rms(data)
                    bands = compute_bands(data, max_frames=FFT_FRAMES)
                    self._update_levels(left, right, bands)
        except Exception as exc:
            self.error = f"Error en el pipeline: {exc}"
        finally:
            for proc in (self.proc_ffmpeg, self.proc_sink):
                if proc is None:
                    continue
                try:
                    if proc.poll() is None:
                        proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            self.proc_ffmpeg = None
            self.proc_sink = None
            with self.lock:
                self._reset_levels_locked()

    def _update_levels(self, left: float, right: float, bands: list[float]) -> None:
        with self.lock:
            self.levels["left"] = max(left, self.levels["left"] * 0.85)
            self.levels["right"] = max(right, self.levels["right"] * 0.85)

            if left > self.peak_l:
                self.peak_l = left
                self._peak_timer_l = 20
            elif self._peak_timer_l > 0:
                self._peak_timer_l -= 1
            else:
                self.peak_l = max(left, self.peak_l * 0.95)

            if right > self.peak_r:
                self.peak_r = right
                self._peak_timer_r = 20
            elif self._peak_timer_r > 0:
                self._peak_timer_r -= 1
            else:
                self.peak_r = max(right, self.peak_r * 0.95)

            for i in range(NUM_BANDS):
                value = bands[i]
                if value > self.bands[i]:
                    self.bands[i] = value
                else:
                    self.bands[i] = max(value, self.bands[i] * self._band_decay)
                if value > self.peak_bands[i]:
                    self.peak_bands[i] = value
                    self._peak_hold[i] = 15
                elif self._peak_hold[i] > 0:
                    self._peak_hold[i] -= 1
                else:
                    self.peak_bands[i] = max(value, self.peak_bands[i] * 0.93)
