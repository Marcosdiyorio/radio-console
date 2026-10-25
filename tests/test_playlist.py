import unittest
from unittest import mock

from radio import playlist


class ResolveStreamUrlTests(unittest.TestCase):
    def test_pls_returns_first_file(self):
        body = "[playlist]\nNumberOfEntries=2\nFile1=http://a/stream\nTitle1=A\nFile2=http://b\n"
        with mock.patch("radio.playlist._http_get", return_value=body.encode()):
            self.assertEqual(playlist.resolve_stream_url("http://x/radio.pls"), "http://a/stream")

    def test_m3u_skips_comments_and_resolves_relative(self):
        body = "#EXTM3U\n#EXTINF:-1,Radio\nlive/stream.mp3\n"
        with mock.patch("radio.playlist._http_get", return_value=body.encode()):
            self.assertEqual(
                playlist.resolve_stream_url("http://x/y/radio.m3u"),
                "http://x/y/live/stream.mp3",
            )

    def test_m3u8_is_left_alone(self):
        with mock.patch("radio.playlist._http_get") as fetch:
            self.assertEqual(
                playlist.resolve_stream_url("http://x/live.m3u8"), "http://x/live.m3u8"
            )
        fetch.assert_not_called()

    def test_direct_stream_is_left_alone(self):
        with mock.patch("radio.playlist._http_get") as fetch:
            self.assertEqual(playlist.resolve_stream_url("http://x/s.mp3"), "http://x/s.mp3")
        fetch.assert_not_called()

    def test_fetch_error_falls_back_to_original(self):
        with mock.patch("radio.playlist._http_get", side_effect=OSError("caído")):
            self.assertEqual(playlist.resolve_stream_url("http://x/radio.pls"), "http://x/radio.pls")

    def test_nested_playlist_is_followed(self):
        bodies = {
            "http://x/radio.m3u": b"http://x/inner.pls\n",
            "http://x/inner.pls": b"[playlist]\nFile1=http://x/final.mp3\n",
        }
        with mock.patch("radio.playlist._http_get", side_effect=lambda u, **k: bodies[u]):
            self.assertEqual(playlist.resolve_stream_url("http://x/radio.m3u"), "http://x/final.mp3")


if __name__ == "__main__":
    unittest.main()
