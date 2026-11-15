from datetime import datetime, timezone

import cv2
import numpy as np
import pytest

from astroweb import tv_modes


def test_registration_across_ra_zero_with_mirrored_capture():
    reference = [[359.8, 50.2], [0.2, 50.2], [0.2, 49.8], [359.8, 49.8]]
    mirrored = [reference[i] for i in (1, 0, 3, 2)]
    transform = tv_modes.registration_matrix(reference, mirrored, (800, 600), (400, 300))
    pts = np.float64([[0, 0], [100, 150], [399, 299]])
    actual = cv2.perspectiveTransform(pts[None], transform)[0]
    np.testing.assert_allclose(actual, np.column_stack((798.5-2*pts[:, 0], .5+2*pts[:, 1])), atol=.001)


def test_night_tracks_use_capture_site_and_local_date_without_exposing_coordinates():
    record = {"body": "Moon", "observation": {"latitude": 52, "longitude": 5,
              "date_obs": "2026-10-24T21:00:00+00:00", "timezone": "Europe/Amsterdam"}}
    result = tv_modes.night_comparison(record, datetime(2026, 11, 15, 2, tzinfo=timezone.utc))
    a, b = result["capture"], result["tonight"]
    assert a["day"] == "2026-10-24" and b["day"] == "2026-11-14"
    assert len(a["target"]) == 151 and len(b["target"]) == 145  # local clocks went back in October
    assert b["target"] == b["bodies"]["moon"] and a["target"][70] != b["target"][70]
    assert b["peak"] in b["hours"] and b["bodies"]["sun"][b["peak"]][1] < 0
    assert all(k not in result for k in ("longitude", "latitude", "location"))
    assert not result["default_site"]


def test_no_observing_site_for_deep_sky():
    with pytest.raises(ValueError, match="sky_metadata_missing"):
        tv_modes.night_comparison({"observation": {"date_obs": "2026-11-02T10:30:00Z", "ra": 10, "dec": 40}})


def test_program_uses_only_ready_local_movies(monkeypatch):
    def options(store, record, *, local_only):
        assert local_only
        return [{"id": "ready"}, {"id": "absent"}]
    def cached_hubble(store, record, name, *, tv, cached_only, options):
        assert tv and cached_only and len(options) == 2
        return name == "ready"
    def cached_journey(store, record, field, *, cached_only):
        assert cached_only
        return None
    monkeypatch.setattr(tv_modes.journey, "geometry", lambda *_: {"kind": "gaia"})
    monkeypatch.setattr(tv_modes.journey, "movie", cached_journey)
    monkeypatch.setattr(tv_modes.hubble, "eligible", lambda *_: True)
    monkeypatch.setattr(tv_modes.hubble, "fields", options)
    monkeypatch.setattr(tv_modes.hubble, "movie", cached_hubble)
    program = tv_modes.program(None, {"id": "M_31"})
    assert program["journey"] is None
    assert [t["url"] for t in program["trips"]] == ["/media/M_31/hubble/ready?view=tv&cached=1"]
