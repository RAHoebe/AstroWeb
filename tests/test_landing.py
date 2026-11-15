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
        assert_fitted_quarter_turn(start, pose, 600, 900)


def assert_fitted_quarter_turn(start, pose, width, height):
    edge=pose[1]-pose[0]
    heading=np.arctan2(edge[1], edge[0])
    original=start[1]-start[0]
    difference=np.angle(np.exp(1j*(heading-np.arctan2(original[1],original[0]))))
    assert abs(difference)<=np.pi/4+1e-5
    assert abs(np.sin(2*heading))<1e-5
    np.testing.assert_allclose(pose.mean(axis=0),[(WIDTH-1)/2,(HEIGHT-1)/2],atol=.001)
    spans=np.ptp(pose,axis=0)/[WIDTH-1,HEIGHT-1]
    assert abs(max(spans)-1)<1e-5 and np.min(pose)>-.001
    assert np.linalg.det([edge,pose[3]-pose[0]])>0
    assert abs(np.linalg.norm(edge)/np.linalg.norm(pose[3]-pose[0])-(width-1)/(height-1))<1e-5


def test_all_quarter_turns_and_mirrored_fields():
    quad=np.array([[-40,-65],[40,-65],[40,65],[-40,65]],dtype=float)
    for degrees in [-179,-136,-135,-134,-91,-46,-45,-44,0,44,45,46,89,135,179]:
        a=np.deg2rad(degrees)
        field=quad@np.array([[np.cos(a),np.sin(a)],[-np.sin(a),np.cos(a)]])
        for start in [field,field[::-1]]:
            end,flipped=landing(start,81,131,1)
            assert_fitted_quarter_turn(start,end[::-1] if flipped else end,81,131)


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
