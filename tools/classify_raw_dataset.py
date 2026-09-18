from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import pandas as pd
from app.core.ids import dataset_id
from app.data.normalizer.expired_options import normalize_expired_options
from app.data.validator.candles import validate_candles
from app.data.quality import detect_candle_anomalies, classify_dataset_usability
from app.data.contract_identity import diagnose_contract_identity


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a raw Dhan dataset for baseline usability without modifying source data")
    parser.add_argument("raw_path")
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    args = parser.parse_args()
    path = Path(args.raw_path)
    with gzip.open(path, "rb") as f:
        envelope = json.loads(f.read().decode("utf-8"))
    req = envelope["payload"]["request"]
    ds_id = dataset_id(
        envelope["payload"].get("source", "dhan"), "expired_options",
        req.get("underlying_symbol"), req.get("securityId"), req.get("expiryFlag"), req.get("expiryCode"),
        req.get("strike"), req.get("drvOptionType"), req.get("interval"), req.get("fromDate"), req.get("toDate"),
    )
    df = normalize_expired_options(envelope, ds_id)
    validation = validate_candles(df)
    anomalies = detect_candle_anomalies(df)
    identity = diagnose_contract_identity(df)
    report = {
        "raw_path": str(path),
        "dataset_id": ds_id,
        "validation": {
            "ok": validation.ok,
            "record_count": validation.record_count,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "duplicate_records": validation.duplicate_records,
            "invalid_records": validation.invalid_records,
        },
        "anomalies": [a.to_dict() for a in anomalies],
        "usability": classify_dataset_usability(validation.ok, anomalies),
        "contract_identity": identity.to_dict(),
    }
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"Wrote {out}")
    return 0 if report["usability"] == "USABLE_BASELINE" else 2

if __name__ == "__main__":
    raise SystemExit(main())
