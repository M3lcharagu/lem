"""Hydra: exact-time M1 entry setup (EMA bias, RSI7, sweep and SAR flip)."""

from __future__ import annotations


def _ema(values, period):
    alpha = 2.0 / (period + 1.0)
    result = sum(values[:period]) / period
    for value in values[period:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def _rsi(values, period=7):
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(0.0, x) for x in changes[-period:]]
    losses = [max(0.0, -x) for x in changes[-period:]]
    avg_gain, avg_loss = sum(gains) / period, sum(losses) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def _sar_flip(candles, side):
    """Small PSAR state calculation; require the latest completed candle to flip."""
    if len(candles) < 4:
        return False
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    close = [float(c["close"]) for c in candles]
    up = close[1] >= close[0]
    sar = lows[0] if up else highs[0]
    extreme = highs[0] if up else lows[0]
    af, step, cap = 0.02, 0.02, 0.2
    states = []
    for i in range(1, len(candles)):
        prior_up = up
        sar = sar + af * (extreme - sar)
        if up:
            sar = min(sar, lows[i - 1], lows[i - 2] if i > 1 else lows[i - 1])
            if lows[i] < sar:
                up, sar, extreme, af = False, extreme, lows[i], step
            elif highs[i] > extreme:
                extreme, af = highs[i], min(cap, af + step)
        else:
            sar = max(sar, highs[i - 1], highs[i - 2] if i > 1 else highs[i - 1])
            if highs[i] > sar:
                up, sar, extreme, af = True, extreme, highs[i], step
            elif lows[i] < extreme:
                extreme, af = lows[i], min(cap, af + step)
        states.append((prior_up, up))
    return bool(states and states[-1][0] != states[-1][1] and ((side == "BUY" and states[-1][1]) or (side == "SELL" and not states[-1][1])))


def evaluate(candles, bias, now, entry_times, max_daily, entries_today):
    """Return a candidate or explicit veto. Caller passes Africa/Nairobi local time."""
    if now.strftime("%H:%M") not in entry_times:
        return {"verdict": "WAIT", "reason": "not an exact configured entry minute"}
    if now.weekday() > 3:
        return {"verdict": "VETO", "reason": "Hydra permits entries Monday through Thursday only"}
    if entries_today >= int(max_daily):
        return {"verdict": "VETO", "reason": "daily entry limit reached"}
    if len(candles) < 55:
        return {"verdict": "WAIT", "reason": "insufficient M1 candles for EMA/RSI/SAR"}
    if bias not in ("BUY", "SELL"):
        return {"verdict": "VETO", "reason": "Atlas did not establish a directional EMA bias"}
    closes = [float(c["close"]) for c in candles]
    e20, e50 = _ema(closes, 20), _ema(closes, 50)
    rsi = _rsi(closes, 7)
    if bias == "BUY" and not (e20 > e50 and rsi is not None and rsi <= 40):
        return {"verdict": "VETO", "reason": "BUY requires EMA20>EMA50 and RSI7 at/below 40"}
    if bias == "SELL" and not (e20 < e50 and rsi is not None and rsi >= 60):
        return {"verdict": "VETO", "reason": "SELL requires EMA20<EMA50 and RSI7 at/above 60"}
    recent = candles[-7:-1]
    current = candles[-1]
    if len(recent) < 6:
        return {"verdict": "WAIT", "reason": "not enough completed candles for sweep reference"}
    if bias == "BUY":
        level = min(float(c["low"]) for c in recent)
        swept = float(current["low"]) < level and float(current["close"]) > level and float(current["close"]) > float(current["open"])
    else:
        level = max(float(c["high"]) for c in recent)
        swept = float(current["high"]) > level and float(current["close"]) < level and float(current["close"]) < float(current["open"])
    if not swept:
        return {"verdict": "VETO", "reason": "no wick-through-and-rejection sweep of the prior six-candle extreme"}
    if not _sar_flip(candles, bias):
        return {"verdict": "VETO", "reason": "no matching PSAR flip on the latest candle"}
    return {"verdict": "PASS", "side": bias, "swept_level": level, "reason": "EMA bias, RSI7 threshold, rejection sweep and PSAR flip agree"}
