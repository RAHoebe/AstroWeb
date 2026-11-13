import io
import json
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from PIL import Image

from astroweb.app import create_app
from astroweb.jobs import JobQueue
from astroweb.media import identify_files, import_object, normalize_id, validate_images
from astroweb.observation import public_observation, read_observation
from astroweb.render import Parameters, Scene, compose, read_rgb, render_video
from astroweb.store import Store


@pytest.fixture
def images(tmp_path):
    folder = tmp_path / "input"
    folder.mkdir()
    y, x = np.mgrid[:192, :128]
    bg = np.stack((.1 + x / 600, .08 + y / 900, .15 + x / 800), axis=-1).astype(np.float32)
    stars = np.zeros_like(bg)
    stars[45:50, 55:60] = [.7, .6, .5]
    stars[125:128, 95:98] = .45
    final = compose(bg, stars, "screen")
    arrays = {"final": final, "starless": bg, "stars": stars * .5, "stars_laid": stars}
    paths = {}
    for role, data in arrays.items():
        path = folder / f"NGC_7000_test_{role}.png"
        Image.fromarray(np.rint(data * 255).astype(np.uint8)).save(path)
        paths[role] = path
    return paths


def test_originals_preserved_and_bad_inputs_rejected(tmp_path, images):
    store = Store(tmp_path / "state")
    record = import_object(store, "ngc 7000", list(images.values()))
    assert record["width"] == 128 and record["height"] == 192
    for role, path in record["assets"].items():
        assert store.path(path).read_bytes() == images[role].read_bytes()
    assert record["published"] is False
    with pytest.raises(ValueError, match="object_exists"):
        import_object(store, "NGC_7000", list(images.values()))
    for value in ["../NGC_7000", "NGC_7000/../", "NGC7000", "A_1.exe"]:
        with pytest.raises(ValueError):
            normalize_id(value)
    with pytest.raises(ValueError, match="invalid_path"):
        store.path("../escape")
    Image.new("RGB", (130, 192)).save(images["stars"])
    with pytest.raises(ValueError, match="dimension_mismatch"):
        validate_images(images)


def test_layer_selection_loops_and_real_h264(tmp_path, images):
    raw = {key: read_rgb(path) for key, path in images.items()}
    scene = Scene(raw, Parameters())
    assert scene.choice["source"] == "stars_laid"
    assert scene.choice["blend"] == "screen"
    for method in ["layered", "depth", "kenburns"]:
        current = Scene(raw, Parameters(method=method))
        np.testing.assert_allclose(current.frame(0), current.frame(1), atol=1e-5)
        assert np.max(np.abs(current.frame(.25) - current.frame(.75))) > .01
    target = tmp_path / "movie.mp4"
    stats = render_video(images, target, Parameters(duration=4, resolution=720))
    assert stats["frames"] == 96 and stats["width"] == 128
    assert target.stat().st_size > 1000
    import cv2
    cap = cv2.VideoCapture(str(target))
    try:
        assert cap.isOpened()
        assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 96
        assert cap.read()[0]
    finally:
        cap.release()


@pytest.mark.parametrize("raw", [{"method": []}, {"zoom": "nan"}, {"depth": 9}, {"fps": 24.5}, {"resolution": 9999}, {"pan_x": .2}, {"surprise": 1}, []])
def test_parameters_bounded(raw):
    with pytest.raises(ValueError, match="invalid_parameters"):
        Parameters.parse(raw)


def test_fits_provenance_and_location_privacy(tmp_path):
    path = tmp_path / "NGC_7000_final.fits"
    header = fits.Header({"DATE-OBS": "2026-11-09T19:06:24", "RA": 315.309984, "DEC": 44.230958, "SITELAT": 48.0, "SITELONG": 2.0, "EXPTIME": 10., "NCOMBINE": 520, "LIVETIME": 5200., "TELESCOP": "S50 Pro_serial"})
    fits.writeto(path, np.zeros((2, 2)), header)
    before = path.read_bytes()
    obs = read_observation(path)
    assert obs["integration"] == 5200
    assert obs["date_obs"].endswith("+00:00")
    assert obs["time_scale_assumed"]
    assert "date_end" not in obs
    assert obs["telescope"] == "S50 Pro"
    assert path.read_bytes() == before
    public = public_observation(obs)
    assert "latitude" not in public and "header" not in public


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "app-data", testing=True)
    yield app
    app.extensions["jobs"].shutdown()


