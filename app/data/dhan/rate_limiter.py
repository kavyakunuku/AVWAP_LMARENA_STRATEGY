import threading
import time
from collections import deque

class TokenBucketRateLimiter:
    """Simple process-local sliding-window limiter."""
    def __init__(self, per_second: int):
        self.per_second = per_second
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._events and now - self._events[0] >= 1.0:
                    self._events.popleft()
                if len(self._events) < self.per_second:
                    self._events.append(now)
                    return
                sleep_for = max(0.01, 1.0 - (now - self._events[0]))
            time.sleep(sleep_for)
