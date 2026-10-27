import math
import os
import struct
import threading
import unittest
from unittest import mock

from radio.config import CHANNELS, NUM_BANDS, SAMPLE_RATE
from radio.player import AudioPlayer, _apply_gain, compute_bands, compute_rms


def pcm(samples) -> bytes:
    return struct.pack("<" + "h" * len(samples), *samples)


def tone(freq: float, frames: int = 2048, amplitude: int = 12000) -> bytes:
    samples = []
    for i in range(frames):
        value = int(amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
        samples.extend([value] * CHANNELS)
    return pcm(samples)


class RmsTests(unittest.TestCase):
    def test_silence(self):
        self.assertEqual(compute_rms(b"\x00" * 256), (0.0, 0.0))

    def test_full_scale(self):
        left, right = compute_rms(pcm([32767, -32767] * 64))
        self.assertGreater(left, 0.9)
        self.assertGreater(right, 0.9)

    def test_odd_length(self):
        self.assertEqual(compute_rms(b"\x00" * 255), (0.0, 0.0))

    def test_empty(self):
        self.assertEqual(compute_rms(b""), (0.0, 0.0))


class BandTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(compute_bands(b""), [0.0] * NUM_BANDS)

    def test_silence(self):
        self.assertEqual(compute_bands(b"\x00" * 4096), [0.0] * NUM_BANDS)

    def test_tone_lands_in_expected_band(self):
        bands = compute_bands(tone(1000))
        self.assertEqual(bands.index(max(bands)), 3)
        self.assertGreater(bands[3], 0.5)

    def test_low_tone_lands_in_first_band(self):
        bands = compute_bands(tone(200))
        self.assertEqual(bands.index(max(bands)), 1)

    def test_silence_is_zero_in_every_band(self):
        self.assertEqual(compute_bands(tone(1000, amplitude=0)), [0.0] * NUM_BANDS)

    def test_high_tone_moves_top_band(self):
        bands = compute_bands(tone(8000, amplitude=4000))
        self.assertEqual(bands.index(max(bands)), 6)
        self.assertGreater(bands[6], 0.5)

    def test_quiet_signal_stays_low(self):
        quiet = tone(1000, amplitude=40)
        self.assertLess(max(compute_bands(quiet)), 0.2)

    def test_max_frames_limits_work(self):
        bands = compute_bands(tone(1000), max_frames=512)
        self.assertEqual(len(bands), NUM_BANDS)
        self.assertEqual(bands.index(max(bands)), 3)


class FakeProc:
    def __init__(self, stdout=None, stdin=None):
        self.stdout = stdout
        self.stdin = stdin
        self.terminated = False
        self.killed = False
        self._rc = None

    def poll(self):
        return self._rc

    def terminate(self):
        self.terminated = True
        self._rc = -15

    def kill(self):
        self.killed = True
        self._rc = -9

    def wait(self, timeout=None):
        return self._rc if self._rc is not None else 0


class FakeStdin:
    def write(self, data):
        return len(data)

    def flush(self):
        pass


class StallTests(unittest.TestCase):
    def test_stalled_stream_times_out_and_cleans_up(self):
        read_fd, write_fd = os.pipe()
        stdout = os.fdopen(read_fd, "rb", buffering=0)
        ffmpeg = FakeProc(stdout=stdout)
        sink = FakeProc(stdin=FakeStdin())
        player = AudioPlayer()
        player.current_url = "http://x/stream"
        player.current_name = "X"
        with mock.patch("radio.player.find_sink", return_value=["pw-cat"]), \
                mock.patch("radio.player.shutil.which", return_value="/usr/bin/ffmpeg"), \
                mock.patch("radio.player.subprocess.Popen", side_effect=[ffmpeg, sink]), \
                mock.patch("radio.player.STREAM_STALL_SECONDS", 0.2):
            player._run_pipeline_once(threading.Event())
        os.close(write_fd)
        stdout.close()
        self.assertIn("timeout", player.error)
        self.assertTrue(ffmpeg.terminated)
        self.assertTrue(sink.terminated)
        self.assertIsNone(player.proc_ffmpeg)
        self.assertIsNone(player.proc_sink)

    def test_gives_up_after_retries_are_exhausted(self):
        player = AudioPlayer()
        player.current_name = "X"
        player._max_retries = 0

        def fail(stop_event):
            player.error = "boom"

        player._run_pipeline_once = fail
        player._run_with_retry(threading.Event())
        self.assertTrue(player.gave_up)
        self.assertEqual(player.failed_name, "X")


class GainTests(unittest.TestCase):
    def test_half_gain_halves_samples(self):
        data = pcm([1000, -1000, 20000, -20000])
        self.assertEqual(_apply_gain(data, 0.5), pcm([500, -500, 10000, -10000]))

    def test_zero_gain_is_silence(self):
        self.assertEqual(_apply_gain(pcm([1000, -1000]), 0.0), b"\x00" * 4)

    def test_full_gain_is_untouched(self):
        data = pcm([1000, -1000])
        self.assertIs(_apply_gain(data, 1.0), data)

    def test_no_overflow_at_full_scale(self):
        self.assertEqual(_apply_gain(pcm([32767, -32768]), 0.99), pcm([32439, -32440]))


class MuteTests(unittest.TestCase):
    def test_toggle_mute(self):
        player = AudioPlayer()
        self.assertFalse(player.muted)
        self.assertTrue(player.toggle_mute())
        self.assertTrue(player.muted)
        self.assertFalse(player.toggle_mute())
        self.assertFalse(player.muted)

    def test_mute_resets_levels(self):
        player = AudioPlayer()
        with player.lock:
            player.levels["left"] = 0.8
            player.bands[0] = 0.7
            player.peak_l = 0.9
        player.set_muted(True)
        levels = player.get_levels()
        self.assertEqual(levels["left"], 0.0)
        self.assertEqual(levels["bands"], [0.0] * NUM_BANDS)
        self.assertEqual(levels["peak_l"], 0.0)


if __name__ == "__main__":
    unittest.main()
