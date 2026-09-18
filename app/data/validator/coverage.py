from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

@dataclass(slots=True)
class CoverageResult:
    requested_moneyness: str
    available: bool
    actual_records: int
    returned_strikes: list[float]
    reason: str | None = None


def check_requested_coverage(df: pd.DataFrame, requested_moneyness: str) -> CoverageResult:
    if df.empty:
        return CoverageResult(requested_moneyness, False, 0, [], "No rows returned by source")
    strikes = sorted(float(x) for x in df.get("strike_price", pd.Series(dtype=float)).dropna().unique().tolist())
    return CoverageResult(requested_moneyness, True, len(df), strikes, None)
