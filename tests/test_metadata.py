import unittest

from radio.metadata import _parse_title


class ParseTitleTests(unittest.TestCase):
    def test_artist_and_track(self):
        artist, track, url, art = _parse_title("StreamTitle='Daft Punk - One More Time';")
        self.assertEqual(artist, "Daft Punk")
        self.assertEqual(track, "One More Time")
        self.assertEqual(url, "")
        self.assertEqual(art, "")

    def test_track_only(self):
        artist, track, _, _ = _parse_title("StreamTitle='Solo un tema';")
        self.assertEqual(artist, "")
        self.assertEqual(track, "Solo un tema")

    def test_double_quotes(self):
        artist, track, _, _ = _parse_title('StreamTitle="A - B";')
        self.assertEqual((artist, track), ("A", "B"))

    def test_empty(self):
        self.assertEqual(_parse_title(""), ("", "", "", ""))

    def test_url_and_artwork(self):
        _, _, url, art = _parse_title(
            "StreamTitle='A - B';StreamUrl='https://x/y';StreamArtwork='https://x/a.jpg';"
        )
        self.assertEqual(url, "https://x/y")
        self.assertEqual(art, "https://x/a.jpg")

    def test_last_non_empty_title_wins(self):
        _, track, _, _ = _parse_title("StreamTitle='';StreamTitle='A - B';")
        self.assertEqual(track, "B")


if __name__ == "__main__":
    unittest.main()
