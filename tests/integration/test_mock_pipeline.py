from datetime import date
from app.data.dhan.mock import MockDhanClient
from app.data.downloader.resumable import DownloadManifest
from app.data.downloader.jobs import ExpiredOptionsDownloadJob
from app.data.storage.raw_store import RawStore
from app.data.storage.parquet_store import ParquetStore
from app.data.storage.metadata_store import MetadataStore
from app.data.storage.duckdb_catalog import DuckDBCatalog
from app.data.pipeline import ExpiredOptionsPipeline
from app.models.requests import ExpiredOptionRequest


def test_mock_pipeline_writes_parquet_and_duckdb_queries(tmp_path):
    raw = RawStore(tmp_path / "raw")
    manifest = DownloadManifest(tmp_path / "metadata" / "manifest.json")
    job = ExpiredOptionsDownloadJob(MockDhanClient(), raw, manifest)
    pipeline = ExpiredOptionsPipeline(job, ParquetStore(tmp_path / "parquet"), MetadataStore(tmp_path / "metadata" / "catalog.sqlite"))
    req = ExpiredOptionRequest(
        exchange_segment="NSE_FNO",
        interval="15",
        security_id="13",
        instrument="OPTIDX",
        expiry_flag="WEEK",
        expiry_code=1,
        strike="ATM+4",
        drv_option_type="CALL",
        required_data=("open","high","low","close","volume","oi","iv","strike","spot"),
        from_date=date(2026,9,14),
        to_date=date(2026,9,16),
        underlying_symbol="NIFTY",
    )
    result = pipeline.run(req)
    assert result["status"] == "VALIDATED"
    assert result["record_count"] > 0
    assert result["parquet_path"]
    count = DuckDBCatalog(tmp_path / "duckdb" / "analytics.duckdb").count_parquet(result["parquet_path"])
    assert count == result["record_count"]
    result2 = pipeline.run(req)
    assert result2["skipped_download"] is True
