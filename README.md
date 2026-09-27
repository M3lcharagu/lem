# LEM - volatility indices trading lab

LEM is a research scaffold for volatility-index strategy ideas and paper-trading workflow experiments. The repository now includes a small, standard-library-first paper ledger with a hard-coded-to-config schedule and risk checks. It is not a broker-connected or live trading system. Market-data connections, automated signals, and broker integrations are not configured.

## Quick start

From a Catalina shell with Python 3.9 or newer:

```sh
git clone https://github.com/M3lcharagu/lem.git
cd lem
python3 -m agents.executor_agent --paper
```

The command uses the Python standard library and displays local paper-ledger status. It does not fetch data, create signals, or submit orders. See [docs/QUICKSTART.md](docs/QUICKSTART.md) for candidate and price inputs.

## Schedule and paper safeguards

The authoritative schedule is [config/execution_schedule.json](config/execution_schedule.json), in `Africa/Nairobi`: Monday through Thursday only, with sessions at 09:30, 11:30, and 14:30. Pre-analysis begins at 09:00, 11:00, and 14:00 to prepare volatility regime, RVI state, and levels only; it makes no trade decision. Entries are permitted for the exact local minutes 09:40, 11:40, and 14:40 only. The third session is intentionally 14:30 as specified. No wider execution window is inferred.

Each accepted paper entry requires a correctly placed hard stop and is sized to at most 1% of the current paper balance. The ledger permits at most three accepted entries per Nairobi calendar day. A position is closed on a hard-stop trigger or at 45 minutes from entry when a supplied quote is processed; the 45-minute time exit has no implied profit target and can record a loss. Every candidate (accepted or rejected) and every closed outcome is appended as ASCII JSON Lines to `logs/paper_trades.jsonl`. Local state is stored in `data/paper_trader_state.json`; these runtime files are not committed.

There is no live quote feed, so a time exit is processed only when the operator supplies a current quote. Paper fills do not model slippage, spread, fees, or partial fills. This is a demonstration ledger, not financial advice or a production risk engine. Review all behavior before use.

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
