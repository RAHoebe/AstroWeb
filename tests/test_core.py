import io
import json

import numpy as np
import pytest
from astropy.io import fits
from PIL import Image

from astroweb.app import create_app
from astroweb.jobs import JobQueue
from astroweb.media import import_object, normalize_id, validate_images
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
    for value in ["../NGC_7000", "NGC_7000/../", "NGC??7000", "A_1.exe"]:
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


@pytest.mark.parametrize("kind,with_fits",[("startrails",False),("milkyway",True)])
def test_landscape_upload_and_rerender(app,images,monkeypatch,kind,with_fits):
    client=app.test_client();headers=sign_in(client);store=app.extensions["store"];queue=app.extensions["jobs"]
    def no_catalogue(*args):
        pytest.fail("landscape reached a catalogue lookup")
    monkeypatch.setattr("astroweb.skymap.discover",no_catalogue)
    def upload():
        form={"capture_kind":kind,"title":"Night at the lake","images":(io.BytesIO(images["final"].read_bytes()),"landscape.png"),
              "params":json.dumps({"duration":4,"resolution":720})}
        if with_fits:
            data=io.BytesIO()
            fits.PrimaryHDU(header=fits.Header({"OBJECT":"M 31","DATE-OBS":"2026-09-01T20:30:00"})).writeto(data)
            data.seek(0);form["fits"]=(data,"observing-night.fits")
        reply=client.post("/api/admin/objects",headers=headers,data=form)
        assert reply.status_code==202,reply.json
        ident=reply.json["object"]["id"];job=reply.json["job"]["id"]
        queue.futures[job].result(timeout=30)
        rec=store.get("objects",ident)
        assert rec["published"] and rec["capture_kind"]==kind
        assert rec["metadata"]["name"]["nl"]=="Night at the lake"
        assert rec["params"]["orientation"]=="original" and rec["params"]["method"]=="kenburns"
        assert store.path(rec["assets"]["final"]).read_bytes()==images["final"].read_bytes()
        if with_fits:
            assert rec["observation"]["header"]["OBJECT"]=="M 31"
        assert "body" not in rec and "hst_search" not in rec
        detail=client.get("/api/objects/"+ident).json
        assert detail["capture_kind"]==kind and not detail["hubble_available"]
        assert detail["video"] and detail["final"]
        return ident
    first=upload();second=upload()
    assert first!=second and len(client.get("/api/objects").json["objects"])==2
    result=client.post("/api/admin/objects/"+first+"/render",headers=headers,json={"method":"layered","duration":4,"resolution":720})
    assert result.status_code==202
    queue.futures[result.json["job"]["id"]].result(timeout=30)
    assert len(store.get("objects",first)["versions"])==2


def test_panorama_pins_permissions_validation_and_renamed_targets(app, images):
    store=app.extensions["store"]
    rec=import_object(store,"",[images["final"]],nightscape="milkyway")
    target=import_object(store,"NGC_7000",images.values())
    store.update("objects",rec["id"],published=True)
    client=app.test_client()
    route="/api/admin/objects/"+rec["id"]+"/panorama"
    config={"wrap":True,"pins":[{"target":target["id"],"x":.25,"y":.62}]}
    assert client.put(route,json=config).status_code in (401,403)
    headers=sign_in(client)
    assert client.put(route,headers=headers,json=config).status_code==200
    scene="/api/panorama?capture="+rec["id"]
    assert client.get(scene).json["pins"][0]["target"]==target["id"]
    guest=app.test_client()
    assert guest.get(scene).json["pins"]==[]
    assert guest.get("/api/panorama?capture="+target["id"]).status_code==404
    for pin in [dict(target=target["id"],x=1.01,y=.5),dict(target="unknown",x=.5,y=.5),
                dict(target=rec["id"],x=.5,y=.5)]:
        assert client.put(route,headers=headers,json={"wrap":False,"pins":[pin]}).status_code==400
    store.update("objects",target["id"],published=True)
    renamed=store.rename_object(target["id"],"IC_1396",target["metadata"])
    assert guest.get(scene).json["pins"][0]["target"]==renamed["id"]
    assert guest.get(scene).json["wrap"]
    assert client.put(route,headers=headers,json={"wrap":False,"pins":[]}).status_code==200
    assert guest.get(scene).json["pins"]==[]


