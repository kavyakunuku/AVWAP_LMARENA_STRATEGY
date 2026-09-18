from pathlib import Path
import typer
import pandas as pd
from app.data.validator.candles import validate_candles

app = typer.Typer(help="Validate persisted candle datasets")

@app.command()
def parquet(path: str):
    df = pd.read_parquet(Path(path))
    report = validate_candles(df)
    typer.echo(report)
    if not report.ok:
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
