from ipaddress import ip_network

import pytest

from app.core.limits import RateLimiter, resolve_client_ip


def test_sliding_limit_and_bounded_keys():
    limiter = RateLimiter(max_keys=2, window=60)
    assert limiter.allow(("auth", "a"), 1, 0)
    assert not limiter.allow(("auth", "a"), 1, 1)
    assert limiter.allow(("auth", "b"), 1, 1)
    assert not limiter.allow(("auth", "c"), 1, 2)
    assert limiter.allow(("auth", "c"), 1, 61)


@pytest.mark.parametrize(("peer", "forwarded", "expected"), [
    ("192.0.2.1", "198.51.100.8", "192.0.2.1"),
    ("172.30.50.2", "198.51.100.8", "198.51.100.8"),
    ("172.30.50.2", "203.0.113.9, 198.51.100.8, 172.30.50.3", "198.51.100.8"),
    ("172.30.50.2", "bad, 198.51.100.8", "172.30.50.2"),
    ("172.30.50.2", "198.51.100.8,", "172.30.50.2"),
    ("172.30.50.2", "fe80::1%fake", "172.30.50.2"),
    ("172.30.50.2", "172.30.50.3", "172.30.50.2"),
    ("172.30.50.2", "", "172.30.50.2"),
    ("172.30.50.2", "::ffff:198.51.100.8", "198.51.100.8"),
    ("172.30.50.2", "2001:db8::1", "2001:db8::1"),
    ("172.30.50.2", ",".join(["198.51.100.8"] * 33), "172.30.50.2"),
])
def test_forwarded_addresses(peer, forwarded, expected):
    trusted = [ip_network("172.30.50.2/32"), ip_network("172.30.50.3/32")]
    assert resolve_client_ip(peer, forwarded, trusted) == expected


def test_default_trusts_no_proxy():
    assert resolve_client_ip("172.30.50.2", "198.51.100.8", []) == "172.30.50.2"


def test_clients_have_separate_buckets():
    limiter = RateLimiter()
    trusted = [ip_network("172.30.50.2/32")]
    first = resolve_client_ip("172.30.50.2", "198.51.100.1", trusted)
    second = resolve_client_ip("172.30.50.2", "198.51.100.2", trusted)
    assert limiter.allow(("auth", first), 1, 0)
    assert not limiter.allow(("auth", first), 1, 1)
    assert limiter.allow(("auth", second), 1, 1)
