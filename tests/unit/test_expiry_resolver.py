from datetime import date
import pandas as pd
from app.data.expiry_resolver import ExpiryCalendar, annotate_expiry, summarize_expiry_resolution
from app.data.contract_splitter import split_rolling_moneyness_dataset


def test_calendar_resolves_ordinal_expiry_code():
    cal = ExpiryCalendar([
        {"underlying_symbol": "NIFTY", "expiry_flag": "WEEK", "expiry_date": "2026-09-24"},
        {"underlying_symbol": "NIFTY", "expiry_flag": "WEEK", "expiry_date": "2026-10-01"},
    ], source="test")
    res = cal.resolve("NIFTY", "WEEK", 1, date(2026, 9, 18))
    assert res.status == "RESOLVED"
    assert res.resolved_expiry_date == date(2026, 9, 24)
    res2 = cal.resolve("NIFTY", "WEEK", 2, date(2026, 9, 18))
    assert res2.resolved_expiry_date == date(2026, 10, 1)


def test_calendar_refuses_missing_historical_expiry():
    cal = ExpiryCalendar([
        {"underlying_symbol": "NIFTY", "expiry_flag": "WEEK", "expiry_date": "2026-09-24"},
    ], source="test")
    res = cal.resolve("NIFTY", "WEEK", 1, date(2025, 9, 18))
    assert res.status == "UNRESOLVED"
    assert "does not cover this historical period" in res.reason


def test_annotate_expiry_and_strict_split_when_calendar_has_dates():
    df = pd.DataFrame({
        "dataset_id": ["DS1", "DS1"],
        "underlying_symbol": ["NIFTY", "NIFTY"],
        "expiry_flag": ["WEEK", "WEEK"],
        "expiry_code": [1, 1],
        "option_type": ["CALL", "CALL"],
        "strike_price": [25000.0, 25050.0],
        "timestamp": [1790055900, 1790056800],
        "open": [1, 2], "high": [2, 3], "low": [0.5, 1.5], "close": [1.5, 2.5], "volume": [10, 11],
    })
    cal = ExpiryCalendar([{"underlying_symbol": "NIFTY", "expiry_flag": "WEEK", "expiry_date": "2026-09-24"}], source="test")
    annotated = annotate_expiry(df, cal)
    summary = summarize_expiry_resolution(annotated)
    assert summary["all_resolved"] is True
    keyed, split = split_rolling_moneyness_dataset(annotated, strict=True)
    assert split.status == "STRICT_READY"
    assert split.output_contracts == 2


def test_annotate_expiry_marks_unresolved_when_calendar_missing():
    df = pd.DataFrame({
        "underlying_symbol": ["BANKNIFTY"],
        "expiry_flag": ["MONTH"],
        "expiry_code": [1],
        "timestamp": [1790055900],
    })
    annotated = annotate_expiry(df, ExpiryCalendar([], source="empty"))
    assert annotated["expiry_resolution_status"].iloc[0] == "UNRESOLVED"
    assert summarize_expiry_resolution(annotated)["all_resolved"] is False
