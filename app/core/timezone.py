from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

def epoch_to_ist(ts: int | float) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC).astimezone(IST)