def sign_in(client):
    token = client.get("/api/session").json["csrf"]
    headers = {"X-CSRF-Token": token}
    short = client.post("/api/setup", json={"password": "0123456789"}, headers=headers)
    assert short.status_code == 400 and short.json["error"] == "weak_password"
    response = client.post("/api/setup", json={"password": "0123456789a"}, headers=headers)
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["csrf"]}


def test_auth_csrf_host_and_upload_validation(app, images):
    client = app.test_client()
    assert client.get("/api/admin/objects").status_code == 401
    assert client.get("/api/session", base_url="http://evil.example").status_code == 400
    assert client.post("/api/setup", json={"password": "anything"}).status_code == 403
    headers = sign_in(client)
    assert client.get("/api/admin/objects").status_code == 200
    assert client.post("/api/admin/objects/NGC_7000/render", json={}, headers={**headers, "Origin": "https://attacker.example"}).status_code == 403
    assert client.post("/api/admin/objects/NGC_7000/render", json=[], headers=headers).status_code == 400
    response = client.post("/api/admin/objects", data={"identifier": "NGC_7000", "images": [(io.BytesIO(b"not a png"), "NGC_7000_final.png")]}, headers=headers)
    assert response.status_code == 400 and response.json["error"] == "four_images_required"
    assert client.get("/api/objects").json == {"objects": []}
    assert client.get("/").headers["Content-Security-Policy"].startswith("default-src 'self'")
    client.post("/api/logout", headers=headers)
    assert client.get("/api/admin/objects").status_code == 401


def test_jobs_publish_only_success_and_preserve_previous(tmp_path, images, monkeypatch):
    store = Store(tmp_path / "jobs-data")
    import_object(store, "NGC_7000", list(images.values()))
    queue = JobQueue(store)
    with pytest.raises(RuntimeError, match="already has a running"):
        JobQueue(store)
    def good_render(paths, target, params, progress):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"test encoded movie")
        return {"frames": 96}
    monkeypatch.setattr("astroweb.jobs.render_video", good_render)
    try:
        job = queue.submit("NGC_7000", {"duration": 4})
        queue.futures[job["id"]].result(timeout=5)
        successful = store.get("objects", "NGC_7000")
        assert successful["published"] and successful["video"]
        def bad_render(*args, **kwargs):
            raise RuntimeError("encode_failed")
        monkeypatch.setattr("astroweb.jobs.render_video", bad_render)
        failed = queue.submit("NGC_7000", {"duration": 4})
        queue.futures[failed["id"]].result(timeout=5)
        assert store.get("jobs", failed["id"])["status"] == "failed"
        assert store.get("objects", "NGC_7000")["video"] == successful["video"]
    finally:
        queue.shutdown()


def test_real_sky_tracks_match_astropy_reference():
    from astroweb.sky import build_sky
    from astropy.coordinates import AltAz, EarthLocation, SkyCoord
    from astropy.time import Time
    import astropy.units as u
    record = {"id": "NGC_7000", "observation": {"date_obs": "2026-11-09T19:06:24+00:00", "latitude": 48.0, "longitude": 2.0, "ra": 315.309984, "dec": 44.230958, "timezone": "Europe/Amsterdam"}}
    sky = build_sky(record)
    assert sky["evening"] == "2026-11-09"
    assert len(sky["stars"]) > 1000
    assert sky["location"] is None
    first = sky["samples"][0]
    expected = SkyCoord(315.309984 * u.deg, 44.230958 * u.deg).transform_to(AltAz(obstime=Time(first["time"], format="unix"), location=EarthLocation(lat=48.0*u.deg, lon=2.0*u.deg), pressure=0*u.hPa))
    assert abs(first["altitude"] - expected.alt.deg) < .001
    assert len(sky["positions"]) == len(sky["samples"])
    assert len(sky["positions"][0]) == len(sky["stars"])


