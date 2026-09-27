"""Atlas: classify the session regime from M15 and M1 EMA structure."""

from __future__ import annotations


def _ema(values, period):
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    result = sum(values[:period]) / period
    for value in values[period:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def _slope(values, period=20, lookback=5):
    if len(values) < period + lookback:
        return None
    return _ema(values[-(period + lookback):-lookback], period), _ema(values, period)


def evaluate(m15, m1):
    """Return a directional regime verdict; insufficient candles are WAIT."""
    if len(m15) < 55 or len(m1) < 55:
        return {"verdict": "WAIT", "bias": "FLAT", "reason": "insufficient M15/M1 history for EMA regime"}
    closes15 = [float(c["close"]) for c in m15]
    closes1 = [float(c["close"]) for c in m1]
    e20_15, e50_15 = _ema(closes15, 20), _ema(closes15, 50)
    e20_1, e50_1 = _ema(closes1, 20), _ema(closes1, 50)
    slope = _slope(closes15, 20)
    slope1 = _slope(closes1, 20)
    if not slope or not slope1:
        return {"verdict": "WAIT", "bias": "FLAT", "reason": "EMA slope history unavailable"}
    rising = slope[1] > slope[0] and slope1[1] > slope1[0]
    falling = slope[1] < slope[0] and slope1[1] < slope1[0]
    if e20_15 > e50_15 and e20_1 > e50_1 and rising:
        return {"verdict": "PASS", "bias": "BUY", "reason": "M15 and M1 EMA20 above EMA50 with rising EMA20 slopes"}
    if e20_15 < e50_15 and e20_1 < e50_1 and falling:
        return {"verdict": "PASS", "bias": "SELL", "reason": "M15 and M1 EMA20 below EMA50 with falling EMA20 slopes"}
    return {"verdict": "SKIP", "bias": "FLAT", "reason": "EMA structure is mixed/choppy across M15 and M1"}
