from datetime import date
from zoneinfo import ZoneInfo
import hashlib
import json
import time

import astropy.units as u
import cv2
import numpy as np
import pytest
from astropy.cosmology import Planck18
from astropy.wcs import WCS

from astroweb import cosmic, mosaic, planner, solar_compare, stellar_space
from astroweb.app import create_app
from astroweb.metadata import validate_metadata
from astroweb.render import compose
from astroweb.store import Store


def capture(store,identifier="M_31",ra=359.99,sign=-1,published=True):
    h,w=120,160
    yy,xx=np.mgrid[:h,:w]
    background=np.stack([.1+xx*.001,.12+yy*.001,.15+xx*.0005],axis=-1).astype(np.float32)
    stars=np.zeros_like(background);stars[38:43,48:53]=.7;stars[78:83,108:113]=.5
    arrays=dict(final=compose(background,stars,"screen"),starless=background,stars=stars,stars_laid=stars)
    assets={}
    for role,raster in arrays.items():
        path=store.path(identifier+"_"+role+".png")
        cv2.imwrite(str(path),cv2.cvtColor(np.uint8(raster*255),cv2.COLOR_RGB2BGR));assets[role]=path.name
    digest=hashlib.sha256(store.path(assets["final"]).read_bytes()).hexdigest()
    wcs=WCS(naxis=2);wcs.wcs.ctype=["RA---TAN","DEC--TAN"];wcs.wcs.crval=[ra,10]
    wcs.wcs.cdelt=[sign*.001,.001];wcs.wcs.crpix=[80.5,60.5]
    sky=wcs.pixel_to_world([-.5,w-.5,w-.5,-.5],[-.5,-.5,h-.5,h-.5]).icrs
    metadata=dict(target="M 31",name={"nl":"Andromeda","en":"Andromeda"},type={"nl":"Stelsel","en":"Galaxy"},
                  constellation={"nl":"Andromeda","en":"Andromeda"},summary={"nl":"","en":""},description={"nl":"","en":""})
    record=dict(id=identifier,width=w,height=h,assets=assets,sha256={"final":digest},metadata=metadata,published=published,
                capture_date="2026-11-09",observation={"date_obs":"2026-11-09T23:00:00Z"},video=None,params={},versions=[],render=None,
                created_at="2026-11-10T12:00:00Z",poster=assets["final"],
                gaia=dict(status="solved",digest=digest,wcs_header=wcs.to_header().tostring(sep="\n"),corners=np.c_[sky.ra.deg,sky.dec.deg].tolist()))
    store.put("objects",identifier,record)
    return record


def test_mosaic_preserves_raster_parity_ra_wrap_and_source_files(tmp_path):
    store=Store(tmp_path);a=capture(store);b=capture(store,"M_31~second",ra=.06,sign=1)
    before={p.name:p.read_bytes() for r in [a,b] for p in [store.path(r["assets"]["final"]) ]}
    adapter=mosaic.RasterWCS(store,a,(120,160))
    xy=np.array([0.,79.5,159.]);yy=np.array([0.,59.5,119.])
    ra,dec=adapter.pixel_to_world_values(xy,yy);x,y=adapter.world_to_pixel_values(ra,dec)
    np.testing.assert_allclose(x,xy,atol=1e-5);np.testing.assert_allclose(y,yy,atol=1e-5)
    assert len(mosaic.groups(store,[a,b]))==1
    folder=store.path("derived");folder.mkdir()
    result=mosaic.build(store,[a,b],folder)
    image=cv2.imread(str(folder/result["image"]),cv2.IMREAD_UNCHANGED)
    assert image.shape[2] in {3,4} and image[:,:,:3].max()>0
    assert len(result["captures"])==2 and result["width"]>160
    for r in [a,b]:
        p=store.path(r["assets"]["final"]);assert p.read_bytes()==before[p.name]


def test_cosmic_nearby_distance_does_not_misuse_negative_or_local_redshift(tmp_path,monkeypatch):
    store=Store(tmp_path);record=capture(store)
    monkeypatch.setattr(cosmic,"redshift",lambda *args:pytest.fail("nearby galaxy must use its measured distance"))
    data=cosmic.build(store,record)
    assert data["method"]=="catalogue" and data["lookback_years"]==2_500_000


