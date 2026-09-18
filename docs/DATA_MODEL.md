# Data Model

## Historical Candle Storage

Historical candles are stored as Parquet files under:

```text
data/parquet/candles/source=<source>/underlying=<SYMBOL>/timeframe=<INTERVAL>/<dataset_id>.parquet
```

Current logical columns include:

- `dataset_id`
- `source`
- `exchange_segment`
- `instrument`
- `underlying_symbol`
- `underlying_security_id`
- `expiry_flag`
- `expiry_code`
- `option_type`
- `requested_moneyness`
- `timeframe`
- `timestamp`
- `timestamp_ist`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `oi`
- `iv`
- `strike_price`
- `spot`

## Dataset Metadata

Dataset metadata is stored in SQLite at:

```text
data/metadata/catalog.sqlite
```

The `datasets` table records dataset id, source, request parameters, date range, record counts, validation result, raw path, Parquet path, and validation report.

## Data Coverage Table

Coverage records are stored in `data_coverage` with requested vs actual availability, returned strikes, reason, and recommended action. This is the foundation for the Data Health dashboard.

## Expiry Resolution Columns

Milestone 2D adds optional row-level expiry resolution columns:

- `expiry_date`
- `expiry_resolution_status`
- `expiry_resolution_method`
- `expiry_resolution_reason`

The resolver does not invent expiry dates. It can only resolve from an explicit expiry calendar source such as Dhan instrument master snapshots or a user-approved CSV. If the calendar does not cover a historical period, rows remain `UNRESOLVED`.

A max-lookahead guard prevents accidentally mapping old historical rows to far-future active expiries from a current instrument master.

## Contract Keys

Strict baseline contract keys require:

```text
underlying_symbol + actual expiry_date + option_type + returned strike_price
```

If `expiry_date` is unavailable, only provisional keys may be produced:

```text
underlying_symbol + expiry_flag + expiry_code + option_type + returned strike_price
```

Provisional keys are marked:

```text
PROVISIONAL_EXPIRY_UNRESOLVED
```

and are not strict-baseline AVWAP safe.

## Raw Store

Raw Dhan/mock responses are stored as gzipped JSON under:

```text
data/raw/<request_hash>.json.gz
```

The raw envelope contains storage timestamp, original request payload, and original response payload.
