from __future__ import annotations
from datetime import date
import os
import typer
from app.config.loader import load_config
from app.data.dhan.client import DhanHTTPClient
from app.data.dhan.mock import MockDhanClient
from app.data.downloader.resumable import DownloadManifest
from app.data.downloader.jobs import ExpiredOptionsDownloadJob
from app.data.storage.raw_store import RawStore
from app.data.storage.parquet_store import ParquetStore
from app.data.storage.metadata_store import MetadataStore
from app.data.pipeline import ExpiredOptionsPipeline
from app.data.downloader.chunks import date_chunks
from app.models.requests import ExpiredOptionRequest

app = typer.Typer(help="Download Dhan historical market data")

@app.command()
def expired_option(
    underlying: str = typer.Option(...),
    security_id: str = typer.Option(...),
    from_date: str = typer.Option(..., "--from"),
    to_date: str = typer.Option(..., "--to"),
    expiry_flag: str = "WEEK",
    expiry_code: int = 1,
    strike: str = "ATM",
    option_type: str = "CALL",
    instrument: str = "OPTIDX",
    interval: str = "15",
    mock: bool = typer.Option(False, help="Use deterministic mock data instead of Dhan"),
    config_path: str = "config/config.example.yaml",
):
    cfg = load_config(config_path)
    client = MockDhanClient() if mock else DhanHTTPClient(cfg.data.dhan_base_url, timeout=cfg.data.request_timeout_seconds)
    raw = RawStore(cfg.data.raw_root)
    manifest = DownloadManifest(os.path.join(cfg.data.storage_root, "metadata", "download_manifest.json"))
    job = ExpiredOptionsDownloadJob(client, raw, manifest)
    pipeline = ExpiredOptionsPipeline(job, ParquetStore(cfg.data.parquet_root), MetadataStore(cfg.data.metadata_db), source=("mock_dhan" if mock else "dhan"))
    parsed_from_date = date.fromisoformat(from_date)
    parsed_to_date = date.fromisoformat(to_date)
    results = []
    failed = False
    for chunk_from, chunk_to in date_chunks(parsed_from_date, parsed_to_date, max_days=30):
        req = ExpiredOptionRequest(
            exchange_segment="NSE_FNO",
            interval=interval,
            security_id=security_id,
            instrument=instrument,
            expiry_flag=expiry_flag,
            expiry_code=expiry_code,
            strike=strike,
            drv_option_type=option_type,
            required_data=("open","high","low","close","volume","oi","iv","strike","spot"),
            from_date=chunk_from,
            to_date=chunk_to,
            underlying_symbol=underlying,
        )
        result = pipeline.run(req)
        results.append(result)
        typer.echo({k: str(v) for k,v in result.items() if k != "validation"})
        if not result["validation"].ok:
            failed = True
    if failed:
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
