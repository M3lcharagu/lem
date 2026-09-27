# Quick start

Run from a Catalina shell with Python 3.9 or newer:

```sh
git clone https://github.com/M3lcharagu/lem.git
cd lem
python3 -m agents.executor_agent --paper
```

No third-party Python packages are required. This displays local paper-ledger status; it does not connect to a broker or fetch live market data. `--paper` is required for the executor.

## Read the first 30 minutes

Save one-minute OHLC records in a CSV and run the local, read-only analysis:

```sh
python3 agents/planner_agent.py path/to/session.csv
```

Required header and example row:

```csv
timestamp,open,high,low,close
2026-09-28T09:00:00+03:00,100,102,99,101
```

The program uses the first 30 data rows in file order. With no path, a missing file, or no data rows, its only output is exactly:

```text
waiting for first 30 minutes of session data
```

For supplied data it prints separate 240, 180, 60, 45, 30, and 15 minute horizon blocks. Every block describes the same observed snapshot, not a future-price prediction. Direction bias compares the last close to the first open. Key levels are observed session high/low and the first open/last close. An FVG is a three-candle non-overlap gap; a later supplied close beyond its far edge marks it as an IFVG. Liquidity references are equal highs/lows within 0.01% of the latest close and the recent high/low in the last five rows. Invalidation is a simple close beyond the observed range against the stated bias. No live data, certainty, or trade decision is implied.

## Schedule and paper entries

The configuration uses `Africa/Nairobi`, Monday through Thursday. Preparation begins at 09:00, 11:00, and 14:00; sessions start at 09:30, 11:30, and 14:30; entries are allowed only at exact local minutes 09:40, 11:40, and 14:40. A paper candidate requires a hard stop, planned risk is capped at 1% of paper balance, and at most three entries are accepted per local day. Pre-analysis does not decide whether to trade.

There is no holding-time limit or forced time close. The executor currently implements hard-stop closure only; take-profit and manual-close handling are not implemented. An operator-provided quote is not a live feed. See [docs/AUTOMATION.md](AUTOMATION.md) for the automation status and limitations.
