import hashlib

import cv2
import numpy as np
import pytest
import requests
from astropy.io import fits
from astropy.wcs import WCS

from astroweb import archive_search, hubble, mission_archive as missions, skymap
from astroweb.jobs import JobQueue
from astroweb.store import Store


def capture():
    return {"id":"NGC_1300", "metadata":{"target":"NGC 1300"}, "width":640, "height":480,
            "sha256":{"final":"test"}, "assets":{}, "versions":[], "video":None,
            "gaia":{"status":"solved", "digest":"test", "corners":[
                [359.7,.2],[.3,.2],[.3,-.2],[359.7,-.2]]}}


def entry(provider="euclid"):
    return dict(id=provider+"-"+"a"*24, provider=provider, ra=0., dec=0.,
                radius=.01, title="Named detail", filter="VIS", credit="ESA / Euclid", full_footprint=True)


def science_file(store, item, centre=0., science=False):
    wcs=WCS(naxis=2);wcs.wcs.ctype=["RA---TAN","DEC--TAN"]
    wcs.wcs.crval=[centre,0.];wcs.wcs.crpix=[100.5,80.5];wcs.wcs.cdelt=[-.001,.001]
    y,x=np.mgrid[:160,:200]
    data=(10+x/100+y/150+30*np.exp(-((x-100)**2+(y-80)**2)/200)).astype("float32")
    path=missions.image_file(store,item);path.parent.mkdir(parents=True,exist_ok=True)
    if science:
        fits.HDUList([fits.PrimaryHDU(),fits.ImageHDU(data,wcs.to_header(),name="SCI")]).writeto(path)
    else:
        fits.writeto(path,data,wcs.to_header())
    return path


@pytest.mark.parametrize("provider,science",[("euclid",False),("jwst",True)])
def test_actual_fits_registration_parity_and_boundary(tmp_path,provider,science,monkeypatch):
    store=Store(tmp_path);record=capture();item=entry(provider)
    path=science_file(store,item,science=science)
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setenv("ASTROWEB_OFFLINE","1")
    image,matrix,focus=missions.registered_cutout(store,record,item)
    assert image.shape == (160,200,3)
    np.testing.assert_allclose(focus,[99.5,79.5],atol=.001)
    mapped=cv2.perspectiveTransform(np.float64([[focus]]),matrix)[0,0]
    np.testing.assert_allclose(mapped,[319.5,239.5],atol=.1)
    # FITS south is at the top of the displayed raster after the explicit flip.
    assert matrix[1,1]>0
    assert hashlib.sha256(path.read_bytes()).hexdigest()==checksum
    path.unlink();science_file(store,item,centre=.27,science=science)
    with pytest.raises(ValueError,match="hubble_no_field"):
        missions.registered_cutout(store,record,item)


def test_independent_provider_failures_preserve_hst_priority_and_cached_success(tmp_path,monkeypatch):
    store=Store(tmp_path);record=capture()
    signature=archive_search.field_key(store,record)
    hst=dict(id="hst-old",filter="F606W",relation="target")
    record["hst_search"]={"field":signature,"options":[hst]}
    preferred=dict(id="skymap-b0001",digest="test",center=[0.,0.])
    record["skymap"]={"target":skymap.target_key(record),"option":preferred}
    path=skymap.image_file(store,"b0001","test");path.parent.mkdir(parents=True);path.write_bytes(b"cached")
    store.put("objects",record["id"],record)
    calls=[]
    def lookup(store,record,provider):
        calls.append(provider)
        if provider=="jwst":
            raise requests.ConnectionError("unavailable")
        return [entry()]
    monkeypatch.setattr(missions,"lookup",lookup)
    missions.discover(store,record["id"])
    missions.discover(store,record["id"])
    saved=store.get("objects",record["id"])
    assert calls==["euclid","jwst"]
    assert hubble.fields(store,saved,local_only=True)==[preferred,hst,entry()]
    monkeypatch.setattr(missions,"lookup",lambda *args: (_ for _ in ()).throw(requests.ConnectionError("offline")))
    missions.discover(store,record["id"],force=True)
    assert missions.cached_options(store,store.get("objects",record["id"]))==[entry()]
    saved["metadata"]["target"]="M 31"
    assert missions.cached_options(store,saved)==[]


def test_full_upload_pipeline_still_searches_extra_providers_after_hst_failure(tmp_path,monkeypatch):
    store=Store(tmp_path);record=capture();store.put("objects",record["id"],record)
    calls=[]
    monkeypatch.setattr(JobQueue,"align",lambda *args:None)
    monkeypatch.setattr(skymap,"discover",lambda *args:None)
    monkeypatch.setattr(archive_search,"discover",lambda *args: (_ for _ in ()).throw(ValueError("HST unavailable")))
    monkeypatch.setattr(missions,"lookup",lambda store,record,provider: calls.append(provider) or [])
    queue=JobQueue(store,resume=False)
    try:
        queue.prepare_capture(record["id"])
    finally:
        queue.shutdown()
    assert calls==["euclid","jwst"]


def test_no_network_for_unregistered_solar_or_panorama_uploads(tmp_path,monkeypatch):
    store=Store(tmp_path)
    monkeypatch.setattr(missions,"lookup",lambda *args:pytest.fail("unexpected network"))
    for extra in ({"gaia":{}},{"body":"sun"},{"capture_kind":"milkyway"}):
        record=capture();record.update(extra);store.put("objects",record["id"],record)
        missions.discover(store,record["id"])
        assert "mission_search" not in store.get("objects",record["id"])


def test_offline_tap_checks_before_constructing_remote_client(monkeypatch):
    monkeypatch.setenv("ASTROWEB_OFFLINE","1")
    with pytest.raises(requests.ConnectionError,match="offline"):
        missions.euclid_rows(capture()["gaia"]["corners"])


def test_oversized_stream_is_rejected_and_no_partial_product_left(tmp_path,monkeypatch):
    store=Store(tmp_path);item=entry("jwst")
    item["data_uri"]="mast:JWST/product/jw12345-o001_t001_nircam_f200w_i2d.fits"
    class Reply:
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,*args):yield b"SIMPLE"+b" "*500
    monkeypatch.setattr(missions,"MAX_BYTES",100)
    monkeypatch.setattr(missions.external_http,"get",lambda *args,**kwargs:Reply())
    with pytest.raises(ValueError,match="archive_product_too_large"):
        missions.download(store,item)
    assert not list(store.path("survey-cache/mission-archive").iterdir())


def test_euclid_coverage_handles_ra_wrap():
    poly=archive_search.polygon("POLYGON ICRS 359.9 .1 .1 .1 .1 -.1 359.9 -.1")
    assert missions.contains(poly,0,0)
    assert not missions.contains(poly,180,0)


def test_empty_science_product_is_never_a_destination(tmp_path):
    store=Store(tmp_path);item=entry();path=science_file(store,item)
    with fits.open(path,mode="update") as hdus:
        hdus[0].data[:]=0
    with pytest.raises(ValueError,match="hubble_no_field"):
        missions.registered_cutout(store,capture(),item)


def test_euclid_destination_is_offered_when_hst_is_temporarily_unavailable(tmp_path,monkeypatch):
    store=Store(tmp_path);record=capture();signature=archive_search.field_key(store,record)
    record["mission_search"]={"field":signature,"euclid":{"options":[entry()]}}
    record["hst_search"]={"field":signature,"options":[],"unavailable":True}
    monkeypatch.setattr(missions.external_http,"get",lambda *args,**kwargs:pytest.fail("unexpected network"))
    assert hubble.fields(store,record,local_only=True)==[entry()]
