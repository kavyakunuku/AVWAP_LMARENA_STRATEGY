from __future__ import annotations
import os
import time
import httpx
from app.core.enums import ErrorCategory, Severity
from app.core.errors import DhanApiError
from .rate_limiter import TokenBucketRateLimiter

class DhanClient:
    def expired_options_data(self, payload: dict) -> dict:
        raise NotImplementedError

    def intraday_data(self, payload: dict) -> dict:
        raise NotImplementedError

    def instrument_master(self) -> str:
        raise NotImplementedError

class DhanHTTPClient(DhanClient):
    def __init__(
        self,
        base_url: str = "https://api.dhan.co/v2",
        access_token: str | None = None,
        client_id: str | None = None,
        timeout: int = 30,
        retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token or os.getenv("DHAN_ACCESS_TOKEN")
        self.client_id = client_id or os.getenv("DHAN_CLIENT_ID")
        self.timeout = timeout
        self.retries = retries
        self.data_limiter = TokenBucketRateLimiter(5)
        self.quote_limiter = TokenBucketRateLimiter(1)
        if not self.access_token:
            raise DhanApiError(ErrorCategory.AUTH_ERROR, Severity.CRITICAL, "DHAN_ACCESS_TOKEN is missing", False, "Set environment variable")

    def _headers(self) -> dict:
        headers = {"Accept": "application/json", "Content-Type": "application/json", "access-token": self.access_token}
        if self.client_id:
            headers["client-id"] = self.client_id
        return headers

    def _post_data(self, path: str, payload: dict) -> dict:
        self.data_limiter.acquire()
        url = f"{self.base_url}{path}"
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    r = client.post(url, headers=self._headers(), json=payload)
                if r.status_code == 401 or r.status_code == 403:
                    raise DhanApiError(ErrorCategory.AUTH_ERROR, Severity.CRITICAL, f"Dhan auth failed: {r.status_code}", False, "Refresh token")
                if r.status_code == 429:
                    if attempt < self.retries:
                        time.sleep(2 ** attempt)
                        continue
                    raise DhanApiError(ErrorCategory.RATE_LIMIT, Severity.WARNING, "Dhan rate limit exceeded", True, "Retry later")
                if 500 <= r.status_code < 600:
                    if attempt < self.retries:
                        time.sleep(2 ** attempt)
                        continue
                    raise DhanApiError(ErrorCategory.NETWORK_ERROR, Severity.WARNING, f"Dhan server error {r.status_code}", True, "Retry later")
                r.raise_for_status()
                return r.json()
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
                    continue
        raise DhanApiError(ErrorCategory.NETWORK_ERROR, Severity.WARNING, f"Dhan network failure: {last_exc}", True, "Retry later")

    def expired_options_data(self, payload: dict) -> dict:
        return self._post_data("/charts/rollingoption", payload)

    def intraday_data(self, payload: dict) -> dict:
        return self._post_data("/charts/intraday", payload)

    def instrument_master(self) -> str:
        url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.text
