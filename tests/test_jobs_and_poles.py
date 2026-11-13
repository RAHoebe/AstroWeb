from threading import Event

import astropy.units as u
import cv2
import numpy as np
from astropy.coordinates import SkyCoord

from astroweb.journey import CATALOG, panorama_pixels
from astroweb.polar import chart


def test_panorama_catalogue_registration():
    image=cv2.imread(str(CATALOG/"milky-way.jpg"),cv2.IMREAD_GRAYSCALE)
    h,w=image.shape
    # The galactic positions predict independent visible peaks on the photograph:
    # M31's nucleus, Mirach, Alpheratz, Sirius and a bright Pleiades member.
    for ra,dec in [(10.6847,41.269),(17.433,35.62),(2.0969,29.09),(101.287,-16.716),(56.871,24.105)]:
        g=SkyCoord(ra*u.deg,dec*u.deg).galactic
        x,y=panorama_pixels(g.l.radian,g.b.radian,w,h)
        ix,iy=round(float(x)),round(float(y))
        cut=image[iy-16:iy+17,ix-16:ix+17]
        smooth=cv2.GaussianBlur(cut,(0,0),1.5)
        _,maximum,_,pos=cv2.minMaxLoc(smooth)
        assert np.hypot(pos[0]-16,pos[1]-16)<10
        assert maximum>1.45*np.median(smooth)


def test_polar_both_hemispheres_and_missing_position():
    result=chart(None,{"id":"TEST_1","metadata":{"target":"TEST 1","name":{"en":"test","nl":"test"}},
                       "observation":{"ra":33,"dec":-55}})
    assert result["target"]["dec"]==-55
    assert {s[0] for s in result["stars"]} >= {104382,11767}
    assert chart(None,{"id":"TEST_2","metadata":{"target":"TEST 2","name":{}}})["target"] is None


def test_cancel_running_and_queued_jobs(tmp_path,monkeypatch):
    from astroweb.store import Store
    from astroweb.jobs import JobQueue
    store=Store(tmp_path)
    for ident in ("M_31","M_32"):
        store.put("objects",ident,{"id":ident,"metadata":{},"assets":{},"video":"old.mp4",
                                   "versions":[],"gaia":{"status":"solved"}})
    entered,finish=Event(),Event()
    def render(paths,target,params,progress):
        entered.set()
        assert finish.wait(5)
        progress(12)
        raise AssertionError("Cancelled render continued")
    monkeypatch.setattr("astroweb.jobs.render_video",render)
    q=JobQueue(store,resume=False)
    try:
        active=q.submit("M_31")
        assert entered.wait(5)
        queued=q.submit("M_32")
        assert q.cancel(queued["id"])["status"]=="cancelled"
        assert q.cancel(active["id"])["status"]=="cancelling"
        finish.set()
        q.futures[active["id"]].result(timeout=5)
        assert store.get("jobs",active["id"])["status"]=="cancelled"
        assert q.cancel(active["id"])["status"]=="cancelled"
        for ident in ("M_31","M_32"):
            assert store.get("objects",ident)["video"]=="old.mp4"
            assert not store.get("objects",ident)["versions"]
    finally:
        finish.set()
        q.shutdown()
