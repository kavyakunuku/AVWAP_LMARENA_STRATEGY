import pandas as pd
from app.data.expiry_calendar_importer import validate_expiry_calendar_frame, calendar_from_validated_csv


def test_validate_expiry_calendar_normalizes_flags_and_duplicates(tmp_path):
    df = pd.DataFrame({
        "underlying_symbol": ["nifty", "NIFTY", "BANKNIFTY"],
        "expiry_flag": ["W", "WEEK", "M"],
        "expiry_date": ["2025-10-23", "2025-10-23", "2025-10-28"],
    })
    norm, report = validate_expiry_calendar_frame(df)
    assert report.ok
    assert report.row_count == 3
    assert report.normalized_row_count == 2
    assert "NIFTY" in report.symbols
    assert set(norm["expiry_flag"]) == {"WEEK", "MONTH"}


def test_calendar_from_validated_csv_resolves(tmp_path):
    path = tmp_path / "exp.csv"
    path.write_text("underlying_symbol,expiry_flag,expiry_date\nNIFTY,WEEK,2025-10-23\n", encoding="utf-8")
    cal, report = calendar_from_validated_csv(path)
    assert report.ok
    res = cal.resolve("NIFTY", "WEEK", 1, pd.Timestamp("2025-10-20").date())
    assert res.status == "RESOLVED"
    assert res.resolved_expiry_date.isoformat() == "2025-10-23"


def test_validate_expiry_calendar_rejects_bad_date():
    df = pd.DataFrame({"underlying_symbol": ["NIFTY"], "expiry_flag": ["WEEK"], "expiry_date": ["bad"]})
    _, report = validate_expiry_calendar_frame(df)
    assert not report.ok
    assert report.errors
