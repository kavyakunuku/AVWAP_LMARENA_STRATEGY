from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from app.data.expiry_calendar_importer import calendar_from_validated_csv
from app.data.expiry_resolver import annotate_expiry, summarize_expiry_resolution
from app.data.contract_splitter import split_rolling_moneyness_dataset, write_contract_partitions
from app.data.validator.candles import validate_candles
from app.data.quality import detect_candle_anomalies
from app.data.contract_identity import diagnose_contract_identity
from app.data.usability import decide_baseline_usability


def main() -> int:
    parser = argparse.ArgumentParser(description="Build strict contract-ready candle partitions from validated rollingoption Parquet and historical expiry calendar")
    parser.add_argument("parquet_path")
    parser.add_argument("--expiry-calendar", required=True, help="CSV with underlying_symbol,expiry_flag,expiry_date")
    parser.add_argument("--out-root", default="data/parquet_contracts")
    parser.add_argument("--annotated-out", default=None)
    parser.add_argument("--report-out", default="reports/contract_ready_report.json")
    args = parser.parse_args()

    df = pd.read_parquet(args.parquet_path)
    validation = validate_candles(df)
    anomalies = detect_candle_anomalies(df)
    pre_identity = diagnose_contract_identity(df)
    pre_decision = decide_baseline_usability(validation.ok, anomalies, pre_identity)

    calendar, calendar_report = calendar_from_validated_csv(args.expiry_calendar)
    annotated = annotate_expiry(df, calendar)
    expiry_summary = summarize_expiry_resolution(annotated)
    identity_after = diagnose_contract_identity(annotated)
    _, split_summary = split_rolling_moneyness_dataset(annotated, strict=True)

    wrote_partitions = False
    if validation.ok and not anomalies and expiry_summary.get("all_resolved") and split_summary.status == "STRICT_READY":
        split_summary = write_contract_partitions(annotated, args.out_root, strict=True)
        wrote_partitions = True

    if args.annotated_out:
        out = Path(args.annotated_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        annotated.to_parquet(out, index=False)

    report = {
        "input_parquet": args.parquet_path,
        "expiry_calendar": args.expiry_calendar,
        "calendar_validation": calendar_report.to_dict(),
        "source_validation": {
            "ok": validation.ok,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "record_count": validation.record_count,
        },
        "source_anomalies": [a.to_dict() for a in anomalies],
        "pre_expiry_usability": pre_decision.to_dict(),
        "expiry_resolution": expiry_summary,
        "post_expiry_contract_identity": identity_after.to_dict(),
        "strict_split": split_summary.to_dict(),
        "wrote_contract_partitions": wrote_partitions,
        "out_root": args.out_root if wrote_partitions else None,
    }
    out = Path(args.report_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"Wrote report: {out}")
    return 0 if wrote_partitions else 2

if __name__ == "__main__":
    raise SystemExit(main())
