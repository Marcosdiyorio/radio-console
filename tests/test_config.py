import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radio import config


class StationOrderTests(unittest.TestCase):
    def test_recents_first_and_no_duplicates(self):
        stations = [("A", "u1"), ("B", "u2"), ("C", "u3")]
        ordered = config.ordered_stations(stations, ["C", "A", "missing"])
        self.assertEqual([s[0] for s in ordered], ["C", "A", "B"])

    def test_unknown_recents_ignored(self):
        stations = [("A", "u1")]
        self.assertEqual(config.ordered_stations(stations, ["X"]), stations)

    def test_station_info_defaults(self):
        self.assertEqual(config.station_info(("A", "u")), ("A", "u", "", ""))


class VolumePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "volume.json"
        self.patch = mock.patch.object(config, "VOLUME_FILE", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_default_when_missing(self):
        self.assertEqual(config.load_volume(), config.DEFAULT_VOLUME)

    def test_save_and_load(self):
        config.save_volume(40)
        self.assertEqual(config.load_volume(), 40)
        self.assertEqual(json.loads(self.path.read_text()), {"volume": 40})

    def test_load_clamps_out_of_range(self):
        self.path.write_text(json.dumps({"volume": 250}))
        self.assertEqual(config.load_volume(), 100)


class RecentPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "recent.json"
        self.patch = mock.patch.object(config, "RECENT_FILE", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_save_and_load(self):
        config.save_recents(["A", "B", "C"])
        self.assertEqual(config.load_recents(), ["A", "B", "C"])
        self.assertEqual(json.loads(self.path.read_text()), ["A", "B", "C"])

    def test_add_recent_moves_to_front_and_caps(self):
        recents = ["B", "C"]
        config.add_recent(recents, "C")
        self.assertEqual(recents, ["C", "B"])
        for i in range(config.MAX_RECENT + 3):
            config.add_recent(recents, f"S{i}")
        self.assertEqual(len(recents), config.MAX_RECENT)
        self.assertEqual(recents[0], f"S{config.MAX_RECENT + 2}")

    def test_load_stations_from_json_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stations.json"
            path.write_text(json.dumps([
                {"name": "A", "url": "http://a", "genre": "g", "city": "c"},
                ["B", "http://b"],
            ]))
            stations = config.load_stations(project_dir=tmp)
        self.assertEqual(stations, [("A", "http://a", "g", "c"), ("B", "http://b", "", "")])

    def test_load_stations_from_wrapped_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stations.json"
            path.write_text(json.dumps({"stations": [{"name": "X", "url": "http://x"}]}))
            stations = config.load_stations(project_dir=tmp)
        self.assertEqual(stations, [("X", "http://x", "", "")])

    def test_load_stations_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(config.load_stations(project_dir=tmp), config.DEFAULT_STATIONS)

    def test_env_overrides_station_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom.json"
            path.write_text(json.dumps([["Z", "http://z"]]))
            with mock.patch.dict(os.environ, {"RADIO_STATIONS_FILE": str(path)}):
                stations = config.load_stations(project_dir=tmp)
        self.assertEqual(stations, [("Z", "http://z", "", "")])


if __name__ == "__main__":
    unittest.main()
