from pydantic import BaseModel, Field

class TradingConfig(BaseModel):
    mode: str = "PAPER"
    live_requires_confirmation: bool = True

class StrategyConfig(BaseModel):
    name: str = "AVWAP_V1"
    timeframe: str = "15"
    itm_strikes_per_side: int = 4
    expiry_switch_day: int = 24

class RiskConfig(BaseModel):
    quantity_per_trade: int
    max_open_positions: int
    max_trades_per_day: int
    max_daily_loss: float
    max_capital_allocation: float
    max_underlying_exposure: float

class DataConfig(BaseModel):
    source: str = "dhan"
    storage_root: str = "data"
    parquet_root: str = "data/parquet"
    raw_root: str = "data/raw"
    metadata_db: str = "data/metadata/catalog.sqlite"
    duckdb_path: str = "data/duckdb/analytics.duckdb"
    default_interval: str = "15"
    request_timeout_seconds: int = 30
    dhan_base_url: str = "https://api.dhan.co/v2"

class UniverseConfig(BaseModel):
    indices: list[str] = Field(default_factory=list)
    stocks: list[str] = Field(default_factory=list)

class DashboardConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    control_token_env: str = "AVWAP_DASHBOARD_CONTROL_TOKEN"

class AppConfig(BaseModel):
    trading: TradingConfig
    strategy: StrategyConfig
    risk: RiskConfig
    data: DataConfig
    universe: UniverseConfig
    dashboard: DashboardConfig
