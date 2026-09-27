"""Deterministic pre-analysis of the first 30 OHLC records supplied by an operator.

This module reads local CSV only. It does not fetch market data or predict prices.
"""

import argparse
import csv
import math
import sys

HORIZONS_MINUTES = (240, 180, 60, 45, 30, 15)
WAITING_MESSAGE = "waiting for first 30 minutes of session data"
REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")


def load_bars(csv_path):
    """Load and validate up to the first 30 chronological OHLC rows from CSV."""
    bars = []
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            return bars
        columns = {name.strip().lower(): name for name in reader.fieldnames}
        missing = [name for name in REQUIRED_COLUMNS if name not in columns]
        if missing:
            raise ValueError("missing required CSV columns: " + ", ".join(missing))

        for row_number, row in enumerate(reader, start=2):
            if len(bars) >= 30:
                break
            timestamp = (row.get(columns["timestamp"]) or "").strip()
            if not timestamp:
                raise ValueError("row {} has an empty timestamp".format(row_number))
            try:
                values = {
                    name: float(row[columns[name]])
                    for name in ("open", "high", "low", "close")
                }
            except (TypeError, ValueError):
                raise ValueError("row {} has a non-numeric OHLC value".format(row_number))
            if not all(math.isfinite(value) for value in values.values()):
                raise ValueError("row {} has a non-finite OHLC value".format(row_number))
            if (values["high"] < max(values["open"], values["close"])
                    or values["low"] > min(values["open"], values["close"])
                    or values["low"] > values["high"]):
                raise ValueError("row {} has inconsistent OHLC values".format(row_number))
            bars.append({"timestamp": timestamp, **values})
    return bars


def _number(value):
    return "{:.8g}".format(value)


def _bar_ref(index, bar):
    return "bar {} ({})".format(index + 1, bar["timestamp"])


def _find_gaps(bars):
    """Find 3-candle gaps and mark them inverted on a later invalidating close."""
    zones = []
    for index in range(len(bars) - 2):
        first = bars[index]
        third = bars[index + 2]
        if first["high"] < third["low"]:
            direction = "bullish"
            lower, upper = first["high"], third["low"]
        elif first["low"] > third["high"]:
            direction = "bearish"
            lower, upper = third["high"], first["low"]
        else:
            continue

        zone = {
            "direction": direction,
            "lower": lower,
            "upper": upper,
            "start": index,
            "end": index + 2,
            "inverted": None,
        }
        for later_index in range(index + 3, len(bars)):
            close = bars[later_index]["close"]
            if direction == "bullish" and close < lower:
                zone["inverted"] = (later_index, "bearish", "below", lower)
                break
            if direction == "bearish" and close > upper:
                zone["inverted"] = (later_index, "bullish", "above", upper)
                break
        zones.append(zone)
    return zones


def _equal_levels(bars, field, tolerance):
    groups = []
    for index, bar in enumerate(bars):
        value = bar[field]
        group = next(
            (item for item in groups
             if abs(value - sum(item["values"]) / len(item["values"])) <= tolerance),
            None,
        )
        if group is None:
            groups.append({"values": [value], "indices": [index]})
        else:
            group["values"].append(value)
            group["indices"].append(index)
    return [group for group in groups if len(group["indices"]) >= 2]


