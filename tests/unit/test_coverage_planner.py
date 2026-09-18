from datetime import date
from app.data.dhan.instruments import InstrumentMaster
from app.scanner.coverage_planner import baseline_moneyness_for_option_type, build_coverage_plan

MASTER = """EXCH_ID,SEGMENT,SECURITY_ID,ISIN,INSTRUMENT,UNDERLYING_SECURITY_ID,UNDERLYING_SYMBOL,SYMBOL_NAME,DISPLAY_NAME,INSTRUMENT_TYPE,SERIES,LOT_SIZE,SM_EXPIRY_DATE,STRIKE_PRICE,OPTION_TYPE,TICK_SIZE,EXPIRY_FLAG
NSE,I,13,NA,INDEX,13,NIFTY,NIFTY,Nifty 50,INDEX,NA,1,0001-01-01,,XX,0.05,N
NSE,E,1333,INE040A01034,EQUITY,,HDFCBANK,HDFCBANK,HDFC Bank,EQUITY,EQ,1,0001-01-01,,XX,0.05,N
NSE,D,35000,NA,OPTIDX,26000,NIFTY,NIFTY-Sep2026-25000-CE,NIFTY 24 SEP 25000 CALL,OP,NA,75,2026-09-24,25000,CE,5,W
NSE,D,45000,NA,OPTSTK,1333,HDFCBANK,HDFCBANK-Sep2026-1000-CE,HDFCBANK 24 SEP 1000 CALL,OP,NA,550,2026-09-24,1000,CE,5,M
"""


def test_baseline_moneyness_is_itm_directional():
    assert baseline_moneyness_for_option_type("CALL", 4) == ["ATM", "ATM-1", "ATM-2", "ATM-3", "ATM-4"]
    assert baseline_moneyness_for_option_type("PUT", 4) == ["ATM", "ATM+1", "ATM+2", "ATM+3", "ATM+4"]


def test_index_coverage_documents_atm4_available():
    res = InstrumentMaster.from_csv_text(MASTER).resolve_underlying("NIFTY")
    plan = build_coverage_plan(res, date(2026,1,1), date(2026,2,1), "WEEK", 1)
    assert len(plan) == 10
    assert all(x.expected_documented_available for x in plan)
    assert res.spot_security_id == "13"
    assert res.rollingoption_security_id == "13"


def test_stock_coverage_marks_atm4_documented_unavailable():
    res = InstrumentMaster.from_csv_text(MASTER).resolve_underlying("HDFCBANK")
    plan = build_coverage_plan(res, date(2026,1,1), date(2026,2,1), "MONTH", 1)
    unavailable = [x for x in plan if x.request.strike in {"ATM-4", "ATM+4"}]
    assert len(unavailable) == 2
    assert all(not x.expected_documented_available for x in unavailable)