def test_original_detail_at_zoom_target():
    # A stripe per source pixel disappears if the renderer first downsamples
    # the full photograph to the output resolution.
    image = np.zeros((1440, 960, 3), np.float32)
    image[:, 1::2, 0] = 1
    image[:, 480:, 1] = 1
    raw = {role: image for role in ("final", "starless", "stars", "stars_laid")}
    params = Parameters(method="kenburns", zoom=4, focus_x=.75, focus_y=.35,
                        resolution=720, pan_x=0, pan_y=0)
    scene = Scene(raw, params)
    close = scene.frame(.5)
    assert close.shape == (720, 480, 3)
    assert close[:, :, 1].mean() > .99
    assert close[:, :, 0].std() > .2
    np.testing.assert_allclose(scene.frame(0), scene.frame(1))


def test_versions_remain_private_until_selected(app, images, monkeypatch):
    store, queue = app.extensions["store"], app.extensions["jobs"]
    import_object(store, "NGC_7000", list(images.values()))
    def render(paths, target, params, progress):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(str(params.zoom).encode())
        return {"frames": 96}
    monkeypatch.setattr("astroweb.jobs.render_video", render)
    monkeypatch.setattr(queue, "ensure_preview", lambda path: None)
    ids = []
    for zoom in [1.08, 6]:
        job = queue.submit("NGC_7000", {"zoom": zoom})
        queue.futures[job["id"]].result(timeout=5)
        ids.append(job["id"])
    guest = app.test_client()
    admin = app.test_client()
    headers = sign_in(admin)
    prefix = "/api/admin/objects/NGC_7000/versions/"
    assert guest.get(prefix + ids[1] + "/movie").status_code == 401
    assert guest.get("/media/NGC_7000/movie").data == b"1.08"
    versions = admin.get("/api/admin/objects").json["objects"][0]["versions"]
    assert [v["selected"] for v in versions] == [False, True]
    assert versions[0]["params"]["zoom"] == 6
    assert admin.get(versions[0]["url"]).data == b"6.0"
    assert admin.put(prefix + ids[1] + "/select", headers=headers).status_code == 200
    assert guest.get("/media/NGC_7000/movie").data == b"6.0"
    assert "versions" not in guest.get("/api/objects").json["objects"][0]

    keep = store.get("objects", "NGC_7000")
    discarded = store.path(keep["versions"][0]["video"])
    preview = discarded.with_suffix(".preview.mp4")
    preview.write_bytes(b"test preview")
    assert guest.delete(prefix + ids[0], headers=headers).status_code == 403
    assert admin.delete(prefix + ids[0]).status_code == 403
    assert admin.delete(prefix + ids[1], headers=headers).json["error"] == "version_published"
    assert admin.delete(prefix + ids[0], headers=headers).json == {"ok": True, "cleanup_pending": False}
    assert not discarded.exists() and not preview.exists()
    assert admin.get(prefix + ids[0] + "/movie").status_code == 404
    assert guest.get("/media/NGC_7000/movie").data == b"6.0"
    assert len(store.get("objects", "NGC_7000")["versions"]) == 1


@pytest.mark.parametrize("orientation", ["portrait", "original"])
def test_landscape_render_orientation(orientation):
    image = np.zeros((128, 256, 3), np.float32)
    image[:, :128, 0] = 1
    image[:, 128:, 2] = 1
    raw = {role: image for role in ("final", "starless", "stars", "stars_laid")}
    scene = Scene(raw, Parameters(method="kenburns", orientation=orientation, pan_x=0, pan_y=0))
    frame = scene.frame(0)
    if orientation == "portrait":
        assert frame.shape == (256, 128, 3)
        assert frame[32, 64, 0] == 1 and frame[224, 64, 2] == 1
    else:
        assert frame.shape == (128, 256, 3)
        assert frame[64, 32, 0] == 1 and frame[64, 224, 2] == 1

