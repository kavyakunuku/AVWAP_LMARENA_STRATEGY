import pandas as pd
from app.data.quality import detect_candle_anomalies, classify_dataset_usability
from app.data.contract_identity import diagnose_contract_identity


def test_negative_volume_is_critical_and_possible_uint32_overflow():
    df = pd.DataFrame({
        "timestamp": [1], "timestamp_ist": ["2025-09-23T15:00:00+05:30"],
        "open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5],
        "volume": [-4052532196], "oi": [10],
    })
    anomalies = detect_candle_anomalies(df)
    assert anomalies[0].anomaly_type == "NEGATIVE_VOLUME"
    assert anomalies[0].severity == "CRITICAL"
    assert anomalies[0].details["uint32_overflow_candidate_value"] == 242435100
    assert classify_dataset_usability(False, anomalies) == "QUARANTINED_VALIDATION_FAILED"


def test_contract_identity_detects_rolling_moneyness_series():
    df = pd.DataFrame({
        "dataset_id": ["DS1", "DS1"],
        "underlying_symbol": ["NIFTY", "NIFTY"],
        "option_type": ["CALL", "CALL"],
        "expiry_flag": ["WEEK", "WEEK"],
        "expiry_code": [1, 1],
        "requested_moneyness": ["ATM", "ATM"],
        "strike_price": [25150.0, 25200.0],
    })
    diag = diagnose_contract_identity(df)
    assert diag.rolling_series is True
    assert diag.unique_returned_strikes == 2
    assert diag.avwap_contract_identity_status == "MUST_SPLIT_BY_RETURNED_STRIKE_AND_EXPIRY"
