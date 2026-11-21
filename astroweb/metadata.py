"""Curated starting records plus optional, cached, attributed NASA enrichment."""
import copy
import html
import math
import os
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import requests
from . import external_http
from .catalogue import canonical, catalogue_labels, name_key

from .store import now
from .solar import BODIES,body_metadata

NASA_NGC = "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/caldwell-20/"
NASA_IC = "https://science.nasa.gov/photojournal/blowin-in-the-stellar-wind/"
NASA_M45 = "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-45/"

SEEDS = {
    "M_45": {
        "target": "M 45",
        "name": {"nl":"Plejaden","en":"Pleiades"},
        "aliases": ["M 45","Messier 45","Plejaden","Pleiades","Zevengesternte","Seven Sisters","Melotte 22","Cl Melotte 22","Collinder 42"],
        "type": {"nl":"Open sterrenhoop","en":"Open star cluster"},
        "constellation": {"nl":"Stier","en":"Taurus"},
        "summary": {"nl":"De Plejaden, ook het Zevengesternte, zijn een open sterrenhoop in de Stier op ongeveer 445 lichtjaar.",
                    "en":"Also called the Seven Sisters, the Pleiades are an open star cluster in Taurus about 445 light-years away."},
        "description": {
            "nl":"Een handvol heldere, blauwachtige sterren bepaalt het bekende patroon. De open sterrenhoop bevat veel meer, zwakkere leden. Op lang belichte foto’s zie je rond enkele heldere sterren stofwolken die hun licht weerkaatsen, zoals bij Merope.",
            "en":"A handful of bright, blue-white stars make the familiar pattern. The cluster contains many fainter members. Long exposures reveal dust reflecting the light of some bright stars, including Merope.",
        },
        "sources": [
            {"label":"NASA · Messier 45","url":NASA_M45},
            {"label":"Wikipedia · Zevengesternte","url":"https://nl.wikipedia.org/wiki/Zevengesternte"},
            {"label":"Wikipedia · Pleiades","url":"https://en.wikipedia.org/wiki/Pleiades"},
        ],
    },
    "M_31": {
        "target":"M31", "aliases":["M31","M 31","Messier 31","NGC 224","Andromeda Galaxy","Andromedastelsel"],
        "name":{"nl":"Andromedastelsel","en":"Andromeda Galaxy"},
        "type":{"nl":"Spiraalstelsel","en":"Spiral galaxy"}, "constellation":{"nl":"Andromeda","en":"Andromeda"},
        "summary":{"nl":"Op ongeveer 2,5 miljoen lichtjaar ligt M31, het dichtstbijzijnde grote spiraalstelsel bij de Melkweg.",
                   "en":"About 2.5 million light-years away, M31 is the nearest large spiral galaxy to the Milky Way."},
        "description":{"nl":"We kijken schuin op de schijf van Andromeda. De heldere kern ligt tussen banen van stof die het licht van achterliggende sterren tegenhouden. M31 en de Melkweg behoren tot de Lokale Groep. M32 en M110 zijn twee kleinere begeleiders van Andromeda.",
                       "en":"We see Andromeda’s disc at an angle. Dark dust lanes block the light of stars behind them around the bright central bulge. M31 and the Milky Way belong to the Local Group. M32 and M110 are two smaller companions of Andromeda."},
        "sources":[{"label":"NASA · Messier 31","url":"https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-31/"},
                   {"label":"ESA · M31, the Andromeda Galaxy","url":"https://www.esa.int/media/m31-the-andromeda-galaxy"}],
    },
    "NGC_7000": {
        "target": "NGC 7000", "type": {"nl": "Emissienevel", "en": "Emission nebula"},
        "name": {"nl": "Noord-Amerikanevel", "en": "North America Nebula"},
        "constellation": {"nl": "Zwaan", "en": "Cygnus"},
        "summary": {"nl": "Gloeiend waterstof en donkere stofwolken tekenen een kosmische kustlijn in het sterrenbeeld Zwaan.", "en": "Glowing hydrogen and dark dust clouds trace a cosmic coastline in the constellation Cygnus."},
        "description": {
            "nl": "NGC 7000 dankt zijn bijnaam aan de opvallende vorm die op het Noord-Amerikaanse continent lijkt. Het is een uitgestrekt gebied van gas en stof waarin nieuwe sterren ontstaan. Hete jonge sterren laten het omringende gas oplichten, terwijl dichte stofwolken een deel van dat licht tegenhouden. De donkere insnijding die aan de Golf van Mexico doet denken, maakt de vorm bijzonder herkenbaar. De nevel staat aan de hemel in de buurt van Deneb. De kleuren van deze foto hangen samen met de opnamefilters en de beeldbewerking.",
            "en": "NGC 7000 takes its nickname from its striking resemblance to the North American continent. It is an extensive region of gas and dust where new stars are forming. Hot young stars illuminate the surrounding gas, while dense dust clouds obscure some of its light. A dark indentation resembling the Gulf of Mexico makes the outline especially recognizable. The nebula lies near Deneb in our sky. The colors of this photograph depend on its imaging filters and processing."
        },
        "sources": [{"label": "NASA · Caldwell 20", "url": NASA_NGC}],
        "aliases": ["NGC 7000", "North America Nebula", "Caldwell 20"],
    },
    "IC_1848": {
        "target": "IC 1848",
        "name": {"nl": "Zielnevel", "en": "Soul Nebula"},
        "type": {"nl": "Emissienevel en sterrenhoop", "en": "Emission nebula and star cluster"},
        "constellation": {"nl": "Cassiopeia", "en": "Cassiopeia"},
        "aliases": ["IC 1848", "Zielnevel", "Soul Nebula", "Embryonevel", "Embryo Nebula", "W5", "Westerhout 5"],
        "summary": {"nl": "De Zielnevel (W5) is een stervormingsgebied in Cassiopeia. Binnen het nevelgebied ligt de jonge open sterrenhoop IC 1848.",
                    "en": "The Soul Nebula (W5) is a star-forming region in Cassiopeia. The young open cluster IC 1848 lies within it."},
        "description": {
            "nl": "Sterrenwind en ultraviolette straling van jonge, hete sterren hebben holtes uitgesleten in het omringende gas en stof. Dichtere delen blijven langer staan en vormen zuilen. De naam IC 1848 wordt ook vaak gebruikt voor foto's van het bredere nevelgebied.",
            "en": "Stellar winds and ultraviolet radiation from young, hot stars have carved cavities into the surrounding gas and dust. Denser regions erode more slowly, forming pillars. The name IC 1848 is also often used for photographs of the larger nebula.",
        },
        "sources": [
            {"label": "NASA/JPL · Soul Nebula", "url": "https://www.jpl.nasa.gov/images/pia13014-soul-nebula/"},
            {"label": "CDS/SIMBAD · IC 1848", "url": "https://simbad.harvard.edu/simbad/sim-id?Ident=IC+1848"},
        ],
    },
    "NGC_6888": {
        "target": "NGC 6888",
        "name": {"nl": "Sikkelnevel", "en": "Crescent Nebula"},
        "type": {"nl": "Emissienevel", "en": "Emission nebula"},
        "constellation": {"nl": "Zwaan", "en": "Cygnus"},
        "aliases": ["NGC 6888", "Caldwell 27", "C 27", "Sikkelnevel", "Crescent Nebula"],
        "summary": {"nl": "De Sikkelnevel is een gloeiende gasschil rond de Wolf-Rayetster WR 136 in het sterrenbeeld Zwaan.",
                    "en": "The Crescent Nebula is a glowing shell of gas around the Wolf–Rayet star WR 136 in Cygnus."},
        "description": {
            "nl": "De snelle sterrenwind van WR 136 botst op materiaal dat de ster eerder uitstootte. Deze botsing vormt een uitdijende schil. Op diepe opnamen zijn fijne gasfilamenten langs de rand en een zwakkere schil rond de heldere sikkel te zien.",
            "en": "The fast stellar wind from WR 136 collides with material the star shed earlier, driving an expanding shell. Deep exposures reveal fine gas filaments along the edge and a fainter shell around the bright crescent.",
        },
        "sources": [
            {"label": "NASA · Caldwell 27", "url": "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/caldwell-27/"},
            {"label": "Wikipedia · NGC 6888", "url": "https://nl.wikipedia.org/wiki/NGC_6888"},
        ],
    },
    "NGC_6992": {
        "target": "NGC 6992",
        "type": {"nl": "Supernovarest", "en": "Supernova remnant"},
        "name": {"nl": "Oostelijke Sluiernevel · NGC 6992", "en": "Eastern Veil Nebula · NGC 6992"},
        "constellation": {"nl": "Zwaan", "en": "Cygnus"},
        "summary": {"nl": "Fijne gasdraden tekenen de oostelijke boog van een oude supernovarest in de Zwaan.",
                    "en": "Fine filaments trace the eastern arc of an old supernova remnant in Cygnus."},
        "description": {"nl": "NGC 6992 is een deel van de oostelijke Sluiernevel. De uitdijende schokgolf van een supernova raakt hier interstellair gas en laat dunne draden oplichten. NASA beschrijft de oostelijke boog als Caldwell 33. Die omvat ook het naburige gebied NGC 6995. Samen met de westelijke boog maken ze deel uit van de veel grotere Cygnus Loop.",
                        "en": "NGC 6992 is part of the Eastern Veil Nebula. Here the expanding shock wave of a supernova encounters interstellar gas, lighting up thin filaments. NASA lists the eastern arc as Caldwell 33, which also includes neighbouring NGC 6995. The eastern and western arcs belong to the much larger Cygnus Loop."},
        "aliases": ["NGC 6992", "NGC6992"],
        "sources": [
            {"label": "NASA · NGC 6992", "url": "https://science.nasa.gov/image-article/apod-2009-december-1-ngc-6992-filaments-of-the-veil-nebula/"},
            {"label": "NASA · Caldwell 33", "url": "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/caldwell-33/"},
            {"label": "ESA/Hubble · Cygnus Loop", "url": "https://esahubble.org/news/heic0006/"},
            {"label": "CDS/SIMBAD · NGC 6992", "url": "https://simbad.cds.unistra.fr/simbad/sim-id?Ident=NGC+6992"}
        ],
    },
    "IC_1396": {
        "target":"IC 1396", "type":{"nl":"Emissienevel en sterrenhoop","en":"Emission nebula and star cluster"},
        "name":{"nl":"IC 1396 · Het gebied van de Slurfnevel","en":"IC 1396 · The Elephant’s Trunk region"},
        "constellation":{"nl":"Cepheus","en":"Cepheus"},
        "summary":{"nl":"In Cepheus omlijst lichtgevend gas de donkere stofwolken van IC 1396.","en":"In Cepheus, glowing gas surrounds the dark clouds of IC 1396."},
        "description":{"nl":"IC 1396 is een stervormingsgebied in Cepheus. Straling van hete sterren laat het omringende gas oplichten. De Slurfnevel, ook IC 1396A genoemd, is een langgerekte, dichte wolk binnen dit grotere complex.",
                       "en":"IC 1396 is a star-forming region in Cepheus. Radiation from hot stars lights up the surrounding gas. The Elephant’s Trunk, also called IC 1396A, is an elongated dense cloud within this larger complex."},
        "aliases":["IC 1396","IC1396"], "sources":[{"label":"NASA · IC 1396","url":"https://science.nasa.gov/image-article/apod-2017-july-20-ic-1396-emission-nebula-in-cepheus/"},{"label":"NASA/JPL · IC 1396A","url":NASA_IC}]
    },
    "HIP_106890": {
        "target": "IC 1396", "type": {"nl": "Emissienevel en stof", "en": "Emission nebula & dust"},
        "name": {"nl": "Het gebied van de Slurfnevel", "en": "The Elephant’s Trunk region"},
        "constellation": {"nl": "Cepheus", "en": "Cepheus"},
        "summary": {"nl": "Donkere stofstructuren steken af tegen het lichtgevende gas van IC 1396 in Cepheus.", "en": "Dark dust structures stand out against the glowing gas of IC 1396 in Cepheus."},
        "description": {
            "nl": "De Slurfnevel is een dichte wolk van gas en stof in het grotere stervormingsgebied IC 1396. Het licht en de sterrenwind van zware sterren vormen de karakteristieke randen en structuren. Dichte delen van de wolk kunnen zich tegen die straling beschermen en nieuwe sterren bevatten. HIP_106890 is hier het oorspronkelijke opnamelabel uit de telescoopworkflow: een HIP-nummer verwijst naar een ster, niet naar de volledige nevel. Het informatiedoel voor deze opname is daarom apart ingesteld op IC 1396. Zonder plate solving is de precieze kadrering niet bevestigd.",
            "en": "The Elephant’s Trunk is a dense cloud of gas and dust within the larger IC 1396 star-forming region. Radiation and stellar winds from massive stars sculpt its distinctive rims and structures. Dense areas can shield themselves from that radiation and contain young stars. HIP_106890 is retained here as the original capture label from the telescope workflow: a HIP number identifies a star, not the whole nebula. The information target for this capture is therefore set separately to IC 1396. The exact framing has not been confirmed by plate solving."
        },
        "sources": [{"label": "NASA / JPL · IC 1396", "url": NASA_IC}],
        "aliases": ["IC 1396", "Elephant's Trunk", "Elephant Trunk"],
    },
}


