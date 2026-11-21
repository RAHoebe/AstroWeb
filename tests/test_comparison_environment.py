import cv2
import numpy as np
import pytest
from astroweb.autozoom import propose
from astroweb.comparison import raster_sky
from astroweb.discovery import project
from astroweb.environment import neighbourhood, target_galaxy
from astroweb.metadata import initial_metadata
from astroweb.store import Store
from astropy.wcs import WCS


@pytest.mark.parametrize("saved_header",[False,True])
def test_comparison_and_discovery_share_rotated_reflected_coordinates(saved_header):
    wcs=WCS(naxis=2)
    wcs.wcs.ctype=["RA---TAN","DEC--TAN"]
    wcs.wcs.crpix=[102.3,128.5]
    wcs.wcs.crval=[359.95,69.]
    wcs.wcs.cd=[[-.0007,.0003],[-.0003,-.0007]]
    width,height=350,270
    corners=wcs.pixel_to_world([-.5,width-.5,width-.5,-.5],[-.5,-.5,height-.5,height-.5])
    field={"kind":"gaia","corners":np.column_stack((corners.ra.deg,corners.dec.deg)).tolist()}
    solved={"status":"solved","digest":"sample","corners":field["corners"]}
    if saved_header:
        solved["wcs_header"]=wcs.to_header().tostring(sep="\n",padding=False,endcard=False)
    record={"width":width,"height":height,"gaia":solved,"sha256":{"final":"sample"}}
    y,x=np.mgrid[.07:.98:7j,.03:.96:9j]
    sky=raster_sky(None,record,field,x,y)
    expected=wcs.pixel_to_world(x*width-.5,y*height-.5)
    assert np.max(expected.separation(sky).arcsec)<.01
    _,points=project(None,record,sky.ravel())
    np.testing.assert_allclose(points,np.column_stack((x.ravel(),y.ravel())),atol=1e-5)


def test_environment_relations_are_sourced_and_target_specific():
    record={"id":"M_31","metadata":initial_metadata("M_31")}
    data=neighbourhood(None,record)
    assert not data["outline"]
    by_id={o["id"]:o for o in data["objects"]}
    assert by_id["M31"]["relation"]=="target"
    assert by_id["M32"]["relation"]=="satellite"
    assert by_id["M110"]["distance"]==2.7 and by_id["M110"]["relation_source"]
    record["metadata"]["target"]="M51"
    others=neighbourhood(None,record)["objects"]
    assert any(o["relation"]=="interacting" for o in others)
    assert any(o["relation"]=="projected" and not o["relation_source"] for o in others)
    assert target_galaxy({"id":"NGC_7000","metadata":initial_metadata("NGC_7000")}) is None


def test_autozoom_distinct_structures_and_featureless_image(tmp_path):
    store=Store(tmp_path)
    record={"id":"test","poster":"poster.jpg","width":400,"height":200}
    image=np.full((200,400),30,np.uint8)
    path=str(store.path("poster.jpg"))
    cv2.imwrite(path,image)
    assert propose(store,record,4)=={"points":[],"alignment":"missing"}
    for x,y in [(30,50),(220,150),(330,60)]:
        cv2.circle(image,(x,y),16,200,-1)
    cv2.imwrite(path,image)
    points=propose(store,record,3)["points"]
    assert len(points)==3 and all(p["kind"]=="structure" for p in points)
    assert all(0<=p["x"]<=1 and 0<=p["y"]<=1 and 1<=p["zoom"]<=8 for p in points)
    with pytest.raises(ValueError,match="invalid_parameters"):
        propose(store,record,9)
