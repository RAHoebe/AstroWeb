import numpy as np
import astropy.units as u
import pytest
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS

from astroweb.discovery import project, discover
from astroweb.galaxy import galactic_map
from astroweb.metadata import initial_metadata
from astroweb.render import Parameters


@pytest.mark.parametrize("legacy", [False, True])
def test_projection_of_rotated_galaxy_with_and_without_saved_wcs(legacy):
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [500, 350]
    wcs.wcs.crval = [10.68, 41.27]
    wcs.wcs.cd = [[-.0015, .0004], [.0004, .0015]]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    width, height = 1000, 700
    corners = wcs.pixel_to_world([-.5,width-.5,width-.5,-.5],[-.5,-.5,height-.5,height-.5])
    solution = {"status":"solved","digest":"test","corners":np.column_stack((corners.ra.deg,corners.dec.deg)).tolist()}
    if not legacy:
        solution["wcs_header"] = wcs.to_header().tostring(sep="\n",endcard=False,padding=False)
    record = {"id":"M_31","metadata":initial_metadata("M_31"),"width":width,"height":height,
              "sha256":{"final":"test"},"gaia":solution}
    xy = np.array([[40,55],[800,600],[500,350]],dtype=float)
    _, predicted = project(None,record,wcs.pixel_to_world(*xy.T))
    np.testing.assert_allclose(predicted, (xy+.5)/[width,height],atol=1e-5)
    found = {v["id"]:v for v in discover(None,record)["objects"]}
    assert found["M31"]["type"]["en"] == "Spiral galaxy" and found["M32"]["type"]["en"] == "Galaxy"
    assert found["M31"]["source"].startswith("https://")
    assert galactic_map(record) is None
    record["sha256"]["final"] = "different"
    assert discover(None,record) == {"kind":"missing","objects":[]}


def test_named_single_stop_survives_round_trip():
    p = Parameters.parse({"zoom_points":[{"name":"M32","zoom":2,"focus_x":.35,"focus_y":.7}]})
    assert Parameters.parse(p.__dict__).zoom_points == p.zoom_points
    with pytest.raises(ValueError):
        Parameters.parse({"zoom_points":[{"name":"x"*101,"zoom":2,"focus_x":0,"focus_y":1}]})


@pytest.mark.parametrize("identifier",["M_31","M31","M 31","Messier 31","NGC_224"])
def test_m31_metadata_aliases(identifier):
    m=initial_metadata(identifier)
    assert m["target"]=="M31" and m["name"]["nl"]=="Andromedastelsel"
    assert {s["url"].split("/")[2] for s in m["sources"]} == {"science.nasa.gov","www.esa.int"}
