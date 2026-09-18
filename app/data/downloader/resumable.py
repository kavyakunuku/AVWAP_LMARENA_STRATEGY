from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

@dataclass(slots=True)
class ChunkStatus:
    key: str
    status: str
    checksum: str | None = None
    updated_at: str = ""
    error: str | None = None

class DownloadManifest:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.items: dict[str, ChunkStatus] = {}
        if self.path.exists():
            raw=json.loads(self.path.read_text())
            self.items={k: ChunkStatus(**v) for k,v in raw.items()}

    def is_completed(self, key: str) -> bool:
        return self.items.get(key, ChunkStatus(key, "")).status == "COMPLETED"

    def mark(self, key: str, status: str, checksum: str | None = None, error: str | None = None) -> None:
        self.items[key] = ChunkStatus(key, status, checksum, datetime.now(timezone.utc).isoformat(), error)
        self.save()

    def save(self) -> None:
        self.path.write_text(json.dumps({k: asdict(v) for k,v in self.items.items()}, indent=2, sort_keys=True), encoding="utf-8")
