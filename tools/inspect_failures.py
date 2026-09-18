from __future__ import annotations
import json
import sqlite3
from pathlib import Path

DB = Path('data/metadata/catalog.sqlite')
if not DB.exists():
    raise SystemExit(f'Metadata DB not found: {DB}')

with sqlite3.connect(DB) as con:
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("""
        SELECT dataset_id, source, status, underlying_symbol, option_type, requested_moneyness,
               from_date, to_date, record_count, duplicate_records, invalid_records,
               failure_reason, raw_path, parquet_path, validation_report
        FROM datasets
        WHERE status <> 'VALIDATED'
        ORDER BY underlying_symbol, option_type, requested_moneyness, from_date
    """)]

if not rows:
    print('No failed/non-validated datasets found.')
    raise SystemExit(0)

print(f'Failed/non-validated datasets: {len(rows)}')
for r in rows:
    print('\n---')
    for k in ['dataset_id','source','status','underlying_symbol','option_type','requested_moneyness','from_date','to_date','record_count','duplicate_records','invalid_records','failure_reason','raw_path','parquet_path']:
        print(f'{k}: {r.get(k)}')
    vr = r.get('validation_report')
    if vr:
        try:
            print('validation_report:')
            print(json.dumps(json.loads(vr), indent=2))
        except Exception:
            print(f'validation_report: {vr}')
