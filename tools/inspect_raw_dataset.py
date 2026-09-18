from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a raw Dhan expired-options response without modifying data")
    parser.add_argument("raw_path", help="Path to raw .json.gz response, e.g. data/raw/abc.json.gz")
    parser.add_argument("--limit", type=int, default=30, help="Max bad rows to print")
    args = parser.parse_args()

    path = Path(args.raw_path)
    if not path.exists():
        raise SystemExit(f"Raw file not found: {path}")

    with gzip.open(path, "rb") as f:
        envelope = json.loads(f.read().decode("utf-8"))

    payload = envelope.get("payload", {})
    request = payload.get("request", {})
    response = payload.get("response", {})
    data_root = response.get("data", {}) if isinstance(response, dict) else {}

    side = "ce" if request.get("drvOptionType") == "CALL" else "pe"
    data = data_root.get(side)
    if data is None:
        alt = "pe" if side == "ce" else "ce"
        data = data_root.get(alt)
        side = alt if data is not None else side

    print("RAW FILE:", path)
    print("STORED_AT:", envelope.get("stored_at"))
    print("REQUEST:")
    safe_request = dict(request)
    # No credentials should be present here, but keep output focused.
    print(json.dumps(safe_request, indent=2, default=str))
    print("RESPONSE_TOP_LEVEL_KEYS:", list(response.keys()) if isinstance(response, dict) else type(response).__name__)
    print("DATA_SIDE:", side)

    if not data:
        print("No option-side data found in response.")
        print(json.dumps(response, indent=2, default=str)[:4000])
        return 2

    lengths = {k: len(v) for k, v in data.items() if isinstance(v, list)}
    print("FIELD_LENGTHS:")
    print(json.dumps(lengths, indent=2, sort_keys=True))

    n = max(lengths.values()) if lengths else 0
    volumes = data.get("volume", [])
    timestamps = data.get("timestamp", [])
    strikes = data.get("strike", [])
    spots = data.get("spot", [])

    neg_indexes = [i for i, v in enumerate(volumes) if _is_negative(v)]
    print("RECORD_COUNT:", n)
    print("NEGATIVE_VOLUME_COUNT:", len(neg_indexes))
    if volumes:
        numeric_vols = [_to_float(v) for v in volumes if _to_float(v) is not None]
        if numeric_vols:
            print("VOLUME_MIN:", min(numeric_vols))
            print("VOLUME_MAX:", max(numeric_vols))

    if strikes:
        uniq = sorted({str(x) for x in strikes if x is not None})
        print("RETURNED_STRIKE_UNIQUE_COUNT:", len(uniq))
        print("RETURNED_STRIKE_SAMPLE:", uniq[:20])
    if spots:
        numeric_spots = [_to_float(v) for v in spots if _to_float(v) is not None]
        if numeric_spots:
            print("SPOT_MIN_MAX:", min(numeric_spots), max(numeric_spots))

    if neg_indexes:
        print("\nNEGATIVE_VOLUME_ROWS:")
        for i in neg_indexes[: args.limit]:
            ts = timestamps[i] if i < len(timestamps) else None
            print(json.dumps({
                "index": i,
                "timestamp_epoch": ts,
                "timestamp_ist": _epoch_to_ist(ts),
                "open": _get(data, "open", i),
                "high": _get(data, "high", i),
                "low": _get(data, "low", i),
                "close": _get(data, "close", i),
                "volume": _get(data, "volume", i),
                "oi": _get(data, "oi", i),
                "iv": _get(data, "iv", i),
                "strike": _get(data, "strike", i),
                "spot": _get(data, "spot", i),
            }, indent=2, default=str))
        if len(neg_indexes) > args.limit:
            print(f"... {len(neg_indexes) - args.limit} additional negative-volume rows not printed")

    return 0


def _get(data: dict, key: str, i: int):
    arr = data.get(key, [])
    return arr[i] if isinstance(arr, list) and i < len(arr) else None


def _to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def _is_negative(v) -> bool:
    f = _to_float(v)
    return f is not None and f < 0


def _epoch_to_ist(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(IST).isoformat()
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
