import pytest
from app.data.dhan.client import DhanClient
from app.data.dhan.instruments import InstrumentMaster

PUBLIC_SAMPLE = """EXCH_ID,SEGMENT,SECURITY_ID,ISIN,INSTRUMENT,UNDERLYING_SECURITY_ID,UNDERLYING_SYMBOL,SYMBOL_NAME,DISPLAY_NAME,INSTRUMENT_TYPE,SERIES,LOT_SIZE,SM_EXPIRY_DATE,STRIKE_PRICE,OPTION_TYPE,TICK_SIZE,EXPIRY_FLAG
NSE,I,13,NA,INDEX,13,NIFTY,NIFTY,Nifty 50,INDEX,NA,1,0001-01-01,,XX,0.05,N
NSE,D,35000,NA,OPTIDX,26000,NIFTY,NIFTY-Sep2026-25000-CE,NIFTY 24 SEP 25000 CALL,OP,NA,75,2026-09-24,25000,CE,5,W
"""

class StaticInstrumentClient(DhanClient):
    def instrument_master(self) -> str:
        return PUBLIC_SAMPLE
    def expired_options_data(self, payload: dict) -> dict:
        raise NotImplementedError
    def intraday_data(self, payload: dict) -> dict:
        raise NotImplementedError


def test_instrument_master_download_uses_client(tmp_path):
    cache = tmp_path / "im.csv"
    master = InstrumentMaster.download(StaticInstrumentClient(), cache)
    assert cache.exists()
    res = master.resolve_underlying("NIFTY")
    assert res.kind == "INDEX"
    assert res.spot_exchange_segment == "IDX_I"
