from app.security import FixedWindowRateLimiter, resolve_api_key_owner


def test_api_key_owner_resolution() -> None:
    configured = (("correct-secret", "owner-a"),)
    assert resolve_api_key_owner("correct-secret", configured) == "owner-a"
    assert resolve_api_key_owner("wrong-secret", configured) is None
    assert resolve_api_key_owner(None, configured) is None


def test_rate_limiter_rejects_excess_hits() -> None:
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("owner")
    assert limiter.allow("owner")
    assert not limiter.allow("owner")
