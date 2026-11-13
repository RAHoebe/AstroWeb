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

def test_gallery_uses_observation_date_and_keeps_each_session_addressable():
    from astroweb.collection import capture_groups,gallery
    def capture(id,when,published=True):
        return {"id":id,"catalog_id":"NGC_7000","observation":{"date_obs":when},"published":published}
    new=capture("NGC_7000","2026-11-10T00:30:00+00:00")
    old=capture("NGC_7000~old","2026-11-10T01:00:00+02:00")
    unknown=capture("NGC_7000~unknown",None)
    draft=capture("NGC_7000~draft","2027-01-01T00:00:00Z",False)
    rows=[draft,unknown,old,new]
    assert gallery(r for r in rows if r["published"])==[new]
    assert capture_groups(rows)["NGC_7000"]==[draft,new,old,unknown]
    old["capture_date"]="2026-12-15"
    assert gallery([unknown,old,new])==[old]


def test_unnamed_repeat_upload_uses_separate_originals(tmp_path):
    paths=[]
    for role in ("final","starless","stars","stars_laid"):
        p=tmp_path/f"NGC_7000_{role}.png"
        Image.new("RGB",(160,160)).save(p)
        paths.append(p)
    s=Store(tmp_path/"lib")
    first=import_object(s,"NGC_7000",paths,repeat=True,capture_date="2026-10-10")
    second=import_object(s,"NGC_7000",paths,repeat=True,capture_date="2026-11-11")
    assert first["id"]!=second["id"] and second["catalog_id"]==first["id"]
    assert first["assets"]["final"]!=second["assets"]["final"] and second["session_name"]==""

def test_merge_renamed_capture_into_existing_alias_group_preserves_both_records(tmp_path):
    from astroweb.catalogue import canonical
    from astroweb.collection import capture_groups
    assert {canonical(a) for a in ("C20","C 20","Caldwell 20","NGC7000","NGC_7000")}=={"NGC_7000"}
    assert canonical("NGC 224")==canonical("Messier 31")
    assert canonical("C 33")!=canonical("NGC 6992")
    assert canonical("C 7")==canonical("NGC 2403")
    s=Store(tmp_path)
    for ident,data,date in [("NGC_7000","one","2026-10-11"),("TEST_99","two","2026-11-11")]:
        s.put("objects",ident,{"id":ident,"metadata":{"name":{"nl":ident},"target":ident},
              "capture_date":date,"video":data,"assets":{"final":data},"published":True,"versions":[data]})
    s.put("jobs","job",{"object_id":"TEST_99","status":"completed","id":"job"})
    merged=s.rename_object("TEST_99","C_20",{})
    assert merged["id"].startswith("NGC_7000~")
    assert s.current_id("TEST_99")==merged["id"] and merged["storage_id"]=="TEST_99"
    assert s.get("jobs","job")["object_id"]==merged["id"]
    assert s.get("objects","NGC_7000")["versions"]==["one"] and merged["versions"]==["two"]
    assert merged["metadata"]["name"]["nl"]=="NGC_7000"
    # Legacy captures recorded under a different alias group on read as well.
    s.put("objects","C_20",{"id":"C_20","published":True,"capture_date":"2026-01-01"})
    groups=capture_groups(s.all("objects"))
    assert list(groups)==["NGC_7000"] and len(groups["NGC_7000"])==3 and groups["NGC_7000"][0]["id"]==merged["id"]
