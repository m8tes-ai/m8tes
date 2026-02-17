"""Tests for v2 SDK exception hierarchy."""

from m8tes._exceptions import (
    STATUS_MAP,
    APIError,
    AuthenticationError,
    M8tesError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_base(self):
        for exc_cls in [
            AuthenticationError,
            NotFoundError,
            ValidationError,
            RateLimitError,
            APIError,
        ]:
            assert issubclass(exc_cls, M8tesError)

    def test_base_carries_fields(self):
        err = M8tesError("boom", status_code=500, request_id="req_123")
        assert str(err) == "boom"
        assert err.message == "boom"
        assert err.status_code == 500
        assert err.request_id == "req_123"

    def test_defaults_are_none(self):
        err = M8tesError("oops")
        assert err.status_code is None
        assert err.request_id is None


class TestStatusMap:
    def test_401_maps_to_auth(self):
        assert STATUS_MAP[401] is AuthenticationError

    def test_403_maps_to_auth(self):
        assert STATUS_MAP[403] is AuthenticationError

    def test_404_maps_to_not_found(self):
        assert STATUS_MAP[404] is NotFoundError

    def test_422_maps_to_validation(self):
        assert STATUS_MAP[422] is ValidationError

    def test_429_maps_to_rate_limit(self):
        assert STATUS_MAP[429] is RateLimitError

    def test_unknown_code_not_in_map(self):
        assert 500 not in STATUS_MAP
