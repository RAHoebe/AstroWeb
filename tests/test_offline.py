import pytest
import requests
from astroweb import external_http


@pytest.mark.parametrize("method", ["get", "post"])
def test_offline_does_not_reach_transport(monkeypatch, method):
    monkeypatch.setenv("ASTROWEB_OFFLINE", "1")
    def unexpected(*args, **kwargs):
        pytest.fail("Offline request reached network transport")
    monkeypatch.setattr(requests, method, unexpected)
    with pytest.raises(requests.ConnectionError, match="offline"):
        getattr(external_http, method)("https://example.org/")
