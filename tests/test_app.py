import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

from radio import config
from radio.app import FALLBACK_LIMIT, AppState, handle_key, main
from radio.config import STATIONS


class AppStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(
            config, "RECENT_FILE", Path(self.tmp.name) / "recent.json"
        )
        self.patch.start()
        self.volume_patch = mock.patch.object(
            config, "VOLUME_FILE", Path(self.tmp.name) / "volume.json"
        )
        self.volume_patch.start()
        self.state = AppState(STATIONS, theme_name="matrix", theme_mode="dark")
        self.state.player.play = MagicMock()
        self.state.player.stop = MagicMock()
        self.state.player.playing = False
        self.state.fetcher.start = MagicMock()
        self.state.fetcher.stop = MagicMock()

    def tearDown(self):
        self.volume_patch.stop()
        self.patch.stop()
        self.tmp.cleanup()

    def test_arrows_change_volume_and_keep_playing(self):
        self.state.player.playing = True
        handle_key(self.state, "LEFT")
        self.assertEqual(self.state.volume, 95)
        handle_key(self.state, "RIGHT")
        handle_key(self.state, "RIGHT")
        self.assertEqual(self.state.volume, 100)
        self.state.player.stop.assert_not_called()

    def test_plus_minus_change_volume_within_bounds(self):
        handle_key(self.state, "-")
        self.assertEqual(self.state.volume, 95)
        handle_key(self.state, "+")
        handle_key(self.state, "=")
        self.assertEqual(self.state.volume, 100)
        for _ in range(30):
            handle_key(self.state, "-")
        self.assertEqual(self.state.volume, 0)
        self.assertEqual(self.state.player.volume, 0.0)

    def test_volume_is_persisted(self):
        handle_key(self.state, "-")
        self.assertEqual(config.load_volume(), 95)

    def test_recents_are_shown_first(self):
        self.state.recents = ["Metro 95.1", "Rock & Pop 95.9"]
        self.state.rebuild()
        self.assertEqual(self.state.n_recents, 2)
        self.assertEqual(self.state.stations[0][0], "Metro 95.1")
        self.assertEqual(self.state.stations[1][0], "Rock & Pop 95.9")
        catalog = [station[0] for station in self.state.stations[self.state.n_recents:]]
        self.assertEqual(catalog, [station[0] for station in self.state.all_stations])

    def test_catalog_numbers_do_not_change_with_recents(self):
        catalog = [station[0] for station in self.state.all_stations]
        self.state.recents = ["Metro 95.1"]
        self.state.rebuild()
        self.assertTrue(self.state.play_key("1"))
        self.assertEqual(self.state.player.play.call_args.args[0], catalog[0])
        self.state.player.play.reset_mock()
        self.state.recents = ["Metro 95.1", catalog[0]]
        self.state.rebuild()
        self.assertTrue(self.state.play_key("3"))
        self.assertEqual(self.state.player.play.call_args.args[0], catalog[2])

    def test_letter_key_plays_recent(self):
        self.state.recents = ["Metro 95.1"]
        self.state.rebuild()
        self.assertTrue(self.state.play_key("a"))
        self.assertEqual(self.state.player.play.call_args.args[0], "Metro 95.1")
        self.assertEqual(self.state.stations[self.state.selected][0], "Metro 95.1")

    def test_letter_key_out_of_range_is_ignored(self):
        self.state.recents = []
        self.state.rebuild()
        self.assertFalse(self.state.play_key("a"))
        self.state.player.play.assert_not_called()

    def test_playing_moves_cursor_to_first_recent(self):
        self.state.recents = ["Metro 95.1", "Blue 100.7"]
        self.state.rebuild()
        self.state.selected = self.state.n_recents + 2
        self.state.start(self.state.selected)
        self.assertEqual(self.state.selected, 0)
        self.assertEqual(self.state.stations[0][0], self.state.player.play.call_args.args[0])

    def test_digit_key_plays_catalog_entry(self):
        self.state.recents = ["Metro 95.1"]
        self.state.rebuild()
        expected = self.state.stations[self.state.n_recents][0]
        self.assertTrue(self.state.play_key("1"))
        self.assertEqual(self.state.player.play.call_args.args[0], expected)
        self.assertEqual(self.state.stations[self.state.selected][0], expected)

    def test_digit_out_of_range_is_ignored(self):
        state = AppState([STATIONS[0]], theme_name="matrix", theme_mode="dark")
        state.player.play = MagicMock()
        state.fetcher.start = MagicMock()
        self.assertFalse(state.play_key("2"))
        state.player.play.assert_not_called()

    def test_enter_stops_current_station(self):
        name = self.state.stations[0][0]
        self.state.player.playing = True
        self.state.player.current_name = name
        self.state.selected = 0
        handle_key(self.state, "ENTER")
        self.state.player.stop.assert_called_once()
        self.state.fetcher.stop.assert_called_once()

    def test_enter_plays_selected_station(self):
        handle_key(self.state, "ENTER")
        self.state.player.play.assert_called_once()

    def test_space_toggles_mute(self):
        self.state.player.playing = False
        handle_key(self.state, "SPACE")
        self.assertTrue(self.state.player.muted)
        handle_key(self.state, "SPACE")
        self.assertFalse(self.state.player.muted)
        self.state.player.stop.assert_not_called()
        self.state.player.play.assert_not_called()

    def test_m_toggles_mute(self):
        handle_key(self.state, "m")
        self.assertTrue(self.state.player.muted)
        handle_key(self.state, "M")
        self.assertFalse(self.state.player.muted)

    def test_t_cycles_theme(self):
        with mock.patch(
            "radio.app.available_themes", return_value=["matrix", "custom"]
        ), mock.patch(
            "radio.app.load_theme",
            return_value={"_name": "custom", "_mode": "dark"},
        ), mock.patch("radio.app.palette", return_value={"ok": True}):
            handle_key(self.state, "t")
        self.assertEqual(self.state.theme["_name"], "custom")
        self.assertEqual(self.state.pal, {"ok": True})

    def test_t_cycles_real_bundled_theme(self):
        handle_key(self.state, "t")
        self.assertNotEqual(self.state.theme["_name"], "matrix")
        self.assertIn("green", self.state.pal)

    def test_t_with_single_theme_does_nothing(self):
        with mock.patch("radio.app.available_themes", return_value=["matrix"]):
            handle_key(self.state, "t")
        self.assertEqual(self.state.theme["_name"], "matrix")

    def test_navigation_wraps(self):
        self.state.selected = 0
        handle_key(self.state, "UP")
        self.assertEqual(self.state.selected, len(self.state.stations) - 1)
        handle_key(self.state, "DOWN")
        self.assertEqual(self.state.selected, 0)

    def test_quit(self):
        handle_key(self.state, "q")
        self.assertFalse(self.state.running)
        self.state.running = True
        handle_key(self.state, "ESC")
        self.assertFalse(self.state.running)


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(config, "RECENT_FILE", Path(self.tmp.name) / "recent.json"),
            mock.patch.object(config, "VOLUME_FILE", Path(self.tmp.name) / "volume.json"),
        ]
        for patch in self.patches:
            patch.start()
        self.state = AppState(STATIONS, theme_name="matrix", theme_mode="dark")
        self.state.player.play = MagicMock()
        self.state.player.stop = MagicMock()
        self.state.fetcher.start = MagicMock()
        self.state.fetcher.stop = MagicMock()
        self.state.player.playing = False

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.tmp.cleanup()

    def give_up(self):
        self.state.player.gave_up = True
        self.state.player.failed_name = self.state.player.play.call_args.args[0]
        self.state.tick()

    def test_next_station_when_network_is_up(self):
        self.state.start(0)
        first = self.state.player.play.call_args.args[0]
        with mock.patch("radio.app.has_network", return_value=True):
            self.give_up()
        second = self.state.player.play.call_args.args[0]
        self.assertNotEqual(first, second)
        self.assertEqual(second, self.state.all_stations[1][0])
        self.assertIn("no responde", self.state.notice)

    def test_no_fallback_without_network(self):
        self.state.start(0)
        with mock.patch("radio.app.has_network", return_value=False):
            self.give_up()
        self.assertEqual(self.state.player.play.call_count, 1)
        self.assertEqual(self.state.notice, "Sin red: no cambio de emisora")

    def test_fallback_limit_then_stops(self):
        self.state.start(0)
        with mock.patch("radio.app.has_network", return_value=True):
            for _ in range(FALLBACK_LIMIT + 1):
                self.give_up()
        self.assertEqual(self.state.player.play.call_count, 1 + FALLBACK_LIMIT)
        self.assertIn("Ninguna", self.state.notice)

    def test_manual_start_resets_fallback(self):
        self.state.start(0)
        with mock.patch("radio.app.has_network", return_value=True):
            for _ in range(FALLBACK_LIMIT + 1):
                self.give_up()
            self.state.start(0)
            self.give_up()
        self.assertIn("no responde", self.state.notice)
        self.assertEqual(self.state.player.play.call_count, 1 + FALLBACK_LIMIT + 1 + 1)

    def test_user_stop_cancels_pending_fallback(self):
        self.state.start(0)
        self.state.player.gave_up = True
        self.state.player.failed_name = self.state.all_stations[0][0]
        self.state.stop()
        self.state.tick()
        self.assertEqual(self.state.player.play.call_count, 1)


class CliTests(unittest.TestCase):
    def test_list(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(main(["--list"]), 0)
        output = buffer.getvalue()
        self.assertIn("SmoothJazz 320k", output)
        self.assertIn("https://", output)

    def test_station_out_of_range(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(main(["--station", "999"]), 2)


if __name__ == "__main__":
    unittest.main()
