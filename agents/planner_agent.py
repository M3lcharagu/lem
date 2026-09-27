"""Planner agent stub for chat, planning, chart analysis, and structured research notes.

The planner can define structured plans and chart-analysis notes; no chart reader or
chat integration is configured by this scaffold.
"""


def run(request: str = "", chart_notes: str = "") -> dict:
    """Return a placeholder plan and preserve any supplied chart-analysis notes."""
    return {
        "status": "not_implemented",
        "role": "planner",
        "request": request,
        "plan": [],
        "chart_analysis_notes": chart_notes,
    }