def test_cosmic_distinguishes_lookback_and_three_distance_measures(tmp_path,monkeypatch):
    store=Store(tmp_path);record=capture(store);record["metadata"]["target"]="DISTANT TEST"
    monkeypatch.setattr(cosmic,"redshift",lambda *args:dict(z=.5,source="https://ned.ipac.caltech.edu/",method="test"))
    data=cosmic.build(store,record)
    assert data["lookback_years"]==pytest.approx(Planck18.lookback_time(.5).to_value(u.yr))
    assert data["luminosity_distance_ly"]>data["comoving_distance_ly"]>data["angular_diameter_distance_ly"]
    assert data["age_at_emission_years"]+data["lookback_years"]==pytest.approx(data["universe_age_years"])


def test_cited_cosmic_metadata_and_invalid_sources():
    store_record=dict(target="TEST 1",**{k:{"nl":"test","en":"test"} for k in ("name","type","constellation","summary","description")})
    good={**store_record,"redshift":.2,"redshift_source":"https://ned.ipac.caltech.edu/"}
    assert validate_metadata(good)["redshift"]==.2
    for bad in ({"redshift":float("nan")},{"redshift":True},{"redshift":-1},{"redshift_source":"javascript:alert(1)"},{"redshift_source":""}):
        with pytest.raises(ValueError,match="invalid_metadata"):validate_metadata({**good,**bad})


def test_calendar_uses_real_dst_nights_and_protects_private_sites():
    starts,ends,mids,ranges=planner.samples([date(2026,3,28)],ZoneInfo("Europe/Amsterdam"))
    assert len(starts)==46 and ends[-1]-starts[0]==23*3600
    record={"observation":{"latitude":-33.,"longitude":151.,"timezone":"Australia/Sydney","publish_location":False}}
    public,_,assumed=planner.site(record)
    private,_,private_assumed=planner.site(record,True)
    assert assumed and public.lat.deg==pytest.approx(52.15)
    assert not private_assumed and private.lat.deg==pytest.approx(-33.)


def test_netherlands_midsummer_has_no_astronomical_darkness(tmp_path):
    store=Store(tmp_path);record=capture(store)
    result=planner.build(store,record,"2026-06")
    assert len(result["days"])==30 and len(result["seasons"])==12
    assert all(row["dark_hours"]==0 and not row["windows"] for row in result["days"][10:25])
    assert result["default_site"] and result["step_minutes"]==30


def test_measured_space_uses_own_pixels_no_estimated_distances(tmp_path,monkeypatch):
    store=Store(tmp_path);record=capture(store)
    measured=dict(stars=[dict(source_id="near",x=50.5/160,y=40.5/120,distance_pc=100,parallax=10,parallax_error=.1),
                         dict(source_id="far",x=110.5/160,y=80.5/120,distance_pc=1000,parallax=1,parallax_error=.05)],
                  source_size=[160,120],epoch=2026,source="Gaia DR3")
    monkeypatch.setattr(stellar_space,"prepare",lambda *args:measured)
    folder=store.path("space");folder.mkdir();result=stellar_space.build(store,record,folder)
    assert result["measured_count"]==2 and result["range_pc"]==[100,1000]
    assert {p["distance_pc"] for p in result["stars"]}=={100,1000}
    assert all(not p.get("estimated") for p in result["stars"])
    assert (folder/result["atlas"]).is_file() and (folder/result["plane"]).is_file()


def test_solar_rejects_unrelated_epoch_before_loading_image(monkeypatch,tmp_path):
    monkeypatch.setattr(solar_compare,"fetch",lambda *args,**kw:json.dumps(dict(id="1",date="2020-01-01 12:00:00")).encode())
    with pytest.raises(ValueError,match="observatory_solar_no_match"):
        solar_compare.reference("2026-09-01T12:00:00Z",18,"HMI","visible",tmp_path)


