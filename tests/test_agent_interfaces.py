"""Contract tests for LEM's paper-only agent interfaces.

These tests use local inputs and temporary files only; no market feed, browser,
account, or order endpoint is contacted.
"""
import csv
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from agents import hephaestus_agent, hermes_agent, hydra_agent
from agents import mnemosyne_agent, sentinel_agent


class HydraTests(unittest.TestCase):
    def test_rsi_returns_none_until_a_full_period_of_changes_exists(self):
        self.assertIsNone(hydra_agent._rsi([1, 2, 3, 4, 5, 6, 7], 7))

    def test_rsi_is_one_hundred_for_strictly_rising_closes(self):
        self.assertEqual(hydra_agent._rsi(list(range(10)), 7), 100.0)

    def test_unconfigured_entry_minute_waits_before_other_checks(self):
        now = datetime(2024, 1, 8, 9, 41, tzinfo=timezone.utc)
        result = hydra_agent.evaluate([], "BUY", now, ["09:40"], 3, 0)
        self.assertEqual(result, {
            "verdict": "WAIT",
            "reason": "not an exact configured entry minute",
        })

    def test_friday_is_vetoed_even_at_a_configured_minute(self):
        now = datetime(2024, 1, 5, 9, 40, tzinfo=timezone.utc)
        result = hydra_agent.evaluate([], "BUY", now, ["09:40"], 3, 0)
        self.assertEqual(result["verdict"], "VETO")
        self.assertIn("Monday through Thursday", result["reason"])

    def test_daily_entry_cap_is_checked_before_candle_readiness(self):
        now = datetime(2024, 1, 8, 9, 40, tzinfo=timezone.utc)
        result = hydra_agent.evaluate([], "BUY", now, ["09:40"], 3, 3)
        self.assertEqual(result, {
            "verdict": "VETO",
            "reason": "daily entry limit reached",
        })

    def test_sar_flip_rejects_short_history(self):
        self.assertFalse(hydra_agent._sar_flip([], "BUY"))


class SentinelTests(unittest.TestCase):
    def test_risk_cap_rejects_zero_and_values_above_one_percent(self):
        ticket = {"entry": 100, "stop": 99}
        for risk_pct in (0, 0.01001):
            with self.subTest(risk_pct=risk_pct):
                result = sentinel_agent.evaluate({"risk_pct": risk_pct}, ticket, "missing.csv")
                self.assertEqual(result["verdict"], "VETO")
                self.assertIn("risk_pct", result["reason"])

    def test_hard_stop_is_mandatory_and_cannot_equal_entry(self):
        missing = sentinel_agent.evaluate({"risk_pct": 0.01}, {"entry": 100}, "missing.csv")
        equal = sentinel_agent.evaluate({"risk_pct": 0.01}, {"entry": 100, "stop": 100}, "missing.csv")
        self.assertIn("hard stop is mandatory", missing["reason"])
        self.assertIn("hard stop distance is zero", equal["reason"])

    def test_valid_ticket_passes_when_no_loss_streak_exists(self):
        result = sentinel_agent.evaluate(
            {"risk_pct": 0.01}, {"entry": 100, "stop": 99}, "missing.csv"
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["risk_pct"], 0.01)

    def test_two_latest_losses_activate_breaker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trades.csv"
            path.write_text("outcome\nWIN\nLOSS\nLOSS\n", encoding="utf-8")
            result = sentinel_agent.evaluate(
                {"risk_pct": 0.01}, {"entry": 100, "stop": 99}, str(path)
            )
        self.assertEqual(result["verdict"], "VETO")
        self.assertIn("two consecutive", result["reason"])

    def test_disabled_loss_breaker_does_not_veto_two_losses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trades.csv"
            path.write_text("outcome\nLOSS\nLOSS\n", encoding="utf-8")
            result = sentinel_agent.evaluate(
                {"risk_pct": 0.01, "ENABLE_2LOSS_BREAKER": False},
                {"entry": 100, "stop": 99}, str(path),
            )
        self.assertEqual(result["verdict"], "PASS")


