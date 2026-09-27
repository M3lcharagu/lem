# Quick start

Run these commands from a Catalina shell with Python 3.9 or newer:

```sh
git clone https://github.com/M3lcharagu/lem.git
cd lem
python3 -m agents.executor_agent --paper
```

No third-party Python packages are required. The command prints the local paper-ledger status. It does not connect to a broker or fetch live market data.

## Submit a paper candidate

Create a JSON object with a symbol, `side` (`long` or `short`), `entry_price`, and a valid `hard_stop`. Supply an initial `paper_balance` on the first accepted setup. Example candidate file:

```sh
cat > /tmp/lem-candidate.json <<'JSON'
{"symbol":"DEMO","side":"long","entry_price":100.0,"hard_stop":99.0,"paper_balance":1000.0}
JSON
python3 -m agents.executor_agent --paper --candidate-file /tmp/lem-candidate.json
```

A candidate is accepted only on Monday through Thursday at exactly 09:40, 11:40, or 14:40 Africa/Nairobi local time. These are single allowed local minutes, not multi-minute windows. The schedule has session starts 09:30, 11:30, and 14:30; pre-analysis begins 30 minutes before each. The third session is 14:30. Preparation may cover volatility regime, RVI state, and levels, but does not decide whether to trade. Candidates are logged whether accepted or rejected.

The trader sizes quantity from the entry-to-hard-stop distance so planned risk is no more than 1% of paper balance. It allows at most three accepted trades per local calendar day. State persists at `data/paper_trader_state.json`. On the first run that accepts a setup, the supplied balance initializes the paper ledger; closed P/L updates it.

## Update an open position

Supply a quote to evaluate the hard stop or the 45-minute time exit. For example:

```sh
python3 -m agents.executor_agent --paper --symbol DEMO --price 99.5
```

The quote is an operator-supplied price, not a live feed. An open position is closed on a hard-stop trigger, or when an update is processed at or after 45 minutes from entry. The time exit uses the supplied quote; no take-profit price target is inferred. A stop fill is modeled at the stop price without slippage. Closed records include P/L and win, loss, or breakeven outcome in `logs/paper_trades.jsonl`.

For a deterministic replay or test, `--now` accepts an ISO 8601 timestamp with a timezone offset, for example `--now 2026-09-28T09:40:00+03:00`. Do not use replay timestamps as a real clock.

## Limitations

This is a standard-library-first demonstration, not an automated trading system. There is no broker connection, live data feed, automated signal generation, exchange calendar, slippage/spread/fee model, or production-grade state recovery. Expired positions cannot close until a supplied quote is processed. The ledger is local to this checkout. Live trading is unavailable; `--paper` is required.
