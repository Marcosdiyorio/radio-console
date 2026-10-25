import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rich.console import Console

from radio import config
from radio.app import AppState
from radio.config import STATIONS
from radio.ui import _vu_geometry, _vu_outer_width, render


def make_state(recents):
    state = AppState(STATIONS, theme_name="matrix", theme_mode="dark")
    state.recents = recents
    state.rebuild()
    state.player.get_levels = lambda: {
        "left": 0.4,
        "right": 0.3,
        "peak_l": 0.5,
        "peak_r": 0.4,
        "bands": [0.9, 0.7, 0.5, 0.8, 0.4, 0.2, 0.6],
        "peak_bands": [1.0, 0.8, 0.6, 0.9, 0.5, 0.3, 0.7],
    }
    return state


class UiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(
            config, "RECENT_FILE", Path(self.tmp.name) / "recent.json"
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def render_text(self, state, width, height):
        console = Console(
            record=True,
            width=width,
            height=height,
            force_terminal=False,
            color_system=None,
        )
        console.print(render(state, state.pal, width=width, height=height))
        return console.export_text()

    def test_recents_use_letters_and_catalog_numbers(self):
        state = make_state(["Metro 95.1", "Rock & Pop 95.9"])
        output = self.render_text(state, 100, 34)
        self.assertIn("a. Metro 95.1", output)
        self.assertIn("b. Rock & Pop 95.9", output)
        self.assertIn("1. SmoothJazz 320k", output)
        self.assertNotIn("1. Metro 95.1", output)

    def test_layout_fits_standard_terminal(self):
        state = make_state(["Metro 95.1"])
        for width, height in ((100, 34), (80, 24), (120, 40)):
            output = self.render_text(state, width, height)
            for line in output.splitlines():
                self.assertLessEqual(len(line), width, (width, height, line))

    def test_vu_labels_close(self):
        state = make_state([])
        output = self.render_text(state, 100, 34)
        band_line = next(line for line in output.splitlines() if "60" in line and "11k" in line)
        self.assertIn("190", band_line)
        self.assertLessEqual(len(band_line), 100)

    def test_volume_shown_at_end_of_status(self):
        state = make_state(["Metro 95.1"])
        state.volume = 65
        output = self.render_text(state, 100, 34)
        self.assertIn("STATUS: ○ STOPPED · VOL 65%", output)
        state.player.playing = True
        state.player.current_name = "Metro 95.1"
        output = self.render_text(state, 80, 24)
        self.assertIn("VOL 65%", output)

    def test_vu_is_gray_while_muted(self):
        from radio.ui import _gray_gradient, _render_vu
        state = make_state(["Metro 95.1"])
        state.player.bands = [0.9] * 7
        state.player.muted = True
        text = _render_vu(state.player, state.pal, 6, 3, 1)
        styles = {str(span.style) for span in text.spans if "█" in text.plain[span.start:span.end]}
        self.assertGreater(len(styles), 3)
        self.assertTrue(styles <= set(_gray_gradient(state.pal)))

    def test_muted_state_is_visible(self):
        state = make_state(["Metro 95.1"])
        state.player.playing = True
        state.player.current_name = "Metro 95.1"
        state.player.muted = True
        output = self.render_text(state, 100, 34)
        self.assertIn("MUTE", output)
        self.assertIn("MUTED", output)
        self.assertIn("Esp/m", output)

    def test_geometry_fits_inner_width(self):
        for width in (80, 100, 120, 140, 200):
            rows, cell, gap = _vu_geometry(width, 34)
            inner = _vu_outer_width(width) - 4
            needed = 5 + config.NUM_BANDS * (cell + gap)
            self.assertLessEqual(needed, inner, width)
            self.assertGreaterEqual(rows, 3)
            self.assertGreaterEqual(cell + gap, 4)


if __name__ == "__main__":
    unittest.main()
