from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.data.expiry_calendar_importer import (
    load_expiry_calendar_csv,
    validate_expiry_calendar_frame,
    write_normalized_calendar,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a user-approved historical expiry calendar CSV")
    parser.add_argument("csv_path")
    parser.add_argument("--normalized-out", default=None)
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    raw = load_expiry_calendar_csv(args.csv_path)
    norm, report = validate_expiry_calendar_frame(raw)
    text = json.dumps(report.to_dict(), indent=2, default=str)
    print(text)
    if args.normalized_out and report.ok:
        path = write_normalized_calendar(norm, args.normalized_out)
        print(f"Wrote normalized calendar: {path}")
    if args.report_out:
        out = Path(args.report_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"Wrote validation report: {out}")
    return 0 if report.ok else 2

if __name__ == "__main__":
    raise SystemExit(main())
