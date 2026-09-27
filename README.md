# LEM - volatility indices trading lab

LEM is a research scaffold for volatility-index strategy ideas and paper-trading workflow experiments. It is not a broker-connected or live-trading system. Market-data connections, automated signals, and broker integrations are not configured.

## Quick start

From a Catalina shell with Python 3.9 or newer:

```sh
git clone https://github.com/M3lcharagu/lem.git
cd lem
python3 -m agents.executor_agent --paper
```

The command displays local paper-ledger status. It does not fetch data, create signals, or submit orders. See [docs/QUICKSTART.md](docs/QUICKSTART.md) for paper-ledger use and local pre-analysis.

## Pre-analysis

The local planner reads the first 30 OHLC CSV records and prints separate blocks for 240, 180, 60, 45, 30, and 15 minute horizons. Run it with `python3 agents/planner_agent.py path/to/session.csv`; the required columns are `timestamp,open,high,low,close`. With no file or no records, it prints exactly `waiting for first 30 minutes of session data` and produces no analysis. It uses deterministic observed-data heuristics only: a three-candle non-overlap gap is an FVG, a later close invalidating that gap marks an IFVG, and equal/recent highs and lows are liquidity references. All horizon blocks use the same supplied snapshot; they are not predictions and no live or future data is fetched. Details are in [docs/QUICKSTART.md](docs/QUICKSTART.md).

## Schedule and paper safeguards

The authoritative schedule is [config/execution_schedule.json](config/execution_schedule.json), in `Africa/Nairobi`: Monday through Thursday, with sessions at 09:30, 11:30, and 14:30; preparation starts at 09:00, 11:00, and 14:00; entries are allowed only at the exact local minutes 09:40, 11:40, and 14:40. No wider execution window is inferred. At most three entries may be accepted per local calendar day. Each candidate requires a hard stop and is sized so planned risk is at most 1% of paper balance.

There is no holding-time limit or forced time close. The executor currently closes only on its implemented hard stop; take-profit and manual-close handling are not implemented. Paper fills do not model slippage, spread, fees, or partial fills. This is a demonstration ledger, not financial advice or a production risk engine.

## Automation

No launchd files or other scheduler definitions are present. The configured schedule is used for validation and preparation context; it does not run in the background or automatically produce signals. The pre-analysis CLI is manually invoked and reads only the CSV supplied by an operator. See [docs/AUTOMATION.md](docs/AUTOMATION.md).
