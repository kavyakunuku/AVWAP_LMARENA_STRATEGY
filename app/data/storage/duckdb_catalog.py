from __future__ import annotations
from pathlib import Path
import duckdb

class DuckDBCatalog:
    def __init__(self, path: str | Path = "data/duckdb/analytics.duckdb"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def query_parquet(self, parquet_glob: str, sql_where: str = "1=1"):
        with duckdb.connect(str(self.path)) as con:
            return con.execute(f"SELECT * FROM read_parquet(?) WHERE {sql_where}", [parquet_glob]).fetch_df()

    def count_parquet(self, parquet_glob: str) -> int:
        with duckdb.connect(str(self.path)) as con:
            return int(con.execute("SELECT count(*) FROM read_parquet(?)", [parquet_glob]).fetchone()[0])