def test_panorama_uses_original_corner_order_for_each_published_capture(app, images):
    from astropy.coordinates import SkyCoord
    from astroweb.panorama import sky_pixels
    store=app.extensions["store"]
    corners=[[12,41],[10,41],[10,40],[12,40]]
    records=[import_object(store,"NGC_7000",images.values(),repeat=True,capture_date=day)
             for day in ("2026-09-12","2026-11-09")]
    for r in records:
        store.update("objects",r["id"],published=True,gaia={"status":"solved",
                     "digest":r["sha256"]["final"],"corners":corners})
    pins=app.test_client().get("/api/panorama").json["pins"]
    assert [pin["detail"] for pin in pins]==["2026-11-09","2026-09-12"]
    for pin in pins:
        np.testing.assert_allclose(pin["corners"],sky_pixels(SkyCoord(*np.array(corners).T,unit="deg")))
    store.update("objects",records[0]["id"],gaia={},observation={"ra":11,"dec":40.5})
    points=app.test_client().get("/api/panorama").json["pins"]
    assert "corners" not in next(p for p in points if p["target"]==records[0]["id"])


def test_gallery_portrait_poster_rotates_landscape_source(app, images):
    store=app.extensions["store"]
    for path in images.values():
        with Image.open(path) as image:
            rotated=image.transpose(Image.Transpose.ROTATE_90)
        rotated.save(path)
    record=import_object(store,"NGC_7000",images.values())
    store.update("objects",record["id"],published=True)
    client=app.test_client()
    original=client.get("/media/NGC_7000/poster")
    portrait=client.get("/media/NGC_7000/poster?rotation=90")
    assert original.status_code==portrait.status_code==200
    assert portrait.mimetype=="image/jpeg"
    with Image.open(io.BytesIO(original.data)) as source, Image.open(io.BytesIO(portrait.data)) as result:
        expected=source.transpose(Image.Transpose.ROTATE_270)
        assert result.size==expected.size==(128,192)
        assert np.mean(np.abs(np.asarray(result,dtype=float)-np.asarray(expected)))<2


def sign_in(client):
    token = client.get("/api/session").json["csrf"]
    headers = {"X-CSRF-Token": token}
    short = client.post("/api/setup", json={"password": "0123456789"}, headers=headers)
    assert short.status_code == 400 and short.json["error"] == "weak_password"
    response = client.post("/api/setup", json={"password": "0123456789a"}, headers=headers)
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["csrf"]}


def test_studio_can_render_and_rerender_with_only_one_star_layer(app,images,monkeypatch):
    client=app.test_client()
    headers=sign_in(client)
    queue=app.extensions["jobs"]
    store=app.extensions["store"]
    monkeypatch.setattr(queue,"prepare_capture",lambda *_:None)
    monkeypatch.setattr(queue,"prepare_journey",lambda *_:None)
    files=[(io.BytesIO(images[role].read_bytes()),images[role].name) for role in ("final","starless","stars")]
    params=dict(duration=4,resolution=720,star_source="stars_laid")
    reply=client.post("/api/admin/objects",data=dict(identifier="NGC_7000",images=files,params=json.dumps(params)),headers=headers)
    assert reply.status_code==202,reply.json
    queue.futures[reply.json["job"]["id"]].result(timeout=30)
    record=store.get("objects","NGC_7000")
    assert set(record["assets"])=={"final","starless","stars"}
    assert record["render"]["choice"]["source"]=="stars" and record["params"]["star_source"]=="stars"
    assert all(store.path(path).read_bytes()==images[role].read_bytes() for role,path in record["assets"].items())
    again=client.post("/api/admin/objects/NGC_7000/render",json=params,headers=headers)
    assert again.status_code==202
    queue.futures[again.json["job"]["id"]].result(timeout=30)
    assert len(store.get("objects","NGC_7000")["versions"])==2

