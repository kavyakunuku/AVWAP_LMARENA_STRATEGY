from __future__ import annotations
from dataclasses import dataclass, asdict
import pandas as pd
from app.core.ids import stable_hash

@dataclass(frozen=True, slots=True)
class ContractIdentityDiagnostics:
    dataset_id: str
    underlying_symbol: str | None
    option_type: str | None
    expiry_flag: str | None
    expiry_code: int | None
    requested_moneyness: str | None
    row_count: int
    unique_returned_strikes: int
    returned_strike_min: float | None
    returned_strike_max: float | None
    rolling_series: bool
    expiry_identity_status: str
    avwap_contract_identity_status: str
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def diagnose_contract_identity(df: pd.DataFrame) -> ContractIdentityDiagnostics:
    if df.empty:
        return ContractIdentityDiagnostics(
            dataset_id="UNKNOWN", underlying_symbol=None, option_type=None, expiry_flag=None,
            expiry_code=None, requested_moneyness=None, row_count=0, unique_returned_strikes=0,
            returned_strike_min=None, returned_strike_max=None, rolling_series=False,
            expiry_identity_status="UNRESOLVED", avwap_contract_identity_status="UNUSABLE_EMPTY",
            notes=["Dataset has no rows."],
        )
    strikes = pd.to_numeric(df.get("strike_price", pd.Series(dtype=float)), errors="coerce").dropna()
    unique_count = int(strikes.nunique()) if not strikes.empty else 0
    rolling_series = unique_count > 1
    expiry_dates = df.get("expiry_date", pd.Series(dtype=object)).dropna().unique().tolist() if "expiry_date" in df.columns else []
    expiry_resolved = len(expiry_dates) > 0 and df.get("expiry_date", pd.Series(dtype=object)).notna().all()
    notes = []
    if rolling_series:
        notes.append("Returned strike changes inside this dataset. Treat this as rolling moneyness data, not one fixed option contract.")
        notes.append("For AVWAP, split state by actual returned strike and resolved expiry identity.")
    else:
        notes.append("Returned strike is constant inside this dataset chunk.")
    if expiry_resolved:
        notes.append("expiry_date is present for all rows. Strict contract identity can be formed after splitting by expiry_date + returned strike.")
    else:
        notes.append("Dhan rollingoption response, as currently normalized, does not provide explicit expiry_date; expiry identity remains unresolved until mapped from source behavior/metadata.")
    return ContractIdentityDiagnostics(
        dataset_id=str(df.get("dataset_id", pd.Series(["UNKNOWN"])).iloc[0]),
        underlying_symbol=_first(df, "underlying_symbol"),
        option_type=_first(df, "option_type"),
        expiry_flag=_first(df, "expiry_flag"),
        expiry_code=int(_first(df, "expiry_code")) if _first(df, "expiry_code") is not None else None,
        requested_moneyness=_first(df, "requested_moneyness"),
        row_count=len(df),
        unique_returned_strikes=unique_count,
        returned_strike_min=float(strikes.min()) if not strikes.empty else None,
        returned_strike_max=float(strikes.max()) if not strikes.empty else None,
        rolling_series=rolling_series,
        expiry_identity_status="RESOLVED" if expiry_resolved else "UNRESOLVED_NO_EXPLICIT_EXPIRY_DATE",
        avwap_contract_identity_status=(
            "STRICT_IDENTITY_AVAILABLE_AFTER_SPLIT" if rolling_series and expiry_resolved else
            "READY_SINGLE_CONTRACT" if (not rolling_series and expiry_resolved) else
            "MUST_SPLIT_BY_RETURNED_STRIKE_AND_EXPIRY" if rolling_series else
            "NEEDS_EXPIRY_RESOLUTION"
        ),
        notes=notes,
    )


def contract_key_from_row(row: pd.Series) -> str:
    """Deterministic provisional key; not final until expiry_date is resolved."""
    return "CK-" + stable_hash(
        row.get("underlying_symbol"), row.get("expiry_flag"), row.get("expiry_code"),
        row.get("option_type"), row.get("strike_price"), length=24,
    )


def _first(df: pd.DataFrame, col: str):
    if col not in df.columns or df[col].empty:
        return None
    val = df[col].dropna()
    if val.empty:
        return None
    return val.iloc[0]
