"""Stub for an RVI (Relative Vigor Index)-based volatility-index strategy.

This module records a strategy interface only. It does not calculate indicators,
produce trade recommendations, or execute trades yet.
"""


def run(prices: list[float] | None = None) -> dict:
    """Return a placeholder RVI strategy result for future research and backtesting."""
    return {
        "status": "not_implemented",
        "strategy": "volatility_indices_rvi",
        "indicator": "Relative Vigor Index",
        "observations": len(prices) if prices is not None else 0,
        "signal": None,
    }
