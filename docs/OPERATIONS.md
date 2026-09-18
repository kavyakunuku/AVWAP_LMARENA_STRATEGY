# Operations

## Environment Variables

For real Dhan API use, set credentials in your shell environment. Do not commit them and do not paste them into config files:

```powershell
$env:DHAN_CLIENT_ID = "..."
$env:DHAN_ACCESS_TOKEN = "..."
```

If a token has been pasted into chat, logs, screenshots, or tickets, regenerate/rotate it before live use.

## Credential Doctor

Depending on your local Typer version, run one of:

```powershell
python -m app.data.doctor
```

or:

```powershell
python -m app.data.doctor credentials
```

The command does not print the token.

## Coverage Audit

Real Dhan execution:

```powershell
python -m app.data.coverage audit `
  --symbols NIFTY,BANKNIFTY `
  --months 12 `
  --to 2026-09-18 `
  --execute
```

## Inspect Failed Datasets

```powershell
python tools/inspect_failures.py
```

## Inspect Raw Dataset

```powershell
python tools/inspect_raw_dataset.py data\raw\<file>.json.gz
```

## Classify Raw Dataset

```powershell
python tools/classify_raw_dataset.py data\raw\<file>.json.gz --out reports\classification.json
```

## Validate Historical Expiry Calendar CSV

```powershell
python tools\validate_expiry_calendar.py config\historical_expiries.csv --normalized-out data\metadata\historical_expiries.normalized.csv --report-out reports\expiry_calendar_validation.json
```

Required columns:

```text
underlying_symbol,expiry_flag,expiry_date
```

## Export Current Instrument-Master Expiry Snapshot

```powershell
python tools\export_current_expiry_calendar.py --out data\metadata\current_expiry_calendar.csv
```

This is useful for future operation but is not proof of historical expired-contract coverage unless the snapshot was captured for that historical period.

## Resolve Expiry for Validated Parquet Dataset

With a user-approved historical expiry calendar CSV:

```powershell
python tools/resolve_expiry_for_parquet.py data\parquet\...\dataset.parquet --expiry-calendar config\historical_expiries.csv --out reports\annotated.parquet
```

## Build Strict Contract-Ready Dataset

```powershell
python tools\build_contract_ready_dataset.py "data\parquet\candles\source=dhan\underlying=NIFTY\timeframe=15\DS-....parquet" --expiry-calendar config\historical_expiries.csv --out-root data\parquet_contracts --report-out reports\contract_ready_report.json
```

This writes strict contract partitions only when source validation, anomaly checks, expiry resolution, and strict contract splitting all pass.

## Split Contract Partitions

Strict mode requires actual `expiry_date`:

```powershell
python tools/split_contracts_from_parquet.py data\parquet\...\dataset.parquet
```

Diagnostic-only provisional split:

```powershell
python tools/split_contracts_from_parquet.py data\parquet\...\dataset.parquet --allow-provisional
```

Provisional splits are not baseline AVWAP safe.

## Safety

This milestone has no live order code and cannot place trades.