def test_background_explorations_and_media_enforce_visibility(tmp_path,monkeypatch):
    app=create_app(tmp_path,testing=True);store=app.extensions["store"];record=capture(store,published=False)
    monkeypatch.setattr(cosmic,"build",lambda *args:dict(method="catalogue",lookback_years=10))
    client=app.test_client()
    try:
        assert client.get('/api/observatory').json['captures']==[]
        assert client.get('/api/observatory/cosmic?capture=M_31').status_code==404
        with client.session_transaction() as s:s["admin"]=True
        reply=client.get('/api/observatory/cosmic?capture=M_31').json
        deadline=time.monotonic()+5
        while reply["status"]!="ready" and time.monotonic()<deadline:
            time.sleep(.02);reply=client.get('/api/observatory/cosmic?capture=M_31').json
        assert reply["status"]=="ready"
        assert client.get('/api/observatory/cosmic?capture=M_31&month=1999-99').status_code==400
        assert client.get('/media/observatory/not-a-token/result.json').status_code==404
    finally:app.extensions["jobs"].shutdown()


def test_cached_mosaic_never_exposes_unpublished_input(tmp_path,monkeypatch):
    app=create_app(tmp_path,testing=True);store=app.extensions["store"];capture(store,published=False)
    def build(store,records,folder):
        cv2.imwrite(str(folder/'mosaic.webp'),np.full((32,32,3),100,np.uint8))
        return dict(image='mosaic.webp',captures=[])
    monkeypatch.setattr(mosaic,'build',build)
    client=app.test_client()
    try:
        with client.session_transaction() as s:s['admin']=True
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            reply=client.get('/api/observatory/mosaic?capture=M_31').json
            if reply['status']=='ready':break
            time.sleep(.02)
        url=reply['data']['image'];assert client.get(url).status_code==200
        assert client.get(url).headers['Cache-Control']=='private, no-store'
        with client.session_transaction() as s:s.clear()
        assert client.get(url).status_code==404
    finally:app.extensions['jobs'].shutdown()


def test_sdo_time_normalization_header_grid_and_fractional_utc(monkeypatch,tmp_path):
    xml='''<meta><fits><NAXIS1>512</NAXIS1><NAXIS2>512</NAXIS2><CTYPE1>HPLN-TAN</CTYPE1><CTYPE2>HPLT-TAN</CTYPE2>
      <CRPIX1>256.5</CRPIX1><CRPIX2>256.5</CRPIX2><CRVAL1>0</CRVAL1><CRVAL2>0</CRVAL2>
      <CDELT1>4</CDELT1><CDELT2>4</CDELT2><CUNIT1>arcsec</CUNIT1><CUNIT2>arcsec</CUNIT2>
      <DATE-OBS>2026-09-01T13:54:35.100</DATE-OBS><RSUN_REF>695700000</RSUN_REF><DSUN_OBS>150000000000</DSUN_OBS>
      <HGLN_OBS>0</HGLN_OBS><HGLT_OBS>7</HGLT_OBS><RSUN_OBS>956.6</RSUN_OBS><history>Multiple\n history lines</history>
      </fits></meta>'''
    _,png=cv2.imencode('.png',np.full((512,512,3),150,np.uint8))
    def fetch(endpoint,params,*args):
        if endpoint=='getClosestImage':
            assert params['date']=='2026-09-01T13:54:25Z'
            return json.dumps(dict(id='1',date='2026-09-01 13:54:35')).encode()
        return xml.encode() if endpoint=='getJP2Header' else png.tobytes()
    monkeypatch.setattr(solar_compare,'fetch',fetch)
    result=solar_compare.reference('2026-09-01T15:54:25.201+02:00',18,'HMI','visible',tmp_path)
    assert result['delta_seconds']==pytest.approx(9.899)
    assert len(result['grid']['lines'])==10 and result['north_up']
    np.testing.assert_allclose(result['grid']['center'],[.5,.5],atol=.001)
    assert (tmp_path/result['image']).is_file()
    from astropy.io.fits import Header
    from datetime import datetime,timedelta
    header=Header.fromstring((tmp_path/'solar-18.hdr').read_text(encoding='ascii'),sep='\n')
    selected=solar_compare.surface_point(header,x=.5,y=.5)
    assert selected['visible'] and abs(selected['lat']-7)<.1
    later=header.copy();later['DATE-OBS']=(datetime.fromisoformat(header['DATE-OBS'])+timedelta(days=1)).isoformat()
    tracked=solar_compare.surface_point(later,landmark=selected['landmark'])
    assert abs(tracked['lon']-selected['lon'])>10
    assert abs(tracked['lat']-selected['lat'])<.02
    later['DATE-OBS']=(datetime.fromisoformat(header['DATE-OBS'])+timedelta(days=15)).isoformat()
    behind=solar_compare.surface_point(later,landmark=selected['landmark'])
    assert not behind['visible']


