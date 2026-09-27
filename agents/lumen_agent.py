"""Lumen: event/news gate with no synthetic-index news assumptions."""

from __future__ import annotations

from datetime import datetime, timezone


def evaluate(symbol, settings, now=None):
    """No-op for synthetic symbols; lock real instruments around configured events."""
    symbol = str(symbol).upper()
    if symbol.startswith("R_"):
        return {"verdict": "PASS", "reason": "synthetic index: no reliable instrument-specific news feed configured; no news veto applied"}
    now = now or datetime.now(timezone.utc)
    lock_minutes = int(settings.get("event_lock_minutes", 30))
    for item in settings.get("event_lock_utc", []):
        try:
            at = datetime.fromisoformat(str(item["time"]).replace("Z", "+00:00"))
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            if abs((now - at.astimezone(timezone.utc)).total_seconds()) <= lock_minutes * 60:
                return {"verdict": "VETO", "reason": "configured real-instrument event lock: " + str(item.get("label", "event"))}
        except (KeyError, TypeError, ValueError):
            continue
    return {"verdict": "PASS", "reason": "no configured real-instrument event lock is active; no live news feed is connected"}
