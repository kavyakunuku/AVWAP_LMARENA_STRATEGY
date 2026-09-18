from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True, slots=True)
class ExpiredOptionRequest:
    exchange_segment: str
    interval: str
    security_id: str
    instrument: str
    expiry_flag: str
    expiry_code: int
    strike: str
    drv_option_type: str
    required_data: tuple[str, ...]
    from_date: date
    to_date: date
    underlying_symbol: str | None = None

    def as_dhan_payload(self) -> dict:
        return {
            "exchangeSegment": self.exchange_segment,
            "interval": self.interval,
            "securityId": self.security_id,
            "instrument": self.instrument,
            "expiryFlag": self.expiry_flag,
            "expiryCode": self.expiry_code,
            "strike": self.strike,
            "drvOptionType": self.drv_option_type,
            "requiredData": list(self.required_data),
            "fromDate": self.from_date.isoformat(),
            "toDate": self.to_date.isoformat(),
        }
