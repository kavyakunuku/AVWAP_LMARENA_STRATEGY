from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd

@dataclass(slots=True)
class ValidationReport:
    ok: bool
    record_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_records: int = 0
    invalid_records: int = 0


def validate_candles(df: pd.DataFrame) -> ValidationReport:
    errors=[]; warnings=[]
    if df.empty:
        return ValidationReport(False, 0, ["Dataset contains no records"])
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(df.columns))
    if missing:
        return ValidationReport(False, len(df), [f"Missing columns: {missing}"])
    invalid_mask = ~((df["high"] >= df["open"]) & (df["high"] >= df["close"]) & (df["high"] >= df["low"]) & (df["low"] <= df["open"]) & (df["low"] <= df["close"]) & (df["low"] <= df["high"]))
    invalid_records = int(invalid_mask.sum())
    if invalid_records:
        errors.append(f"Invalid OHLC rows: {invalid_records}")
    if (df["volume"] < 0).any():
        errors.append("Negative volume found")
    if "oi" in df.columns and (df["oi"].dropna() < 0).any():
        errors.append("Negative OI found")
    if not df["timestamp"].is_monotonic_increasing:
        errors.append("Timestamps are not sorted ascending")
    dup_cols = [c for c in ["timestamp", "underlying_security_id", "expiry_flag", "expiry_code", "option_type", "strike_price"] if c in df.columns]
    duplicates = int(df.duplicated(subset=dup_cols).sum()) if dup_cols else int(df.duplicated().sum())
    if duplicates:
        errors.append(f"Duplicate candle rows: {duplicates}")
    if "timestamp_ist" in df.columns:
        hours = pd.to_datetime(df["timestamp_ist"].astype(str)).dt.strftime("%H:%M")
        outside = int(((hours < "09:15") | (hours > "15:30")).sum())
        if outside:
            warnings.append(f"Rows outside regular NSE session: {outside}")
    return ValidationReport(not errors, len(df), errors, warnings, duplicates, invalid_records)
