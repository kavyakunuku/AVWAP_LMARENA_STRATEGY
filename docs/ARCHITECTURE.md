# Architecture

## Current Milestone

This repository implements Milestone 0, Milestone 1 foundation, Milestone 2 coverage planning, data-quality anomaly classification, and Milestone 2D expiry/contract identity resolver foundation.

## Implemented Flow

```text
DhanClient or MockDhanClient
  -> InstrumentMaster resolver
  -> Coverage planner
  -> ExpiredOptionsDownloadJob
  -> RawStore
  -> normalize_expired_options
  -> validate_candles
  -> Data anomaly classifier
  -> Expiry resolver
  -> Contract splitter
  -> ParquetStore
  -> DuckDBCatalog
  -> MetadataStore
```

## Design Rules Preserved

- Market data is never fabricated.
- Mock data is persisted as `source=mock_dhan`, never `source=dhan`.
- Raw API responses are persisted before normalization.
- Parquet is used for historical candles.
- DuckDB is used for analytical queries over Parquet.
- SQLite is used only for metadata/state in this milestone.
- Dhan credentials are read from environment variables only.
- LIVE trading is not implemented in this milestone.

## Instrument Master Resolution

`InstrumentMaster` parses Dhan's detailed scrip master and resolves index/equity spot IDs, Dhan rollingoption request IDs, instrument type, derivative underlying IDs, and available option expiry flags.

Observed from public instrument master:

- NIFTY spot index security id: `13`.
- BANKNIFTY spot index security id: `25`.
- Derivative option rows may contain separate derivative underlying IDs such as `26000` for NIFTY and `26009` for BANKNIFTY.

The platform stores both, but uses the documented spot security ID for `rollingoption` requests.

## Rolling Moneyness Finding

Real Dhan data inspection showed a single `ATM` request can return many absolute strikes. Therefore:

```text
Dhan rollingoption ATM response != one fixed option contract
```

The platform must split rows by actual returned strike and resolved expiry before AVWAP.

## Expiry Resolver

The expiry resolver consumes only explicit expiry calendar sources:

- Dhan instrument master snapshots.
- User-approved imported expiry CSV.

It does not hardcode expiry dates. It rejects implausible matches using a max-lookahead guard so a current/future master cannot accidentally resolve old historical rows to far-future expiries.

Strict AVWAP remains blocked until expiry is resolved.
