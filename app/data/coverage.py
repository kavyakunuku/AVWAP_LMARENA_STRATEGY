from __future__ import annotations
from datetime import date, timedelta
from dataclasses import replace
import json
import os
from pathlib import Path
import typer
import pandas as pd
from app.config.loader import load_config
from app.core.errors import DhanApiError
from app.core.enums import ErrorCategory
from app.data.dhan.client import DhanHTTPClient
from app.data.dhan.mock import MockDhanClient
from app.data.dhan.instruments import InstrumentMaster
from app.data.downloader.resumable import DownloadManifest
from app.data.downloader.jobs import ExpiredOptionsDownloadJob
from app.data.storage.raw_store import RawStore
from app.data.storage.parquet_store import ParquetStore
from app.data.storage.metadata_store import MetadataStore
from app.data.pipeline import ExpiredOptionsPipeline
from app.data.downloader.chunks import date_chunks
from app.scanner.coverage_planner import build_coverage_plan
from app.core.ids import stable_hash

app = typer.Typer(help="Build data coverage reports for baseline scanner requirements")

@app.command()
def plan(
    symbols: str = typer.Option("NIFTY,BANKNIFTY", help="Comma-separated symbols"),
    from_date: str = typer.Option(..., "--from"),
    to_date: str = typer.Option(..., "--to"),
    expiry_flag: str = "WEEK",
    expiry_code: int = 1,
    instrument_master_path: str | None = None,
    mock: bool = False,
    config_path: str = "config/config.example.yaml",
):
    cfg = load_config(config_path)
    client = MockDhanClient() if mock else DhanHTTPClient(cfg.data.dhan_base_url, timeout=cfg.data.request_timeout_seconds)
    master = _load_master(client, instrument_master_path, cfg.data.storage_root)
    started = date.fromisoformat(from_date)
    ended = date.fromisoformat(to_date)
    rows = []
    for symbol in _split_symbols(symbols):
        res = master.resolve_underlying(symbol)
        effective_expiry_flag = expiry_flag
        if symbol.upper() == "BANKNIFTY" and expiry_flag == "WEEK":
            effective_expiry_flag = "MONTH"
        for item in build_coverage_plan(res, started, ended, effective_expiry_flag, expiry_code, cfg.data.default_interval, cfg.strategy.itm_strikes_per_side):
            rows.append({
                "symbol": item.symbol,
                "kind": item.kind,
                "rollingoption_security_id": item.request.security_id,
                "instrument": item.request.instrument,
                "expiry_flag": item.request.expiry_flag,
                "expiry_code": item.request.expiry_code,
                "option_type": item.request.drv_option_type,
                "requested_moneyness": item.request.strike,
                "documented_available": item.expected_documented_available,
                "limitation_reason": item.limitation_reason,
            })
    typer.echo(json.dumps(rows, indent=2))

