"""Hephaestus: build a paper ticket with hard stop, 2:1 target and risk size."""

from __future__ import annotations


def build(candles, signal, account_balance, risk_pct):
    if not signal or signal.get("verdict") != "PASS" or not candles:
        return None
    side = signal["side"]
    last = candles[-1]
    entry = float(last["close"])
    swept = float(signal["swept_level"])
    recent_range = max(float(c["high"]) - float(c["low"]) for c in candles[-6:])
    pad = max(recent_range * 0.05, abs(entry) * 1e-8)
    stop = swept - pad if side == "BUY" else swept + pad
    distance = abs(entry - stop)
    if distance <= 0:
        return None
    target = entry + 2.0 * distance if side == "BUY" else entry - 2.0 * distance
    risk_amount = float(account_balance) * float(risk_pct)
    # Price-distance units assume linear one-unit P/L; broker contract multipliers are unknown.
    size_units = risk_amount / distance
    return {
        "side": side, "entry": entry, "stop": stop, "target": target,
        "risk_amount": risk_amount, "size_units": size_units,
        "swept_level": swept, "reward_risk": 2.0,
        "sizing_note": "paper linear price-unit estimate only; verify Deriv contract multiplier before any real use",
    }
