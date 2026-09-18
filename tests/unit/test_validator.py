import pandas as pd
from app.data.validator.candles import validate_candles


def test_validator_rejects_invalid_ohlc():
    df = pd.DataFrame({"timestamp":[1], "open":[10], "high":[9], "low":[8], "close":[10], "volume":[1]})
    report = validate_candles(df)
    assert not report.ok
    assert "Invalid OHLC" in report.errors[0]


def test_validator_accepts_valid_ohlc():
    df = pd.DataFrame({"timestamp":[1,2], "open":[10,11], "high":[12,12], "low":[9,10], "close":[11,10.5], "volume":[1,2]})
    report = validate_candles(df)
    assert report.ok
