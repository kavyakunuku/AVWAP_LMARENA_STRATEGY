from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from app.data.contract_splitter import write_contract_partitions, split_rolling_moneyness_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Split a validated rollingoption Parquet dataset into contract-keyed partitions")
    parser.add_argument("parquet_path")
    parser.add_argument("--out-root", default="data/parquet_contracts")
    parser.add_argument("--allow-provisional", action="store_true", help="Allow split without actual expiry_date. Output is not strict-baseline usable.")
    parser.add_argument("--summary-out", default=None)
    args = parser.parse_args()

    df = pd.read_parquet(args.parquet_path)
    strict = not args.allow_provisional
    if args.allow_provisional:
        summary = write_contract_partitions(df, args.out_root, strict=False)
    else:
        _, summary = split_rolling_moneyness_dataset(df, strict=True)
        if summary.status == "FAILED":
            print(json.dumps(summary.to_dict(), indent=2, default=str))
            return 2
        summary = write_contract_partitions(df, args.out_root, strict=True)
    text = json.dumps(summary.to_dict(), indent=2, default=str)
    print(text)
    if args.summary_out:
        out = Path(args.summary_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    return 0 if summary.status == "STRICT_READY" else 2

if __name__ == "__main__":
    raise SystemExit(main())
