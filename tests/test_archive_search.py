import numpy as np
import pytest
import requests
from astropy.io import fits
from astropy.wcs import WCS

from astroweb import archive_search, hst_archive, hubble, skymap
from astroweb.jobs import JobQueue
from astroweb.store import Store


def capture():
    return {"id":"NGC_1300","metadata":{"target":"NGC 1300"},"width":640,"height":480,
            "sha256":{"final":"test"},"assets":{}, "versions":[], "video":None,
            "gaia":{"status":"solved","digest":"test","corners":[
                [359.7,.2],[.3,.2],[.3,-.2],[359.7,-.2]]}}


def row(region="POLYGON ICRS 359.9 .1 .1 .1 .1 -.1 359.9 -.1",target="NGC-1300"):
    return dict(obs_id="hst_15133_06_wfc3_uvis_f475w_idkv06",target_name=target,
                s_ra=0.,s_dec=0.,s_region=region,t_exptime=700.)


@pytest.mark.parametrize("region,target", [
    ("POLYGON 359.9 .1 .1 .1 .31 -.1 359.9 -.1","NGC1300"),
    ("","NGC1300"),("CIRCLE ICRS 0 0 .2","NGC1300"),
    ("POLYGON GALACTIC 1 1 2 1 2 2","NGC1300"),
    ("POLYGON 359.9 .1 .1 .1 .1 -.1 359.9 -.1","NGC13001"),
    ("POLYGON 359.9 .1 .1 .1 .1 -.1 359.9 -.1","ANY")])
def test_unproven_footprints_and_other_targets_are_rejected(region,target):
    rec=capture()
    assert archive_search.ranked_entries(None,rec,[row(region,target)],archive_search.target_names(rec))==[]


@pytest.mark.parametrize("skymap_hit",[False,True])
def test_upload_pipeline_searches_both_catalogues_and_saves_only_full_match(tmp_path,monkeypatch,skymap_hit):
    st=Store(tmp_path)
    rec=capture()
    st.put("objects",rec["id"],rec)
    photo = {"id":"skymap-b0001","digest":"test","center":[0.,0.]}
    if skymap_hit:
        path=skymap.image_file(st,"b0001","test")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"cached")
    monkeypatch.setattr(skymap,"lookup",lambda store,record: photo if skymap_hit else None)
    calls=[]
    def nasa(terms):
        calls.append("NASA")
        assert "NGC-1300" in terms
        raise requests.ConnectionError("test offline")
    def esa(terms):
        calls.append("ESA")
        return [row(),row(),row(target="NGC13001")]
    monkeypatch.setattr(archive_search,"nasa_rows",nasa)
    monkeypatch.setattr(archive_search,"esa_rows",esa)
    monkeypatch.setattr(hst_archive,"registered_cutout",lambda store,record,e: calls.append(e["id"]))
    queue=JobQueue(st,resume=False)
    try:
        queue.prepare_capture(rec["id"])
        queue.prepare_capture(rec["id"])
    finally:
        queue.shutdown()
    saved=st.get("objects",rec["id"])
    assert sorted(calls)==["ESA","NASA",row()["obs_id"]]
    destinations=hubble.fields(st,saved)
    if skymap_hit:
        preferred,option=destinations
        assert preferred==photo
    else:
        option,=destinations
    assert option["id"]==row()["obs_id"] and option["full_footprint"] and option["relation"]=="target"
    saved["gaia"]["corners"]=[[179.8,1],[180.2,1],[180.2,0],[179.8,0]]
    assert not hubble.fields(st,saved)


def test_no_archive_network_without_registration(tmp_path,monkeypatch):
    st=Store(tmp_path)
    rec=capture()
    rec["gaia"]={}
    rec["skymap"]={"target":"NGC_1300","option":None}
    st.put("objects",rec["id"],rec)
    monkeypatch.setattr(archive_search,"lookup",lambda *a: pytest.fail("unexpected archive lookup"))
    archive_search.discover(st,rec["id"])
    assert "hst_search" not in st.get("objects",rec["id"])


def test_partial_archive_match_leaves_skymap_first_and_only(tmp_path,monkeypatch):
    st=Store(tmp_path)
    rec=capture()
    photo={"id":"skymap-b0001","digest":"test","center":[0.,0.]}
    rec["skymap"]={"target":"NGC_1300","option":photo}
    path=skymap.image_file(st,"b0001","test")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"cached")
    st.put("objects",rec["id"],rec)
    monkeypatch.setattr(archive_search,"nasa_rows",lambda terms:[row(region="POLYGON 359.9 .1 .1 .1 .31 -.1 359.9 -.1")])
    monkeypatch.setattr(archive_search,"esa_rows",lambda terms:[])
    archive_search.discover(st,rec["id"])
    saved=st.get("objects",rec["id"])
    assert saved["hst_search"]["option"] is None
    assert hubble.fields(st,saved)==[photo]


def test_actual_fits_pixel_edges_must_fit_even_when_catalogue_polygon_fits(tmp_path,monkeypatch):
    st=Store(tmp_path);rec=capture()
    entry,=archive_search.ranked_entries(st,rec,[row()],archive_search.target_names(rec))
    monkeypatch.setattr(hst_archive,"SIZE",180)
    w=WCS(naxis=2);w.wcs.ctype=["RA---TAN","DEC--TAN"];w.wcs.crval=[.25,0]
    w.wcs.crpix=[90,90];w.wcs.cdelt=[-.001,.001]
    path=st.path("survey-cache/hst-archive/"+entry["id"]+".fits");path.parent.mkdir(parents=True)
    fits.writeto(path,np.ones((180,180),dtype="float32"),w.to_header())
    with pytest.raises(ValueError,match="hubble_no_field"):
        hst_archive.registered_cutout(st,rec,entry)
