from __future__ import annotations
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from app.data.dhan.client import DhanClient

CANONICAL_COLUMNS = [
    "EXCH_ID", "SEGMENT", "SECURITY_ID", "ISIN", "INSTRUMENT", "UNDERLYING_SECURITY_ID",
    "UNDERLYING_SYMBOL", "SYMBOL_NAME", "DISPLAY_NAME", "INSTRUMENT_TYPE", "SERIES",
    "LOT_SIZE", "SM_EXPIRY_DATE", "STRIKE_PRICE", "OPTION_TYPE", "TICK_SIZE", "EXPIRY_FLAG",
]

@dataclass(frozen=True, slots=True)
class UnderlyingResolution:
    symbol: str
    kind: str  # INDEX or EQUITY
    spot_security_id: str
    spot_exchange_segment: str
    rollingoption_security_id: str
    rollingoption_instrument: str
    derivative_underlying_security_id: str | None
    available_option_expiry_flags: tuple[str, ...]

class InstrumentMaster:
    def __init__(self, frame: pd.DataFrame, snapshot_id: str | None = None):
        self.frame = _normalize_frame(frame)
        self.snapshot_id = snapshot_id or datetime.now(timezone.utc).strftime("IM-%Y%m%d-%H%M%S")

    @classmethod
    def from_csv_text(cls, text: str) -> "InstrumentMaster":
        return cls(pd.read_csv(StringIO(text), dtype=str, low_memory=False))

    @classmethod
    def from_path(cls, path: str | Path) -> "InstrumentMaster":
        return cls(pd.read_csv(path, dtype=str, low_memory=False))

    @classmethod
    def download(cls, client: DhanClient, cache_path: str | Path | None = None) -> "InstrumentMaster":
        text = client.instrument_master()
        if cache_path:
            path = Path(cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return cls.from_csv_text(text)

    def resolve_underlying(self, symbol: str) -> UnderlyingResolution:
        symbol = symbol.upper()
        df = self.frame

        index_rows = df[(df["EXCH_ID"] == "NSE") & (df["SEGMENT"] == "I") & (df["INSTRUMENT"] == "INDEX") & (df["SYMBOL_NAME"] == symbol)]
        if not index_rows.empty:
            spot_id = str(index_rows.iloc[0]["SECURITY_ID"])
            opt_rows = df[(df["EXCH_ID"] == "NSE") & (df["SEGMENT"] == "D") & (df["INSTRUMENT"] == "OPTIDX") & (df["UNDERLYING_SYMBOL"] == symbol)]
            flags = tuple(sorted(x for x in opt_rows["EXPIRY_FLAG"].dropna().unique().tolist() if x and x != "nan"))
            derivative_underlying_id = None
            if not opt_rows.empty:
                derivative_underlying_id = str(opt_rows.iloc[0]["UNDERLYING_SECURITY_ID"])
            # Dhan rollingoption docs use spot index IDs for NIFTY examples; keep derivative id separately for diagnostics.
            return UnderlyingResolution(
                symbol=symbol,
                kind="INDEX",
                spot_security_id=spot_id,
                spot_exchange_segment="IDX_I",
                rollingoption_security_id=spot_id,
                rollingoption_instrument="OPTIDX",
                derivative_underlying_security_id=derivative_underlying_id,
                available_option_expiry_flags=flags,
            )

        eq_rows = df[(df["EXCH_ID"] == "NSE") & (df["SEGMENT"] == "E") & (df["INSTRUMENT"] == "EQUITY") & (df["SYMBOL_NAME"] == symbol)]
        opt_rows = df[(df["EXCH_ID"] == "NSE") & (df["SEGMENT"] == "D") & (df["INSTRUMENT"] == "OPTSTK") & (df["UNDERLYING_SYMBOL"] == symbol)]
        if not eq_rows.empty or not opt_rows.empty:
            if not eq_rows.empty:
                spot_id = str(eq_rows.iloc[0]["SECURITY_ID"])
            else:
                # Fallback for cases where NSE equity row is absent but derivative underlying ID is available.
                spot_id = str(opt_rows.iloc[0]["UNDERLYING_SECURITY_ID"])
            derivative_underlying_id = str(opt_rows.iloc[0]["UNDERLYING_SECURITY_ID"]) if not opt_rows.empty else None
            flags = tuple(sorted(x for x in opt_rows["EXPIRY_FLAG"].dropna().unique().tolist() if x and x != "nan"))
            return UnderlyingResolution(
                symbol=symbol,
                kind="EQUITY",
                spot_security_id=spot_id,
                spot_exchange_segment="NSE_EQ",
                # For stock rollingoption, docs say securityId is underlying exchange standard ID.
                rollingoption_security_id=spot_id,
                rollingoption_instrument="OPTSTK",
                derivative_underlying_security_id=derivative_underlying_id,
                available_option_expiry_flags=flags,
            )
        raise KeyError(f"Could not resolve underlying symbol from instrument master: {symbol}")

    def option_expiries(self, symbol: str, instrument: str | None = None, expiry_flag: str | None = None) -> list[str]:
        symbol = symbol.upper()
        df = self.frame[(self.frame["EXCH_ID"] == "NSE") & (self.frame["SEGMENT"] == "D") & (self.frame["UNDERLYING_SYMBOL"] == symbol)]
        if instrument:
            df = df[df["INSTRUMENT"] == instrument]
        if expiry_flag:
            df = df[df["EXPIRY_FLAG"] == _dhan_master_expiry_flag(expiry_flag)]
        vals = sorted(v for v in df["SM_EXPIRY_DATE"].dropna().unique().tolist() if v and v != "0001-01-01")
        return vals


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [c.strip() for c in out.columns]
    for col in CANONICAL_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    for col in ["EXCH_ID", "SEGMENT", "INSTRUMENT", "UNDERLYING_SYMBOL", "SYMBOL_NAME", "OPTION_TYPE", "EXPIRY_FLAG"]:
        out[col] = out[col].astype("string").str.upper().str.strip()
    out["SECURITY_ID"] = out["SECURITY_ID"].astype("string").str.strip()
    out["UNDERLYING_SECURITY_ID"] = out["UNDERLYING_SECURITY_ID"].astype("string").str.strip()
    return out


def _dhan_master_expiry_flag(expiry_flag: str) -> str:
    val = expiry_flag.upper()
    return {"WEEK": "W", "MONTH": "M"}.get(val, val)