def analyze(bars):
    """Return deterministic observations from supplied rows; never invent prices."""
    if not bars:
        return None
    session_high = max(bar["high"] for bar in bars)
    session_low = min(bar["low"] for bar in bars)
    first_open = bars[0]["open"]
    last_close = bars[-1]["close"]
    if last_close > first_open:
        bias = "Bullish (last close above first open)"
        invalidation = "A close below observed session low {}".format(_number(session_low))
    elif last_close < first_open:
        bias = "Bearish (last close below first open)"
        invalidation = "A close above observed session high {}".format(_number(session_high))
    else:
        bias = "Neutral (last close equals first open)"
        invalidation = "A close outside observed range [{}, {}]".format(
            _number(session_low), _number(session_high)
        )

    zones = []
    for zone in _find_gaps(bars):
        span = "{}-{}".format(
            _bar_ref(zone["start"], bars[zone["start"]]),
            _bar_ref(zone["end"], bars[zone["end"]]),
        )
        lower, upper = _number(zone["lower"]), _number(zone["upper"])
        inverted = zone["inverted"]
        if inverted:
            later_index, new_direction, relation, boundary = inverted
            zones.append(
                "IFVG ({} inversion of {} gap) zone [{}, {}], formed at {}; "
                "later close {} {} {}".format(
                    new_direction, zone["direction"], lower, upper, span,
                    _number(bars[later_index]["close"]), relation,
                    _number(boundary),
                )
            )
        else:
            zones.append(
                "FVG ({} gap) zone [{}, {}], formed at {}".format(
                    zone["direction"], lower, upper, span
                )
            )

    tolerance = max(abs(last_close) * 0.0001, 1e-8)
    liquidity = []
    for field, label in (("high", "equal highs"), ("low", "equal lows")):
        groups = _equal_levels(bars, field, tolerance)
        if groups:
            for group in groups:
                level = sum(group["values"]) / len(group["values"])
                refs = ", ".join(str(index + 1) for index in group["indices"])
                liquidity.append("{} near {} at bars {}".format(label, _number(level), refs))
        else:
            liquidity.append("no {} detected".format(label))
    recent = bars[-5:]
    recent_start = len(bars) - len(recent)
    recent_high_index = max(range(len(recent)), key=lambda i: recent[i]["high"])
    recent_low_index = min(range(len(recent)), key=lambda i: recent[i]["low"])
    liquidity.append(
        "recent 5-record high {} at {}; recent 5-record low {} at {}".format(
            _number(recent[recent_high_index]["high"]),
            _bar_ref(recent_start + recent_high_index, recent[recent_high_index]),
            _number(recent[recent_low_index]["low"]),
            _bar_ref(recent_start + recent_low_index, recent[recent_low_index]),
        )
    )

    return {
        "bias": bias,
        "session_high": session_high,
        "session_low": session_low,
        "first_open": first_open,
        "last_close": last_close,
        "last_timestamp": bars[-1]["timestamp"],
        "zones": zones,
        "liquidity": liquidity,
        "invalidation": invalidation,
    }


def format_report(result):
    lines = [
        "Snapshot uses only the supplied first 30 records; horizons are scenario labels, not price predictions.",
        "",
    ]
    for horizon in HORIZONS_MINUTES:
        lines.extend([
            "=== {}-minute horizon ===".format(horizon),
            "Direction bias: {}".format(result["bias"]),
            "Key levels: session high {}; session low {}; first open {}; last close {} at {}".format(
                _number(result["session_high"]), _number(result["session_low"]),
                _number(result["first_open"]), _number(result["last_close"]),
                result["last_timestamp"],
            ),
            "FVG/IFVG zones:",
        ])
        lines.extend("- " + zone for zone in result["zones"])
        if not result["zones"]:
            lines.append("- None observed in supplied records.")
        lines.append("Liquidity pools:")
        lines.extend("- " + item for item in result["liquidity"])
        lines.append("Invalidation: {}".format(result["invalidation"]))
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze the first 30 OHLC rows in a local CSV file."
    )
    parser.add_argument(
        "csv_path", nargs="?", help="CSV with timestamp,open,high,low,close columns"
    )
    args = parser.parse_args(argv)
    if not args.csv_path:
        print(WAITING_MESSAGE)
        return 0
    try:
        bars = load_bars(args.csv_path)
    except FileNotFoundError:
        print(WAITING_MESSAGE)
        return 0
    except (OSError, csv.Error, ValueError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2
    if not bars:
        print(WAITING_MESSAGE)
        return 0
    print(format_report(analyze(bars)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
