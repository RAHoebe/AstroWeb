import pytest
import requests

from astroweb import wikimedia
from astroweb.catalogue import belongs,canonical,catalogue_labels
from astroweb.media import upload_identity
from astroweb.metadata import initial_metadata,refresh_metadata,use_catalogue_metadata
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


@pytest.mark.parametrize("name",["IC 1848","IC1848","Zielnevel","Soul Nebula","Embryonevel"])
def test_soul_nebula_has_an_offline_identity_and_description(name,tmp_path,monkeypatch):
    monkeypatch.setenv("ASTROWEB_OFFLINE","1")
    assert canonical(name)=="IC_1848"
    assert upload_identity(["preview_final.png"],name,store=Store(tmp_path))[:2]==("IC_1848","fits")
    assert catalogue_labels()["IC_1848"]["type"]=="Cl+N"
    metadata=refresh_metadata(initial_metadata(name))
    assert metadata["name"]=={"nl":"Zielnevel","en":"Soul Nebula"}
    assert "open sterrenhoop IC 1848" in metadata["summary"]["nl"]
    assert metadata["external"]["url"]=="https://www.jpl.nasa.gov/images/pia13014-soul-nebula/"


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


def test_fireworks_uses_dutch_catalogue_text_with_an_english_only_caption(tmp_path,monkeypatch):
    monkeypatch.setenv("ASTROWEB_OFFLINE","1")
    assert upload_identity(["field_final.png"],"Vuurwerkstelsel",store=Store(tmp_path))[:2]==("NGC_6946","fits")
    metadata=initial_metadata("NGC_6946")
    metadata.update(name={"nl":"NGC 6946","en":"Fireworks Galaxy"},translation="unavailable",
                    external={"provider":"NASA Image and Video Library","fetched_at":metadata["updated_at"],
                              "text":{"nl":"","en":"Public NASA caption."}})
    repaired=refresh_metadata(metadata)
    assert repaired["name"]["nl"]=="Vuurwerkstelsel" and repaired["translation"]=="curated"
    assert "supernova" in repaired["summary"]["nl"] and repaired["external"]==metadata["external"]
    assert initial_metadata("NGC_6939")["type"]["nl"]=="Open sterrenhoop"


def test_wikipedia_leads_are_language_specific_and_match_the_wikidata_item(tmp_path,monkeypatch):
    identity={"identifier":"NGC_1788","name":{"en":"Catalogue Example"},"sources":[
        {"label":"Wikidata","url":"https://www.wikidata.org/wiki/Q123"},
        {"label":"Wikipedia NL","url":"https://nl.wikipedia.org/wiki/NGC_1788"},
        {"label":"Wikipedia EN","url":"https://en.wikipedia.org/wiki/NGC_1788"}]}
    monkeypatch.setattr(wikimedia,"lookup",lambda *_:identity)
    def fetch(url,**kwargs):
        correct=url.startswith("https://nl.")
        return response({"query":{"pages":[{"pageprops":{"wikibase_item":"Q123" if correct else "Q456"},
                          "extract":"Nederlandse catalogusbeschrijving." if correct else "Unrelated English text."}]}})
    monkeypatch.setattr(wikimedia.external_http,"get",fetch)
    metadata=refresh_metadata(initial_metadata("NGC_1788"),store=Store(tmp_path))
    assert metadata["external"]["text"]=={"nl":"Nederlandse catalogusbeschrijving.","en":""}
    assert metadata["external"]["provider"]=="Wikipedia / Wikidata"
    assert any("CC BY-SA" in link["label"] for link in metadata["sources"])


def test_cached_english_caption_can_be_translated_when_service_is_configured(monkeypatch):
    monkeypatch.setenv("ASTROWEB_TRANSLATE_URL","https://translate.example.org")
    def translate(url,**kwargs):
        assert url=="https://translate.example.org/translate"
        assert kwargs["json"]["q"]=="Public English description."
        return response({"translatedText":"Openbare Nederlandse beschrijving."})
    monkeypatch.setattr(wikimedia.external_http,"post",translate)
    metadata=initial_metadata("NGC_1788")
    metadata["external"]={"provider":"NASA Image and Video Library","fetched_at":metadata["updated_at"],
                          "translation":"unavailable","text":{"nl":"","en":"Public English description."}}
    translated=refresh_metadata(metadata)["external"]
    assert translated["translation"]=="machine"
    assert translated["text"]["nl"]=="Openbare Nederlandse beschrijving."


def test_catalogue_facts_and_verified_links_are_available_without_network(monkeypatch):
    monkeypatch.setenv("ASTROWEB_OFFLINE","1")
    for label in ("IC 1805","IC1805","Hartnevel","Heart Nebula"):
        assert initial_metadata(label)["name"]["nl"]=="Hartnevel"
    nebula=initial_metadata("NGC_1788")
    assert nebula["type"]["nl"]=="Reflectienevel"
    assert "Orion" in nebula["summary"]["nl"] and "boogminuten" in nebula["description"]["nl"]
    galaxy=initial_metadata("NGC_2403")
    assert "Mpc" in galaxy["description"]["en"]
    assert any("caldwell-7/" in item["url"] for item in galaxy["sources"])
    assert any("vizier" in item["url"] for item in galaxy["sources"])


def test_wikipedia_numeric_redirect_checks_catalogue_identity(tmp_path,monkeypatch):
    qid="Q33586"
    entity={"id":qid,"claims":{"P3083":[claim("IC 1805")]},"labels":{"nl":{"value":"Hartnevel"}}}
    def get(url,params,**kwargs):
        if "sites" in params:
            return response({"success":1,"entities":{}})
        if params["action"]=="query":
            assert params["redirects"]==1 and params["titles"]=="IC 1805"
            return response({"query":{"pages":[{"pageprops":{"wikibase_item":qid}}]}})
        if params["action"]=="wbsearchentities":
            return response({"search":[{"id":qid}]})
        assert params["ids"]==qid
        return response({"entities":{qid:entity}})
    monkeypatch.setattr(wikimedia.external_http,"get",get)
    assert wikimedia.lookup(Store(tmp_path/"one"),"IC1805")["name"]["nl"]=="Hartnevel"
    entity["claims"]["P3083"]=[claim("IC 1848")]
    assert wikimedia.lookup(Store(tmp_path/"two"),"IC1805") is None

def test_nasa_caption_mentioning_neighbour_is_not_used_for_heart_nebula(monkeypatch):
    def get(url,params,**kwargs):
        return response({"collection":{"items":[{"data":[{"nasa_id":"PIA13014","title":"Soul Nebula",
                         "description":"The Soul Nebula is near the Heart Nebula (IC 1805)."}]}]}})
    monkeypatch.setattr(wikimedia.external_http,"get",get)
    found=refresh_metadata(initial_metadata("IC_1805"),force=True)
    assert found["external"]["provider"]=="NASA Science"
    assert "ic-1805" in found["external"]["url"]


def test_fits_target_keywords_have_stable_precedence():
    from astroweb.observation import header_target
    assert header_target({"OBJECT":" IC 1805 ","TARGNAME":"other"})=="IC 1805"
    assert header_target({"OBJECT":" ", "TARGNAME":"M 31","OBJNAME":"IC 1805"})=="M 31"
    assert header_target({"OBJNAME":"NGC 6946"})=="NGC 6946"
