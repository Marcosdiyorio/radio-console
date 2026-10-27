import unittest
from unittest import mock

from radio import network


class HasNetworkTests(unittest.TestCase):
    def setUp(self):
        network._cache.update(at=None, value=False)

    def test_true_when_connect_succeeds(self):
        with mock.patch("radio.network.socket.create_connection") as connect:
            self.assertTrue(network.has_network())
        connect.assert_called_once()

    def test_false_when_connect_fails(self):
        with mock.patch("radio.network.socket.create_connection", side_effect=OSError("sin red")):
            self.assertFalse(network.has_network())

    def test_result_is_cached(self):
        with mock.patch("radio.network.socket.create_connection") as connect:
            network.has_network()
            network.has_network()
        self.assertEqual(connect.call_count, 1)


if __name__ == "__main__":
    unittest.main()
