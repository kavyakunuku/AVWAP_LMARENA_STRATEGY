from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
import typer
from app.config.loader import load_config
from app.data.storage.metadata_store import MetadataStore

app = typer.Typer(help="Generate data health and coverage reports")

@app.command()
def health(
    out: str = typer.Option("reports/data_health.json", help="Output JSON report path"),
    config_path: str = "config/config.example.yaml",
):
    cfg = load_config(config_path)
    store = MetadataStore(cfg.data.metadata_db)
    datasets = store.list_datasets()
    coverage = store.list_coverage()

    ds_status = Counter(r.get("status") for r in datasets)
    cov_status = Counter(r.get("coverage_status") for r in coverage)
    failures = [r for r in datasets if r.get("status") != "VALIDATED"]
    unavailable = [r for r in coverage if r.get("coverage_status") not in ("AVAILABLE", None)]

    by_symbol: dict[str, Counter] = defaultdict(Counter)
    for r in coverage:
        by_symbol[r.get("underlying_symbol") or "UNKNOWN"][r.get("coverage_status") or "UNKNOWN"] += 1

    report = {
        "summary": {
            "dataset_count": len(datasets),
            "coverage_record_count": len(coverage),
            "dataset_status_counts": dict(ds_status),
            "coverage_status_counts": dict(cov_status),
        },
        "coverage_by_symbol": {k: dict(v) for k, v in sorted(by_symbol.items())},
        "failed_datasets": [
            {
                "dataset_id": r.get("dataset_id"),
                "source": r.get("source"),
                "underlying_symbol": r.get("underlying_symbol"),
                "option_type": r.get("option_type"),
                "requested_moneyness": r.get("requested_moneyness"),
                "from_date": r.get("from_date"),
                "to_date": r.get("to_date"),
                "record_count": r.get("record_count"),
                "duplicate_records": r.get("duplicate_records"),
                "invalid_records": r.get("invalid_records"),
                "failure_reason": r.get("failure_reason"),
                "raw_path": r.get("raw_path"),
                "validation_report": _safe_json(r.get("validation_report")),
            }
            for r in failures
        ],
        "unavailable_coverage": [
            {
                "coverage_id": r.get("coverage_id"),
                "dataset_id": r.get("dataset_id"),
                "underlying_symbol": r.get("underlying_symbol"),
                "option_type": r.get("option_type"),
                "requested_moneyness": r.get("requested_moneyness"),
                "from_date": r.get("from_date"),
                "to_date": r.get("to_date"),
                "coverage_status": r.get("coverage_status"),
                "actual_records": r.get("actual_records"),
                "reason": r.get("reason"),
                "recommended_action": r.get("recommended_action"),
            }
            for r in unavailable
        ],
    }
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    typer.echo(f"Wrote {path}")
    typer.echo(json.dumps(report["summary"], indent=2))


def _safe_json(value):
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value

if __name__ == "__main__":
    app()
