# LEM - volatility indices trading lab

LEM is a research scaffold for volatility-index strategy ideas and paper-trading workflow experiments. The repository includes a small, standard-library-only paper ledger with a hard-coded-to-config schedule and risk checks. It is not a broker-connected or live-trading system. Market-data connections, automated signals, and broker integrations are not configured.

## Quick start

From a Catalina shell with Python 3.9 or newer:

```sh
git clone https://github.com/M3lcharagu/lem.git
cd lem
python3 -m agents.executor_agent --paper
```

The command displays local paper-ledger status. It does not fetch data, create signals, or submit orders. See [docs/QUICKSTART.md](docs/QUICKSTART.md) for candidate and quote inputs.

## Schedule and paper safeguards

The authoritative schedule is [config/execution_schedule.json](config/execution_schedule.json), in `Africa/Nairobi`: Monday through Thursday only, with sessions at 09:30, 11:30, and 14:30. Pre-analysis starts at 09:00, 11:00, and 14:00. Entries are permitted only at the exact local minutes 09:40, 11:40, and 14:40. No wider execution window is inferred. At most three entries may be accepted per local calendar day.

Each accepted paper entry requires a correctly placed hard stop and is sized so planned risk is at most 1% of the paper balance. The configured hard stop is the only automatic exit implemented by the executor. There is no holding-time limit: the intended position policy is to hold until a price-based take-profit target, a stop loss, or a manual close. However, the current executor does not implement take-profit targets or manual-close input; those exits are not performed or simulated by this code. Open positions can remain in the local ledger until an operator-supplied quote reaches the hard stop.

Every candidate and closed outcome is appended as ASCII JSON Lines to `logs/paper_trades.jsonl`. Local state is stored in `data/paper_trader_state.json`; runtime files are not committed. The quote is supplied by an operator; it is not a live feed. Paper fills do not model slippage, spread, fees, or partial fills. This is a demonstration ledger, not financial advice or a production risk engine.

## Automation

No launchd files or other scheduler definitions are present in this repository. This change leaves automation unchanged: the schedule is used for setup validation and preparation context, but the executor is not a background scheduler and does not automatically produce signals or close positions. See [docs/AUTOMATION.md](docs/AUTOMATION.md).

## RVI methodology note

The Relative Vigor Index (RVI) compares a smoothed close-minus-open move with a smoothed high-minus-low range. RVI/signal-line crossovers are conventional momentum interpretations, not guarantees of direction, returns, or future performance. Formula details, smoothing periods, and signal-line conventions vary among platforms. This repository does not currently calculate RVI or produce signals.

References: [TradingView, Relative Vigor Index (RVI)](https://www.tradingview.com/support/solutions/43000502358-relative-vigor-index-rvi/) and [MetaTrader 5, Relative Vigor Index](https://www.metatrader5.com/en/terminal/help/indicators/oscillators/rvi).

## Scaffold

- `agents/` contains lightweight research, planning, and scheduled paper-execution modules.
- `strategies/` contains a placeholder RVI strategy interface and research ideas.
- `config/settings.json` and `config/execution_schedule.json` contain starting configuration.
- `data/`, `logs/`, and `signals/` are tracked runtime directories; paper state and logs are local runtime files.
- `web_interface/` is a placeholder for future UI work.

Treat strategy concepts as research, not trading advice. No broker or actual market-data integration is configured.
