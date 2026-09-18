from __future__ import annotations
from dataclasses import dataclass, asdict
from app.data.quality import DataAnomaly
from app.data.contract_identity import ContractIdentityDiagnostics

@dataclass(frozen=True, slots=True)
class BaselineUsabilityDecision:
    status: str
    usable_for_baseline_avwap: bool
    reasons: list[str]
    required_actions: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def decide_baseline_usability(
    validation_ok: bool,
    anomalies: list[DataAnomaly],
    identity: ContractIdentityDiagnostics,
    strict_expiry_required: bool = True,
) -> BaselineUsabilityDecision:
    reasons: list[str] = []
    actions: list[str] = []

    if not validation_ok:
        reasons.append("Dataset validation failed")
        actions.append("Quarantine failed dataset; inspect raw source response")
    critical = [a for a in anomalies if a.severity == "CRITICAL"]
    if critical:
        reasons.extend(sorted({f"Critical anomaly: {a.anomaly_type}" for a in critical}))
        actions.append("Do not use critical-anomaly rows for baseline AVWAP")
    if identity.rolling_series:
        reasons.append("Rolling moneyness response contains multiple returned strikes")
        actions.append("Split rows by actual returned strike before AVWAP")
    if strict_expiry_required and identity.expiry_identity_status != "RESOLVED":
        reasons.append("Actual expiry identity is unresolved")
        actions.append("Resolve actual expiry_date before strict contract-specific AVWAP")

    usable = not reasons
    return BaselineUsabilityDecision(
        status="USABLE_BASELINE" if usable else "BLOCKED_BASELINE",
        usable_for_baseline_avwap=usable,
        reasons=reasons,
        required_actions=actions,
    )
