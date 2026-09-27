# LEM - volatility indices paper-trading lab

LEM is a research scaffold for synthetic volatility-index strategy experiments. It is paper-only: it does not connect a broker account, submit orders, or run unattended.

## Quickstart

From a Python 3.9+ shell at the repository root:

```sh
python3 agents/hermes_agent.py --paper
```

The public runner is `agents/hermes_agent.py`; it orchestrates six internal role modules and prints one `HERMES CALL: ENTER/SKIP/WAIT` decision block. It requires the exact configured Africa/Nairobi entry minute, Mon-Thu and the controls in `config/settings.json`. The default symbol is `R_25` (choose `R_75` there as needed), M1 entries use M15/M1 regime context, maximum three per day and `risk_pct` defaults to 0.01. A paper balance of 1000.0 is a configurable simulation default, not an account balance.

For public Deriv candle history, install optional `websocket-client` and set `DERIV_APP_ID` to an app ID you control. Without it or when the feed is unavailable Hermes safely reports `WAIT`. No authorization or order API is used. Browser diagnostics are opt-in (`USE_BROWSER_FEED` defaults false); live chart selectors are unverified and Catalina ChromeDriver 115.x compatibility is not verified.

Paper decisions append to `logs/trades.csv` and skips to `logs/skips.csv`. An `ENTER` records a paper plan only, not a fill. See [docs/AGENT_OPS.md](docs/AGENT_OPS.md) for the seven roles, safety limits, data protocol and compatibility notes.

## Existing research tools and schedule

The existing paper executor and planner are preserved. `config/execution_schedule.json` remains the schedule reference: Monday-Thursday, sessions 09:30, 11:30 and 14:30 Africa/Nairobi with exact entry minutes 09:40, 11:40 and 14:40. The planner's CSV pre-analysis remains separate; no scheduler, broker integration, future-data source or live order interface is enabled.

This software is experimental and is not financial advice. Paper sizing is illustrative and does not model contract multipliers, payouts, spread, fees, slippage or partial fills.
