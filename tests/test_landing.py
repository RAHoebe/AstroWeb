import numpy as np

from astroweb.journey import HEIGHT, WIDTH, landing
from astroweb.metadata import initial_metadata, refresh_metadata


def test_landing_keeps_all_four_corners():
    quad = np.array([[260, 400], [165, 150], [690, 95], [810, 355]], dtype=np.float32)
    for start in (quad, quad[[3, 2, 1, 0]]):
        initial, _ = landing(start, 600, 900, 0)
        np.testing.assert_allclose(initial, start, atol=.001)
        for progress in np.linspace(0, 1, 32):
            pose, mirrored = landing(start, 600, 900, progress)
            assert abs(np.linalg.det([pose[1]-pose[0], pose[3]-pose[0]])) > 1000
        if mirrored:
            pose = pose[[3, 2, 1, 0]]
        np.testing.assert_allclose(pose[[0, 1], 1], 0, atol=.001)
        np.testing.assert_allclose(pose[[2, 3], 1], HEIGHT-1, atol=.001)
        assert 0 < pose[0, 0] < pose[1, 0] < WIDTH
        assert abs((pose[1, 0]-pose[0, 0])/(HEIGHT-1) - 599/899) < .001


def test_eastern_veil_rejects_unrelated_caldwell_search_hits(monkeypatch):
    queries = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"collection": {"items": [{"data": [{"title": "Caldwell crew briefing",
                    "description": "Launch anniversary 33", "nasa_id": "other"}]}]}}

    def search(url, params, **kwargs):
        queries.append(params["q"])
        return Response()

    monkeypatch.setattr("astroweb.metadata.requests.get", search)
    record = initial_metadata("NGC_6992")
    record["description"]["nl"] = "Eigen tekst"
    refreshed = refresh_metadata(record)
    assert "Caldwell 33" in queries
    assert refreshed["description"]["nl"] == "Eigen tekst"
    assert refreshed["external"]["url"].startswith("https://science.nasa.gov/")
    assert refreshed["external"]["text"]["nl"]
