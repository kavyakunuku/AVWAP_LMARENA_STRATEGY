from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone


def stable_hash(*parts: object, length: int = 16) -> str:
    normalized = ["" if p is None else p for p in parts]
    joined = json.dumps(normalized, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def utc_now_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}"


def dataset_id(*parts: object) -> str:
    return "DS-" + stable_hash(*parts, length=24)
