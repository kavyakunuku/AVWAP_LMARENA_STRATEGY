# Historical Expiry Calendar

## Option C Investigation Result

Dhan documentation reviewed for Milestone 2E shows:

- `POST /charts/rollingoption` returns expired rolling option candles with OHLC, volume, OI, IV, strike, spot, and timestamp, but the documented response does not include actual expiry date.
- `POST /optionchain/expirylist` returns active/current option expiries for an underlying, not a documented historical expiry calendar.
- Dhan instrument master exposes expiry dates for listed instruments, but this is treated as a current/snapshot source unless persisted over time.

Therefore the platform cannot safely infer historical expiries from rollingoption alone. Strict AVWAP requires an explicit expiry calendar source.

## Option A Fallback

The fallback is a user-approved CSV:

```text
underlying_symbol,expiry_flag,expiry_date
NIFTY,WEEK,2025-10-23
NIFTY,WEEK,2025-10-30
BANKNIFTY,MONTH,2025-10-28
```

The system validates the CSV but does not generate or fabricate dates.

## Validation

Run:

```powershell
python tools\validate_expiry_calendar.py config\historical_expiries.csv --normalized-out data\metadata\historical_expiries.normalized.csv --report-out reports\expiry_calendar_validation.json
```

## Building Contract-Ready Data

Given a validated rollingoption Parquet dataset and a historical expiry CSV:

```powershell
python tools\build_contract_ready_dataset.py "data\parquet\candles\source=dhan\underlying=NIFTY\timeframe=15\DS-....parquet" --expiry-calendar config\historical_expiries.csv --out-root data\parquet_contracts --report-out reports\contract_ready_report.json
```

This only writes strict contract partitions if:

- the source candle dataset validates,
- no critical anomalies are present,
- expiry resolution succeeds for every row,
- strict contract split succeeds.

## Current Instrument Master Snapshot Export

For diagnostics and future snapshots:

```powershell
python tools\export_current_expiry_calendar.py --out data\metadata\current_expiry_calendar.csv
```

This is not proof of historical expiry coverage unless the snapshot was captured at the relevant historical time.