def test_journey_field_sources_and_hammer_projection(tmp_path):
    from astroweb.journey import SOLUTIONS, geometry, hammer, fits_footprint
    from astropy.wcs import WCS
    from astropy.wcs.utils import pixel_to_skycoord

    store = Store(tmp_path)
    record = {"observation": {}}
    assert geometry(store, record) == {"kind": "missing"}
    record["observation"] = {"ra": 12, "dec": -3}
    assert geometry(store, record) == {"kind": "point", "center": [12, -3]}
    record["sha256"] = {"final": next(iter(SOLUTIONS))}
    result = geometry(store, record)
    assert result["kind"] == "gaia" and len(result["corners"]) == 4
    np.testing.assert_allclose(hammer(np.array([0, np.pi]), np.array([0, 0])), [[.5,.5],[0,.5]])

    # Test the actual on-disk FITS row convention against a vertically
    # flipped raster, including off-diagonal (rotated) WCS terms.
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [48,48]
    wcs.wcs.crval = [120,20]
    wcs.wcs.cd = [[-.001,.0005],[.0005,.001]]
    wcs.wcs.ctype = ["RA---TAN","DEC--TAN"]
    yy,xx = np.mgrid[:96,:96]
    data = np.uint8((xx*2+yy*5+xx*yy/72)%223)
    path = tmp_path / "field.fits"
    fits.writeto(path, data, header=wcs.to_header())
    poster = tmp_path / "field.png"
    Image.fromarray(data[::-1]).save(poster)
    corners = fits_footprint(path,poster,96,96)
    top_left = pixel_to_skycoord(-.5,95.5,wcs,origin=0)
    np.testing.assert_allclose(corners[0], [top_left.ra.deg,top_left.dec.deg], atol=1e-7)
    assert fits_footprint(path,poster,95,96) is None

def test_camera_keeps_footprints_in_frame():
    from astroweb.journey import SOLUTIONS, FRAMES, WIDTH, HEIGHT, field_projection, camera_at
    for solution in SOLUTIONS.values():
        _, points, _, _ = field_projection(solution)
        width, height = np.ptp(points, axis=0)
        end = min(WIDTH*.77/width, HEIGHT*.73/height)
        for t in np.linspace(0, 1, FRAMES):
            scale, offset = camera_at(t, points, WIDTH*.46, end)
            projected = points*scale + offset
            assert (projected > 20).all()
            assert (projected < [WIDTH-20, HEIGHT-20]).all()


def test_gaia_recovers_reflected_field_and_rejects_unrelated_stars():
    from astropy.wcs import WCS
    from astroweb.gaia import fit_field
    rng = np.random.default_rng(83)
    pixels = rng.uniform([0, 0], [1000, 800], (145, 2))
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [500, 400]
    wcs.wcs.crval = [359.9, 65]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.cd = [[.0004, .0003], [.0003, -.0004]]
    coords = wcs.pixel_to_world(*pixels.T)
    catalog = np.column_stack((coords.ra.deg, coords.dec.deg, np.linspace(6, 12, len(pixels))))
    result = fit_field(pixels+rng.normal(0, .12, pixels.shape), catalog, [359.9, 65], 1000, 800, (1, 3))
    assert result["verified"] >= 30 and result["median_arcsec"] < 1
    corners = wcs.pixel_to_world([-.5, 999.5, 999.5, -.5], [-.5, -.5, 799.5, 799.5])
    np.testing.assert_allclose(result["corners"], np.column_stack((corners.ra.deg, corners.dec.deg)), atol=.0002)
    unrelated = rng.uniform([0, 0], [1000, 800], pixels.shape)
    assert fit_field(unrelated, catalog, [359.9, 65], 1000, 800, (1, 3)) is None
