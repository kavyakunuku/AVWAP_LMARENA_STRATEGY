from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
from app.data.expiry_resolver import ExpiryCalendar

REQUIRED_COLUMNS = {"underlying_symbol", "expiry_flag", "expiry_date"}
VALID_FLAGS = {"WEEK", "MONTH", "W", "M"}

@dataclass(frozen=True, slots=True)
class ExpiryCalendarValidationReport:
    ok: bool
    row_count: int
    normalized_row_count: int
    errors: list[str]
    warnings: list[str]
    symbols: list[str]
    min_expiry_date: str | None
    max_expiry_date: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def load_expiry_calendar_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Expiry calendar CSV not found: {path}")
    return pd.read_csv(path, dtype=str)


def normalize_expiry_calendar_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Expiry calendar missing required columns: {sorted(missing)}")
    out = df.copy()
    out["underlying_symbol"] = out["underlying_symbol"].astype("string").str.upper().str.strip()
    out["expiry_flag"] = out["expiry_flag"].astype("string").str.upper().str.strip().replace({"W": "WEEK", "M": "MONTH"})
    out["expiry_date"] = pd.to_datetime(out["expiry_date"], errors="coerce").dt.date
    out = out.dropna(subset=["underlying_symbol", "expiry_flag", "expiry_date"])
    out = out.drop_duplicates(subset=["underlying_symbol", "expiry_flag", "expiry_date"])
    out = out.sort_values(["underlying_symbol", "expiry_flag", "expiry_date"]).reset_index(drop=True)
    return out


def validate_expiry_calendar_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, ExpiryCalendarValidationReport]:
    errors: list[str] = []
    warnings: list[str] = []
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return df.copy(), ExpiryCalendarValidationReport(
            ok=False,
            row_count=len(df),
            normalized_row_count=0,
            errors=[f"Missing required columns: {sorted(missing)}"],
            warnings=[],
            symbols=[],
            min_expiry_date=None,
            max_expiry_date=None,
        )
    invalid_flags = sorted(set(df["expiry_flag"].dropna().astype(str).str.upper().str.strip()) - VALID_FLAGS)
    if invalid_flags:
        errors.append(f"Invalid expiry_flag values: {invalid_flags}")
    parsed_dates = pd.to_datetime(df["expiry_date"], errors="coerce")
    invalid_dates = int(parsed_dates.isna().sum())
    if invalid_dates:
        errors.append(f"Invalid expiry_date rows: {invalid_dates}")
    duplicate_count = int(df.duplicated(subset=["underlying_symbol", "expiry_flag", "expiry_date"]).sum())
    if duplicate_count:
        warnings.append(f"Duplicate expiry rows will be ignored: {duplicate_count}")

    try:
        norm = normalize_expiry_calendar_frame(df)
    except Exception as exc:
        return df.copy(), ExpiryCalendarValidationReport(
            ok=False,
            row_count=len(df),
            normalized_row_count=0,
            errors=errors + [str(exc)],
            warnings=warnings,
            symbols=[],
            min_expiry_date=None,
            max_expiry_date=None,
        )

    # Gap warnings catch obviously incomplete calendars without generating dates.
    for (symbol, flag), grp in norm.groupby(["underlying_symbol", "expiry_flag"]):
        dates = list(grp["expiry_date"])
        if len(dates) < 2:
            warnings.append(f"Only {len(dates)} expiry date(s) for {symbol} {flag}; may be insufficient for historical resolution")
            continue
        gaps = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
        if flag == "WEEK" and any(g > 14 for g in gaps):
            warnings.append(f"Large weekly expiry gap for {symbol}: max_gap_days={max(gaps)}")
        if flag == "MONTH" and any(g > 45 for g in gaps):
            warnings.append(f"Large monthly expiry gap for {symbol}: max_gap_days={max(gaps)}")

    symbols = sorted(norm["underlying_symbol"].dropna().unique().tolist())
    min_date = min(norm["expiry_date"]).isoformat() if not norm.empty else None
    max_date = max(norm["expiry_date"]).isoformat() if not norm.empty else None
    return norm, ExpiryCalendarValidationReport(
        ok=not errors,
        row_count=len(df),
        normalized_row_count=len(norm),
        errors=errors,
        warnings=warnings,
        symbols=symbols,
        min_expiry_date=min_date,
        max_expiry_date=max_date,
    )


def write_normalized_calendar(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["expiry_date"] = out["expiry_date"].astype(str)
    out.to_csv(path, index=False)
    return path


def calendar_from_validated_csv(path: str | Path) -> tuple[ExpiryCalendar, ExpiryCalendarValidationReport]:
    raw = load_expiry_calendar_csv(path)
    norm, report = validate_expiry_calendar_frame(raw)
    if not report.ok:
        raise ValueError(f"Invalid expiry calendar: {report.errors}")
    return ExpiryCalendar(norm.to_dict("records"), source=f"csv:{path}"), report
