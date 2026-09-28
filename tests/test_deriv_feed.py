"""Offline contract tests for the public, unauthenticated Deriv feed adapter."""
import json
import os
import sys
import types
import unittest
from unittest import mock

from data import deriv_feed


class FakeWebSocket:
    def __init__(self, response):
        self.response = response
        self.sent = None
        self.closed = False

    def send(self, payload):
        self.sent = payload

    def recv(self):
        return json.dumps(self.response)

    def close(self):
        self.closed = True


class DerivFeedTests(unittest.TestCase):
    def test_fetch_requires_operator_owned_app_id_before_connecting(self):
        with mock.patch.dict(os.environ, {"DERIV_APP_ID": ""}), \
             mock.patch.dict(sys.modules, {"websocket": None}):
            with self.assertRaisesRegex(RuntimeError, "DERIV_APP_ID is unset"):
                deriv_feed.fetch_candles("R_25")

    def test_fetch_sends_ticks_history_request_converts_values_and_closes_socket(self):
        socket = FakeWebSocket({"candles": [
            {"epoch": 1700000000, "open": "1.0", "high": "1.5",
             "low": "0.8", "close": "1.2"}
        ]})
        create_connection = mock.Mock(return_value=socket)
        websocket_module = types.ModuleType("websocket")
        websocket_module.create_connection = create_connection
        with mock.patch.dict(os.environ, {"DERIV_APP_ID": "operator-app"}), \
             mock.patch.dict(sys.modules, {"websocket": websocket_module}):
            candles = deriv_feed.fetch_candles("R_25", granularity=60, count=1, timeout=4)
        create_connection.assert_called_once_with(
            "wss://ws.derivws.com/websockets/v3?app_id=operator-app", timeout=4
        )
        request = json.loads(socket.sent)
        self.assertEqual(request["ticks_history"], "R_25")
        self.assertEqual(request["granularity"], 60)
        self.assertEqual(request["count"], 1)
        self.assertEqual(request["style"], "candles")
        self.assertEqual(candles, [{
            "epoch": 1700000000, "open": 1.0, "high": 1.5, "low": 0.8, "close": 1.2
        }])
        self.assertTrue(socket.closed)

    def test_api_error_is_reported_and_socket_still_closes(self):
        socket = FakeWebSocket({"error": {"message": "bad request"}})
        websocket_module = types.ModuleType("websocket")
        websocket_module.create_connection = mock.Mock(return_value=socket)
        with mock.patch.dict(os.environ, {"DERIV_APP_ID": "operator-app"}), \
             mock.patch.dict(sys.modules, {"websocket": websocket_module}):
            with self.assertRaisesRegex(RuntimeError, "Deriv API error: bad request"):
                deriv_feed.fetch_candles("R_25")
        self.assertTrue(socket.closed)

    def test_empty_candle_payload_is_rejected(self):
        socket = FakeWebSocket({"candles": []})
        websocket_module = types.ModuleType("websocket")
        websocket_module.create_connection = mock.Mock(return_value=socket)
        with mock.patch.dict(os.environ, {"DERIV_APP_ID": "operator-app"}), \
             mock.patch.dict(sys.modules, {"websocket": websocket_module}):
            with self.assertRaisesRegex(RuntimeError, "no candle history"):
                deriv_feed.fetch_candles("R_25")
        self.assertTrue(socket.closed)

    def test_browser_probe_is_disabled_by_default_without_optional_selenium(self):
        self.assertEqual(deriv_feed.browser_probe(), {
            "enabled": False, "status": "disabled"
        })


if __name__ == "__main__":
    unittest.main()
