import numpy as np
import pytest
from astroweb import hubble
from astroweb.polar import chart_catalog, chart


def test_mosaic_core_and_orientation():
    # Nucleus visibly sits at (about 529,196) in the release's 1280x299 view.
    x,y=hubble.registration().world_to_pixel_values(10.684792,41.269056)
    assert x*1280/hubble.MW == pytest.approx(529,abs=2)
    assert (hubble.MH-1-y)*299/hubble.MH == pytest.approx(196,abs=2)
    assert hubble.eligible({"metadata":{"target":"M 31"}})
    assert not hubble.eligible({"metadata":{"target":"M 32"}})


def test_off_field_never_offers_a_hubble_window():
    r={"width":100,"height":120,"metadata":{"target":"M31"},"sha256":{"final":"other"},
       "gaia":{"status":"solved","digest":"other","corners":[[180,0],[181,0],[181,1],[180,1]]}}
    assert all(hubble.window_geometry(None,r,k) is None for k in hubble.WINDOWS)


def test_motion_units_match_measured_proper_motion():
    data=chart_catalog()
    p=np.asarray(data["motion"]["69673"])
    now=p[:3]
    later=now+p[3:]
    angle=np.arctan2(np.linalg.norm(np.cross(now,later)),np.dot(now,later))
    # Arcturus: pmRA*cos(dec) = -1093.45, pmDec = -1999.4 mas/yr.
    assert np.rad2deg(angle)*3600000 == pytest.approx(np.hypot(1093.45,1999.4),rel=.005)
    assert len(data["motion"])==1631
    r={"id":"TEST_1","metadata":{"target":"test","name":{}},"observation":{"date_obs":"2024-07-02T00:00:00+00:00"}}
    assert chart(None,r)["epoch"]==pytest.approx(2024.5)


@pytest.mark.parametrize("name,ra,dec", [
    ("ngc206",10.130417,40.739278),("m32",10.674292,40.865278),("nucleus",10.684792,41.269056)
])
def test_named_m31_destinations_use_catalogue_centres(name,ra,dec):
    x,y=hubble.registration().world_to_pixel_values(ra,dec)
    np.testing.assert_allclose(hubble.WINDOWS[name],(x,hubble.MH-1-y),atol=1)


def test_ground_based_plate_offered_only_inside_registered_capture():
    r={"width":500,"height":480,"metadata":{"target":"C 20"},"sha256":{"final":"example"},
       "gaia":{"status":"solved","digest":"example","corners":[[315,42.6],[316.9,45.1],[314.9,45.9],[313.1,43.4]]}}
    options=hubble.fields(None,r)
    assert [o["id"] for o in options]==["c20-wfpc2","heic0510a"]
    assert options[0]["telescope"]=="HST/WFPC2"
    option=options[1]
    assert option["id"]=="heic0510a" and "Digitized Sky Survey" in option["credit"]
    r["gaia"]["corners"]=[[80,0],[81,0],[81,1],[80,1]]
    assert hubble.window_geometry(None,r,option["id"]) is None

def test_caldwell20_whole_frame_required_for_each_capture():
    record={"width":800,"height":1200,"sha256":{"final":"test"},"metadata":{"target":"NGC 7000"},
            "gaia":{"status":"solved","digest":"test","corners":[
                [317.18230,43.88614],[316.14037,44.97247],[313.44828,43.58705],[314.51414,42.52549]]}}
    assert hubble.window_geometry(None,record,"c20-wfpc2") is None
    assert hubble.window_geometry(None,record,"heic0510a") is not None
    plate=hubble.PLATES["c20-wfpc2"]
    x,y=plate["focus"]
    sky=hubble.plate_wcs(plate).pixel_to_world(x,plate["size"][1]-1-y)
    assert (sky.ra.deg,sky.dec.deg)==pytest.approx((314.714925,44.264741),abs=.00001)

def test_caldwell20_prefers_published_plate_to_its_archive_observation():
    from astroweb.archive_search import field_key
    r={"width":500,"height":480,"metadata":{"target":"C 20"},"sha256":{"final":"example"},
       "gaia":{"status":"solved","digest":"example","corners":[[315,42.6],[316.9,45.1],[314.9,45.9],[313.1,43.4]]}}
    r["hst_search"]={"field":field_key(None,r),"options":[
        {"id":"hst_08216_44_wfpc2_f606w_wf","relation":"region"},
        {"id":"other-pointing","relation":"field"}]}
    assert [f["id"] for f in hubble.fields(None,r)]==["c20-wfpc2","heic0510a","other-pointing"]


@pytest.mark.parametrize("mirror", [1,-1])
def test_tv_destination_camera_aligns_both_layers(mirror,monkeypatch):
    import cv2
    monkeypatch.setattr(hubble,"WIDTH",96)
    monkeypatch.setattr(hubble,"HEIGHT",64)
    rng=np.random.default_rng(17)
    dest=rng.integers(20,250,(64,96,3),dtype=np.uint8)
    # A non-quarter-turn pose exercises parity, rotation and translation.
    affine=cv2.getRotationMatrix2D((48,32),31,.95)
    affine[:,2]+=[35,35]
    matrix=np.vstack((affine,[0,0,1]))@np.array([[mirror,0,95 if mirror<0 else 0],[0,1,0],[0,0,1]])
    own=cv2.warpPerspective(dest,matrix,(168,144))
    frames=list(hubble.aligned_skymap_frames(own,dest,matrix))
    assert np.array_equal(frames[-1],dest)
    # At 77% the camera is settled and both sources still contribute.
    a=frames[221][5:-5,5:-5].mean(2).ravel()
    b=dest[5:-5,5:-5].mean(2).ravel()
    assert np.corrcoef(a,b)[0,1]>.99


@pytest.mark.parametrize("target", [(0,0),(998,748),(999,0),(-40,880)])
@pytest.mark.parametrize("end", [.05, 2., 2500.])
def test_hubble_target_stays_inside_every_frame(target,end):
    from astroweb.camera import FocusZoom
    width,height=1280,720
    center=(np.array([width,height])-1)/2
    camera=FocusZoom(np.array([500,375]),target,.96,end,width,height)
    for t in np.linspace(0,1,288):
        progress=t*t*(3-2*t)
        _,matrix=camera.at(progress)
        screen=(matrix@[*target,1])[:2]
        assert np.all(screen>=0) and np.all(screen<=[width-1,height-1])
        np.testing.assert_allclose(screen,center+(1-progress)*camera.initial_offset,atol=1e-7)
