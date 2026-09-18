from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
from app.core.ids import stable_hash

CONTRACT_GROUP_COLUMNS_WITH_EXPIRY = [
    "underlying_symbol",
    "expiry_date",
    "option_type",
    "strike_price",
]

CONTRACT_GROUP_COLUMNS_PROVISIONAL = [
    "underlying_symbol",
    "expiry_flag",
    "expiry_code",
    "option_type",
    "strike_price",
]

@dataclass(frozen=True, slots=True)
class ContractSplitSummary:
    dataset_id: str
    input_rows: int
    output_contracts: int
    strict: bool
    expiry_resolved: bool
    status: str
    reason: str | None
    contracts: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def add_contract_keys(df: pd.DataFrame, strict: bool = True) -> pd.DataFrame:
    """Add deterministic contract keys without fabricating expiry dates.

    Strict mode requires an `expiry_date` column. If expiry is missing, the function fails loudly.
    Non-strict mode creates provisional keys using expiry_flag + expiry_code and marks them provisional.
    """
    if df.empty:
        raise ValueError("Cannot add contract keys to empty dataset")
    has_expiry = "expiry_date" in df.columns and df["expiry_date"].notna().any()
    if strict and not has_expiry:
        raise ValueError("Strict contract identity requires actual expiry_date; rollingoption response has only expiry_flag/expiry_code")

    out = df.copy()
    if has_expiry:
        missing = [c for c in CONTRACT_GROUP_COLUMNS_WITH_EXPIRY if c not in out.columns]
        if missing:
            raise ValueError(f"Missing columns for strict contract key: {missing}")
        out["contract_identity_status"] = "RESOLVED"
        out["contract_key"] = out.apply(
            lambda r: "CK-" + stable_hash(
                r.get("underlying_symbol"), r.get("expiry_date"), r.get("option_type"), r.get("strike_price"), length=24
            ),
            axis=1,
        )
    else:
        missing = [c for c in CONTRACT_GROUP_COLUMNS_PROVISIONAL if c not in out.columns]
        if missing:
            raise ValueError(f"Missing columns for provisional contract key: {missing}")
        out["contract_identity_status"] = "PROVISIONAL_EXPIRY_UNRESOLVED"
        out["contract_key"] = out.apply(
            lambda r: "PCK-" + stable_hash(
                r.get("underlying_symbol"), r.get("expiry_flag"), r.get("expiry_code"), r.get("option_type"), r.get("strike_price"), length=24
            ),
            axis=1,
        )
    return out


def split_rolling_moneyness_dataset(df: pd.DataFrame, strict: bool = True) -> tuple[pd.DataFrame, ContractSplitSummary]:
    """Split Dhan rolling moneyness candles into contract-keyed rows.

    This does not create prices, volumes, or expiry dates. It only annotates rows and reports whether
    the split is strict-baseline safe.
    """
    dataset_id = _first(df, "dataset_id") or "UNKNOWN"
    try:
        keyed = add_contract_keys(df, strict=strict)
    except Exception as exc:
        return df.copy(), ContractSplitSummary(
            dataset_id=str(dataset_id),
            input_rows=len(df),
            output_contracts=0,
            strict=strict,
            expiry_resolved=False,
            status="FAILED",
            reason=str(exc),
            contracts=[],
        )

    contracts = []
    for key, grp in keyed.groupby("contract_key", dropna=False):
        contracts.append({
            "contract_key": key,
            "identity_status": str(grp["contract_identity_status"].iloc[0]),
            "underlying_symbol": _first(grp, "underlying_symbol"),
            "expiry_date": _first(grp, "expiry_date"),
            "expiry_flag": _first(grp, "expiry_flag"),
            "expiry_code": _first(grp, "expiry_code"),
            "option_type": _first(grp, "option_type"),
            "strike_price": float(_first(grp, "strike_price")) if _first(grp, "strike_price") is not None else None,
            "row_count": len(grp),
            "first_timestamp": str(grp["timestamp_ist"].min()) if "timestamp_ist" in grp.columns else str(grp["timestamp"].min()),
            "last_timestamp": str(grp["timestamp_ist"].max()) if "timestamp_ist" in grp.columns else str(grp["timestamp"].max()),
            "contract_birth_verified": False,
            "contract_birth_note": "First timestamp is observed in this dataset only; true contract birth is not verified yet.",
        })

    expiry_resolved = keyed["contract_identity_status"].eq("RESOLVED").all()
    status = "STRICT_READY" if strict and expiry_resolved else "PROVISIONAL_ONLY" if not strict else "FAILED"
    reason = None if status == "STRICT_READY" else "Expiry unresolved; not safe for strict baseline AVWAP."
    return keyed, ContractSplitSummary(
        dataset_id=str(dataset_id),
        input_rows=len(df),
        output_contracts=len(contracts),
        strict=strict,
        expiry_resolved=bool(expiry_resolved),
        status=status,
        reason=reason,
        contracts=contracts,
    )


def write_contract_partitions(df: pd.DataFrame, root: str | Path, strict: bool = True) -> ContractSplitSummary:
    keyed, summary = split_rolling_moneyness_dataset(df, strict=strict)
    if summary.status == "FAILED":
        return summary
    root = Path(root)
    for key, grp in keyed.groupby("contract_key", dropna=False):
        underlying = str(_first(grp, "underlying_symbol") or "UNKNOWN")
        option_type = str(_first(grp, "option_type") or "UNKNOWN")
        strike = str(_first(grp, "strike_price") or "UNKNOWN").replace(".", "_")
        out_dir = root / "contracts" / f"underlying={underlying}" / f"option_type={option_type}" / f"strike={strike}"
        out_dir.mkdir(parents=True, exist_ok=True)
        grp.to_parquet(out_dir / f"{key}.parquet", index=False)
    return summary


def _first(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return None
    s = df[col].dropna()
    if s.empty:
        return None
    return s.iloc[0]
