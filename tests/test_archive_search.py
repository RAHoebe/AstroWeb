import numpy as np
import pytest
import requests
from astropy.io import fits
from astropy.wcs import WCS

from astroweb import archive_search, hst_archive, hubble, skymap
from astroweb.jobs import JobQueue
from astroweb.store import Store


@pytest.fixture
def offline_spatial_catalogue(monkeypatch):
    monkeypatch.setattr(archive_search, "spatial_rows", lambda corners: [])
    monkeypatch.setattr(archive_search, "mast_spatial_rows", lambda corners: [])


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
])
def test_unproven_footprints_are_rejected(region,target):
    rec=capture()
    assert archive_search.ranked_entries(None,rec,[row(region,target)],archive_search.target_names(rec))==[]


@pytest.mark.parametrize("skymap_hit",[False,True])
def test_upload_pipeline_searches_both_catalogues_and_saves_only_full_match(tmp_path,monkeypatch,offline_spatial_catalogue,skymap_hit):
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
    def cutout(store,record,e):
        calls.append(e["id"])
        return None,np.eye(3),None
    monkeypatch.setattr(hst_archive,"registered_cutout",cutout)
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


def test_partial_archive_match_leaves_skymap_first_and_only(tmp_path,monkeypatch,offline_spatial_catalogue):
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
    assert saved["hst_search"]["options"] == []
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

def test_spatial_selection_checks_both_footprints_and_upgrades_legacy_result(tmp_path,monkeypatch,offline_spatial_catalogue):
    rec=capture()
    st=Store(tmp_path)
    def candidate(i,x,w=1.):
        return {"id":str(i),"footprint":[[x,0],[x+w,0],[x+w,w],[x,w]]}
    rows=[candidate(1,0),candidate(2,.5,.4),candidate(3,2),candidate(4,4),candidate(5,6)]
    prior={"id":"1","full_footprint":True}
    rec.update(skymap={"target":"NGC_1300"},hst_search={"field":archive_search.field_key(st,rec),"option":prior})
    st.put("objects",rec["id"],rec)
    assert hubble.fields(st,rec)==[prior]
    monkeypatch.setattr(archive_search,"nasa_rows",lambda terms: [])
    monkeypatch.setattr(archive_search,"esa_rows",lambda terms: [])
    monkeypatch.setattr(archive_search,"ranked_entries",lambda *args:[rows[1],rows[0],*rows[2:]])
    def cutout(store,record,entry):
        assert entry["id"]!="2"  # smaller chip inside the preferred field
        if entry["id"]=="4":
            raise ValueError("hubble_no_field")
        m=np.eye(3)
        if entry["id"]=="5":m[0,2]=hst_archive.SIZE
        return None,m,None
    monkeypatch.setattr(hst_archive,"registered_cutout",cutout)
    archive_search.discover(st,rec["id"])
    assert [o["id"] for o in hubble.fields(st,st.get("objects",rec["id"]))]==["1","5"]


def test_coordinate_only_and_named_regions_keep_distinct_relations(tmp_path,monkeypatch,offline_spatial_catalogue):
    st=Store(tmp_path)
    rec=capture()
    rec["metadata"]["target"]="Caldwell 20"
    calls=[]
    def nasa(terms):
        assert "V1057-CYG" in terms
        return []
    def spatial(corners):
        calls.append(corners)
        return [row(target="V1057-CYG")]
    monkeypatch.setattr(archive_search,"nasa_rows",nasa)
    monkeypatch.setattr(archive_search,"esa_rows",lambda terms:[])
    monkeypatch.setattr(archive_search,"spatial_rows",spatial)
    monkeypatch.setattr(hst_archive,"registered_cutout",lambda *args:(None,np.eye(3),None))
    region,=archive_search.lookup(st,rec)
    assert region["relation"]=="region" and calls==[rec["gaia"]["corners"]]
    for name in ("PN-G098.2+04.9","ANY","NGC13001"):
        field,=archive_search.ranked_entries(st,rec,[row(target=name)],archive_search.target_names(rec))
        assert field["relation"]=="field"


def test_spatial_query_wraps_ra_and_checks_declination(monkeypatch):
    queries=[]
    monkeypatch.setattr(archive_search,"esa_search",queries.append)
    archive_search.spatial_rows(capture()["gaia"]["corners"])
    import re
    ra,dec,radius=map(float,re.search(r"CIRCLE\('ICRS',([^,]+),([^,]+),([^)]*)\)",queries[0]).groups())
    assert min(ra,360-ra)<.01 and abs(dec)<.01 and .35<radius<.38


def test_mast_coordinate_query_spans_both_sides_of_ra_zero(monkeypatch):
    monkeypatch.setattr(archive_search,"mast_search",lambda filters:filters)
    filters={item["paramName"]:item["values"] for item in archive_search.mast_spatial_rows(capture()["gaia"]["corners"])}
    assert filters["s_ra"][0]["max"]==360 and filters["s_ra"][1]["min"]==0
    assert -.38<filters["s_dec"][0]["min"]<-.35
