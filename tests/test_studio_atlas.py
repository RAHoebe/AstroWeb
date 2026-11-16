import numpy as np
import pytest

from astroweb.galaxy import face_position, galactic_map
from astroweb.metadata import initial_metadata, renamed_metadata
from astroweb.render import Parameters, Scene
from astroweb.store import Store


def test_map_requires_identified_galactic_distance():
    assert galactic_map({"id":"M_31","metadata":{"target":"M31"}}) is None
    assert galactic_map({"id":"HIP_106890","metadata":{"target":"IC 1396"}})["ly"] == 3000
    assert galactic_map({"id":"NGC_1976","metadata":{"target":"NGC 1976"}})["ly"] == 1500
    custom = {"id":"TEST_1","metadata":{"target":"TEST 1","galactic_distance_ly":200}}
    assert galactic_map(custom) is None
    custom["observation"] = {"ra":14,"dec":-10}
    assert galactic_map(custom)["xy"] == face_position(14,-10,200)


@pytest.mark.parametrize("count",[2,4,8])
def test_points_in_order_and_loop(count):
    stops = [{"focus_x":i/(count+1), "focus_y":1-i/(count+1), "zoom":i} for i in range(1,count+1)]
    scene = Scene.__new__(Scene)
    scene.params = Parameters.parse({"zoom_points":stops})
    for i, stop in enumerate(stops, 1):
        np.testing.assert_allclose(scene.camera_pose(i/(count+1), 0)[:3],
                                   [stop["focus_x"]-.5,stop["focus_y"]-.5,stop["zoom"]-1])
    assert scene.camera_pose(0,0) == scene.camera_pose(1,0)
    with pytest.raises(ValueError):
        Parameters.parse({"zoom_points":[stops[0]] * 9})
    with pytest.raises(ValueError):
        Parameters.parse({"zoom_points":[{"zoom":9,"focus_x":1,"focus_y":1}]})
    scene.params = Parameters.parse({"focus_x":.2,"focus_y":.6,"zoom":4})
    np.testing.assert_allclose(scene.camera_pose(.5,1),[-.3,.1,3,.35])


def test_rename_keeps_storage_jobs_and_aliases(tmp_path):
    store = Store(tmp_path)
    old, new = "HIP_106890", "IC_1396"
    store.put("objects",old,{"id":old,"metadata":initial_metadata(old),"video":"objects/HIP_106890/movies/a.mp4"})
    store.put("jobs","a",{"id":"a","object_id":old,"status":"running"})
    with pytest.raises(ValueError,match="rename_busy"):
        store.rename_object(old,new,renamed_metadata(new))
    store.update("jobs","a",status="completed")
    result = store.rename_object(old,new,renamed_metadata(new))
    assert result["storage_id"] == old and result["video"].startswith("objects/HIP_106890/")
    assert result["metadata"]["target"] == "IC 1396" and "HIP" not in result["metadata"]["description"]["en"]
    assert store.current_id(old) == new and store.get("jobs","a")["object_id"] == new
    store.rename_object(new,old,initial_metadata(old))
    assert store.current_id(new) == old and store.current_id(old) == old

def test_expanded_atlas_separates_sky_objects_from_galactic_distances():
    from astroweb.galaxy import field_catalog, landmarks, target_entry
    assert len(landmarks()) > 800
    assert len(field_catalog()[0]) > 11000
    assert target_entry("SIRIUS")["ly"] < 10
    assert galactic_map({"id":"M_31", "metadata":{"target":"M31"}}) is None
    assert galactic_map({"id":"NGC_104", "metadata":{"target":"47 Tuc"}})["ly"] > 10000
    assert "xy" not in target_entry("TRUMPLER37")


def test_gaia_map_scale_and_galactic_axes():
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    from astroweb.galaxy import SUN, LY_PER_IMAGE, MAP_CREDIT
    np.testing.assert_allclose(SUN,(.5,.704))
    assert abs(LY_PER_IMAGE-130462.55)<.1
    toward=SkyCoord(l=0*u.deg,b=0*u.deg,frame="galactic").icrs
    np.testing.assert_allclose(face_position(toward.ra.deg,toward.dec.deg,
        (SUN[1]-.5)*LY_PER_IMAGE),[.5,.5],atol=1e-10)
    east=SkyCoord(l=90*u.deg,b=0*u.deg,frame="galactic").icrs
    x,y=face_position(east.ra.deg,east.dec.deg,1000)
    assert x<SUN[0] and abs(y-SUN[1])<1e-10
    payload=galactic_map({"id":"NGC_7000","metadata":{"target":"NGC 7000"}})
    assert payload["map_credit"]==MAP_CREDIT and "Gaia" in MAP_CREDIT
    assert "by-sa/3.0/igo" in payload["map_license"]
