"""Research agent stub for web research, market news, volatility-index behavior, and strategy intelligence.

This stdlib-friendly module defines a role boundary only; it does not fetch web pages or market data.
"""


def run(topic: str = "") -> dict:
    """Return a placeholder research result for the requested topic."""
    return {
        "status": "not_implemented",
        "role": "research",
        "topic": topic,
        "notes": "Web research and market-data sources are not configured.",
    }
