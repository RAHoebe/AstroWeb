import pytest
from PIL import Image
from astroweb import hst_archive
from astroweb.hubble import eligible
from astroweb.media import import_object,normalize_id
from astroweb.physical import field_scale
from astroweb.render import Scene,Parameters
from astroweb.store import Store


def test_archive_filter_only_offers_real_optical_imaging_products():
    for name in ("hst_09080_01_wfpc2_f656n_wf","hst_11657_70_wfc3_uvis_f502n"):
        assert hst_archive.FIELD_ID.fullmatch(name)
    for name in ("hst_09080_01_wfpc2_total_wf","hst_01234_01_wfc3_ir_g141","../drz.fits"):
        assert not hst_archive.FIELD_ID.fullmatch(name)
    assert eligible({"metadata":{"target":"a future nebula"},"gaia":{"corners":[[1,2]]}})
    assert not eligible({"metadata":{"target":"an unregistered field"}})


def test_solar_single_image_and_observing_distance(tmp_path):
    store=Store(tmp_path/"lib")
    original=tmp_path/"disk.png"
    Image.new("RGB",(380,256),"orange").save(original)
    record=import_object(store,"Maan",[original],"night one")
    assert record["body"]=="MOON" and record["catalog_id"]=="MOON" and record["gaia"]["status"]=="not_applicable"
    assert normalize_id("Saturnus")=="SATURN" and normalize_id("Zon")=="SUN"
    assert list(record["assets"])==["final"] and record["params"]["method"]=="kenburns"
    frame=Scene.from_paths({"final":store.path(record["assets"]["final"])},Parameters.parse(record["params"])).frame(.5)
    assert frame.shape==(256,380,3)
    assert field_scale(store,record)["distance_ly"] is None
    record["observation"]={"date_obs":"2026-11-10T22:00:00+00:00"}
    assert 340000<field_scale(store,record)["distance_km"]<430000
    with pytest.raises(ValueError,match="single_image_required"):
        import_object(store,"Mars",[original,original])


def test_physical_axes_and_missing_scale():
    rec={"metadata":{"target":"NGC 224"},"id":"M_31","sha256":{"final":"fit"},
         "gaia":{"digest":"fit","status":"solved","corners":[[0,1],[2,1],[2,0],[0,0]]}}
    result=field_scale(None,rec)
    assert result["distance_ly"]==2500000
    assert result["width_ly"]/result["height_ly"]==pytest.approx(2,rel=.001)
    del rec["gaia"]
    assert field_scale(None,rec)["height_ly"] is None
    rec["metadata"]["target"]="unknown"
    assert field_scale(None,rec)["distance_ly"] is None

def test_hst_target_classification_distinguishes_region_and_projection():
    def relation(target,name):
        return hst_archive.field_relation({"id":target,"metadata":{"target":target}},name)
    assert relation("NGC 7000","V1057-CYG")=="region"
    assert relation("NGC 7000","ANY")=="field"
    assert relation("M31","NGC-224")=="target"
    assert relation("M1","M101")=="field"
    assert relation("IC 1396","PN-G098.2+04.9")=="field"
    assert relation("NGC 6992","CYGLOOP-NENR1")=="region"
