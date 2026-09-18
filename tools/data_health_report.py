from __future__ import annotations
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
import sys

def _parse(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value

DB = Path('data/metadata/catalog.sqlite')
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('reports/data_health_nifty_banknifty.json')
if not DB.exists():
    raise SystemExit(f'Metadata DB not found: {DB}')

with sqlite3.connect(DB) as con:
    con.row_factory = sqlite3.Row
    datasets = [dict(r) for r in con.execute('SELECT * FROM datasets')]
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    if 'data_coverage' in tables:
        coverage = [dict(r) for r in con.execute('SELECT * FROM data_coverage')]
    else:
        coverage = []

ds_status = Counter(r.get('status') for r in datasets)
by_symbol = defaultdict(Counter)
by_leg = defaultdict(Counter)
for r in datasets:
    symbol = r.get('underlying_symbol') or 'UNKNOWN'
    by_symbol[symbol][r.get('status') or 'UNKNOWN'] += 1
    leg = f"{symbol}|{r.get('option_type')}|{r.get('requested_moneyness')}"
    by_leg[leg][r.get('status') or 'UNKNOWN'] += 1

failed = [r for r in datasets if r.get('status') != 'VALIDATED']
report = {
    'summary': {
        'dataset_count': len(datasets),
        'dataset_status_counts': dict(ds_status),
        'coverage_record_count': len(coverage),
    },
    'datasets_by_symbol': {k: dict(v) for k, v in sorted(by_symbol.items())},
    'datasets_by_leg': {k: dict(v) for k, v in sorted(by_leg.items())},
    'failed_datasets': [
        {
            'dataset_id': r.get('dataset_id'),
            'source': r.get('source'),
            'status': r.get('status'),
            'underlying_symbol': r.get('underlying_symbol'),
            'option_type': r.get('option_type'),
            'requested_moneyness': r.get('requested_moneyness'),
            'from_date': r.get('from_date'),
            'to_date': r.get('to_date'),
            'record_count': r.get('record_count'),
            'duplicate_records': r.get('duplicate_records'),
            'invalid_records': r.get('invalid_records'),
            'failure_reason': r.get('failure_reason'),
            'raw_path': r.get('raw_path'),
            'validation_report': _parse(r.get('validation_report')),
        }
        for r in failed
    ],
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
print(f'Wrote {OUT}')
print(json.dumps(report['summary'], indent=2))
if failed:
    print(f'Failed datasets: {len(failed)}')
    for f in failed:
        print(f"- {f.get('dataset_id')} {f.get('underlying_symbol')} {f.get('option_type')} {f.get('requested_moneyness')} {f.get('from_date')}->{f.get('to_date')} reason={f.get('failure_reason')}")
