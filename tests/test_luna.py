import json

import pytest

from astroweb import luna
from astroweb.metadata import initial_metadata, repair_source_endings
from astroweb.prose import excerpt, summary_for
from astroweb.store import Store


def test_legacy_truncation_keeps_complete_sentences_and_manual_edits():
    text = "De nevel staat op 1.5 kpc. Dr. Janssen beschreef de heldere rand. De oorsprong is…"
    assert (
        excerpt(text, 5000)
        == "De nevel staat op 1.5 kpc. Dr. Janssen beschreef de heldere rand."
    )
    assert (
        summary_for("Dr. Janssen zag de rand. De wolk straalt.", "")
        == "Dr. Janssen zag de rand."
    )
    assert (
        excerpt("First paragraph.\n\nSecond paragraph.", 4000)
        == "First paragraph.\n\nSecond paragraph."
    )
    meta = initial_metadata("IC_63")
    meta["description"].update(nl=text, en="An intentional ending…")
    meta["edited_fields"] = ["description.en"]
    meta["external"] = {"text": {"nl": text}}
    clean = repair_source_endings(meta)
    assert (
        clean["description"]["nl"]
        == clean["external"]["text"]["nl"]
        == excerpt(text, 5000)
    )
    assert clean["description"]["en"] == "An intentional ending…"


def test_opt_in_source_proposal_cache_and_conflict(tmp_path, monkeypatch):
    store = Store(tmp_path)
    meta = initial_metadata("IC_63")
    meta["edited_fields"] = ["description.nl"]
    store.put("objects", "a", {"metadata": meta})
    monkeypatch.delenv("ASTROWEB_OFFLINE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    calls = []

    def mock(**payload):
        calls.append(payload)
        return [
            {
                "text": json.dumps(
                    {
                        "en": {
                            "description": "Radiation gradually erodes the cloud.",
                            "sources": [0],
                        }
                    }
                )
            }
        ]

    monkeypatch.setattr(luna, "response", mock)
    draft = luna.proposal(store, meta, False, expand=True)
    assert list(draft["changes"]) == ["en"]
    assert draft["changes"]["en"]["description"].startswith(
        meta["description"]["en"] + "\n\n"
    )
    assert luna.proposal(store, meta, False, expand=True) == draft and len(calls) == 1
    assert store.get("objects", "a")["metadata"] == meta
    original = luna.fingerprint(meta)
    saved = luna.apply(store, "a", original, draft)
    assert saved["description"]["nl"] == meta["description"]["nl"]
    assert saved["luna"]["sources"] == draft["sources"]
    with pytest.raises(ValueError, match="metadata_changed"):
        luna.apply(store, "a", original, draft)
    monkeypatch.setenv("ASTROWEB_OFFLINE", "1")
    assert not luna.configured()


def test_web_sources_keep_only_citations_from_allowed_domains(monkeypatch):
    monkeypatch.setattr(
        luna,
        "response",
        lambda **_: [
            {
                "text": "IC 63 scatters light.",
                "annotations": [
                    {
                        "type": "url_citation",
                        "url": "https://esahubble.org/images/heic1818a/",
                        "title": "IC 63",
                        "start_index": 6,
                    },
                    {
                        "type": "url_citation",
                        "url": "https://eso.org.example.net/",
                        "start_index": 6,
                    },
                ],
            }
        ],
    )
    assert [ref["url"] for ref in luna.web_evidence("IC 63")] == [
        "https://esahubble.org/images/heic1818a/"
    ]


def test_guide_only_saves_sourced_bilingual_explanations(tmp_path, monkeypatch):
    from astroweb import luna_guide as guide

    store = Store(tmp_path)
    point = {
        "id": "IC 1396A",
        "name": {"en": "Elephant's Trunk"},
        "type": {"en": "Nebula"},
    }
    source = {
        "url": "https://science.nasa.gov/nebula/?utm_source=openai",
        "label": "NASA",
        "text": "A dense cloud in IC 1396.",
    }
    monkeypatch.setattr(luna, "web_evidence", lambda _: [source])
    monkeypatch.setattr(
        guide,
        "structured",
        lambda *_: {
            "text": {"nl": "Een dichte wolk.", "en": "A dense cloud."},
            "sources": [0],
        },
    )
    draft = guide.prepare_explanation(store, point)
    assert draft["sources"] == [
        {"url": "https://science.nasa.gov/nebula/", "label": "NASA"}
    ]
    guide.attach_explanations(store, [point])
    assert point["guide"] == draft
    assert guide.explanation(store, dict(point, id="IC 1396")) is None


def test_route_uses_catalogue_coordinates_and_rejects_invented_indexes(
    tmp_path, monkeypatch
):
    from astroweb import autozoom, luna_guide as guide

    store = Store(tmp_path)
    point = {
        "id": "M31",
        "name": {"nl": "Andromeda", "en": "Andromeda"},
        "type": {"en": "Galaxy"},
        "x": 0.11,
        "y": 0.79,
    }
    monkeypatch.setattr(
        autozoom, "discover", lambda *_a, **_kw: {"kind": "wcs", "objects": [point]}
    )
    note = {"nl": "De kern.", "en": "The nucleus."}
    monkeypatch.setattr(
        guide, "structured", lambda *_: {"stops": [{"index": 1, "note": note}]}
    )
    record = {"metadata": {"target": "M31"}}
    with pytest.raises(ValueError, match="lunaUnavailable"):
        autozoom.luna_route(store, record, 1)
    monkeypatch.setattr(
        guide, "structured", lambda *_: {"stops": [{"index": 0, "note": note}]}
    )
    assert autozoom.luna_route(store, record, 1)["points"][0] == {
        "name": "M31",
        "label": point["name"],
        "x": 0.11,
        "y": 0.79,
        "zoom": 2.1,
        "kind": "catalog",
        "note": note,
    }


def test_archive_rank_keeps_new_fields_and_skymap(tmp_path):
    from astroweb import luna_guide as guide

    store = Store(tmp_path)
    record = {"id": "M31", "metadata": {"target": "M31"}, "sha256": {"final": "own"}}
    fields = [{"id": "skymap-m31"}, {"id": "first"}, {"id": "second"}, {"id": "new"}]
    note = {"nl": "Een deelgebied.", "en": "A subregion."}
    store.put(
        "settings",
        guide.archive_key(record),
        {"order": [{"id": "second", "note": note}]},
    )
    saved = guide.archive_options(store, record, fields)
    assert [item["id"] for item in saved] == ["skymap-m31", "second", "first", "new"]
    assert saved[1]["guide_note"] == note and "guide_note" not in fields[2]
