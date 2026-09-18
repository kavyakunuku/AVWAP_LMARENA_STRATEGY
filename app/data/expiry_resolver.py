from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
import pandas as pd

from app.data.dhan.instruments import InstrumentMaster

@dataclass(frozen=True, slots=True)
class ExpiryResolution:
    underlying_symbol: str
    expiry_flag: str
    expiry_code: int
    as_of_date: date
    resolved_expiry_date: date | None
    status: str
    method: str
    reason: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["as_of_date"] = self.as_of_date.isoformat()
        d["resolved_expiry_date"] = self.resolved_expiry_date.isoformat() if self.resolved_expiry_date else None
        return d


class ExpiryCalendar:
    """Explicit expiry calendar source.

    The platform must not hardcode expiry dates. This class is fed by Dhan instrument master snapshots
    or user-approved imported expiry files. It only returns dates it was actually given.
    """

    def __init__(self, rows: Iterable[dict], source: str):
        self.source = source
        self._by_key: dict[tuple[str, str], list[date]] = {}
        for row in rows:
            symbol = str(row["underlying_symbol"]).upper()
            flag = _normalize_flag(str(row["expiry_flag"]))
            expiry = _to_date(row["expiry_date"])
            if expiry is None:
                continue
            self._by_key.setdefault((symbol, flag), []).append(expiry)
        for key in list(self._by_key.keys()):
            self._by_key[key] = sorted(set(self._by_key[key]))

    @classmethod
    def from_instrument_master(cls, master: InstrumentMaster) -> "ExpiryCalendar":
        df = master.frame
        rows = []
        subset = df[(df["EXCH_ID"] == "NSE") & (df["SEGMENT"] == "D") & (df["INSTRUMENT"].isin(["OPTIDX", "OPTSTK"]))]
        for _, r in subset.iterrows():
            exp = _to_date(r.get("SM_EXPIRY_DATE"))
            if exp is None or exp.year <= 1901:
                continue
            rows.append({
                "underlying_symbol": r.get("UNDERLYING_SYMBOL"),
                "expiry_flag": r.get("EXPIRY_FLAG"),
                "expiry_date": exp,
            })
        return cls(rows, source=f"instrument_master:{master.snapshot_id}")

    @classmethod
    def from_csv(cls, path: str | Path, source: str | None = None) -> "ExpiryCalendar":
        df = pd.read_csv(path, dtype=str)
        required = {"underlying_symbol", "expiry_flag", "expiry_date"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Expiry calendar CSV missing columns: {sorted(missing)}")
        return cls(df.to_dict("records"), source=source or f"csv:{path}")

    def expiries(self, underlying_symbol: str, expiry_flag: str) -> list[date]:
        return list(self._by_key.get((underlying_symbol.upper(), _normalize_flag(expiry_flag)), []))

    def resolve(self, underlying_symbol: str, expiry_flag: str, expiry_code: int, as_of_date: date) -> ExpiryResolution:
        flag = _normalize_flag(expiry_flag)
        max_gap_days = _max_reasonable_gap_days(flag, expiry_code)
        expiries = [e for e in self.expiries(underlying_symbol, flag) if e >= as_of_date]
        if not expiries:
            return ExpiryResolution(
                underlying_symbol=underlying_symbol.upper(),
                expiry_flag=flag,
                expiry_code=expiry_code,
                as_of_date=as_of_date,
                resolved_expiry_date=None,
                status="UNRESOLVED",
                method=self.source,
                reason="No expiry date >= as_of_date found in supplied expiry calendar. Historical expired contracts may be absent from current instrument master.",
            )
        if expiry_code < 1:
            return ExpiryResolution(
                underlying_symbol=underlying_symbol.upper(),
                expiry_flag=flag,
                expiry_code=expiry_code,
                as_of_date=as_of_date,
                resolved_expiry_date=None,
                status="UNRESOLVED",
                method=self.source,
                reason="expiry_code must be >= 1 for rollingoption ordinal resolution.",
            )
        idx = expiry_code - 1
        if idx >= len(expiries):
            return ExpiryResolution(
                underlying_symbol=underlying_symbol.upper(),
                expiry_flag=flag,
                expiry_code=expiry_code,
                as_of_date=as_of_date,
                resolved_expiry_date=None,
                status="UNRESOLVED",
                method=self.source,
                reason=f"Requested expiry_code={expiry_code}, but only {len(expiries)} future expiries are available in calendar.",
            )
        candidate = expiries[idx]
        gap_days = (candidate - as_of_date).days
        if gap_days > max_gap_days:
            return ExpiryResolution(
                underlying_symbol=underlying_symbol.upper(),
                expiry_flag=flag,
                expiry_code=expiry_code,
                as_of_date=as_of_date,
                resolved_expiry_date=None,
                status="UNRESOLVED",
                method=self.source,
                reason=(
                    f"Nearest candidate expiry {candidate.isoformat()} is {gap_days} days after as_of_date, "
                    f"exceeding max reasonable gap {max_gap_days}. Calendar likely does not cover this historical period."
                ),
            )
        return ExpiryResolution(
            underlying_symbol=underlying_symbol.upper(),
            expiry_flag=flag,
            expiry_code=expiry_code,
            as_of_date=as_of_date,
            resolved_expiry_date=candidate,
            status="RESOLVED",
            method=f"{self.source}:ordinal_expiry_code",
            reason="Resolved using supplied expiry calendar and ordinal expiry_code. Assumes Dhan expiryCode is ordinal from as_of_date for the given expiry flag.",
        )


def annotate_expiry(df: pd.DataFrame, calendar: ExpiryCalendar) -> pd.DataFrame:
    """Add expiry resolution columns to candle rows.

    Does not invent dates: rows remain unresolved if the calendar lacks the required expiry.
    """
    if df.empty:
        return df.copy()
    required = {"underlying_symbol", "expiry_flag", "expiry_code"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Cannot resolve expiry; missing columns: {sorted(missing)}")
    if "timestamp_ist" in df.columns:
        dates = pd.to_datetime(df["timestamp_ist"].astype(str)).dt.date
    elif "timestamp" in df.columns:
        dates = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata").dt.date
    else:
        raise ValueError("Cannot resolve expiry; missing timestamp/timestamp_ist")

    out = df.copy()
    cache: dict[tuple[str, str, int, date], ExpiryResolution] = {}
    resolved_dates = []
    statuses = []
    methods = []
    reasons = []
    for i, row in out.iterrows():
        as_of = dates.loc[i]
        key = (str(row["underlying_symbol"]).upper(), str(row["expiry_flag"]), int(row["expiry_code"]), as_of)
        if key not in cache:
            cache[key] = calendar.resolve(key[0], key[1], key[2], key[3])
        res = cache[key]
        resolved_dates.append(res.resolved_expiry_date.isoformat() if res.resolved_expiry_date else None)
        statuses.append(res.status)
        methods.append(res.method)
        reasons.append(res.reason)
    out["expiry_date"] = resolved_dates
    out["expiry_resolution_status"] = statuses
    out["expiry_resolution_method"] = methods
    out["expiry_resolution_reason"] = reasons
    return out


def summarize_expiry_resolution(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"row_count": 0, "status_counts": {}, "expiry_dates": []}
    status_counts = df.get("expiry_resolution_status", pd.Series(dtype=str)).value_counts(dropna=False).to_dict()
    expiry_dates = sorted(str(x) for x in df.get("expiry_date", pd.Series(dtype=str)).dropna().unique().tolist())
    return {
        "row_count": len(df),
        "status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "expiry_dates": expiry_dates,
        "all_resolved": bool(len(df) > 0 and set(status_counts.keys()) == {"RESOLVED"}),
    }


def _normalize_flag(flag: str) -> str:
    val = flag.upper().strip()
    return {"W": "WEEK", "M": "MONTH"}.get(val, val)


def _to_date(value) -> date | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text or text.lower() == "nan" or text == "0001-01-01":
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except Exception:
        return None


def _max_reasonable_gap_days(flag: str, expiry_code: int) -> int:
    """Safety guard against mapping historical rows to far-future active expiries.

    This is not an expiry-date generator. It only rejects implausible matches from a supplied
    calendar. Weekly current/next expiries should be nearby; monthly expiries can be farther.
    """
    code = max(1, int(expiry_code))
    if _normalize_flag(flag) == "WEEK":
        return 7 * code + 7
    if _normalize_flag(flag) == "MONTH":
        return 35 * code + 10
    return 370
