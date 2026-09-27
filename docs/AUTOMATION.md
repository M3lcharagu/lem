# Automation status

No launchd files or other scheduler definitions are present in this repository. The schedule remains configuration for validation and preparation context; it is not a background scheduler and does not automatically wake, fetch prices, generate signals, or submit orders. Existing automation is unchanged by the local pre-analysis CLI addition.

## Manual pre-analysis

Run `python3 agents/planner_agent.py path/to/session.csv` from the repository root. Python's standard library is sufficient. The CSV must have the header `timestamp,open,high,low,close`; timestamps are non-empty labels and OHLC values must be finite numbers with consistent high/low ranges. The program reads at most the first 30 data rows in file order. Omitting the path, supplying a missing file, or supplying an empty CSV prints exactly `waiting for first 30 minutes of session data` and no result. The GitHub file editing mechanism does not set executable file permissions, so the documented invocation is through `python3`; no executable shell wrapper is included.

For supplied rows, six labeled blocks are printed for 240, 180, 60, 45, 30, and 15 minute horizons. They share the same observed first-30-row snapshot; horizon labels do not imply forecast accuracy or future data. Bias compares last close with first open. Key levels are observed session high/low and open/close. An FVG is the non-overlap between candle 1's high and candle 3's low (bullish), or candle 1's low and candle 3's high (bearish); a later supplied close beyond the far edge marks that gap as an inverted FVG (IFVG). Liquidity references include highs/lows repeated within 0.01% of the latest close and the highest/lowest values in the last five rows. Invalidation is a deterministic close beyond the observed range against the stated bias. These are simple descriptive heuristics, not certainty, live data, or trading advice.

## Configured paper schedule and exits

`config/execution_schedule.json` is authoritative. It specifies `Africa/Nairobi`, Monday through Thursday, pre-analysis starting at 09:00, 11:00, and 14:00, sessions starting at 09:30, 11:30, and 14:30, and exact entry minutes 09:40, 11:40, and 14:40. The analysis settings use 30 minutes and horizons `[240, 180, 60, 45, 30, 15]`. Existing exact-time, hard-stop, 1% per-trade risk, and three-trades-per-day settings are preserved.

There is no timed exit or hold limit. The current executor implements hard-stop closure only; take-profit and manual-close handling are not implemented. Do not infer automatic scheduling or unimplemented exit behavior from the configuration.
