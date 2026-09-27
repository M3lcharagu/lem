"""Readiness-only executor placeholder.

This module intentionally has no market-data, signal, broker, or order
submission integrations. Paper mode reports scaffold readiness only.
"""


def run(action: str = "", paper: bool = True) -> dict:
    """Return a readiness status without submitting or simulating any trade."""
    if not paper:
        return {
            "status": "blocked",
            "role": "executor",
            "action": action,
            "mode": "live",
            "message": "Live trading is disabled; no orders were submitted.",
            "orders_submitted": 0,
        }

    return {
        "status": "ready",
        "role": "executor",
        "action": action,
        "mode": "paper_readiness_only",
        "market_data": "not_configured",
        "signals": "not_configured",
        "message": "Readiness only; no data fetched, signals generated, or orders submitted.",
        "orders_submitted": 0,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the safe readiness-only CLI; live mode is not available."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check LEM paper-mode scaffold readiness; no trading is performed."
    )
    parser.add_argument(
        "--paper",
        action="store_true",
        help="report readiness only (no simulation, data access, or order submission)",
    )
    args = parser.parse_args(argv)
    if not args.paper:
        parser.error("live trading is unavailable; pass --paper for a readiness-only check")

    run(paper=True)
    print("LEM executor readiness: READY (paper-only check).")
    print("Market data: not configured; no data fetched.")
    print("Signals: not configured; no signals generated.")
    print("Trading: disabled; no orders submitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
