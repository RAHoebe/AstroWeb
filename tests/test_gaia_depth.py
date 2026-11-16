import numpy as np
import pytest
from astroweb.render import Parameters, Scene, compose, render_video, save_jpg
from astroweb.gaia_depth import prepare


def inputs():
    bg = np.full((160, 240, 3), .25, np.float32)
    stars = np.zeros_like(bg)
    stars[40:45,60:65] = .3
    stars[100:105,170:175] = .8
    raw = {"final":compose(bg,stars,"screen"),"starless":bg,"stars":stars,"stars_laid":stars}
    data = {"stars":[{"x":62.5/240,"y":42.5/160,"distance_pc":100,"source_id":"near"},
                    {"x":172.5/240,"y":102.5/160,"distance_pc":1000,"source_id":"far"}],
            "source_size":[240,160],"epoch":2026}
    return raw,data


@pytest.mark.parametrize("orientation", ["portrait", "original"])
@pytest.mark.parametrize("blend", ["screen", "add"])
def test_measured_distance_controls_motion_and_background_stays_intact(orientation, blend):
    raw,data=inputs()
    scene=Scene(raw,Parameters(method="gaia",orientation=orientation,blend=blend),stellar_depth=data)
    sprites={p["source_id"]:p for p in scene.gaia_sprites}
    assert sprites["near"]["factor"] > sprites["far"]["factor"]
    assert scene.gaia_report["matched"]==2
    assert np.max(np.abs(scene.bg[0]/65535-.25)) < 1/65535
    np.testing.assert_allclose(scene.frame(0),scene.frame(1),atol=1e-5)
    for phase in (0,.25,.5,.75):
        assert scene.frame(phase).min() >= .25-2/65535


def test_unmatched_field_fails_instead_of_using_brightness_as_distance():
    raw,data=inputs()
    data["stars"][0]["x"]=.98
    data["stars"][1]["x"]=.01
    with pytest.raises(ValueError,match="gaia_depth_no_stars"):
        Scene(raw,Parameters(method="gaia"),stellar_depth=data)
    with pytest.raises(ValueError,match="gaia_depth_missing"):
        Scene(raw,Parameters(method="gaia"))


def test_gaia_h264_entry_point_records_provenance(tmp_path):
    raw,data=inputs()
    paths={}
    for key,raster in raw.items():
        paths[key]=tmp_path/(key+".jpg")
        save_jpg(paths[key],raster,100)
    stats=render_video(paths,tmp_path/"movie.mp4",
                       Parameters(method="gaia",duration=4,resolution=720),stellar_depth=data)
    assert stats["gaia"]["matched"]==2 and stats["frames"]==96
    assert (tmp_path/"movie.mp4").stat().st_size>1000


def test_epoch_propagation_and_ids_are_preserved(monkeypatch):
    import astroweb.gaia_depth as gd
    monkeypatch.setattr(gd,"geometry",lambda *_:{"kind":"gaia","corners":[]})
    monkeypatch.setattr(gd,"catalogue",lambda *_:[{"source_id":"1234567890123456789","ra":10,"dec":30,
        "pmra":1000,"pmdec":0,"ref_epoch":2016,"parallax":10,"parallax_error":.1,"ruwe":1}])
    def projected(store,record,coords):
        assert coords.ra.deg[0] > 10.003
        return "gaia",np.array([[.5,.5]])
    monkeypatch.setattr(gd,"project",projected)
    d=prepare(None,{"observation":{"date_obs":"2026-01-01T00:00:00Z"},"width":240,"height":160})
    assert d["stars"][0]["source_id"]=="1234567890123456789"
    assert d["stars"][0]["distance_pc"]==100


def test_catalogue_uses_esa_fallback_and_keeps_the_cache(tmp_path,monkeypatch):
    import io
    import requests
    from astropy.table import Table
    from astroweb import gaia_depth
    from astroweb.store import Store
    table=Table(rows=[(1234567890123456789,10.,30.,2016.,0.,0.,10.,.1,1.)],
                names=['source_id','ra','dec','ref_epoch','pmra','pmdec','parallax','parallax_error','ruwe'])
    stream=io.BytesIO();table.write(stream,format='votable')
    calls=[]
    class Reply:
        content=stream.getvalue()
        def raise_for_status(self):pass
    def get(url,**kwargs):
        calls.append(url)
        if 'aip.de' in url:raise requests.HTTPError('temporary mirror failure')
        return Reply()
    monkeypatch.setattr(gaia_depth.external_http,'get',get)
    store=Store(tmp_path);field={'corners':[[9.9,29.9],[10.1,29.9],[10.1,30.1],[9.9,30.1]]}
    rows=gaia_depth.catalogue(store,field)
    assert rows[0]['source_id']=='1234567890123456789'
    assert gaia_depth.catalogue(store,field)==rows
    assert len(calls)==2 and calls[1].startswith('https://gea.esac.esa.int/')


