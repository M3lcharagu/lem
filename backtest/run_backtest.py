#!/usr/bin/env python3
"""Small, dependency-free Deriv candle fetcher and SMA-crossover backtester.

Online:  python backtest/run_backtest.py
Offline: python backtest/run_backtest.py --offline candles.json
        (with no filename, --offline reads ./candles.json)

Offline JSON may be either {"R_25": [candle, ...], "R_75": [candle, ...]},
{"candles": [...]}, or a single candle list. Each candle uses epoch/open/high/low/close.
This is an educational close-to-close backtest, not a trading recommendation.
"""

import argparse
import base64
import hashlib
import json
import math
import os
import random
import socket
import ssl
import statistics
import struct
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"
SYMBOLS = ("R_25", "R_75")
GRANULARITY = 60
CANDLE_COUNT = 5000
FAST_PERIOD = 10
SLOW_PERIOD = 30
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME_SIZE = 16 * 1024 * 1024


class WebSocketError(RuntimeError):
    pass


class MinimalWebSocket:
    """Minimal client-side RFC 6455 text-frame support using only stdlib."""

    def __init__(self, url, timeout=30):
        self.url = url
        self.timeout = timeout
        self.sock = None

    def connect(self):
        parts = urlsplit(self.url)
        if parts.scheme != "wss" or not parts.hostname:
            raise WebSocketError("Only a valid wss:// URL is supported")
        port = parts.port or 443
        raw = socket.create_connection((parts.hostname, port), timeout=self.timeout)
        self.sock = ssl.create_default_context().wrap_socket(
            raw, server_hostname=parts.hostname
        )
        self.sock.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        request = (
            "GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ) % (path, parts.hostname, port, key)
        self.sock.sendall(request.encode("ascii"))

        # Read only through the HTTP header terminator, one byte at a time, so
        # bytes belonging to the first WebSocket frame remain in the socket.
        header = bytearray()
        while not header.endswith(b"\r\n\r\n"):
            b = self.sock.recv(1)
            if not b:
                raise WebSocketError("Connection closed during WebSocket handshake")
            header.extend(b)
            if len(header) > 65536:
                raise WebSocketError("Oversized WebSocket handshake headers")
        lines = header.decode("iso-8859-1").split("\r\n")
        if not lines or " 101 " not in (lines[0] + " "):
            raise WebSocketError("WebSocket upgrade rejected: " + (lines[0] if lines else "no response"))
        response_headers = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                response_headers[name.strip().lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1((key + WS_GUID).encode("ascii")).digest()).decode("ascii")
        if response_headers.get("sec-websocket-accept") != expected:
            raise WebSocketError("Invalid Sec-WebSocket-Accept in handshake")
        return self

    def _read_exact(self, count):
        data = bytearray()
        while len(data) < count:
            block = self.sock.recv(count - len(data))
            if not block:
                raise WebSocketError("WebSocket connection closed unexpectedly")
            data.extend(block)
        return bytes(data)

    def send_frame(self, opcode, payload=b""):
        if self.sock is None:
            raise WebSocketError("WebSocket is not connected")
        payload = bytes(payload)
        first = 0x80 | (opcode & 0x0F)
        length = len(payload)
        if length < 126:
            header = bytes((first, 0x80 | length))
        elif length < 65536:
            header = bytes((first, 0x80 | 126)) + struct.pack("!H", length)
        else:
            header = bytes((first, 0x80 | 127)) + struct.pack("!Q", length)
        mask = os.urandom(4)
        masked = bytes(value ^ mask[i % 4] for i, value in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def send_json(self, value):
        self.send_frame(1, json.dumps(value, separators=(",", ":")).encode("utf-8"))

    def receive_text(self):
        fragments = bytearray()
        message_opcode = None
        while True:
            first, second = self._read_exact(2)
            fin = bool(first & 0x80)
            opcode = first & 0x0F
            if first & 0x70:
                raise WebSocketError("Unsupported WebSocket extension bits")
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            if length > MAX_FRAME_SIZE:
                raise WebSocketError("WebSocket frame exceeds the 16 MiB safety limit")
            mask = self._read_exact(4) if masked else None
            payload = self._read_exact(length)
            if masked:
                payload = bytes(value ^ mask[i % 4] for i, value in enumerate(payload))

            if opcode == 8:
                raise WebSocketError("Server closed the WebSocket")
            if opcode == 9:
                self.send_frame(10, payload)
                continue
            if opcode == 10:
                continue
            if opcode in (1, 2):
                if message_opcode is not None:
                    raise WebSocketError("Unexpected new data frame during fragmented message")
                message_opcode = opcode
                fragments.extend(payload)
            elif opcode == 0:
                if message_opcode is None:
                    raise WebSocketError("Unexpected WebSocket continuation frame")
                fragments.extend(payload)
            else:
                raise WebSocketError("Unsupported WebSocket opcode: %d" % opcode)

            if len(fragments) > MAX_FRAME_SIZE:
                raise WebSocketError("WebSocket message exceeds the 16 MiB safety limit")
            if fin:
                if message_opcode != 1:
                    raise WebSocketError("Expected a text JSON message from Deriv")
                try:
                    return json.loads(fragments.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise WebSocketError("Invalid JSON received from Deriv: %s" % exc)

    def close(self):
        if self.sock is not None:
            try:
                self.send_frame(8, struct.pack("!H", 1000))
            except OSError:
                pass
            try:
                self.sock.close()
            finally:
                self.sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def convert_candles(raw_candles):
    """Normalize API/local candle records into sorted numeric OHLC dictionaries."""
    candles = []
    for row in raw_candles:
        if not isinstance(row, dict):
            continue
        try:
            candle = {
                "epoch": int(row.get("epoch", row.get("time"))),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if all(math.isfinite(candle[key]) for key in ("open", "high", "low", "close")):
            candles.append(candle)
    candles.sort(key=lambda item: item["epoch"])
    # Deduplicate epochs while retaining the last supplied version of each bar.
    by_epoch = {item["epoch"]: item for item in candles}
    return [by_epoch[epoch] for epoch in sorted(by_epoch)]


def fetch_history(symbol):
    # The 5,000-bar request limit was not independently verified; the API may
    # impose a lower maximum or require pagination, in which case reduce count
    # or add paging based on Deriv's current ticks_history limits.
    request = {
        "ticks_history": symbol,
        "adjust_start": 1,
        "count": CANDLE_COUNT,
        "end": "latest",
        "granularity": GRANULARITY,
        "style": "candles",
        "req_id": 1,
    }
    with MinimalWebSocket(WS_URL) as ws:
        ws.send_json(request)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            response = ws.receive_text()
            if response.get("error"):
                error = response["error"]
                raise RuntimeError("Deriv %s: %s" % (error.get("code", "error"), error.get("message", error)))
            if response.get("req_id") not in (None, 1):
                continue
            if response.get("msg_type") == "candles" or "candles" in response:
                return convert_candles(response.get("candles", []))
        raise TimeoutError("Timed out waiting for %s candle history" % symbol)


def load_offline(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    result = {}
    for symbol in SYMBOLS:
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and symbol in data:
            rows = data[symbol]
        elif isinstance(data, dict) and isinstance(data.get("candles"), list):
            rows = data["candles"]
        else:
            rows = []
        result[symbol] = convert_candles(rows)
    return result


def sma(values, end, period):
    start = end - period + 1
    return sum(values[start : end + 1]) / period


def iso_time(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def backtest(symbol, candles):
    closes = [item["close"] for item in candles]
    if len(closes) < SLOW_PERIOD + 2:
        raise ValueError("%s needs at least %d valid candles; found %d" % (symbol, SLOW_PERIOD + 2, len(closes)))
    if any(value <= 0 for value in closes):
        raise ValueError("%s contains non-positive close prices" % symbol)

    bar_returns = []
    calls = []
    trades = []
    position = 0
    entry_price = None
    entry_epoch = None

    # A signal is formed at a completed candle and is applied only to the
    # following candle's close-to-close return, avoiding look-ahead.
    for i in range(SLOW_PERIOD - 1, len(candles) - 1):
        fast = sma(closes, i, FAST_PERIOD)
        slow = sma(closes, i, SLOW_PERIOD)
        new_position = 1 if fast > slow else -1
        if new_position != position:
            direction = "CALL" if new_position == 1 else "PUT"
            call = {
                "time": iso_time(candles[i]["epoch"]),
                "symbol": symbol,
                "call": direction,
                "price": closes[i],
                "fast_sma": fast,
                "slow_sma": slow,
            }
            calls.append(call)
            if position and entry_price is not None:
                trades.append(position * (closes[i] / entry_price - 1.0))
            position = new_position
            entry_price = closes[i]
            entry_epoch = candles[i]["epoch"]
        bar_returns.append(position * (closes[i + 1] / closes[i] - 1.0))

    if position and entry_price is not None:
        trades.append(position * (closes[-1] / entry_price - 1.0))

    equity = 1.0
    equity_curve = [equity]
    for value in bar_returns:
        equity *= 1.0 + value
        equity_curve.append(equity)
    total_return = equity - 1.0
    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            max_drawdown = max(max_drawdown, 1.0 - value / peak)
    wins = [value for value in trades if value > 0]
    losses = [value for value in trades if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    returns_mean = statistics.mean(bar_returns) if bar_returns else 0.0
    volatility = statistics.stdev(bar_returns) if len(bar_returns) > 1 else 0.0
    # Annualization assumes 365 days of 1-minute bars; reported for context only.
    sharpe = (returns_mean / volatility * math.sqrt(365 * 24 * 60)) if volatility else 0.0
    elapsed_minutes = max(1, len(bar_returns))
    years = elapsed_minutes / (365.0 * 24.0 * 60.0)
    cagr = (equity ** (1.0 / years) - 1.0) if equity > 0 else -1.0
    return {
        "symbol": symbol,
        "candles": len(candles),
        "start": iso_time(candles[0]["epoch"]),
        "end": iso_time(candles[-1]["epoch"]),
        "strategy": "SMA(%d)/SMA(%d) crossover, close-to-close, no fees/slippage" % (FAST_PERIOD, SLOW_PERIOD),
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_drawdown * 100.0,
        "annualized_sharpe": sharpe,
        "trade_count": len(trades),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate_pct": (100.0 * len(wins) / len(trades)) if trades else 0.0,
        "average_trade_return_pct": (100.0 * statistics.mean(trades)) if trades else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss else (math.inf if gross_profit else 0.0),
        "last_5_hermes_calls": calls[-5:],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch or locally load Deriv candles and run a simple SMA crossover backtest.")
    parser.add_argument("--offline", nargs="?", const="candles.json", metavar="PATH", help="read local candles.json (or PATH) instead of connecting to Deriv")
    args = parser.parse_args(argv)

    try:
        if args.offline is not None:
            histories = load_offline(args.offline)
            source = "offline:%s" % args.offline
        else:
            histories = {symbol: fetch_history(symbol) for symbol in SYMBOLS}
            source = WS_URL
        output = {"source": source, "granularity_seconds": GRANULARITY, "requested_count": CANDLE_COUNT, "results": []}
        for symbol in SYMBOLS:
            result = backtest(symbol, histories.get(symbol, []))
            output["results"].append(result)
        print(json.dumps(output, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError, WebSocketError, json.JSONDecodeError) as exc:
        print("backtest error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
