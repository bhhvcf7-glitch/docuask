from collections import OrderedDict, deque
from time import monotonic


class RateLimiter:
    """Bounded per-process sliding window; reject new keys when full."""

    def __init__(self, max_keys: int = 10000, window: float = 60):
        self.max_keys = max_keys
        self.window = window
        self.buckets: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()

    def allow(self, key: tuple[str, str], limit: int, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        cutoff = now - self.window
        while self.buckets:
            oldest = next(iter(self.buckets))
            if self.buckets[oldest][-1] > cutoff:
                break
            self.buckets.popitem(last=False)
        bucket = self.buckets.get(key)
        if bucket is None:
            if len(self.buckets) >= self.max_keys:
                return False
            bucket = self.buckets[key] = deque()
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        self.buckets.move_to_end(key)
        return True
