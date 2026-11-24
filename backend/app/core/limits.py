from collections import OrderedDict, deque
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address
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


def parse_address(value: str) -> IPv4Address | IPv6Address:
    if "%" in value:
        raise ValueError("Scoped addresses are not supported")
    address = ip_address(value.strip())
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def resolve_client_ip(
    peer: str, forwarded: str, trusted: list[IPv4Network | IPv6Network],
) -> str:
    try:
        direct = parse_address(peer)
    except ValueError:
        return peer

    def is_trusted(address: IPv4Address | IPv6Address) -> bool:
        return any(address.version == network.version and address in network for network in trusted)

    if not is_trusted(direct) or not forwarded or len(forwarded) > 4096:
        return str(direct)
    parts = forwarded.split(",")
    if len(parts) > 32:
        return str(direct)
    try:
        chain = [parse_address(part) for part in parts]
    except ValueError:
        return str(direct)
    for address in reversed(chain):
        if not is_trusted(address):
            return str(address)
    return str(direct)
