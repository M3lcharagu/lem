"""Offline regressions for LEM's actual paper-agent interfaces."""
import csv
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from agents import hephaestus_agent, hermes_agent, hydra_agent, mnemosyne_agent, sentinel_agent


def bars(side="BUY"):
    closes = [100.0 + i for i in range(55)] if side == "BUY" else [200.0 - i for i in range(55)]
    result = [{"open": c - .25, "high": c + .5, "low": c - .5, "close": c} for c in closes]
    if side == "BUY":
        result[-1]["low"] = min(x["low"] for x in result[-7:-1]) - 1
    else:
        result[-1]["open"] += .5
        result[-1]["high"] = max(x["high"] for x in result[-7:-1]) + 1
    return result


class HydraTests(unittest.TestCase):
    now = datetime(2024, 1, 8, 9, 40, tzinfo=timezone.utc)

    def check(self, side="BUY", data=None, entries=0, now=None):
        return hydra_agent.evaluate(bars(side) if data is None else data, side,
                                    now or self.now, ["09:40"], 3, entries)

    def test_ema20_50_and_rsi7_agreement_at_inclusive_thresholds(self):
        with mock.patch.object(hydra_agent, "_rsi", return_value=40), \
             mock.patch.object(hydra_agent, "_sar_flip", return_value=True), \
             mock.patch.object(hydra_agent, "_ema", wraps=hydra_agent._ema) as ema:
            self.assertEqual(self.check()["verdict"], "PASS")
        self.assertEqual([c.args[1] for c in ema.call_args_list], [20, 50])
        with mock.patch.object(hydra_agent, "_ema", side_effect=[50, 60]), \
             mock.patch.object(hydra_agent, "_rsi", return_value=40), \
             mock.patch.object(hydra_agent, "_sar_flip", return_value=True):
            self.assertIn("EMA20>EMA50", self.check()["reason"])
        with mock.patch.object(hydra_agent, "_rsi", return_value=41), \
             mock.patch.object(hydra_agent, "_sar_flip", return_value=True):
            self.assertIn("RSI7", self.check()["reason"])
        with mock.patch.object(hydra_agent, "_rsi", return_value=60), \
             mock.patch.object(hydra_agent, "_sar_flip", return_value=True):
            self.assertEqual(self.check("SELL")["verdict"], "PASS")
        with mock.patch.object(hydra_agent, "_rsi", return_value=59), \
             mock.patch.object(hydra_agent, "_sar_flip", return_value=True):
            self.assertIn("RSI7", self.check("SELL")["reason"])

    def test_sweep_gate_and_monday_thursday_exact_minute_daily_cap(self):
        data = bars()
        data[-1]["low"] = min(x["low"] for x in data[-7:-1])
        with mock.patch.object(hydra_agent, "_rsi", return_value=40), \
             mock.patch.object(hydra_agent, "_sar_flip", return_value=True):
            result = self.check(data=data)
        self.assertEqual(result["verdict"], "VETO")
        self.assertIn("sweep", result["reason"])
        for day in (8, 9, 10, 11):
            date = datetime(2024, 1, day, 9, 40, tzinfo=timezone.utc)
            self.assertIn("insufficient M1", self.check(data=[], now=date)["reason"])
        late = self.check(now=datetime(2024, 1, 8, 9, 41, tzinfo=timezone.utc))
        self.assertEqual(late["verdict"], "WAIT")
        self.assertIn("exact configured entry minute", late["reason"])
        friday = self.check(now=datetime(2024, 1, 12, 9, 40, tzinfo=timezone.utc))
        self.assertEqual(friday["verdict"], "VETO")
        self.assertIn("Monday through Thursday", friday["reason"])
        self.assertEqual(self.check(entries=3)["reason"], "daily entry limit reached")


class SentinelTests(unittest.TestCase):
    def test_risk_fractions_and_two_consecutive_loss_breaker(self):
        for fraction in (.01, .0075):
            out = sentinel_agent.evaluate({"risk_pct": fraction}, {"entry": 100, "stop": 99}, "missing.csv")
            self.assertEqual((out["verdict"], out["risk_pct"]), ("PASS", fraction))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "trades.csv"
            path.write_text("outcome\nWIN\nLOSS\nLOSS\n", encoding="utf-8")
            out = sentinel_agent.evaluate({"risk_pct": .0075}, {"entry": 100, "stop": 99}, str(path))
        self.assertEqual(out["verdict"], "VETO")
        self.assertIn("two consecutive", out["reason"])


