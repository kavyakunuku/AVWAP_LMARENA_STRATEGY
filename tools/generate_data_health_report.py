from __future__ import annotations
import argparse
import gzip
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from app.data.normalizer.expired_options import normalize_expired_options
from app.data.validator.candles import validate_candles
from app.data.quality import detect_candle_anomalies, classify_dataset_usability
from app.data.contract_identity import diagnose_contract_identity
from app.core.ids import dataset_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate consolidated data health + contract identity report from local catalog")
    parser.add_argument("--db", default="data/metadata/catalog.sqlite")
    parser.add_argument("--out", default="reports/data_health_contract_identity.json")
    parser.add_argument("--max-datasets", type=int, default=0, help="Optional limit for expensive identity diagnostics; 0 means all")
    args = parser.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"Metadata DB not found: {db}")

    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        datasets = [dict(r) for r in con.execute("SELECT * FROM datasets ORDER BY underlying_symbol, option_type, requested_moneyness, from_date")]
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        coverage = [dict(r) for r in con.execute("SELECT * FROM data_coverage")] if "data_coverage" in tables else []

    status_counts = Counter(r.get("status") for r in datasets)
    by_symbol = defaultdict(Counter)
    by_leg = defaultdict(Counter)
    for r in datasets:
        symbol = r.get("underlying_symbol") or "UNKNOWN"
        leg = f"{symbol}|{r.get('expiry_flag')}|{r.get('option_type')}|{r.get('requested_moneyness')}"
        by_symbol[symbol][r.get("status") or "UNKNOWN"] += 1
        by_leg[leg][r.get("status") or "UNKNOWN"] += 1

    failed = [r for r in datasets if r.get("status") != "VALIDATED"]
    failed_reports = []
    for r in failed:
        failed_reports.append(_classify_failed_raw(r))

    identity_reports = []
    candidates = [r for r in datasets if r.get("parquet_path")]
    if args.max_datasets > 0:
        candidates = candidates[: args.max_datasets]
    for r in candidates:
        identity_reports.append(_identity_from_parquet(r))

    rolling_count = sum(1 for r in identity_reports if r.get("contract_identity", {}).get("rolling_series"))
    unresolved_expiry_count = sum(1 for r in identity_reports if r.get("contract_identity", {}).get("expiry_identity_status") == "UNRESOLVED_NO_EXPLICIT_EXPIRY_DATE")

    report = {
        "report_type": "DATA_HEALTH_CONTRACT_IDENTITY",
        "summary": {
            "dataset_count": len(datasets),
            "coverage_record_count": len(coverage),
            "dataset_status_counts": dict(status_counts),
            "failed_dataset_count": len(failed),
            "identity_diagnostics_count": len(identity_reports),
            "rolling_moneyness_dataset_count": rolling_count,
            "unresolved_expiry_identity_count": unresolved_expiry_count,
        },
        "datasets_by_symbol": {k: dict(v) for k, v in sorted(by_symbol.items())},
        "datasets_by_leg": {k: dict(v) for k, v in sorted(by_leg.items())},
        "failed_dataset_reports": failed_reports,
        "contract_identity_reports": identity_reports,
        "baseline_usability": _baseline_usability(by_symbol, failed_reports, identity_reports),
        "policy": {
            "negative_volume": "QUARANTINE. Do not repair or use in baseline AVWAP unless an explicit source-approved repair policy is added.",
            "rolling_moneyness": "Do not compute AVWAP over a rolling moneyness series as one contract. Split by actual returned strike and resolved expiry identity.",
            "expiry_unresolved": "Strict contract-specific AVWAP remains blocked until actual expiry identity is resolved.",
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out}")
    print(json.dumps(report["summary"], indent=2, default=str))
    print("Baseline usability:")
    print(json.dumps(report["baseline_usability"], indent=2, default=str))
    return 0


def _classify_failed_raw(row: dict) -> dict:
    raw_path = row.get("raw_path")
    base = {
        "dataset_id": row.get("dataset_id"),
        "underlying_symbol": row.get("underlying_symbol"),
        "option_type": row.get("option_type"),
        "requested_moneyness": row.get("requested_moneyness"),
        "from_date": row.get("from_date"),
        "to_date": row.get("to_date"),
        "status": row.get("status"),
        "failure_reason": row.get("failure_reason"),
        "raw_path": raw_path,
    }
    if not raw_path or not Path(raw_path).exists():
        return {**base, "raw_available": False, "classification": "FAILED_RAW_MISSING"}
    with gzip.open(raw_path, "rb") as f:
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
    return {
        **base,
        "raw_available": True,
        "classification": classify_dataset_usability(validation.ok, anomalies),
        "validation": {
            "ok": validation.ok,
            "record_count": validation.record_count,
            "errors": validation.errors,
            "warnings": validation.warnings,
        },
        "anomalies": [a.to_dict() for a in anomalies],
        "contract_identity": diagnose_contract_identity(df).to_dict(),
    }


def _identity_from_parquet(row: dict) -> dict:
    path = row.get("parquet_path")
    base = {
        "dataset_id": row.get("dataset_id"),
        "underlying_symbol": row.get("underlying_symbol"),
        "option_type": row.get("option_type"),
        "requested_moneyness": row.get("requested_moneyness"),
        "from_date": row.get("from_date"),
        "to_date": row.get("to_date"),
        "parquet_path": path,
    }
    try:
        df = pd.read_parquet(path)
        return {**base, "parquet_available": True, "contract_identity": diagnose_contract_identity(df).to_dict()}
    except Exception as exc:
        return {**base, "parquet_available": False, "error": str(exc)}


def _baseline_usability(by_symbol: dict, failed_reports: list[dict], identity_reports: list[dict]) -> dict:
    result = {}
    symbols = sorted(set(by_symbol.keys()) | {r.get("underlying_symbol") for r in failed_reports if r.get("underlying_symbol")})
    for symbol in symbols:
        failures = [r for r in failed_reports if r.get("underlying_symbol") == symbol]
        identities = [r for r in identity_reports if r.get("underlying_symbol") == symbol]
        rolling = any(r.get("contract_identity", {}).get("rolling_series") for r in identities)
        expiry_unresolved = any(r.get("contract_identity", {}).get("expiry_identity_status") == "UNRESOLVED_NO_EXPLICIT_EXPIRY_DATE" for r in identities)
        if failures:
            coverage = "PARTIAL"
        else:
            coverage = "AVAILABLE"
        strict_avwap = "BLOCKED" if rolling or expiry_unresolved or failures else "READY"
        reasons = []
        if failures:
            reasons.append(f"{len(failures)} failed/quarantined dataset chunks")
        if rolling:
            reasons.append("rolling moneyness detected; must split by returned strike")
        if expiry_unresolved:
            reasons.append("expiry identity unresolved in rollingoption response")
        result[symbol] = {
            "coverage_status": coverage,
            "strict_baseline_avwap_status": strict_avwap,
            "reasons": reasons,
        }
    return result


if __name__ == "__main__":
    raise SystemExit(main())
