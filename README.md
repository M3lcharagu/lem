# LEM - volatility indices trading lab

LEM is a research scaffold for volatility-index strategy ideas and backtesting. Existing agent and strategy modules are placeholders; market data, signal generation, broker connections, and trading are not implemented.

## Quick start

From a shell with Python 3.10 or newer:

```sh
git clone https://github.com/M3lcharagu/lem.git
cd lem
python3 -m agents.executor_agent --paper
```

The command uses only the Python standard library. It performs a readiness check only; it does not fetch market data, calculate signals, simulate fills, connect to a broker, or submit orders. Expected output:

```text
LEM executor readiness: READY (paper-only check).
Market data: not configured; no data fetched.
Signals: not configured; no signals generated.
Trading: disabled; no orders submitted.
```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for the same copy-pasteable setup and safety notes.

## RVI methodology note

The Relative Vigor Index (RVI) compares a smoothed close-minus-open move with a smoothed high-minus-low range. RVI/signal-line crossovers are conventional momentum interpretations, not guarantees of direction, returns, or future performance. Formula details, smoothing periods, and signal-line conventions vary among platforms. This repository does not currently calculate RVI or produce signals.

References: [TradingView, Relative Vigor Index (RVI)](https://www.tradingview.com/support/solutions/43000502358-relative-vigor-index-rvi/) and [MetaTrader 5, Relative Vigor Index](https://www.metatrader5.com/en/terminal/help/indicators/oscillators/rvi).

## Scaffold

- `agents/` contains lightweight agent placeholders.
- `strategies/` contains a placeholder RVI strategy interface and research ideas.
- `config/settings.json` is a starting point for future configuration.
- `data/`, `logs/`, and `signals/` are empty tracked directories.
- `web_interface/` is a placeholder for future UI work.

No trading or data integrations are configured. Treat all strategy concepts as research, not trading advice.
