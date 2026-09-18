from __future__ import annotations
from app.core.ids import dataset_id
from app.models.requests import ExpiredOptionRequest
from app.data.downloader.jobs import ExpiredOptionsDownloadJob
from app.data.normalizer.expired_options import normalize_expired_options
from app.data.validator.candles import validate_candles
from app.data.storage.metadata_store import MetadataStore
from app.data.storage.parquet_store import ParquetStore

class ExpiredOptionsPipeline:
    def __init__(self, job: ExpiredOptionsDownloadJob, parquet: ParquetStore, metadata: MetadataStore, source: str = "dhan"):
        self.job = job
        self.parquet = parquet
        self.metadata = metadata
        self.source = source

    def run(self, req: ExpiredOptionRequest) -> dict:
        ds_id = dataset_id(self.source, "expired_options", req.underlying_symbol, req.security_id, req.expiry_flag, req.expiry_code, req.strike, req.drv_option_type, req.interval, req.from_date, req.to_date)
        raw_path, key, skipped = self.job.run_request(req)
        envelope = self.job.raw_store.read_json(raw_path)
        # Preserve user-friendly symbol and source marker for downstream partitioning.
        envelope["payload"]["request"]["underlying_symbol"] = req.underlying_symbol
        envelope["payload"]["source"] = self.source
        df = normalize_expired_options(envelope, ds_id)
        report = validate_candles(df)
        parquet_path = None
        status = "VALIDATED" if report.ok else "FAILED"
        if report.ok:
            parquet_path = str(self.parquet.write_candles(df, ds_id))
        self.metadata.upsert_dataset({
            "dataset_id": ds_id,
            "source": self.source,
            "dataset_type": "expired_options",
            "underlying_symbol": req.underlying_symbol,
            "underlying_security_id": req.security_id,
            "exchange_segment": req.exchange_segment,
            "instrument": req.instrument,
            "expiry_flag": req.expiry_flag,
            "expiry_code": req.expiry_code,
            "option_type": req.drv_option_type,
            "requested_moneyness": req.strike,
            "timeframe": req.interval,
            "from_date": req.from_date.isoformat(),
            "to_date": req.to_date.isoformat(),
            "to_date_semantics": "non-inclusive",
            "record_count": report.record_count,
            "missing_records": None,
            "duplicate_records": report.duplicate_records,
            "invalid_records": report.invalid_records,
            "checksum": key,
            "schema_version": "candles_v1",
            "status": status,
            "failure_reason": "; ".join(report.errors) if report.errors else None,
            "parquet_path": parquet_path,
            "raw_path": str(raw_path),
            "validation_report": {"ok": report.ok, "errors": report.errors, "warnings": report.warnings},
        })
        return {"dataset_id": ds_id, "status": status, "record_count": report.record_count, "raw_path": str(raw_path), "parquet_path": parquet_path, "skipped_download": skipped, "validation": report}