def known_target(name):
    if seed := SEEDS.get(canonical(name)):
        return seed
    normalize = lambda v: re.sub(r"[\s_-]+", "", v).casefold()
    return next((seed for seed in SEEDS.values() if any(normalize(name) == normalize(alias)
                for alias in [seed["target"], *seed["aliases"]])), None)


def initial_metadata(identifier):
    if identifier in BODIES:
        return {**body_metadata(identifier), "updated_at":now()}
    seed = known_target(identifier)
    if seed:
        result = copy.deepcopy(seed)
        result["translation"] = "curated"
    else:
        name = identifier.replace("_", " ")
        result = {
            "target": name, "name": {"nl": name, "en": name}, "type": {"nl": "Deep-skyobject", "en": "Deep-sky object"},
            "constellation": {"nl": "", "en": ""},
            "summary": {"nl": "Een eigen blik op het diepe heelal.", "en": "A personal view of the deep sky."},
            "description": {"nl": "Er is nog geen gecontroleerde Nederlandse objectbeschrijving. De beheerder kan broninformatie ophalen en de tekst aanvullen.", "en": "A verified object description has not yet been added. The administrator can fetch source information and edit the text."},
            "sources": [], "aliases": [name], "translation": "pending",
        }
        if entry := catalogue_labels().get(canonical(identifier)):
            result["name"].update(nl=entry.get("nl",name),en=entry.get("en",name))
            result["aliases"]=list(dict.fromkeys([name,*result["name"].values(),*entry.get("aliases",[])]))
            if entry.get("source"):
                result["sources"]=[{"label":entry["id"],"url":entry["source"]}]
    result["updated_at"] = now()
    return result


