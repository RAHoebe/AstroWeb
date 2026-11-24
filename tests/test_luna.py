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
