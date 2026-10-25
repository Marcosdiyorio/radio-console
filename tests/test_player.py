import math
import struct
import unittest

from radio.config import CHANNELS, NUM_BANDS, SAMPLE_RATE
from radio.player import AudioPlayer, compute_bands, compute_rms


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
