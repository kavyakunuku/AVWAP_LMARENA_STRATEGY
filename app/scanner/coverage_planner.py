from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from app.models.requests import ExpiredOptionRequest
from app.data.dhan.instruments import UnderlyingResolution

@dataclass(frozen=True, slots=True)
class CoveragePlanItem:
    symbol: str
    kind: str
    request: ExpiredOptionRequest
    baseline_required: bool = True
    expected_documented_available: bool = True
    limitation_reason: str | None = None


def baseline_moneyness_for_option_type(option_type: str, itm_per_side: int = 4) -> list[str]:
    """Baseline scanner: ATM plus ITM strikes.

    Dhan rolling moneyness is interpreted as absolute strike rank relative to ATM:
    ATM+N is higher strike; ATM-N is lower strike. Calls are ITM below ATM; puts are ITM above ATM.
    """
    opt = option_type.upper()
    if opt == "CALL":
        return ["ATM"] + [f"ATM-{i}" for i in range(1, itm_per_side + 1)]
    if opt == "PUT":
        return ["ATM"] + [f"ATM+{i}" for i in range(1, itm_per_side + 1)]
    raise ValueError(f"Unsupported option type: {option_type}")


def build_coverage_plan(
    resolution: UnderlyingResolution,
    from_date: date,
    to_date: date,
    expiry_flag: str,
    expiry_code: int,
    interval: str = "15",
    itm_per_side: int = 4,
) -> list[CoveragePlanItem]:
    items: list[CoveragePlanItem] = []
    for option_type in ("CALL", "PUT"):
        for moneyness in baseline_moneyness_for_option_type(option_type, itm_per_side):
            documented = _documented_available(resolution.kind, moneyness)
            req = ExpiredOptionRequest(
                exchange_segment="NSE_FNO",
                interval=interval,
                security_id=resolution.rollingoption_security_id,
                instrument=resolution.rollingoption_instrument,
                expiry_flag=expiry_flag,
                expiry_code=expiry_code,
                strike=moneyness,
                drv_option_type=option_type,
                required_data=("open", "high", "low", "close", "volume", "oi", "iv", "strike", "spot"),
                from_date=from_date,
                to_date=to_date,
                underlying_symbol=resolution.symbol,
            )
            items.append(CoveragePlanItem(
                symbol=resolution.symbol,
                kind=resolution.kind,
                request=req,
                expected_documented_available=documented,
                limitation_reason=None if documented else "Dhan documents non-index expired-options coverage only up to ATM±3",
            ))
    return items


def _documented_available(kind: str, moneyness: str) -> bool:
    rank = 0 if moneyness == "ATM" else int(moneyness.replace("ATM+", "").replace("ATM-", ""))
    if kind == "INDEX":
        return rank <= 10
    return rank <= 3