def test_studio_recognises_crescent_and_uses_verified_fits_for_draft_zoom(app, monkeypatch):
    from astropy.wcs import WCS
    from astroweb.metadata import initial_metadata

    monkeypatch.setenv("ASTROWEB_OFFLINE","1")
    client=app.test_client()
    headers=sign_in(client)
    picked=client.post("/api/admin/upload-identity",json={"names":["C_27_final.png"],"object":""},headers=headers).json
    assert picked["identifier"]=="C_27"
    assert picked["target"]=={"id":"NGC_6888","known":True,"name":{"nl":"Sikkelnevel","en":"Crescent Nebula"}}

    store=app.extensions["store"]
    legacy=initial_metadata("NGC_6888")
    legacy.update(translation="curated",summary={"nl":"Catalogusidentificatie: HD 192163.","en":"Catalogue identification: HD 192163."},
                  external={"provider":"CDS/SIMBAD","title":"HD 192163"},sources=[])
    store.put("objects","NGC_6888",dict(id="NGC_6888",published=False,metadata=legacy))
    info=client.post("/api/admin/objects/NGC_6888/metadata/refresh",json={},headers=headers)
    assert info.status_code==200
    saved=store.get("objects","NGC_6888")["metadata"]
    assert "WR 136" in saved["summary"]["nl"] and saved["external"]["provider"]=="NASA Science"
    assert any(source["url"]=="https://nl.wikipedia.org/wiki/NGC_6888" for source in saved["sources"])

    y,x=np.mgrid[:192,:256]
    image=np.asarray(220*np.exp(-((x-55)**2+(y-27)**2)/500)+
                     90*np.exp(-((x-190)**2+(y-130)**2)/400)+x/9+y/19,dtype=np.uint8)
    preview=io.BytesIO()
    Image.fromarray(image).save(preview,"JPEG",quality=95)
    wcs=WCS(naxis=2)
    wcs.wcs.ctype=["RA---TAN","DEC--TAN"]
    wcs.wcs.crval=[303.027292,38.354944]
    wcs.wcs.crpix=[91,121]
    wcs.wcs.cd=[[-.001,.0002],[.0002,.001]]
    fits_data=io.BytesIO()
    fits.PrimaryHDU(data=image[::-1].copy(),header=wcs.to_header()).writeto(fits_data)

    def upload(**parts):
        return client.post("/api/admin/upload-autozoom",data={
            "count":"4","identifier":"NGC_6888","preview":(io.BytesIO(preview.getvalue()),"preview.jpg"),**parts
        },headers=headers)

    route=upload(fits=(io.BytesIO(fits_data.getvalue()),"C_27_final.fits"))
    assert route.status_code==200,route.json
    assert route.json["alignment"]=="wcs"
    point=route.json["points"][0]
    assert point["kind"]=="catalog" and point["label"]["nl"]=="Sikkelnevel"
    assert point["x"]==pytest.approx(90.5/256,abs=1e-5)
    assert point["y"]==pytest.approx(71.5/192,abs=1e-5)
    fallback=upload().json
    assert fallback["alignment"]=="missing"
    assert fallback["points"] and all(p["kind"]=="structure" for p in fallback["points"])


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


@pytest.mark.parametrize("header_id, expected", [
    ("M 31", "M_31"), ("Andromeda Galaxy", "M_31"), ("C 20", "NGC_7000"),
    ("", "NGC_7000"), ("unknown science target", "NGC_7000"),
])
def test_upload_identifies_capture_from_fits_before_prefix(app, images, monkeypatch, header_id, expected):
    client = app.test_client()
    headers = sign_in(client)
    monkeypatch.setattr(app.extensions["jobs"], "submit", lambda *args: {"id": "test"})
    data = io.BytesIO()
    fits.PrimaryHDU(header=fits.Header({"OBJECT": header_id})).writeto(data)
    data.seek(0)
    files = [(io.BytesIO(p.read_bytes()), p.name) for p in images.values()]
    preview = client.post("/api/admin/upload-identity", json={
        "object": header_id, "names": [name for _, name in files]}, headers=headers).json
    assert preview["source"] == ("fits" if header_id in ("M 31","Andromeda Galaxy","C 20") else "prefix")
    response = client.post("/api/admin/objects", data={
        "identifier": "IC_1396", "images": files, "fits": (data, "NGC_7000_final.fits")
    }, headers=headers)
    assert response.status_code == 202, response.json
    assert response.json["object"]["id"] == expected
    assert app.extensions["store"].get("objects", expected)["observation"]["header"]["OBJECT"] == header_id


def test_fits_upload_validates_common_export_family(tmp_path, images):
    store = Store(tmp_path / "captures")
    paths = [p.rename(p.with_name("mosaic_" + role + ".png")) for role, p in images.items()]
    record = import_object(store,"M_31",paths,allow_export_prefix=True)
    assert set(record["assets"]) == set(images)
    paths[0] = paths[0].rename(paths[0].with_name("other_final.png"))
    with pytest.raises(ValueError,match="invalid_filename"):
        import_object(store,"M_31",paths,allow_export_prefix=True,repeat=True)