def test_studio_preview_and_queue_use_gaia_method(tmp_path, monkeypatch):
    from astroweb.app import create_app
    from astroweb.media import import_object
    app=create_app(tmp_path/"data",testing=True)
    store,queue=app.extensions["store"],app.extensions["jobs"]
    raw,data=inputs()
    paths=[]
    for key,raster in raw.items():
        path=tmp_path/f"NGC_7000_{key}.jpg";save_jpg(path,raster,100);paths.append(path)
    record=import_object(store,"NGC_7000",paths)
    monkeypatch.setattr("astroweb.gaia_depth.prepare",lambda *_:data)
    monkeypatch.setattr(queue,"prepare_capture",lambda *_:None)
    monkeypatch.setattr(queue,"prepare_journey",lambda *_:None)
    try:
        client=app.test_client()
        with client.session_transaction() as session:
            session["admin"]=True;session["csrf"]="test"
        headers={"X-CSRF-Token":"test"}
        report=client.get("/api/admin/objects/NGC_7000/gaia-depth")
        assert report.status_code==200 and report.json["matched"]==2
        preview=client.post("/api/admin/objects/NGC_7000/preview",headers=headers,json={"method":"gaia"})
        assert preview.status_code==200 and preview.mimetype=="image/jpeg"
        response=client.post("/api/admin/objects/NGC_7000/render",headers=headers,json={"method":"gaia","duration":4,"resolution":720})
        assert response.status_code==202
        job=response.json["job"]
        queue.futures[job["id"]].result(timeout=30)
        done=store.get("jobs",job["id"])
        assert done["status"]=="completed"
        assert store.get("objects",record["id"])["render"]["gaia"]["matched"]==2
    finally:
        queue.shutdown()


def test_stars_stop_with_camera_at_constrained_image_edge():
    raw,data=inputs()
    scene=Scene(raw,Parameters(method="gaia",orientation="original",depth=1.5),stellar_depth=data)
    pose=(0,-.25,2,.35)
    first=scene.gaia_frame(0,200,pose)
    second=scene.gaia_frame(0,400,pose)
    np.testing.assert_allclose(first,second,atol=1e-6)


def test_local_interpolation_rejects_mixed_depths_and_extrapolation():
    from astroweb.gaia_depth import local_estimates
    centers=np.array([[0,0],[114,74],[126,74],[126,86],[114,86],[120,80]],float)
    boxes=np.tile([0,0,1,1,1],(6,1))
    stars=np.ones((160,240,3),np.uint16)
    measured=[(i,{"distance_pc":100+i,"source_id":str(i)}) for i in range(1,5)]
    estimate=local_estimates(measured,np.arange(1,6),centers,boxes,stars,240,160)
    assert len(estimate)==1 and estimate[0][0]==5 and estimate[0][1]["estimated"]
    assert 100<estimate[0][1]["distance_pc"]<105
    centers[5]=[180,80]
    assert not local_estimates(measured,np.arange(1,6),centers,boxes,stars,240,160)
    centers[5]=[120,80]
    measured[0][1]["distance_pc"]=1
    measured[1][1]["distance_pc"]=1000
    assert not local_estimates(measured,np.arange(1,6),centers,boxes,stars,240,160)


def test_zoom_target_travel_drives_parallax_without_an_orbit():
    raw,data=inputs()
    scene=Scene(raw,Parameters(method="gaia",orientation="original",depth=1.5,
                               pan_x=0,pan_y=0),stellar_depth=data)
    pose=(.15,-.1,1,.2)
    moving=scene.gaia_frame(0,0,pose)
    factors=[p["factor"] for p in scene.gaia_sprites]
    for sprite in scene.gaia_sprites:sprite["factor"]=1
    same_plane=scene.gaia_frame(0,0,pose)
    assert np.max(np.abs(moving-same_plane))>.1
    for sprite,factor in zip(scene.gaia_sprites,factors):sprite["factor"]=factor
    scene.params.depth=0
    no_depth=scene.gaia_frame(0,0,pose)
    for sprite in scene.gaia_sprites:sprite["factor"]=1
    np.testing.assert_allclose(no_depth,scene.gaia_frame(0,0,pose),atol=1e-6)
