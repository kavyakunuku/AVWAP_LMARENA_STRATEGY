from __future__ import annotations
import pandas as pd
from app.core.timezone import epoch_to_ist

FIELD_MAP = {
    "timestamp": "timestamp",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "oi": "oi",
    "iv": "iv",
    "strike": "strike_price",
    "spot": "spot",
}


def normalize_expired_options(envelope: dict, dataset_id: str) -> pd.DataFrame:
    payload = envelope["payload"]
    req = payload["request"]
    resp = payload["response"]
    option_key = "ce" if req["drvOptionType"] == "CALL" else "pe"
    data = resp.get("data", {}).get(option_key)
    if not data:
        return pd.DataFrame()
    lengths = {k: len(v) for k, v in data.items() if isinstance(v, list)}
    if len(set(lengths.values())) > 1:
        raise ValueError(f"Dhan response arrays have unequal lengths: {lengths}")
    df = pd.DataFrame({FIELD_MAP.get(k, k): v for k, v in data.items() if isinstance(v, list)})
    if df.empty:
        return df
    df["timestamp_ist"] = df["timestamp"].map(epoch_to_ist)
    df["dataset_id"] = dataset_id
    df["source"] = payload.get("source", "dhan")
    df["exchange_segment"] = req["exchangeSegment"]
    df["instrument"] = req["instrument"]
    df["underlying_symbol"] = payload["request"].get("underlyingSymbol") or req.get("underlying_symbol")
    df["underlying_security_id"] = str(req["securityId"])
    df["expiry_flag"] = req["expiryFlag"]
    df["expiry_code"] = int(req["expiryCode"])
    df["option_type"] = req["drvOptionType"]
    df["requested_moneyness"] = req["strike"]
    df["timeframe"] = str(req["interval"])
    return df