def use_catalogue_metadata(metadata):
    """Upgrade generated labels without replacing operator-authored text."""
    result = copy.deepcopy(metadata)
    target = result["target"]
    known = known_target(target)
    generic = all(name_key(v)==name_key(target) for v in result["name"].values())
    translation = result.get("translation")
    lookup_only = (result.get("external") or {}).get("provider") == "CDS/SIMBAD"
    needs_description = known and (translation == "pending" or lookup_only)
    if translation != "admin" and (needs_description or (generic and (known or canonical(target) in catalogue_labels()))):
        # Older records can have a catalogue name with only a coordinate lookup.
        current = initial_metadata(canonical(target))
        result["name"] = current["name"]
        if known:
            for field in ("type","constellation","summary","description","translation"):
                result[field] = current[field]
        result["sources"]=list({s["url"]:s for s in result.get("sources",[])+current["sources"]}.values())
    return result


def renamed_metadata(identifier):
    result = initial_metadata(identifier)
    if identifier in SEEDS or identifier in BODIES:
        return result
    try:
        result = refresh_metadata(result)
    except (requests.RequestException, ValueError):
        return result
    external = result["external"]
    for language, text in external["text"].items():
        if text:
            result["description"][language] = text
            result["summary"][language] = text.split(". ",1)[0][:300]
    result["translation"] = external["translation"]
    return result


