# Quick start

Run these commands from a shell with Python 3.10 or newer:

```sh
git clone https://github.com/M3lcharagu/lem.git
cd lem
python3 -m agents.executor_agent --paper
```

No third-party Python packages are required for this command. Expected output:

```text
LEM executor readiness: READY (paper-only check).
Market data: not configured; no data fetched.
Signals: not configured; no signals generated.
Trading: disabled; no orders submitted.
```

`--paper` runs a readiness check only. It does not fetch data, calculate signals, simulate trades or fills, connect to a broker, or submit orders. Live mode is unavailable. The repository is a research scaffold, not a functioning trading system.
