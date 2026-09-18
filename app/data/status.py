import typer
from app.config.loader import load_config
from app.data.storage.metadata_store import MetadataStore

app = typer.Typer(help="Show data catalog status")

@app.command()
def datasets(config_path: str = "config/config.example.yaml"):
    cfg = load_config(config_path)
    rows = MetadataStore(cfg.data.metadata_db).list_datasets()
    if not rows:
        typer.echo("No datasets registered.")
        return
    for r in rows:
        typer.echo(f"{r['dataset_id']} source={r['source']} {r['status']} {r['underlying_symbol']} {r['requested_moneyness']} {r['option_type']} records={r['record_count']} parquet={r['parquet_path']}")

@app.command()
def coverage(config_path: str = "config/config.example.yaml"):
    cfg = load_config(config_path)
    rows = MetadataStore(cfg.data.metadata_db).list_coverage()
    if not rows:
        typer.echo("No coverage records registered.")
        return
    for r in rows:
        typer.echo(f"{r['underlying_symbol']} {r['expiry_flag']} {r['option_type']} {r['requested_moneyness']} {r['from_date']}->{r['to_date']} {r['coverage_status']} records={r['actual_records']} reason={r['reason']}")

@app.command()
def failures(config_path: str = "config/config.example.yaml"):
    cfg = load_config(config_path)
    rows = [r for r in MetadataStore(cfg.data.metadata_db).list_datasets() if r.get("status") != "VALIDATED"]
    if not rows:
        typer.echo("No failed/non-validated datasets registered.")
        return
    for r in rows:
        typer.echo(f"{r['dataset_id']} {r['status']} {r['underlying_symbol']} {r['from_date']}->{r['to_date']} {r['option_type']} {r['requested_moneyness']} records={r['record_count']} duplicates={r['duplicate_records']} invalid={r['invalid_records']} reason={r['failure_reason']} raw={r['raw_path']}")

if __name__ == "__main__":
    app()
