"""Mnemosyne: append-only timestamped CSV audit logs for every decision."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TRADE_FIELDS = ["timestamp", "symbol", "side", "entry", "stop", "target", "size_units", "risk_pct", "risk_amount", "swept_level", "reason", "outcome"]
SKIP_FIELDS = ["timestamp", "symbol", "decision", "reason"]


def _append(path, fields, row):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def timestamp(now=None):
    now = now or datetime.now(ZoneInfo("Africa/Nairobi"))
    return now.isoformat(timespec="seconds")


def log_skip(symbol, decision, reason, path="logs/skips.csv", now=None):
    _append(path, SKIP_FIELDS, {"timestamp": timestamp(now), "symbol": symbol, "decision": decision, "reason": reason})


def log_trade(symbol, ticket, risk_pct, reason, path="logs/trades.csv", now=None):
    row = {"timestamp": timestamp(now), "symbol": symbol, **ticket, "risk_pct": risk_pct, "reason": reason, "outcome": "PAPER_PLANNED"}
    _append(path, TRADE_FIELDS, row)


def entries_on_day(path="logs/trades.csv", day=None):
    if not os.path.exists(path):
        return 0
    day = day or datetime.now(ZoneInfo("Africa/Nairobi")).date().isoformat()
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            return sum(1 for row in csv.DictReader(handle) if str(row.get("timestamp", "")).startswith(day))
    except (OSError, csv.Error):
        return 0