@pytest.mark.parametrize("failure",[True,False])
def test_journey_prepared_after_alignment_before_publication(tmp_path, images, monkeypatch, failure):
    store = Store(tmp_path / "lib")
    record = import_object(store, "NGC_7000", images.values())
    jobs = JobQueue(store,resume=False)
    calls = []
    monkeypatch.setattr("astroweb.skymap.catalogue",lambda store: [])
    def fake_render(paths, target, params, progress):
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(b"capture")
        return {"frames":96}
    def fake_journey(current, capture, field, progress):
        assert not capture["published"]
        assert capture["skymap"]["target"] == "NGC_7000"
        calls.append(field)
        progress(.5)
        if failure:
            raise OSError("test")
    monkeypatch.setattr(jobs,"align",lambda id: store.update("objects",id,observation={"ra":12,"dec":8}))
    monkeypatch.setattr(jobs,"ensure_preview",lambda path: None)
    monkeypatch.setattr("astroweb.jobs.render_video",fake_render)
    monkeypatch.setattr("astroweb.journey.movie",fake_journey)
    try:
        job = jobs.submit(record["id"])
        jobs.futures[job["id"]].result(timeout=10)
        assert calls == [{"kind":"point","center":[12,8]}]
        assert store.get("jobs",job["id"])["status"] == "completed"
        assert store.get("objects",record["id"])["published"]
    finally:
        jobs.shutdown()


def test_jobs_publish_only_success_and_preserve_previous(tmp_path, images, monkeypatch):
    monkeypatch.setattr("astroweb.skymap.catalogue",lambda store: [])
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


def test_latest_version_is_published_and_can_be_reselected(app, images, monkeypatch):
    monkeypatch.setattr("astroweb.skymap.catalogue",lambda store: [])
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
    assert guest.get("/media/NGC_7000/movie").data == b"6.0"
    versions = admin.get("/api/admin/objects").json["objects"][0]["versions"]
    assert [v["selected"] for v in versions] == [True, False]
    assert versions[0]["params"]["zoom"] == 6
    assert admin.get(versions[0]["url"]).data == b"6.0"
    assert admin.put(prefix + ids[0] + "/select", headers=headers).status_code == 200
    assert guest.get("/media/NGC_7000/movie").data == b"1.08"
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

def test_gzip_negotiation_of_large_json(app):
    import gzip
    store = app.extensions["store"]
    store.put("objects","M_31",{"id":"M_31","width":200,"height":120,"assets":{"final":"M_31.png"},
              "params":{},"render":None,"metadata":{"description":"x"*24000},"video":None,
              "published":True,"created_at":"2026-01-01"})
    client=app.test_client()
    plain=client.get("/api/objects",headers={"Accept-Encoding":"gzip;q=0"})
    compressed=client.get("/api/objects",headers={"Accept-Encoding":"gzip"})
    assert plain.status_code == compressed.status_code == 200
    assert "Content-Encoding" not in plain.headers
    assert compressed.headers["Content-Encoding"] == "gzip"
    assert gzip.decompress(compressed.data) == plain.data
    assert "Accept-Encoding" in plain.vary and "Accept-Encoding" in compressed.vary


def test_changing_catalogue_target_clears_old_source_links(app, images):
    from astroweb.metadata import initial_metadata
    store=app.extensions["store"]
    record=import_object(store,"NGC_7000",list(images.values()))
    meta=record["metadata"]
    meta["external"]={"provider":"test","url":"https://example.org/old"}
    store.update("objects",record["id"],metadata=meta)
    client=app.test_client()
    headers=sign_in(client)
    url="/api/admin/objects/NGC_7000/metadata"
    response=client.put(url,json=meta,headers=headers)
    assert response.status_code==200
    assert store.get("objects",record["id"])["metadata"]["external"]==meta["external"]
    assert store.get("objects",record["id"])["metadata"]["aliases"]==meta["aliases"]
    updated=initial_metadata("M_31")
    assert client.put(url,json=updated,headers=headers).status_code==200
    saved=store.get("objects",record["id"])["metadata"]
    assert not saved["sources"] and "external" not in saved
