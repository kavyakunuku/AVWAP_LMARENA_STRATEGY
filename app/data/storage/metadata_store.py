from __future__ import annotations
from pathlib import Path
import json
import sqlite3
from datetime import datetime, timezone

class MetadataStore:
    def __init__(self, path: str | Path = "data/metadata/catalog.sqlite"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                dataset_type TEXT NOT NULL,
                underlying_symbol TEXT,
                underlying_security_id TEXT,
                exchange_segment TEXT,
                instrument TEXT,
                expiry_flag TEXT,
                expiry_code INTEGER,
                option_type TEXT,
                requested_moneyness TEXT,
                timeframe TEXT,
                from_date TEXT,
                to_date TEXT,
                to_date_semantics TEXT,
                record_count INTEGER,
                missing_records INTEGER,
                duplicate_records INTEGER,
                invalid_records INTEGER,
                checksum TEXT,
                schema_version TEXT,
                status TEXT,
                failure_reason TEXT,
                parquet_path TEXT,
                raw_path TEXT,
                validation_report TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """)
            con.execute("""
            CREATE TABLE IF NOT EXISTS data_coverage (
                coverage_id TEXT PRIMARY KEY,
                dataset_id TEXT,
                underlying_symbol TEXT,
                kind TEXT,
                expiry_flag TEXT,
                expiry_code INTEGER,
                option_type TEXT,
                requested_moneyness TEXT,
                from_date TEXT,
                to_date TEXT,
                documented_available INTEGER,
                available INTEGER,
                actual_records INTEGER,
                returned_strikes TEXT,
                coverage_status TEXT,
                reason TEXT,
                recommended_action TEXT,
                created_at TEXT
            )
            """)

    def upsert_dataset(self, row: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = {**row, "updated_at": now}
        row.setdefault("created_at", now)
        row["validation_report"] = json.dumps(row.get("validation_report", {}), default=str)
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "dataset_id")
        with sqlite3.connect(self.path) as con:
            con.execute(f"INSERT INTO datasets ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(dataset_id) DO UPDATE SET {updates}", [row[c] for c in cols])

    def list_datasets(self) -> list[dict]:
        with sqlite3.connect(self.path) as con:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute("SELECT * FROM datasets ORDER BY updated_at DESC")]

    def insert_coverage(self, row: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = {**row, "created_at": now}
        row["returned_strikes"] = json.dumps(row.get("returned_strikes", []), default=str)
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        with sqlite3.connect(self.path) as con:
            con.execute(f"INSERT OR REPLACE INTO data_coverage ({','.join(cols)}) VALUES ({placeholders})", [row[c] for c in cols])

    def list_coverage(self) -> list[dict]:
        with sqlite3.connect(self.path) as con:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute("SELECT * FROM data_coverage ORDER BY created_at DESC")]
