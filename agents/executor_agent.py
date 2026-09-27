"""Executor agent stub for command and strategy workflows, paper trades, and fill logs.

This module is a stdlib-friendly placeholder. It does not execute commands, connect
to a broker, or provide live trading. Paper-trade behavior and fill logging are not
implemented yet.
"""


def run(action: str = "", paper: bool = True) -> dict:
    """Return a placeholder result; refuse live mode until a safe integration exists."""
    if not paper:
        return {
            "status": "blocked",
            "role": "executor",
            "action": action,
            "mode": "live",
            "message": "Live trading integrations are not implemented.",
            "fills": [],
        }
    return {
        "status": "not_implemented",
        "role": "executor",
        "action": action,
        "mode": "paper",
        "message": "Paper-trade simulation and fill logging are not implemented yet.",
        "fills": [],
    }