def validate_metadata(raw):
    if not isinstance(raw, dict):
        raise ValueError("invalid_metadata")
    result = {}
    for key in ["name", "type", "constellation", "summary", "description"]:
        value = raw.get(key)
        if not isinstance(value, dict) or set(value) != {"nl", "en"}:
            raise ValueError("invalid_metadata")
        maximum = 5000 if key == "description" else 350
        if any(not isinstance(t, str) or len(t) > maximum for t in value.values()):
            raise ValueError("invalid_metadata")
        result[key] = {language: text.strip() for language, text in value.items()}
    target = raw.get("target", "")
    if not isinstance(target, str) or not target.strip() or not re.fullmatch(r"[A-Za-z0-9 _+.'-]{1,100}", target):
        raise ValueError("invalid_metadata")
    result["target"] = target.strip()
    distance = raw.get("galactic_distance_ly")
    if distance is not None:
        if isinstance(distance, bool) or not isinstance(distance, (float, int)) or not math.isfinite(distance) or distance <= 0:
            raise ValueError("invalid_metadata")
        result["galactic_distance_ly"] = distance
    for field,source,minimum,maximum in (("distance_ly","distance_source",0,1e12),("redshift","redshift_source",0,20)):
        value = raw.get(field)
        if value is not None:
            reference = raw.get(source)
            if (isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value)
                    or not minimum<value<=maximum or not isinstance(reference,str)
                    or not re.fullmatch(r"https://[^\s<>\"']{3,1000}",reference)):
                raise ValueError("invalid_metadata")
            result[field],result[source] = value,reference
    result["aliases"] = [result["target"]]
    result["translation"] = "admin"
    result["updated_at"] = now()
    return result


