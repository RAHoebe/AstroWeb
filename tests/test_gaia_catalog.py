"""Plate solving must survive an unavailable or malformed Gaia mirror."""
import io
from types import SimpleNamespace

import numpy as np
import pytest
import requests
from astropy.table import Table

from astroweb import gaia
from astroweb.store import Store


@pytest.mark.parametrize("failure", ["timeout", "invalid-votable", "missing-columns"])
def test_alignment_uses_esa_fallback_and_caches_valid_sorted_columns(tmp_path, monkeypatch, failure):
    output = io.BytesIO()
    Table(dict(ra=[11., 10., np.nan], dec=[41., 40., 39.], phot_g_mean_mag=[12., 9., 8.])).write(output, format="votable")
    payload = output.getvalue().replace(b'ID="ra"', b'ID="column_1"').replace(b'ID="dec"', b'ID="column_2"')
    calls = []

    def get(endpoint, **kwargs):
        calls.append(endpoint)
        if len(calls) == 1:
            if failure == "timeout":
                raise requests.Timeout("Catalogue handshake timed out")
            if failure == "invalid-votable":
                return SimpleNamespace(content=b"<html>Maintenance</html>", raise_for_status=lambda: None)
            missing = io.BytesIO()
            Table(dict(other=[1])).write(missing, format="votable")
            return SimpleNamespace(content=missing.getvalue(), raise_for_status=lambda: None)
        return SimpleNamespace(content=payload, raise_for_status=lambda: None)

    monkeypatch.setattr(gaia.external_http, "get", get)
    store = Store(tmp_path)
    result = gaia.catalog_stars(store, 10, 41, 1.5)
    np.testing.assert_allclose(result, [[10, 40, 9], [11, 41, 12]])
    assert calls == ["https://gaia.aip.de/tap/sync", "https://gea.esac.esa.int/tap-server/tap/sync"]
    np.testing.assert_allclose(gaia.catalog_stars(store, 10, 41, 1.5), result)
    assert len(calls) == 2


def test_failed_mirrors_do_not_cache_an_empty_catalogue(tmp_path, monkeypatch):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(1)
        raise requests.ConnectionError("Offline")

    monkeypatch.setattr(gaia.external_http, "get", unavailable)
    store = Store(tmp_path)
    for _ in range(2):
        with pytest.raises(requests.ConnectionError):
            gaia.catalog_stars(store, 10, 41, 1.5)
    assert len(calls) == 4
