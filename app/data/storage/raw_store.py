from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

class RawStore:
    def __init__(self, root: str | Path = "data/raw"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for_key(self, key: str) -> Path:
        return self.root / f"{key}.json.gz"

    def write_json(self, key: str, payload: dict) -> tuple[Path, str]:
        envelope = {"stored_at": datetime.now(timezone.utc).isoformat(), "payload": payload}
        encoded = json.dumps(envelope, sort_keys=True, default=str).encode("utf-8")
        checksum = hashlib.sha256(encoded).hexdigest()
        path = self.path_for_key(key)
        with gzip.open(path, "wb") as f:
            f.write(encoded)
        return path, checksum

    def read_json(self, path: str | Path) -> dict:
        with gzip.open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