class HephaestusTests(unittest.TestCase):
    def test_stop_is_beyond_swept_level_and_target_is_exactly_2r(self):
        candles = [{"high": 105, "low": 95, "close": 101} for _ in range(6)]
        ticket = hephaestus_agent.build(candles, {"verdict": "PASS", "side": "BUY", "swept_level": 100}, 1000, .01)
        self.assertLess(ticket["stop"], ticket["swept_level"])
        self.assertAlmostEqual(ticket["target"] - ticket["entry"], 2 * (ticket["entry"] - ticket["stop"]))
        self.assertEqual(ticket["reward_risk"], 2.0)


class MnemosyneTests(unittest.TestCase):
    def test_trade_and_skip_csv_append_format_and_header(self):
        now = datetime(2024, 2, 1, 9, 40, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            trades, skips = Path(d) / "t.csv", Path(d) / "s.csv"
            ticket = {"side": "BUY", "entry": 100, "stop": 99, "target": 102,
                      "size_units": 2, "risk_amount": 10, "swept_level": 99.5}
            for sym, risk in (("R_25", .01), ("R_75", .0075)):
                mnemosyne_agent.log_trade(sym, ticket, risk, "test", str(trades), now)
            mnemosyne_agent.log_skip("R_25", "WAIT", "entry minute", str(skips), now)
            mnemosyne_agent.log_skip("R_75", "VETO", "daily limit", str(skips), now)
            with trades.open(newline="", encoding="utf-8") as f:
                tr = csv.DictReader(f); trade_rows = list(tr); trade_fields = tr.fieldnames
            with skips.open(newline="", encoding="utf-8") as f:
                sk = csv.DictReader(f); skip_rows = list(sk); skip_fields = sk.fieldnames
        self.assertEqual(trade_fields, mnemosyne_agent.TRADE_FIELDS)
        self.assertEqual(skip_fields, mnemosyne_agent.SKIP_FIELDS)
        self.assertEqual(len(trade_rows), 2); self.assertEqual(len(skip_rows), 2)
        self.assertEqual(trade_rows[1]["risk_pct"], "0.0075")
        self.assertEqual(trade_rows[0]["outcome"], "PAPER_PLANNED")
        self.assertEqual(skip_rows[0]["decision"], "WAIT")
        self.assertEqual(skip_rows[1]["reason"], "daily limit")
        self.assertTrue(trade_rows[0]["timestamp"].startswith("2024-02-01T09:40:00"))


class HermesVetoTests(unittest.TestCase):
    def test_final_sentinel_veto_blocks_otherwise_valid_trade(self):
        settings = {"timezone": "Africa/Nairobi", "symbol": "R_25", "allowed_symbols": ["R_25"],
                    "entry_times": ["09:40"], "max_trades_per_day": 3,
                    "paper_balance": 10000, "risk_pct": .01}
        now = datetime(2024, 1, 8, 9, 40, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d, ExitStack() as stack:
            stack.enter_context(mock.patch.object(hermes_agent, "ROOT", Path(d)))
            stack.enter_context(mock.patch.object(hermes_agent, "datetime", mock.Mock(now=mock.Mock(return_value=now))))
            stack.enter_context(mock.patch.object(hermes_agent, "_settings", return_value=settings))
            stack.enter_context(mock.patch.object(hermes_agent.deriv_feed, "browser_probe", return_value={"status": "disabled"}))
            stack.enter_context(mock.patch.object(hermes_agent.deriv_feed, "fetch_candles", side_effect=[[{}], [{}]]))
            stack.enter_context(mock.patch.object(hermes_agent.atlas_agent, "evaluate", return_value={"verdict": "PASS", "bias": "BUY"}))
            stack.enter_context(mock.patch.object(hermes_agent.lumen_agent, "evaluate", return_value={"verdict": "PASS"}))
            stack.enter_context(mock.patch.object(hermes_agent.mnemosyne_agent, "entries_on_day", return_value=0))
            stack.enter_context(mock.patch.object(hermes_agent.hydra_agent, "evaluate", return_value={"verdict": "PASS", "reason": "signal ok"}))
            stack.enter_context(mock.patch.object(hermes_agent.hephaestus_agent, "build", return_value={"entry": 100, "stop": 99, "target": 102}))
            stack.enter_context(mock.patch.object(hermes_agent.sentinel_agent, "evaluate", return_value={"verdict": "VETO", "reason": "breaker"}))
            skipped = stack.enter_context(mock.patch.object(hermes_agent.mnemosyne_agent, "log_skip"))
            traded = stack.enter_context(mock.patch.object(hermes_agent.mnemosyne_agent, "log_trade"))
            stack.enter_context(mock.patch.object(hermes_agent, "_block"))
            self.assertEqual(hermes_agent.run(True), 0)
        self.assertEqual(skipped.call_args.args[1:3], ("SKIP", "breaker"))
        traded.assert_not_called()


if __name__ == "__main__":
    unittest.main()
