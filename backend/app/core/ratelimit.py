"""Đếm giới hạn tần suất trong bộ nhớ (một tiến trình uvicorn, 12 mục 3.7)."""

import threading
import time
from collections import defaultdict, deque

from app.core.errors import RateLimitError


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int, cost: int = 1) -> None:
        """Ghi `cost` lượt; vượt `limit` trong cửa sổ thì ném RateLimitError."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) + cost > limit:
                retry = int(window_seconds - (now - hits[0])) + 1 if hits else window_seconds
                raise RateLimitError(headers={"Retry-After": str(max(retry, 1))})
            hits.extend([now] * cost)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindow()
