from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import pandas as pd

UINT32_MOD = 2**32

@dataclass(frozen=True, slots=True)
class DataAnomaly:
    anomaly_type: str
    severity: str
    row_index: int | None
    field: str
    value: Any
    timestamp: Any = None
    details: dict[str, Any] | None = None
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_candle_anomalies(df: pd.DataFrame) -> list[DataAnomaly]:
    anomalies: list[DataAnomaly] = []
    if df.empty:
        anomalies.append(DataAnomaly(
            anomaly_type="EMPTY_DATASET",
            severity="CRITICAL",
            row_index=None,
            field="*",
            value=None,
            recommendation="Do not use this dataset for baseline backtests.",
        ))
        return anomalies

    if "volume" in df.columns:
        for idx, row in df[df["volume"] < 0].iterrows():
            value = int(row["volume"])
            unsigned_candidate = value + UINT32_MOD if value < 0 else None
            anomalies.append(DataAnomaly(
                anomaly_type="NEGATIVE_VOLUME",
                severity="CRITICAL",
                row_index=int(idx),
                field="volume",
                value=value,
                timestamp=row.get("timestamp_ist", row.get("timestamp")),
                details={
                    "possible_uint32_overflow": bool(unsigned_candidate and unsigned_candidate >= 0),
                    "uint32_overflow_candidate_value": unsigned_candidate,
                    "why_critical": "AVWAP is volume-weighted; negative volume corrupts cumulative PV and cumulative volume.",
                },
                recommendation="Quarantine dataset for baseline. Re-query source and/or raise with Dhan. Do not auto-convert unless approved as an explicit repair policy.",
            ))
    if "oi" in df.columns:
        for idx, row in df[df["oi"].dropna() < 0].iterrows():
            anomalies.append(DataAnomaly(
                anomaly_type="NEGATIVE_OI",
                severity="CRITICAL",
                row_index=int(idx),
                field="oi",
                value=row.get("oi"),
                timestamp=row.get("timestamp_ist", row.get("timestamp")),
                recommendation="Quarantine dataset until source is corrected or explicitly classified.",
            ))
    return anomalies


def classify_dataset_usability(validation_ok: bool, anomalies: list[DataAnomaly]) -> str:
    if validation_ok and not anomalies:
        return "USABLE_BASELINE"
    critical = [a for a in anomalies if a.severity == "CRITICAL"]
    if critical:
        return "QUARANTINED_VALIDATION_FAILED"
    if not validation_ok:
        return "UNUSABLE_VALIDATION_FAILED"
    return "USABLE_WITH_WARNINGS"
