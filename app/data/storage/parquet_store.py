from __future__ import annotations
from pathlib import Path
import pandas as pd

class ParquetStore:
    def __init__(self, root: str | Path = "data/parquet"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_candles(self, df: pd.DataFrame, dataset_id: str) -> Path:
        if df.empty:
            raise ValueError("Refusing to write empty dataset to Parquet")
        underlying = str(df["underlying_symbol"].iloc[0] or "UNKNOWN")
        timeframe = str(df["timeframe"].iloc[0])
        source = str(df["source"].iloc[0] if "source" in df.columns else "unknown")
        out_dir = self.root / "candles" / f"source={source}" / f"underlying={underlying}" / f"timeframe={timeframe}"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{dataset_id}.parquet"
        df.to_parquet(path, index=False)
        return path

    def read(self, path: str | Path) -> pd.DataFrame:
        return pd.read_parquet(path)
