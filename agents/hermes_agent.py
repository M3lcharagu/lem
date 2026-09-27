"""Hermes is the single public runner; all role modules are internal."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import atlas_agent, hephaestus_agent, hydra_agent, lumen_agent, mnemosyne_agent, sentinel_agent
from data import deriv_feed


def _settings():
    with (ROOT / "config" / "settings.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def _block(call, reason, roles):
    print("HERMES DECISION")
    print("HERMES CALL: " + call)
    print("REASON: " + str(reason).replace("\n", " "))
    print("ROLE VERDICTS:")
    for name, result in roles:
        print("- " + name + ": " + str(result.get("verdict", result.get("status", "INFO"))) + " - " + str(result.get("reason", result.get("status", ""))).replace("\n", " "))


def run(paper):
    settings = _settings()
    zone = ZoneInfo(settings.get("timezone", "Africa/Nairobi"))
    now = datetime.now(zone)
    symbol = str(settings.get("symbol", "R_25")).upper()
    roles = []

    def finish(call, reason):
        mnemosyne_agent.log_skip(symbol, call, reason, path=str(ROOT / "logs" / "skips.csv"), now=now)
        _block(call, reason, roles)
        return 0

    if not paper:
        return finish("SKIP", "paper mode is mandatory; no real execution path exists")
    if symbol not in [str(x).upper() for x in settings.get("allowed_symbols", ["R_25", "R_75"])] or symbol not in ("R_25", "R_75"):
        return finish("SKIP", "symbol must be one of the configured synthetic indices R_25 or R_75")
    if now.weekday() > 3:
        return finish("SKIP", "schedule permits Monday through Thursday only")
    entry_times = settings.get("entry_times", ["09:40", "11:40", "14:40"])
    if now.strftime("%H:%M") not in entry_times:
        return finish("SKIP", "not an exact configured Africa/Nairobi entry minute")

    browser_enabled = str(__import__("os").environ.get("USE_BROWSER_FEED", str(settings.get("USE_BROWSER_FEED", False)))).lower() in ("1", "true", "yes", "on")
    browser_result = deriv_feed.browser_probe(browser_enabled)
    roles.append(("Browser feed", {"verdict": "INFO", "reason": browser_result.get("status", "disabled") + (": " + browser_result.get("reason", "") if browser_result.get("reason") else "; chart state is not read")}))
    try:
        m1 = deriv_feed.fetch_candles(symbol, granularity=60, count=120)
        m15 = deriv_feed.fetch_candles(symbol, granularity=900, count=120)
    except Exception as exc:
        return finish("WAIT", "public candle feed unavailable: " + str(exc))

    atlas = atlas_agent.evaluate(m15, m1)
    roles.append(("Atlas", atlas))
    lumen = lumen_agent.evaluate(symbol, settings, now.astimezone(timezone.utc))
    roles.append(("Lumen", lumen))
    entries_today = mnemosyne_agent.entries_on_day(str(ROOT / "logs" / "trades.csv"), now.date().isoformat())
    hydra = hydra_agent.evaluate(m1, atlas.get("bias"), now, entry_times, settings.get("max_trades_per_day", 3), entries_today)
    roles.append(("Hydra", hydra))

    ticket = None
    if hydra.get("verdict") == "PASS" and atlas.get("verdict") == "PASS" and lumen.get("verdict") == "PASS":
        ticket = hephaestus_agent.build(m1, hydra, float(settings.get("paper_balance", 0.0)), float(settings.get("risk_pct", 0.01)))
    if ticket:
        roles.append(("Hephaestus", {"verdict": "PASS", "reason": "paper ticket built with hard stop and 2:1 target"}))
        sentinel = sentinel_agent.evaluate(settings, ticket, str(ROOT / "logs" / "trades.csv"))
    else:
        roles.append(("Hephaestus", {"verdict": "SKIP", "reason": "no eligible Hydra setup; no ticket built"}))
        sentinel = {"verdict": "SKIP", "reason": "not evaluated without a valid ticket"}
    roles.append(("Sentinel", sentinel))

    failed = [r for r in (atlas, lumen, hydra, sentinel) if r.get("verdict") in ("VETO", "SKIP")]
    waiting = any(r.get("verdict") == "WAIT" for r in (atlas, hydra))
    if not ticket or failed or sentinel.get("verdict") != "PASS":
        call = "WAIT" if waiting else "SKIP"
        reason = next((r.get("reason") for r in (atlas, lumen, hydra, sentinel) if r.get("verdict") in ("VETO", "SKIP", "WAIT")), "no valid paper ticket")
        return finish(call, reason)

    mnemosyne_agent.log_trade(symbol, ticket, float(settings.get("risk_pct", 0.01)), hydra["reason"], path=str(ROOT / "logs" / "trades.csv"), now=now)
    roles.append(("Mnemosyne", {"verdict": "PASS", "reason": "paper ticket logged; outcome remains PAPER_PLANNED"}))
    _block("ENTER", "all role gates passed; paper ticket recorded only, no broker order submitted", roles)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run the LEM paper-only Hermes orchestrator")
    parser.add_argument("--paper", action="store_true", required=True, help="required; this runner has no live trading mode")
    args = parser.parse_args()
    try:
        return run(args.paper)
    except Exception as exc:
        now = datetime.now(ZoneInfo("Africa/Nairobi"))
        reason = "Hermes stopped safely: " + str(exc)
        try:
            mnemosyne_agent.log_skip("UNKNOWN", "WAIT", reason, path=str(ROOT / "logs" / "skips.csv"), now=now)
        except Exception:
            pass
        _block("WAIT", reason, [])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
