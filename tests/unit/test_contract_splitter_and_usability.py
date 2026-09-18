import pandas as pd
from app.data.contract_splitter import split_rolling_moneyness_dataset
from app.data.contract_identity import diagnose_contract_identity
from app.data.quality import detect_candle_anomalies
from app.data.usability import decide_baseline_usability


def _df(with_expiry=False):
    d = {
        "dataset_id": ["DS1", "DS1", "DS1"],
        "underlying_symbol": ["NIFTY", "NIFTY", "NIFTY"],
        "expiry_flag": ["WEEK", "WEEK", "WEEK"],
        "expiry_code": [1, 1, 1],
        "option_type": ["CALL", "CALL", "CALL"],
        "strike_price": [25150.0, 25200.0, 25150.0],
        "timestamp": [1, 2, 3],
        "timestamp_ist": pd.to_datetime(["2025-09-23 09:15", "2025-09-23 09:30", "2025-09-23 09:45"]),
        "open": [1, 2, 3], "high": [2, 3, 4], "low": [0.5, 1.5, 2.5], "close": [1.5, 2.5, 3.5],
        "volume": [100, 200, 300], "oi": [10, 11, 12],
    }
    if with_expiry:
        d["expiry_date"] = ["2025-09-25", "2025-09-25", "2025-09-25"]
    return pd.DataFrame(d)


def test_strict_split_fails_without_expiry_date():
    keyed, summary = split_rolling_moneyness_dataset(_df(), strict=True)
    assert summary.status == "FAILED"
    assert "expiry_date" in summary.reason
    assert "contract_key" not in keyed.columns


def test_provisional_split_groups_by_returned_strike():
    keyed, summary = split_rolling_moneyness_dataset(_df(), strict=False)
    assert summary.status == "PROVISIONAL_ONLY"
    assert summary.output_contracts == 2
    assert keyed["contract_identity_status"].eq("PROVISIONAL_EXPIRY_UNRESOLVED").all()


def test_strict_split_ready_with_expiry_date():
    keyed, summary = split_rolling_moneyness_dataset(_df(with_expiry=True), strict=True)
    assert summary.status == "STRICT_READY"
    assert summary.output_contracts == 2
    assert keyed["contract_identity_status"].eq("RESOLVED").all()


def test_usability_blocks_rolling_unresolved_expiry():
    df = _df()
    decision = decide_baseline_usability(True, detect_candle_anomalies(df), diagnose_contract_identity(df))
    assert decision.status == "BLOCKED_BASELINE"
    assert any("Rolling moneyness" in r for r in decision.reasons)
    assert any("expiry" in r for r in decision.reasons)