@app.command()
def audit(
    symbols: str = typer.Option("NIFTY,BANKNIFTY", help="Comma-separated symbols"),
    months: int = typer.Option(12, help="Approximate lookback months; converted to 365 days for 12 months"),
    to_date: str | None = typer.Option(None, "--to"),
    expiry_flag: str = "WEEK",
    expiry_code: int = 1,
    mock: bool = typer.Option(False, help="Use deterministic mock data"),
    instrument_master_path: str | None = None,
    config_path: str = "config/config.example.yaml",
    execute: bool = typer.Option(False, help="Actually call Dhan/mock and persist datasets. Without this, only prints the plan."),
):
    cfg = load_config(config_path)
    end = date.fromisoformat(to_date) if to_date else date.today()
    start = end - timedelta(days=365 if months == 12 else months * 30)
    client = MockDhanClient() if mock else DhanHTTPClient(cfg.data.dhan_base_url, timeout=cfg.data.request_timeout_seconds)
    master = _load_master(client, instrument_master_path, cfg.data.storage_root)
    plan_items = []
    for symbol in _split_symbols(symbols):
        res = master.resolve_underlying(symbol)
        effective_expiry_flag = expiry_flag
        if symbol.upper() == "BANKNIFTY" and expiry_flag == "WEEK":
            effective_expiry_flag = "MONTH"
        plan_items.extend(build_coverage_plan(res, start, end, effective_expiry_flag, expiry_code, cfg.data.default_interval, cfg.strategy.itm_strikes_per_side))

    chunks = date_chunks(start, end, max_days=30)
    if not execute:
        typer.echo(f"Planned {len(plan_items)} baseline coverage legs and {len(plan_items) * len(chunks)} API chunks for {start} -> {end}. Use --execute to download.")
        for item in plan_items:
            typer.echo(f"{item.symbol} {item.request.expiry_flag} {item.request.drv_option_type} {item.request.strike} securityId={item.request.security_id} documented_available={item.expected_documented_available}")
        return

    raw = RawStore(cfg.data.raw_root)
    manifest = DownloadManifest(os.path.join(cfg.data.storage_root, "metadata", "download_manifest.json"))
    job = ExpiredOptionsDownloadJob(client, raw, manifest)
    metadata = MetadataStore(cfg.data.metadata_db)
    pipeline = ExpiredOptionsPipeline(job, ParquetStore(cfg.data.parquet_root), metadata, source=("mock_dhan" if mock else "dhan"))
    for item in plan_items:
        if not item.expected_documented_available:
            typer.echo(f"DATA_UNAVAILABLE_DOCUMENTED {item.symbol} {item.request.drv_option_type} {item.request.strike}: {item.limitation_reason}")
            metadata.insert_coverage({
                "coverage_id": "COV-" + stable_hash(item.symbol, item.request.drv_option_type, item.request.strike, start, end, length=24),
                "dataset_id": None,
                "underlying_symbol": item.symbol,
                "kind": item.kind,
                "expiry_flag": item.request.expiry_flag,
                "expiry_code": item.request.expiry_code,
                "option_type": item.request.drv_option_type,
                "requested_moneyness": item.request.strike,
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "documented_available": 0,
                "available": 0,
                "actual_records": 0,
                "returned_strikes": [],
                "coverage_status": "DATA_UNAVAILABLE_DOCUMENTED",
                "reason": item.limitation_reason,
                "recommended_action": "Do not substitute another strike silently. Exclude or run a separate research variant.",
            })
            continue
        for chunk_from, chunk_to in chunks:
            chunk_req = replace(item.request, from_date=chunk_from, to_date=chunk_to)
            try:
                result = pipeline.run(chunk_req)
            except DhanApiError as exc:
                typer.echo(f"DHAN_API_ERROR {exc.category}: {exc.message}. action={exc.action}")
                if exc.category == ErrorCategory.AUTH_ERROR:
                    typer.echo("Stopping coverage audit because authentication failed. Run: python -m app.data.doctor credentials")
                    raise typer.Exit(1)
                metadata.insert_coverage({
                    "coverage_id": "COV-" + stable_hash(item.symbol, item.request.drv_option_type, item.request.strike, chunk_from, chunk_to, "api_error", length=24),
                    "dataset_id": None,
                    "underlying_symbol": item.symbol,
                    "kind": item.kind,
                    "expiry_flag": item.request.expiry_flag,
                    "expiry_code": item.request.expiry_code,
                    "option_type": item.request.drv_option_type,
                    "requested_moneyness": item.request.strike,
                    "from_date": chunk_from.isoformat(),
                    "to_date": chunk_to.isoformat(),
                    "documented_available": 1,
                    "available": 0,
                    "actual_records": 0,
                    "returned_strikes": [],
                    "coverage_status": "API_ERROR",
                    "reason": str(exc),
                    "recommended_action": exc.action,
                })
                continue
            returned_strikes = []
            if result.get("parquet_path"):
                try:
                    frame = pd.read_parquet(result["parquet_path"], columns=["strike_price"])
                    returned_strikes = sorted(float(x) for x in frame["strike_price"].dropna().unique().tolist())
                except Exception:
                    returned_strikes = []
            available = result["status"] == "VALIDATED" and result["record_count"] > 0
            metadata.insert_coverage({
                "coverage_id": "COV-" + stable_hash(item.symbol, item.request.drv_option_type, item.request.strike, chunk_from, chunk_to, length=24),
                "dataset_id": result["dataset_id"],
                "underlying_symbol": item.symbol,
                "kind": item.kind,
                "expiry_flag": item.request.expiry_flag,
                "expiry_code": item.request.expiry_code,
                "option_type": item.request.drv_option_type,
                "requested_moneyness": item.request.strike,
                "from_date": chunk_from.isoformat(),
                "to_date": chunk_to.isoformat(),
                "documented_available": 1,
                "available": 1 if available else 0,
                "actual_records": result["record_count"],
                "returned_strikes": returned_strikes,
                "coverage_status": "AVAILABLE" if available else "UNAVAILABLE",
                "reason": None if available else str(result["validation"].errors),
                "recommended_action": None if available else "Inspect Dhan response and do not use this dataset for baseline backtest.",
            })
            typer.echo(f"{item.symbol} {item.request.drv_option_type} {item.request.strike} {chunk_from}->{chunk_to} -> {result['status']} records={result['record_count']} dataset={result['dataset_id']}")


def _load_master(client, path: str | None, storage_root: str) -> InstrumentMaster:
    if path:
        return InstrumentMaster.from_path(path)
    if isinstance(client, MockDhanClient):
        return InstrumentMaster.from_csv_text(_mock_master_csv())
    cache_path = Path(storage_root) / "cache" / "instrument_master_detailed.csv"
    return InstrumentMaster.download(client, cache_path)


def _split_symbols(symbols: str) -> list[str]:
    return [s.strip().upper() for s in symbols.split(",") if s.strip()]


def _mock_master_csv() -> str:
    return """EXCH_ID,SEGMENT,SECURITY_ID,ISIN,INSTRUMENT,UNDERLYING_SECURITY_ID,UNDERLYING_SYMBOL,SYMBOL_NAME,DISPLAY_NAME,INSTRUMENT_TYPE,SERIES,LOT_SIZE,SM_EXPIRY_DATE,STRIKE_PRICE,OPTION_TYPE,TICK_SIZE,EXPIRY_FLAG
NSE,I,13,NA,INDEX,13,NIFTY,NIFTY,Nifty 50,INDEX,NA,1,0001-01-01,,XX,0.05,N
NSE,I,25,NA,INDEX,25,BANKNIFTY,BANKNIFTY,Nifty Bank,INDEX,NA,1,0001-01-01,,XX,0.05,N
NSE,D,35000,NA,OPTIDX,26000,NIFTY,NIFTY-Sep2026-25000-CE,NIFTY 24 SEP 25000 CALL,OP,NA,75,2026-09-24,25000,CE,5,W
NSE,D,35001,NA,OPTIDX,26009,BANKNIFTY,BANKNIFTY-Sep2026-55000-CE,BANKNIFTY 29 SEP 55000 CALL,OP,NA,30,2026-09-29,55000,CE,5,M
"""

if __name__ == "__main__":
    app()
