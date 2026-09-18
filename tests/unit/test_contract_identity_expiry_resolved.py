import pandas as pd
from app.data.contract_identity import diagnose_contract_identity


def test_contract_identity_recognizes_resolved_expiry_date():
    df = pd.DataFrame({
        "dataset_id": ["DS1", "DS1"],
        "underlying_symbol": ["NIFTY", "NIFTY"],
        "option_type": ["CALL", "CALL"],
        "expiry_flag": ["WEEK", "WEEK"],
        "expiry_code": [1, 1],
        "requested_moneyness": ["ATM-1", "ATM-1"],
        "expiry_date": ["2025-10-23", "2025-10-23"],
        "strike_price": [25800.0, 25850.0],
    })
    diag = diagnose_contract_identity(df)
    assert diag.expiry_identity_status == "RESOLVED"
    assert diag.avwap_contract_identity_status == "STRICT_IDENTITY_AVAILABLE_AFTER_SPLIT"
