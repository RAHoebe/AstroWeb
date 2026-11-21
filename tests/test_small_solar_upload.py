import io
import json

import cv2
import numpy as np
import pytest
from astropy.io import fits
from PIL import Image

from astroweb.app import create_app
from astroweb.observation import read_observation
from astroweb.solar_detail import saturn_registration


STACK = "2026-11-20-180949-Saturn-RAW_Planet_50_final"


@pytest.mark.parametrize("with_fits",[False,True])
def test_saturn_preview_upload_and_render_preserve_original(tmp_path,monkeypatch,with_fits):
    app = create_app(tmp_path/"data",testing=True)
    client = app.test_client()
    store,queue = app.extensions["store"],app.extensions["jobs"]
    monkeypatch.setattr(queue,"prepare_capture",lambda *_:None)
    monkeypatch.setattr(queue,"prepare_journey",lambda *_:None)
    with client.session_transaction() as session:
        session.update(admin=True,csrf="test-small-solar")
    headers = {"X-CSRF-Token":"test-small-solar"}
    source = io.BytesIO()
    Image.new("RGB",(30,55),"khaki").save(source,format="PNG")
    original = source.getvalue()
    form = {"identifier":"SATURN","images":(io.BytesIO(original),STACK+".png"),
            "params":json.dumps({"duration":4,"resolution":720,"method":"kenburns","orientation":"original"})}
    if with_fits:
        source = io.BytesIO()
        header = fits.Header({"SWCREATE":"ASIVideoStack","DATE-OBS":"2026-11-21T09:31:07.292",
                              "DATE-END":"2019-03-07T07:50:41.022"})
        fits.writeto(source,np.zeros((55,30),dtype=np.float32),header)
        raw_fits = source.getvalue()
        form["fits"] = (io.BytesIO(raw_fits),"renamed.fits")
    try:
        preview = client.post("/api/admin/upload-poster",data={
            "identifier":"SATURN","image":(io.BytesIO(original),STACK+".png")},headers=headers)
        assert Image.open(io.BytesIO(preview.data)).size == (140,256)
        response = client.post("/api/admin/objects",data=form,headers=headers)
        assert response.status_code == 202,response.json
        job_id = response.json["job"]["id"]
        queue.futures[job_id].result(timeout=30)
        rec = store.get("objects","SATURN")
        assert rec["published"] and rec["render"]["height"] == 256
        assert store.path(rec["assets"]["final"]).read_bytes() == original
        obs = rec["observation"]
        assert obs["time_source"] == "filename"
        assert obs["date_obs"] == "2026-11-20T18:09:49+01:00"
        if with_fits:
            assert store.path(rec["fits"]).read_bytes() == raw_fits
            assert obs["header"]["DATE-END"] == "2019-03-07T07:50:41.022"
        assert client.get("/media/SATURN/final?download=1").data == original
        display = client.get("/media/SATURN/original-view")
        assert Image.open(io.BytesIO(display.data)).size == (140,256)
    finally:
        queue.shutdown()


def test_asi_rejects_unusable_filename_without_using_fits_clock(tmp_path):
    path = tmp_path/"2026-10-25-021500-Saturn-RAW_Planet_50_final.fits"
    header = fits.Header({"SWCREATE":"ASIVideoStack","DATE-OBS":"2026-11-21T09:31:07.292"})
    fits.writeto(path,np.zeros((5,5)),header)
    obs = read_observation(path)
    assert obs["date_obs"] is None  # Local 02:15 occurred twice.
    assert obs["time_source"] == "filename"
    assert obs["header"]["DATE-OBS"] == "2026-11-21T09:31:07.292"


def test_saturn_ring_alignment_measures_axis_and_rejects_round_disks():
    photo = np.zeros((256,140,3),dtype=np.uint8)
    center = np.array([74,135])
    cv2.circle(photo,tuple(center),16,(245,245,245),-1)
    overview = np.zeros((200,400,3),dtype=np.uint8)
    assert saturn_registration(photo,overview) is None
    cv2.ellipse(photo,tuple(center),(43,7),-33,0,360,(220,220,220),-1)
    transform = saturn_registration(photo,overview)
    assert transform is not None
    np.testing.assert_allclose((transform@np.array([.504*400,.507*200,1]))[:2],center,atol=1)
    angle = np.rad2deg(np.arctan2(transform[1,0],transform[0,0]))
    assert angle == pytest.approx(-33,abs=1.5)
