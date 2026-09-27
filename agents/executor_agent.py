"""Schedule-enforced paper trader; no broker or market-data integration exists."""

import argparse
import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE_PATH = ROOT / "config" / "execution_schedule.json"
STATE_PATH = ROOT / "data" / "paper_trader_state.json"
LOG_PATH = ROOT / "logs" / "paper_trades.jsonl"


def _read_json(path):
    with path.open("r", encoding="ascii") as handle:
        return json.load(handle)


def _number(value, label):
    if isinstance(value, bool):
        raise ValueError(label + " must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(label + " must be a finite number")
    if not math.isfinite(result):
        raise ValueError(label + " must be a finite number")
    return result


def _positive(value, label):
    result = _number(value, label)
    if result <= 0:
        raise ValueError(label + " must be greater than zero")
    return result


def _aware_datetime(value, timezone):
    if value is None:
        return datetime.now(timezone)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            raise ValueError("timestamp must be ISO 8601 and timezone-aware")
    else:
        raise ValueError("timestamp must be ISO 8601 and timezone-aware")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed.astimezone(timezone)


class PaperTrader:
    """Persistent paper ledger with strict Nairobi-minute entry checks."""

    def __init__(self, schedule_path=None, state_path=None, log_path=None):
        self.schedule_path = Path(schedule_path or SCHEDULE_PATH)
        self.state_path = Path(state_path or STATE_PATH)
        self.log_path = Path(log_path or LOG_PATH)
        self.schedule = _read_json(self.schedule_path)
        try:
            self.timezone = ZoneInfo(self.schedule["timezone"])
        except (KeyError, ZoneInfoNotFoundError):
            raise ValueError("configured IANA timezone is unavailable")
        if self.state_path.exists():
            self.state = _read_json(self.state_path)
        else:
            self.state = {
                "version": 1,
                "paper_balance": None,
                "open_positions": [],
                "trades_by_day": {}
            }
        self.state.setdefault("open_positions", [])
        self.state.setdefault("trades_by_day", {})
        self.state.setdefault("paper_balance", None)

    def _persist(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(self.state_path.name + ".tmp")
        with temporary.open("w", encoding="ascii", newline="\n") as handle:
            json.dump(self.state, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(str(temporary), str(self.state_path))

    def _log(self, event):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="ascii", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True, default=str))
            handle.write("\n")

    def _local_time(self, value=None):
        return _aware_datetime(value, self.timezone)

    def _weekday_allowed(self, local_time):
        return local_time.strftime("%A") in self.schedule["allowed_weekdays"]

    def allowed_entry_minutes(self):
        return [session["entry_time"] for session in self.schedule["sessions"]]

    def pre_analysis_context(self, now=None, volatility_regime=None, rvi_state=None, levels=None):
        """Describe preparation windows only; this function never makes a trade decision."""
        local_time = self._local_time(now)
        session = None
        if self._weekday_allowed(local_time):
            clock = local_time.strftime("%H:%M")
            for item in self.schedule["sessions"]:
                if item["pre_analysis_start"] <= clock < item["session_start"]:
                    session = item
                    break
        return {
            "allowed": session is not None,
            "local_time": local_time.isoformat(),
            "session_start": session["session_start"] if session else None,
            "prepared_context": {
                "volatility_regime": volatility_regime,
                "rvi_state": rvi_state,
                "levels": levels
            },
            "trade_decision": None,
            "note": "Preparation only; research and planning do not decide whether to trade."
        }

    def evaluate_setup(self, candidate, now=None):
        """Log and validate one setup; accepted quantity risks at most 1 percent."""
        raw_candidate = candidate
        if not isinstance(candidate, dict):
            candidate = {}
        local_time = None

        def reject(reason):
            event = {
                "event": "setup_evaluated",
                "result": "rejected",
                "reason": reason,
                "evaluated_at": local_time.isoformat() if local_time else self._local_time().isoformat(),
                "candidate": raw_candidate
            }
            self._log(event)
            return {"accepted": False, "reason": reason}

        try:
            requested_time = now if now is not None else candidate.get("timestamp")
            local_time = self._local_time(requested_time)
        except (ValueError, TypeError) as exc:
            return reject("invalid_timestamp: " + str(exc))
        if not isinstance(raw_candidate, dict):
            return reject("candidate_must_be_a_json_object")
        if not self._weekday_allowed(local_time):
            return reject("weekday_not_allowed")
        if local_time.strftime("%H:%M") not in self.allowed_entry_minutes():
            return reject("outside_allowed_entry_minute")

        try:
            symbol = str(candidate.get("symbol", "")).strip()
            side = str(candidate.get("side", "")).strip().lower()
            if not symbol:
                return reject("symbol_required")
            if side not in ("long", "short"):
                return reject("side_must_be_long_or_short")
            entry = _positive(candidate.get("entry_price"), "entry_price")
            stop = _positive(candidate.get("hard_stop"), "hard_stop")
            if side == "long" and stop >= entry:
                return reject("long_hard_stop_must_be_below_entry")
            if side == "short" and stop <= entry:
                return reject("short_hard_stop_must_be_above_entry")
            balance = self.state.get("paper_balance")
            if balance is None:
                balance = _positive(candidate.get("paper_balance"), "initial paper_balance")
            else:
                balance = _positive(balance, "paper_balance")
        except ValueError as exc:
            return reject("invalid_setup: " + str(exc))

        local_day = local_time.date().isoformat()
        daily_count = int(self.state["trades_by_day"].get(local_day, 0))
        max_trades = int(self.schedule["execution"]["max_trades_per_local_day"])
        if daily_count >= max_trades:
            return reject("daily_trade_limit_reached")

        execution = self.schedule["execution"]
        risk_fraction = float(execution["risk_cap_percent_of_paper_balance_per_trade"]) / 100.0
        max_risk = balance * risk_fraction
        risk_per_unit = abs(entry - stop)
        quantity = max_risk / risk_per_unit
        opened_at = local_time
        deadline = opened_at + timedelta(minutes=int(execution["max_hold_minutes"]))
        position = {
            "position_id": str(__import__("uuid").uuid4()),
            "symbol": symbol,
            "side": side,
            "entry_time": opened_at.isoformat(),
            "entry_date": local_day,
            "entry_price": entry,
            "hard_stop": stop,
            "quantity": quantity,
            "risk_amount": max_risk,
            "max_risk_amount": max_risk,
            "max_hold_deadline": deadline.isoformat(),
            "take_profit_at_minutes_after_entry": int(execution["take_profit_minutes_after_entry"])
        }
        self.state["paper_balance"] = balance
        self.state["trades_by_day"][local_day] = daily_count + 1
        self.state["open_positions"].append(position)
        self._persist()
        self._log({
            "event": "setup_evaluated",
            "result": "accepted",
            "reason": "schedule_and_risk_checks_passed",
            "evaluated_at": opened_at.isoformat(),
            "candidate": raw_candidate,
            "position": position
        })
        return {"accepted": True, "position": position}

    def update_price(self, symbol, price, now=None):
        """Apply a supplied quote and close at stop or the 45-minute max-hold deadline."""
        local_time = self._local_time(now)
        quote = _positive(price, "price")
        symbol = str(symbol).strip()
        closed = []
        remaining = []
        for position in self.state["open_positions"]:
            if position["symbol"] != symbol:
                remaining.append(position)
                continue
            deadline = datetime.fromisoformat(position["max_hold_deadline"])
            is_long = position["side"] == "long"
            stop_hit = quote <= position["hard_stop"] if is_long else quote >= position["hard_stop"]
            if stop_hit:
                exit_price = position["hard_stop"]
                reason = "hard_stop"
            elif local_time >= deadline:
                exit_price = quote
                reason = "time_exit_max_hold_45m"
            else:
                remaining.append(position)
                continue
            points = exit_price - position["entry_price"]
            pnl = points * position["quantity"] * (1.0 if is_long else -1.0)
            if pnl > 0:
                outcome = "win"
            elif pnl < 0:
                outcome = "loss"
            else:
                outcome = "breakeven"
            self.state["paper_balance"] = float(self.state["paper_balance"]) + pnl
            record = {
                "event": "position_closed",
                "position_id": position["position_id"],
                "symbol": symbol,
                "side": position["side"],
                "entry_time": position["entry_time"],
                "exit_time": local_time.isoformat(),
                "entry_price": position["entry_price"],
                "observed_price": quote,
                "exit_price": exit_price,
                "quantity": position["quantity"],
                "pnl": pnl,
                "outcome": outcome,
                "close_reason": reason,
                "paper_balance_after_close": self.state["paper_balance"]
            }
            self._log(record)
            closed.append(record)
        if len(remaining) != len(self.state["open_positions"]):
            self.state["open_positions"] = remaining
            self._persist()
        return closed

    def status(self):
        local_time = self._local_time()
        return {
            "mode": "paper_only",
            "timezone": self.schedule["timezone"],
            "local_time": local_time.isoformat(),
            "allowed_weekdays": self.schedule["allowed_weekdays"],
            "allowed_entry_minutes": self.allowed_entry_minutes(),
            "paper_balance": self.state["paper_balance"],
            "open_positions": self.state["open_positions"],
            "market_data_connection": False,
            "broker_connection": False,
            "note": "No live data or broker is connected. Supply paper candidates and prices explicitly."
        }


def run(action="", paper=True):
    """Compatibility status helper; it never submits or simulates an order."""
    if not paper:
        return {"status": "blocked", "mode": "live", "orders_submitted": 0}
    return {
        "status": "ready",
        "role": "executor",
        "action": action,
        "mode": "scheduled_paper_only",
        "market_data": "not_configured",
        "broker": "not_configured",
        "orders_submitted": 0
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run LEM's local scheduled paper ledger; no live data or broker access."
    )
    parser.add_argument("--paper", action="store_true", help="required; live trading is unavailable")
    parser.add_argument("--candidate-file", help="JSON object describing one setup to evaluate")
    parser.add_argument("--symbol", help="symbol for a supplied quote to update open paper positions")
    parser.add_argument("--price", type=float, help="supplied quote for stop or max-hold evaluation")
    parser.add_argument("--balance", type=float, help="initial paper balance for the first accepted setup")
    parser.add_argument("--now", help="optional ISO 8601 timestamp with timezone offset, for replay/testing")
    args = parser.parse_args(argv)
    if not args.paper:
        parser.error("live trading is unavailable; pass --paper")
    if args.price is not None and not (args.symbol or args.candidate_file):
        parser.error("--price requires --symbol or a --candidate-file with a symbol")

    try:
        trader = PaperTrader()
        result = {"mode": "paper_only"}
        if args.price is not None:
            symbol = args.symbol
            if not symbol and args.candidate_file:
                with open(args.candidate_file, "r", encoding="ascii") as handle:
                    candidate_for_symbol = json.load(handle)
                symbol = candidate_for_symbol.get("symbol")
            if not symbol:
                parser.error("candidate file must contain a symbol when --price is used")
            result["closed_positions"] = trader.update_price(symbol, args.price, args.now)
        if args.candidate_file:
            with open(args.candidate_file, "r", encoding="ascii") as handle:
                candidate = json.load(handle)
            if not isinstance(candidate, dict):
                raise ValueError("candidate file must contain a JSON object")
            candidate = dict(candidate)
            if args.balance is not None:
                candidate["paper_balance"] = args.balance
            result["setup"] = trader.evaluate_setup(candidate, args.now)
        else:
            result["status"] = trader.status()
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("Paper trader error: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
