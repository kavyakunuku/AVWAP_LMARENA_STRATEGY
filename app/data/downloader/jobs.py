from __future__ import annotations
from pathlib import Path
from app.models.requests import ExpiredOptionRequest
from app.data.dhan.client import DhanClient
from app.data.storage.raw_store import RawStore
from app.data.downloader.resumable import DownloadManifest
from app.core.ids import stable_hash

class ExpiredOptionsDownloadJob:
    def __init__(self, client: DhanClient, raw_store: RawStore, manifest: DownloadManifest):
        self.client = client
        self.raw_store = raw_store
        self.manifest = manifest

    def run_request(self, req: ExpiredOptionRequest) -> tuple[Path, str, bool]:
        key = stable_hash(req.as_dhan_payload(), length=32)
        if self.manifest.is_completed(key):
            existing = self.raw_store.path_for_key(key)
            return existing, key, True
        self.manifest.mark(key, "STARTED")
        try:
            payload = req.as_dhan_payload()
            response = self.client.expired_options_data(payload)
            path, checksum = self.raw_store.write_json(key, {"request": payload, "response": response})
            self.manifest.mark(key, "COMPLETED", checksum=checksum)
            return path, key, False
        except Exception as exc:
            self.manifest.mark(key, "FAILED", error=str(exc))
            raise
