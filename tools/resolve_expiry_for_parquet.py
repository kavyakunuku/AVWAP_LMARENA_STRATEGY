from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from app.data.dhan.client import DhanHTTPClient
from app.data.dhan.instruments import InstrumentMaster
from app.data.expiry_resolver import ExpiryCalendar, annotate_expiry, summarize_expiry_resolution
from app.data.contract_splitter import split_rolling_moneyness_dataset, write_contract_partitions


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve expiry identity for a Parquet dataset using explicit expiry calendar data")
    parser.add_argument("parquet_path")
    parser.add_argument("--instrument-master", default=None, help="Path to Dhan detailed instrument master CSV. If omitted, downloads current public master.")
    parser.add_argument("--expiry-calendar", default=None, help="User-approved CSV with underlying_symbol,expiry_flag,expiry_date")
    parser.add_argument("--out", default=None, help="Optional annotated Parquet output path")
    parser.add_argument("--split-out-root", default=None, help="Optional root to write contract-keyed partitions if all expiry rows resolve")
    args = parser.parse_args()

    df = pd.read_parquet(args.parquet_path)
    if args.expiry_calendar:
        calendar = ExpiryCalendar.from_csv(args.expiry_calendar)
    else:
        if args.instrument_master:
            master = InstrumentMaster.from_path(args.instrument_master)
        else:
            master = InstrumentMaster.download(DhanHTTPClient())
        calendar = ExpiryCalendar.from_instrument_master(master)

    annotated = annotate_expiry(df, calendar)
    summary = summarize_expiry_resolution(annotated)
    _, split_summary = split_rolling_moneyness_dataset(annotated, strict=True)
    report = {
        "input": args.parquet_path,
        "calendar_source": calendar.source,
        "expiry_resolution": summary,
        "strict_contract_split": split_summary.to_dict(),
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        annotated.to_parquet(out, index=False)
        report["annotated_output"] = str(out)
    if args.split_out_root and summary.get("all_resolved"):
        report["partition_write"] = write_contract_partitions(annotated, args.split_out_root, strict=True).to_dict()
    elif args.split_out_root:
        report["partition_write"] = "SKIPPED_EXPIRY_UNRESOLVED"
    print(json.dumps(report, indent=2, default=str))
    return 0 if summary.get("all_resolved") else 2

if __name__ == "__main__":
    raise SystemExit(main())
