import io
import time

import numpy as np
import requests
from PIL import Image

from astroweb import hubble, skymap
from astroweb.store import Store


def entry(ident, name):
    return {"cm_id": ident, "name": name, "longitude": -121.2, "latitude": -21.5,
            "url": "https://science.nasa.gov/mission/hubble/"}


def test_exact_object_and_aliases_only():
    rows = [entry("M001","Crab Nebula (M1)"), entry("M101","Pinwheel Galaxy (M101)"),
            entry("M031","Andromeda Galaxy (M31)"), entry("B0123","Galaxy NGC 2841")]
    rows[2]["description"] = "Also visible is its companion M32."
    for query, expected in [("NGC 224","M031"), ("M1","M001"), ("M101","M101"),
                            ("NGC 2841","B0123"), ("M32",None), ("B123",None)]:
        result = skymap.candidates({"metadata":{"target":query}},rows)
        assert [r["cm_id"] for r in result] == ([expected] if expected else [])


def test_preferred_photo_is_downloaded_and_playable_offline(tmp_path, monkeypatch):
    st = Store(tmp_path)
    rec = {"id":"NGC_224","metadata":{"target":"NGC 224"},"width":320,"height":160,
           "sha256":{"final":"sha"},"assets":{"final":"photo.jpg"}}
    st.put("objects",rec["id"],rec)
    Image.new("RGB",(320,160),"navy").save(st.path("photo.jpg"))
    data = io.BytesIO()
    Image.new("RGB",(160,260),"red").save(data,"JPEG")
    urls = []
    def get(url, **kwargs):
        urls.append(url)
        if url.endswith("data.json"):
            reply = requests.Response()
            reply.status_code = 200
            import json
            reply._content = json.dumps([entry("M031","Andromeda Galaxy (M31)")]).encode()
        else:
            reply = requests.Response()
            reply.status_code = 404 if "/full_size_image/" in url else 200
            reply.raw = io.BytesIO(data.getvalue())
        return reply
    monkeypatch.setattr(skymap.requests,"get",get)
    skymap.discover(st,rec["id"])
    rec = st.get("objects",rec["id"])
    assert len(urls)==3 and urls[-1].endswith("/lightbox_images/m031.jpg")
    monkeypatch.setattr(skymap.requests,"get",lambda *a,**kw: (_ for _ in ()).throw(AssertionError("network")))
    skymap.discover(st,rec["id"])
    assert hubble.eligible(rec)
    option, = hubble.fields(st,rec)
    assert option["title"]=="Andromeda Galaxy (M31)" and option["relation"]=="target"
    assert skymap.focus_point(st,rec,option)==[]
    path = hubble.movie(st,rec,option["id"])
    assert path.stat().st_size>1000
    import cv2
    video = cv2.VideoCapture(str(path))
    try:
        video.set(cv2.CAP_PROP_POS_FRAMES,280)
        ok, frame = video.read()
        assert ok and frame[360,640,2]>220 and np.max(frame[360,0])<15
    finally:
        video.release()
    assert hubble.movie(st,rec,option["id"])==path
    assert skymap.cached_option(st,{**rec,"metadata":{"target":"M 32"}}) is None
    rec["gaia"]={"status":"solved","digest":"sha","corners":[[180,0],[181,0],[181,1],[180,1]]}
    assert skymap.focus_point(st,rec,option) is None


def test_nasa_failure_uses_old_index_or_existing_destination(tmp_path,monkeypatch):
    store=Store(tmp_path)
    obj={"id":"M_31","metadata":{"target":"M31"}}
    store.put("objects","M_31",obj)
    def offline(*args,**kwargs):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(skymap.requests,"get",offline)
    skymap.discover(store,"M_31")
    state=store.get("objects","M_31")["skymap"]
    assert state["option"] is None and state["retry"]>time.time()
    rows=[entry("M031","Andromeda Galaxy (M31)")]
    store.put("settings","hubble_skymap",{"rows":rows,"checked":0})
    assert skymap.catalogue(store)==rows


def test_ic349_uses_its_calibrated_footprint_instead_of_m45_overview_position(tmp_path):
    store=Store(tmp_path)
    ident,digest=skymap.MEROPE_PLATE
    rec={"id":"M_45","metadata":{"target":"M 45"},"width":1000,"height":1600,"sha256":{"final":"m45"},
         "gaia":{"status":"solved","digest":"m45","corners":[[56.2,24.55],[57.5,24.55],[57.5,23.5],[56.2,23.5]]},
         "skymap":{"target":"M_45","option":dict(id=ident,digest=digest,center=[57.7,24.3])}}
    path=skymap.image_file(store,"m045",digest)
    path.parent.mkdir(parents=True)
    Image.new("RGB",(2116,2376),"navy").save(path)
    option=skymap.cached_option(store,rec)
    assert option["alignment"]=="merope-wfpc2"
    assert skymap.merope_journey(store,rec)==ident
    assert skymap.focus_point(store,rec,option) is not None
    assert skymap.image_registration(store,rec,option).shape==(3,3)
    rec["gaia"]["corners"]=[[56.2,24.55],[57.5,24.55],[57.5,24.05],[56.2,24.05]]
    assert skymap.merope_journey(store,rec) is None
    assert skymap.focus_point(store,rec,option) is None
