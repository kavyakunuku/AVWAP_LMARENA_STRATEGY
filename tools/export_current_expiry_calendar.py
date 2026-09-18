from __future__ import annotations
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.data.dhan.client import DhanHTTPClient
from app.data.dhan.instruments import InstrumentMaster
from app.data.expiry_resolver import ExpiryCalendar


def main() -> int:
    parser = argparse.ArgumentParser(description="Export current Dhan instrument-master expiries to CSV for diagnostics/snapshots")
    parser.add_argument("--instrument-master", default=None)
    parser.add_argument("--out", default="data/metadata/current_expiry_calendar.csv")
    args = parser.parse_args()
    if args.instrument_master:
        master = InstrumentMaster.from_path(args.instrument_master)
    else:
        master = InstrumentMaster.download(DhanHTTPClient())
    cal = ExpiryCalendar.from_instrument_master(master)
    rows = []
    for (symbol, flag), expiries in sorted(cal._by_key.items()):  # controlled diagnostic export
        for expiry in expiries:
            rows.append({"underlying_symbol": symbol, "expiry_flag": flag, "expiry_date": expiry.isoformat(), "source": cal.source})
    import pandas as pd
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {out} rows={len(rows)}")
    print("Note: this is a current instrument-master snapshot, not proof of historical expired coverage.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