def test_retry_waits_for_new_data_instead_of_returning_an_old_error(tmp_path,monkeypatch):
    from threading import Event
    app=create_app(tmp_path,testing=True);store=app.extensions['store'];capture(store)
    client=app.test_client();release=Event();started=Event()
    monkeypatch.setattr(cosmic,'build',lambda *args:(_ for _ in ()).throw(ValueError('observatory_cosmic_missing')))
    try:
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            reply=client.get('/api/observatory/cosmic?capture=M_31').json
            if reply['status']=='error':break
            time.sleep(.02)
        with store.connect() as db:
            key,raw=db.execute("SELECT id,record FROM settings WHERE id LIKE 'observatory-v1:%'").fetchone()
        prior=json.loads(raw);prior['time']-=30;store.put('settings',key,prior)
        def build(*args):
            started.set();assert release.wait(5);return dict(lookback_years=100)
        monkeypatch.setattr(cosmic,'build',build)
        assert client.get('/api/observatory/cosmic?capture=M_31&retry=1').json['status']=='preparing'
        assert started.wait(2)
        assert client.get('/api/observatory/cosmic?capture=M_31').json['status']=='preparing'
        release.set()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            reply=client.get('/api/observatory/cosmic?capture=M_31').json
            if reply['status']=='ready':break
            time.sleep(.02)
        assert reply['data']['lookback_years']==100
    finally:
        release.set();app.extensions['jobs'].shutdown()


def test_viewer_only_offers_mosaics_for_overlaps_and_embed_is_same_origin(tmp_path):
    app=create_app(tmp_path,testing=True);store=app.extensions['store'];capture(store)
    client=app.test_client()
    try:
        assert not client.get('/api/objects/M_31').json['explorations']['mosaic']
        capture(store,'M_31~next',ra=.02)
        assert client.get('/api/objects/M_31').json['explorations']['mosaic']
        embedded=client.get('/observatory?embed=1&capture=M_31&mode=space')
        assert embedded.headers['X-Frame-Options']=='SAMEORIGIN'
        assert "frame-ancestors 'self'" in embedded.headers['Content-Security-Policy']
        assert client.get('/calendar').headers['X-Frame-Options']=='DENY'
        assert client.get('/observatory?embed=1&capture=DOES_NOT_EXIST&mode=space').status_code==404
        assert client.get('/observatory?capture=M_31').location.endswith('/viewer/M_31#original')
    finally:app.extensions['jobs'].shutdown()


def test_collection_calendar_exposes_only_allowed_capture_dates(tmp_path,monkeypatch):
    app=create_app(tmp_path,testing=True);store=app.extensions['store'];capture(store);capture(store,'PRIVATE',published=False)
    monkeypatch.setattr(planner,'collection_calendar',lambda month:dict(month=month,kind='collection',days=[]))
    client=app.test_client()
    try:
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            result=client.get('/api/calendar?month=2026-11').json
            if result['status']=='ready':break
            time.sleep(.02)
        assert result['data']['kind']=='collection' and 'capture' not in result['data']
        assert [r['id'] for r in result['data']['events']]==['M_31']
        assert result['data']['events'][0]['day']=='2026-11-09'
        assert 'rotation=90' in result['data']['events'][0]['poster']
        with client.session_transaction() as s:s['admin']=True
        assert len(client.get('/api/calendar?month=2026-11').json['data']['events'])==2
    finally:app.extensions['jobs'].shutdown()
