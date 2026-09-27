# Automation status

No launchd files or other scheduler definitions are present in this repository. No automation has been added or changed by this update.

`config/execution_schedule.json` defines the allowed paper-candidate weekdays, preparation/session times, exact entry minutes, daily trade limit, and risk cap. The executor uses that schedule to validate a candidate and to describe preparation context. It is not a daemon, does not wake up at those times, and does not automatically produce candidate signals, obtain market prices, or submit orders.

Position closing is also not scheduled. The executor has no time-based close: it can close a paper position only when an operator supplies a quote that reaches the required price-based hard stop. A price-based take-profit target and manual-close input are not implemented. The intended hold policy is to remain open until a price-based take-profit target, stop loss, or manual close; currently, only stop-loss closing is supported by the executor.

The current automation setup is therefore unchanged and limited to manually invoked paper-ledger commands. Do not infer that the configured session times run automatically. Any future scheduler or price-feed integration would be a separate change and should preserve paper-only safeguards unless explicitly reviewed.
