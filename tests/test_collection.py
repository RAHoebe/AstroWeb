import numpy as np
from astroweb.collection import atlas_data, neighbours
from astroweb.media import import_object
from astroweb.store import Store
from astroweb.galaxy import journey_labels
from astroweb import journey
from PIL import Image
import pytest


def test_independent_sessions_share_target_and_protect_drafts(tmp_path):
    store=Store(tmp_path/"data")
    paths=[]
    for role in ("final","starless","stars","stars_laid"):
        path=tmp_path/f"M_31_{role}.png"
        Image.new("RGB",(140,200)).save(path)
        paths.append(path)
    first=import_object(store,"M_31",paths)
    store.update("objects",first["id"],published=True,observation={"ra":10,"dec":40,"latitude":45})
    second=import_object(store,"M_31",paths,"Panel B")
    assert first["assets"]!=second["assets"] and second["catalog_id"]=="M_31"
    assert len(atlas_data(store)["captures"])==1
    private=atlas_data(store,True)["captures"]
    assert private[0]["field"]["kind"]=="missing" and private[1]["field"]=={"kind":"point","center":[10,40]}
    assert "latitude" not in str(private)
    with pytest.raises(ValueError,match="session_exists"):
        import_object(store,"M_31",paths,"panel b")
    store.update("objects",second["id"],published=True)
    records=store.all("objects")
    assert neighbours(records,first["id"])["next"]["id"]==second["id"]
    assert neighbours(records,second["id"])["previous"]["id"]==first["id"]
    assert neighbours(records[:1],second["id"])=={}


def test_journey_labels_follow_final_pose_even_for_reflected_photo():
    field={"kind":"gaia","corners":[[10,40],[10.5,40],[10.5,41],[10,41]]}
    r={"id":"M_31","metadata":{"target":"M31","name":{"nl":"M31","en":"M31"}},"width":500,"height":1000}
    _,quad,_,_=journey.field_projection(field)
    for corners in [field["corners"],field["corners"][::-1]]:
        field["corners"]=corners
        _,quad,_,_=journey.field_projection(field)
        data=journey_labels(r,field)
        assert all(frame[-1]==1 for frame in data["frames"])
        matrix=np.asarray(data["frames"][-1][:9]).reshape(3,3)
        h=np.column_stack((quad,np.ones(4))) @ matrix.T
        pixels=h[:,:2]/h[:,2:3]
        assert abs(pixels[0,1])<.2 and abs(pixels[1,1])<.2
        assert abs(pixels[2,1]-journey.HEIGHT+1)<.2 and pixels[0,0]<pixels[1,0]
