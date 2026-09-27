# LEM Agent Operations

LEM is a paper-only research scaffold. Its public/runnable entry point is `agents/hermes_agent.py`; the six role modules below are internal implementation modules, not separate user-facing commands.

## Seven-role flow

1. **Hermes** (`agents/hermes_agent.py`): loads settings, observes exact time rules, obtains public candle history and orchestrates all roles. It prints one final decision block containing `HERMES CALL: ENTER`, `SKIP` or `WAIT` and a one-line reason. `ENTER` means a paper ticket was recorded, never a broker order.
2. **Atlas** (`agents/atlas_agent.py`): classifies trend/chop using EMA20/EMA50 structure and EMA20 slope on M15 and M1. Insufficient history waits; mixed structure is choppy.
3. **Lumen** (`agents/lumen_agent.py`): synthetic `R_` symbols are a no-op because there is no reliable per-index news feed. Real instruments can be locked by operator-configured UTC events in `event_lock_utc`; this is not a live calendar feed.
4. **Hydra** (`agents/hydra_agent.py`): allows Monday-Thursday entries only at the exact configured Africa/Nairobi entry minutes; applies M1 EMA bias, RSI7 thresholds (BUY <= 40, SELL >= 60), wick-through/rejection sweep, and a matching PSAR flip. The daily maximum defaults to three.
5. **Sentinel** (`agents/sentinel_agent.py`): requires a hard stop, enforces `risk_pct` > 0 and <= 1%, and has `ENABLE_2LOSS_BREAKER` default true. The breaker reads manually recorded `WIN`/`LOSS` outcomes; a planned paper ticket is not a result.
6. **Hephaestus** (`agents/hephaestus_agent.py`): creates a paper ticket at the latest candle close, puts the stop beyond the swept level, targets 2R and estimates size from balance*risk divided by stop distance. Price-unit sizing is illustrative; Deriv contract multipliers, payouts, spread and slippage are not modeled.
7. **Mnemosyne** (`agents/mnemosyne_agent.py`): appends timestamped CSV records to `logs/trades.csv` and `logs/skips.csv`. Planned entries are labelled `PAPER_PLANNED`; manually update an outcome to `WIN` or `LOSS` only after a paper result is known.

## Data and compatibility

`data/deriv_feed.py` uses Deriv's documented public WebSocket `ticks_history` request with `style=candles` and 60-second granularity. It sends no `authorize` request and submits no orders. Set `DERIV_APP_ID` to an app ID you control; no ID is fabricated or bundled. Install optional `websocket-client` to fetch candles. Network, endpoint policy and symbol availability can vary; feed failures return `WAIT`.

`USE_BROWSER_FEED` defaults to false. If enabled and Selenium plus ChromeDriver/Chrome are installed, LEM may navigate to `https://charts.deriv.com` as a diagnostic. No chart selectors or live-chart integration are verified, so it does not scrape or infer chart state. Matching Chrome and a Catalina-targeted ChromeDriver 115.x are unverified; WebSocket candles remain the feed path, with manual chart review as fallback. No Selenium or WebSocket package is required by the core modules.

## Configuration and safety

Edit `config/settings.json` for `symbol` (`R_25` or `R_75`), timeframe, sessions, entries, weekdays, maximum, risk, breaker, browser flag and paper balance. `config/execution_schedule.json` remains authoritative for the existing prep schedule; this build does not add a scheduler or alter the planner/executor paper workflow. Core uses Python standard library only. No real-account API, credentials, order placement, or unattended execution is implemented.

A future Hermes Claude API adapter would require a separate documented, opt-in design; there is no Claude client or API key integration here.
