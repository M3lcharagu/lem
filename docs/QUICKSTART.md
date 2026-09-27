# Quick start

Run these commands from a Catalina shell with Python 3.9 or newer:

```sh
git clone https://github.com/M3lcharagu/lem.git
cd lem
python3 -m agents.executor_agent --paper
```

No third-party Python packages are required. The command prints local paper-ledger status. It does not connect to a broker or fetch live market data.

## Submit a paper candidate

Create a JSON object with a symbol, `side` (`long` or `short`), `entry_price`, and a valid `hard_stop`. Supply an initial `paper_balance` on the first accepted setup. Example candidate file:

```sh
cat > /tmp/lem-candidate.json <<'JSON'
{"symbol":"DEMO","side":"long","entry_price":100.0,"hard_stop":99.0,"paper_balance":1000.0}
JSON
python3 -m agents.executor_agent --paper --candidate-file /tmp/lem-candidate.json
```

A candidate is accepted only Monday through Thursday at exactly 09:40, 11:40, or 14:40 `Africa/Nairobi` local time. The schedule's sessions start at 09:30, 11:30, and 14:30; pre-analysis begins at 09:00, 11:00, and 14:00. These are exact allowed local minutes, not multi-minute windows. Preparation may cover volatility regime, RVI state, and levels, but does not decide whether to trade. Candidates are logged whether accepted or rejected.

The trader sizes quantity from the entry-to-hard-stop distance so planned risk is no more than 1% of paper balance. It accepts at most three entries per local calendar day. A hard stop is mandatory for every candidate.

## Update a hard stop

Supply an operator-provided quote to evaluate the hard stop of open paper positions for a symbol. For example:

```sh
python3 -m agents.executor_agent --paper --symbol DEMO --price 99.5
```

The quote is not a live feed. An open position closes in the ledger only when the supplied price reaches or passes its hard stop, with the paper exit recorded at the stop price. The executor has no holding-time limit. The intended policy is to hold until a price-based take-profit target, a stop loss, or a manual close. Only hard-stop closing is currently implemented: take-profit targets and manual-close input are not implemented, so the executor will not execute or simulate those exits. An open position without a supplied stop-triggering quote remains open.

For deterministic replay or testing, `--now` accepts a timezone-aware ISO 8601 timestamp, for example `--now 2026-09-28T09:40:00+03:00`. Do not use replay timestamps as a real clock.

## Limitations

This is a standard-library-first demonstration, not an automated trading system. There is no broker connection, live data feed, automated signal generation, exchange calendar, target-based exit, manual-close command, slippage/spread/fee model, or production-grade state recovery. The schedule gates candidate evaluation; it does not launch a background scheduler. State persists at `data/paper_trader_state.json`, and event logs are written to `logs/paper_trades.jsonl`. These files are local to this checkout. Live trading is unavailable; `--paper` is required.
