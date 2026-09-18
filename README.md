# AVWAP F&O Options Trading Platform V2

Professional research and trading platform foundation for the AVWAP option-selling strategy.

Current implementation status: **Milestone 0/1 + Milestone 2B/2C/2D/2E foundations**.

Implemented now:

- Clean Python project skeleton.
- Structured YAML configuration.
- Universe config for NIFTY, BANKNIFTY, and the approved F&O stock list.
- Dhan V2 client interface with retry/rate-limit handling.
- Deterministic mock Dhan client for tests without credentials.
- Public Dhan instrument-master parser and underlying resolver.
- Baseline coverage planner for ATM + 4 ITM calls and ATM + 4 ITM puts.
- Explicit stock ATM±4 documented-unavailability handling.
- Historical download planning with resumable chunk state.
- Raw API response storage with checksums.
- Expired-options response normalization.
- Candle validation.
- Negative-volume anomaly classification.
- Contract identity diagnostics for rolling moneyness data.
- Expiry resolver foundation using explicit calendars only.
- Historical expiry calendar CSV validation/import fallback.
- Current Dhan instrument-master expiry snapshot export for future diagnostics.
- Contract-ready dataset builder gated by validation/anomaly/expiry checks.
- Contract splitter with strict and provisional modes.
- Baseline usability gate.
- Parquet storage.
- DuckDB query catalog.
- Dataset metadata and data coverage metadata in SQLite.
- CLI/tooling under `python -m app.data.*` and `tools/`.

Not implemented yet:

- Full historical expiry calendar acquisition from an official historical endpoint, because Dhan docs inspected so far do not show one.
- AVWAP engine.
- Strategy engine.
- Backtester.
- Paper/live trading.
- Dashboard.

LIVE trading is intentionally not available in this milestone.

## Key Real-Data Finding

Real Dhan data for NIFTY ATM weekly options showed reproducible negative volume in two chunks:

- NIFTY CALL ATM 2025-09-18 -> 2025-10-18
- NIFTY PUT ATM 2025-09-18 -> 2025-10-18

These are quarantined for baseline use.

Real Dhan rollingoption data also showed that `ATM` responses contain multiple returned absolute strikes. Therefore rollingoption responses must be split by returned strike and resolved expiry before AVWAP.

## Expiry Calendar

See `docs/EXPIRY_CALENDAR.md`.

Example validation:

```powershell
python tools\validate_expiry_calendar.py config\historical_expiries.example.csv --normalized-out data\metadata\historical_expiries.normalized.csv
```

## Quick Test

```bash
pytest -q
```

## Real Dhan Use

Set credentials in environment variables only:

```powershell
$env:DHAN_CLIENT_ID="..."
$env:DHAN_ACCESS_TOKEN="..."
```

Then run the credential doctor and coverage commands documented in `docs/OPERATIONS.md`.
