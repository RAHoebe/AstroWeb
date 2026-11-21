import pytest
import requests

from astroweb import wikimedia
from astroweb.catalogue import belongs,canonical
from astroweb.media import upload_identity
from astroweb.metadata import initial_metadata,use_catalogue_metadata
from astroweb.store import Store


@pytest.mark.parametrize("name", ["M 45","M045","Plejaden","Pleiades","Zevengesternte","Seven_Sisters","Cl Melotte 22","Collinder 42"])
def test_pleiades_catalogue_id_and_names_work_offline(name,monkeypatch,tmp_path):
    def refuse_network(*args,**kwargs):
        pytest.fail("a known catalogue alias must be resolved locally")
    monkeypatch.setattr(wikimedia.external_http,"get",refuse_network)
    store=Store(tmp_path)
    assert canonical(name)=="M_45"
    assert upload_identity(["stacked_final.png"],name,store=store)[:2]==("M_45","fits")
    assert belongs(name+"_starless.png","M_45")
    meta=initial_metadata(name)
    assert meta["name"]=={"nl":"Plejaden","en":"Pleiades"}
    assert meta["constellation"]=={"nl":"Stier","en":"Taurus"}


def test_generated_pleiades_title_can_be_upgraded_without_changing_archive_names():
    original=dict(target="M 45",aliases=["M 45"],name={"nl":"M 45","en":"M 45"},
                  translation="curated",description={"nl":"Catalogusidentificatie","en":"Catalogue identification"},
                  external={"provider":"CDS/SIMBAD","title":"Cl Melotte 22"})
    repaired=use_catalogue_metadata(original)
    assert repaired["name"]["nl"]=="Plejaden" and repaired["aliases"]==original["aliases"]
    assert repaired["external"]==original["external"]
    assert "Zevengesternte" in repaired["summary"]["nl"]
    edited=dict(original,translation="admin",name={"nl":"Eigen titel","en":"Custom title"})
    assert use_catalogue_metadata(edited)==edited


def response(data):
    class Reply:
        def raise_for_status(self):
            pass
        def json(self):
            return data
    return Reply()


def claim(value):
    return {"mainsnak":{"datavalue":{"value":value}}}


def test_wikipedia_title_requires_astronomical_id_and_caches_recognition(tmp_path,monkeypatch):
    store=Store(tmp_path)
    calls=[]
    entity={"id":"Q123", "claims":{"P3083":[claim("Cl Instrument 5")],"P528":[claim("NGC 1788")]},
            "labels":{"en":{"value":"Catalogue Example"}}, "sitelinks":{"enwiki":{"title":"Catalogue Example"}}}
    def get(url,**kwargs):
        assert url==wikimedia.API and kwargs["params"]["action"]=="wbgetentities"
        assert kwargs["params"]["titles"]=="Catalogue Example"
        calls.append(kwargs["params"]["sites"])
        return response({"success":1,"entities":{"Q123":entity}})
    monkeypatch.setattr(wikimedia.external_http,"get",get)
    assert upload_identity(["generic_final.png"],"Catalogue Example",store=store)==("NGC_1788","wiki",None)
    meta=wikimedia.add_metadata(store,initial_metadata("NGC_1788"),"Catalogue Example")
    assert meta["name"]=={"nl":"NGC 1788","en":"Catalogue Example"}
    assert meta["sources"][-1]["url"]=="https://en.wikipedia.org/wiki/Catalogue_Example"
    assert calls==["nlwiki"]
    entity["claims"].pop("P3083")
    assert wikimedia.read_identity(entity) is None


def test_wikipedia_failure_uses_filename_and_is_not_cached(tmp_path,monkeypatch):
    store=Store(tmp_path)
    calls=[]
    def unavailable(*args,**kwargs):
        calls.append(1)
        raise requests.Timeout
    monkeypatch.setattr(wikimedia.external_http,"get",unavailable)
    for _ in range(2):
        assert upload_identity(["Orion_Nebula_final.png"],"Unknown title",store=store)==("M_42","prefix","M_42")
    assert len(calls)==2
