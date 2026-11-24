from app.core.limits import RateLimiter


def test_sliding_limit_and_bounded_keys():
    limiter = RateLimiter(max_keys=2, window=60)
    assert limiter.allow(("auth", "a"), 1, 0)
    assert not limiter.allow(("auth", "a"), 1, 1)
    assert limiter.allow(("auth", "b"), 1, 1)
    assert not limiter.allow(("auth", "c"), 1, 2)
    assert limiter.allow(("auth", "c"), 1, 61)
