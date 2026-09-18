from __future__ import annotations
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from app.data.dhan.client import DhanClient

IST = ZoneInfo("Asia/Kolkata")

class MockDhanClient(DhanClient):
    """Deterministic mock for tests and local development. It never represents real market data."""

    def expired_options_data(self, payload: dict) -> dict:
        from_date = datetime.fromisoformat(payload["fromDate"]).date()
        to_date = datetime.fromisoformat(payload["toDate"]).date()
        interval = int(payload.get("interval", "15"))
        side = "ce" if payload["drvOptionType"] == "CALL" else "pe"
        timestamps=[]; opens=[]; highs=[]; lows=[]; closes=[]; vols=[]; ois=[]; ivs=[]; strikes=[]; spots=[]
        d = from_date
        base = 100.0
        strike_offset = _moneyness_to_offset(payload["strike"])
        abs_strike = 25000 + strike_offset * 50
        while d < to_date:
            if d.weekday() < 5:
                t = datetime.combine(d, time(9,15), tzinfo=IST)
                end = datetime.combine(d, time(15,30), tzinfo=IST)
                while t < end:
                    n = len(timestamps)
                    o = base + (n % 7) * 0.5
                    c = o + (1 if n % 3 else -1) * 0.4
                    h = max(o,c)+0.3
                    l = min(o,c)-0.3
                    timestamps.append(int(t.timestamp()))
                    opens.append(round(o,2)); highs.append(round(h,2)); lows.append(round(l,2)); closes.append(round(c,2))
                    vols.append(1000+n); ois.append(10000+n); ivs.append(12.5); strikes.append(abs_strike); spots.append(25000+n*0.1)
                    t += timedelta(minutes=interval)
            d += timedelta(days=1)
        return {"data": {side: {"timestamp": timestamps, "open": opens, "high": highs, "low": lows, "close": closes, "volume": vols, "oi": ois, "iv": ivs, "strike": strikes, "spot": spots}, ("pe" if side=="ce" else "ce"): None}, "status": "success"}

    def intraday_data(self, payload: dict) -> dict:
        return {"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []}

    def instrument_master(self) -> str:
        return "EXCH_ID,SEGMENT,UNDERLYING_SECURITY_ID,UNDERLYING_SYMBOL,SYMBOL_NAME,SM_EXPIRY_DATE,STRIKE_PRICE,OPTION_TYPE,LOT_SIZE,TICK_SIZE,EXPIRY_FLAG\n"

def _moneyness_to_offset(s: str) -> int:
    if s == "ATM":
        return 0
    if s.startswith("ATM+"):
        return int(s[4:])
    if s.startswith("ATM-"):
        return -int(s[4:])
    raise ValueError(f"Invalid moneyness {s}")