class HephaestusTests(unittest.TestCase):
    def setUp(self):
        self.candles = [
            {"high": 105, "low": 95, "open": 100, "close": 101}
            for _ in range(6)
        ]

    def test_non_passing_signal_never_builds_ticket(self):
        self.assertIsNone(hephaestus_agent.build(
            self.candles, {"verdict": "VETO", "side": "BUY", "swept_level": 100},
            1000, 0.01,
        ))

    def test_valid_signal_builds_hard_stop_two_to_one_target_and_linear_size(self):
        ticket = hephaestus_agent.build(
            self.candles,
            {"verdict": "PASS", "side": "BUY", "swept_level": 100},
            1000, 0.01,
        )
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["entry"], 101.0)
        self.assertLess(ticket["stop"], ticket["entry"])
        self.assertAlmostEqual(ticket["target"] - ticket["entry"],
                               2 * (ticket["entry"] - ticket["stop"]))
        self.assertEqual(ticket["risk_amount"], 10.0)
        self.assertAlmostEqual(ticket["size_units"],
                               ticket["risk_amount"] / (ticket["entry"] - ticket["stop"]))
        self.assertEqual(ticket["reward_risk"], 2.0)

    def test_invalid_stop_geometry_returns_none(self):
        self.assertIsNone(hephaestus_agent.build(
            self.candles,
            {"verdict": "PASS", "side": "BUY", "swept_level": 101},
            1000, 0.01,
        ))


class MnemosyneTests(unittest.TestCase):
    def test_skip_log_appends_rows_with_one_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "skips.csv"
            now = datetime(2024, 2, 1, 9, 40, tzinfo=timezone.utc)
            mnemosyne_agent.log_skip("R_25", "WAIT", "not scheduled", str(path), now)
            mnemosyne_agent.log_skip("R_75", "SKIP", "bad symbol", str(path), now)
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
                handle.seek(0)
                lines = handle.readlines()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "R_25")
        self.assertEqual(rows[1]["decision"], "SKIP")
        self.assertEqual(sum(line.startswith("timestamp,") for line in lines), 1)
        self.assertTrue(rows[0]["timestamp"].startswith("2024-02-01T09:40:00"))

    def test_trade_log_is_paper_planned_and_daily_count_uses_date_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trades.csv"
            now = datetime(2024, 2, 1, 9, 40, tzinfo=timezone.utc)
            ticket = {"side": "BUY", "entry": 100, "stop": 99, "target": 102,
                      "size_units": 2, "risk_amount": 10}
            mnemosyne_agent.log_trade("R_25", ticket, 0.01, "unit test", str(path), now)
            mnemosyne_agent.log_trade("R_75", ticket, 0.01, "unit test", str(path), now)
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            count = mnemosyne_agent.entries_on_day(str(path), "2024-02-01")
        self.assertEqual(count, 2)
        self.assertEqual(rows[0]["outcome"], "PAPER_PLANNED")
        self.assertEqual(rows[0]["side"], "BUY")


class HermesTests(unittest.TestCase):
    def test_run_refuses_non_paper_mode_before_any_feed_or_order_work(self):
        settings = {"timezone": "Africa/Nairobi", "symbol": "R_25"}
        with mock.patch.object(hermes_agent, "_settings", return_value=settings), \
             mock.patch.object(hermes_agent.mnemosyne_agent, "log_skip") as log_skip, \
             mock.patch.object(hermes_agent, "_block") as block, \
             mock.patch.object(hermes_agent.deriv_feed, "fetch_candles") as fetch:
            result = hermes_agent.run(False)
        self.assertEqual(result, 0)
        log_skip.assert_called_once()
        self.assertEqual(log_skip.call_args.args[:3], ("R_25", "SKIP", "paper mode is mandatory; no real execution path exists"))
        block.assert_called_once()
        fetch.assert_not_called()

    def test_command_line_requires_explicit_paper_flag(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["hermes_agent.py"]), \
             redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            hermes_agent.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--paper", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
