import pandas as pd
from app.data.expiry_calendar_importer import calendar_from_validated_csv
from app.data.expiry_resolver import annotate_expiry, summarize_expiry_resolution
from app.data.contract_splitter import split_rolling_moneyness_dataset


def test_expiry_csv_enables_strict_split(tmp_path):
    df = pd.DataFrame({
        "dataset_id": ["DSX", "DSX"],
        "underlying_symbol": ["NIFTY", "NIFTY"],
        "expiry_flag": ["WEEK", "WEEK"],
        "expiry_code": [1, 1],
        "option_type": ["CALL", "CALL"],
        "strike_price": [25000.0, 25050.0],
        "timestamp": [1760931900, 1760932800],
        "timestamp_ist": pd.to_datetime(["2025-10-20 09:15:00+05:30", "2025-10-20 09:30:00+05:30"]),
        "open": [1.0, 2.0], "high": [2.0, 3.0], "low": [0.5, 1.5], "close": [1.5, 2.5],
        "volume": [100, 200], "oi": [10, 20],
    })
    exp = tmp_path / "exp.csv"
    exp.write_text("underlying_symbol,expiry_flag,expiry_date\nNIFTY,WEEK,2025-10-23\n", encoding="utf-8")
    cal, _ = calendar_from_validated_csv(exp)
    annotated = annotate_expiry(df, cal)
    assert summarize_expiry_resolution(annotated)["all_resolved"] is True
    _, summary = split_rolling_moneyness_dataset(annotated, strict=True)
    assert summary.status == "STRICT_READY"
    assert summary.output_contracts == 2