def clean_text(value):
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def refresh_metadata(metadata, force=False):
    result = use_catalogue_metadata(metadata)
    external = result.get("external")
    target = result["target"]
    known = known_target(target)
    if known is SEEDS["M_31"] and result.get("translation") != "admin":
        # Upgrade generated SIMBAD-only or default records while preserving
        # operator-authored texts and their chosen target.
        for key in ("name","type","constellation","summary","description"):
            result[key] = copy.deepcopy(known[key])
        result.update(aliases=known["aliases"].copy(), translation="curated")
    if known:
        result["sources"] = list({s["url"]:s for s in result.get("sources", []) + known["sources"]}.values())
    if external and not force and not (known and external.get("provider") == "CDS/SIMBAD"):
        age = datetime.now(timezone.utc) - datetime.fromisoformat(external["fetched_at"])
        if age.days < 30:
            return result
    aliases = list(dict.fromkeys([target, *result.get("aliases", []), *(known["aliases"] if known else [])]))
    # Query additional designations, but accept a media caption only when it
    # identifies the target. Caldwell 33 is a wider region than NGC 6992.
    queries = list(aliases)
    if known is SEEDS["NGC_6992"]:
        queries.extend(["Eastern Veil Nebula", "Caldwell 33"])
    external = None
    for query in queries:
        try:
            response = external_http.get("https://images-api.nasa.gov/search", params={"q": query, "media_type": "image", "page_size": 30}, headers={"User-Agent": "AstroWeb/0.1"}, timeout=(4, 12))
            response.raise_for_status()
        except requests.RequestException:
            break
        matches = []
        for item in response.json().get("collection", {}).get("items", []):
            data = next(iter(item.get("data", [])), {})
            text = clean_text(data.get("title", "") + " " + data.get("description", ""))
            score = sum(bool(re.search(r"(?<![a-z0-9])" + re.escape(alias).replace(r"\ ", r"\s*") + r"(?![a-z0-9])", text, re.I)) for alias in aliases)
            if score and data.get("nasa_id") and data.get("description"):
                matches.append((score, data))
        if matches:
            data = max(matches, key=lambda item: item[0])[1]
            external = {"provider":"NASA Image and Video Library", "title":clean_text(data.get("title","")),
                        "text":{"en":clean_text(data["description"])[:3000], "nl":""},
                        "credit":data.get("photographer") or data.get("secondary_creator") or data.get("center","NASA"),
                        "url":"https://images.nasa.gov/details/"+requests.utils.quote(data["nasa_id"],safe="")}
            break
    if external is None and known:
        # Local, bilingual editorial summary with the relevant primary source.
        external = {"provider":"NASA Science", "title":known["name"]["en"], "text":copy.deepcopy(known["summary"]),
                    "credit":"AstroWeb · NASA Science", "url":known["sources"][0]["url"]}
    if external is None:
        url = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/S?"+requests.utils.quote(target, safe="")
        response = external_http.get(url, timeout=(4,12))
        response.raise_for_status()
        try:
            resolver = ET.fromstring(response.content).find(".//Resolver")
        except ET.ParseError as exc:
            raise requests.RequestException("Invalid Sesame response") from exc
        if resolver is None or not resolver.findtext("oname"):
            raise ValueError("metadata_not_found")
        name = resolver.findtext("oname")
        ra, dec = resolver.findtext("jradeg"), resolver.findtext("jdedeg")
        position = f" (ICRS {float(ra):.5f}°, {float(dec):+.5f}°)" if ra and dec else ""
        external = {"provider":"CDS/SIMBAD", "title":name, "text":{"en":f"Catalogue identification: {name}{position}.",
                    "nl":f"Catalogusidentificatie: {name}{position}."}, "credit":"CDS, Strasbourg",
                    "url":"https://simbad.cds.unistra.fr/simbad/sim-id?Ident="+requests.utils.quote(name,safe="")}
    result["external"] = external
    external.update(fetched_at=now(), translation="curated" if external["text"]["nl"] else "unavailable")
    description = external["text"]["en"]
    translate_url = os.environ.get("ASTROWEB_TRANSLATE_URL", "").rstrip("/")
    if translate_url and description and not external["text"]["nl"]:
        try:
            translated = external_http.post(translate_url + "/translate", json={"q": description, "source": "en", "target": "nl", "format": "text", "api_key": os.environ.get("ASTROWEB_TRANSLATE_KEY", "")}, timeout=(5, 60))
            translated.raise_for_status()
            value = translated.json().get("translatedText", "")
            if isinstance(value, str) and value.strip():
                result["external"]["text"]["nl"] = value.strip()[:6000]
                result["external"]["translation"] = "machine"
        except (requests.RequestException, ValueError):
            result["external"]["translation"] = "failed"
    return result
