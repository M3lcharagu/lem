"""Sentinel: enforce risk caps, hard stops, and optional two-loss breaker."""

from __future__ import annotations

import csv
import os


def _loss_streak(path):
    if not os.path.exists(path):
        return 0
    streak = 0
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return 0
    for row in reversed(rows):
        outcome = str(row.get("outcome", "")).upper()
        if outcome not in ("WIN", "LOSS"):
            continue
        if outcome == "LOSS":
            streak += 1
        else:
            break
    return streak


def evaluate(settings, ticket, trades_path="logs/trades.csv"):
    risk_pct = float(settings.get("risk_pct", 0.01))
    if not 0.0 < risk_pct <= 0.01:
        return {"verdict": "VETO", "reason": "risk_pct must be greater than 0 and at most 0.01"}
    if not ticket or ticket.get("stop") is None:
        return {"verdict": "VETO", "reason": "a hard stop is mandatory"}
    try:
        if float(ticket["entry"]) == float(ticket["stop"]):
            return {"verdict": "VETO", "reason": "hard stop distance is zero"}
    except (KeyError, TypeError, ValueError):
        return {"verdict": "VETO", "reason": "ticket entry/stop is invalid"}
    enabled = bool(settings.get("ENABLE_2LOSS_BREAKER", True))
    streak = _loss_streak(trades_path)
    if enabled and streak >= 2:
        return {"verdict": "VETO", "reason": "two consecutive recorded losses; breaker is active"}
    return {"verdict": "PASS", "risk_pct": risk_pct, "reason": "risk cap, hard stop and loss-breaker checks passed"}
