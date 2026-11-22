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
from .catalogue import facts, fact_id, nasa_pages, TYPES, canonical, catalogue_labels, name_key

from .store import now
from .solar import BODIES,body_metadata

NASA_NGC = "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/caldwell-20/"
NASA_IC = "https://science.nasa.gov/photojournal/blowin-in-the-stellar-wind/"
NASA_M45 = "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-45/"

TEXT_FIELDS = ("name", "type", "constellation", "summary", "description")
DEFAULT_TYPE = {"nl": "Deep-skyobject", "en": "Deep-sky object"}
DEFAULT_SUMMARY = {"nl": "Een eigen blik op het diepe heelal.", "en": "A personal view of the deep sky."}
DEFAULT_DESCRIPTION = {
    "nl": "Er is nog geen gecontroleerde Nederlandse objectbeschrijving. De beheerder kan broninformatie ophalen en de tekst aanvullen.",
    "en": "A verified object description has not yet been added. The administrator can fetch source information and edit the text.",
}

SEEDS = {
    "M_57": {
        "target": "M 57",
        "name": {"nl": "Ringnevel", "en": "Ring Nebula"},
        "type": {"nl": "Planetaire nevel", "en": "Planetary nebula"},
        "constellation": {"nl": "Lier", "en": "Lyra"},
        "aliases": ["M 57", "Messier 57", "NGC 6720", "Ringnevel", "Ring Nebula"],
        "summary": {"nl": "De Ringnevel in de Lier bestaat uit oplichtend gas dat een ster aan het eind van haar leven uitstootte.",
                    "en": "The Ring Nebula in Lyra is glowing gas shed by a star near the end of its life."},
        "description": {
            "nl": "De overgebleven hete kern van de ster laat het uitgestoten gas oplichten. Vanaf de aarde zien we een heldere ring met een zwakkere buitenhalo. Webb ziet in het infrarood fijne structuren in het gas rond de ring.",
            "en": "The star’s remaining hot core illuminates the expelled gas. From Earth we see a bright ring and a fainter outer halo. In the infrared, Webb resolves fine structures in the gas around the ring.",
        },
        "sources": [
            {"label":"NASA · Messier 57","url":"https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-57/"},
            {"label":"NASA/ESA/CSA · Ring Nebula (Webb)","url":"https://science.nasa.gov/asset/webb/ring-nebula-nircam-image/"},
        ],
    },
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
    "IC_1805": {
        "target":"IC 1805", "aliases":["IC 1805","Hartnevel","Heart Nebula"],
        "name":{"nl":"Hartnevel","en":"Heart Nebula"},
        "type":{"nl":"Emissienevel en sterrenhoop","en":"Emission nebula and star cluster"},
        "constellation":{"nl":"Cassiopeia","en":"Cassiopeia"},
        "summary":{"nl":"In de Hartnevel in Cassiopeia laten jonge, hete sterren het omringende waterstofgas oplichten.",
                   "en":"Hot young stars light up hydrogen gas in the Heart Nebula in Cassiopeia."},
        "description":{"nl":"In het hart van IC 1805 ligt de open sterrenhoop Melotte 15. Straling en sterrenwinden van de zwaarste sterren vormen de randen en stofzuilen van de nevel.",
                       "en":"The open cluster Melotte 15 lies at the centre of IC 1805. Radiation and stellar winds from its massive stars sculpt the nebula’s rims and dust pillars."},
        "sources":[{"label":"NASA · IC 1805","url":"https://science.nasa.gov/image-article/apod-2019-september-11-ic-1805-the-heart-nebula/"}],
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
    "NGC_6946": {
        "target": "NGC 6946",
        "name": {"nl": "Vuurwerkstelsel", "en": "Fireworks Galaxy"},
        "type": {"nl": "Spiraalstelsel", "en": "Spiral galaxy"},
        "constellation": {"nl": "Cepheus / Zwaan", "en": "Cepheus / Cygnus"},
        "aliases": ["NGC 6946", "Caldwell 12", "C 12", "Fireworks Galaxy", "Vuurwerkstelsel",
                    "Vuurwerksterrenstelsel", "Arp 29", "UGC 11597", "PGC 65001"],
        "summary": {"nl": "Van bovenaf zien we de spiraalarmen van het Vuurwerkstelsel. De bijnaam verwijst naar de vele supernova’s die er zijn waargenomen.",
                    "en": "The nearly face-on Fireworks Galaxy shows its spiral arms. Its nickname comes from the many supernovae observed in it."},
        "description": {
            "nl": "In de spiraalarmen liggen stofbanen en gebieden waar nieuwe sterren ontstaan. Hubble brengt deze gebieden op verschillende golflengten in beeld. Webb onderzocht het stof rond de supernova’s SN 2004et en SN 2017eaw. In een breed opnameveld staat de open sterrenhoop NGC 6939 vlakbij aan de hemel. Die sterrenhoop bevindt zich in onze Melkweg, veel dichterbij dan het Vuurwerkstelsel.",
            "en": "The spiral arms contain dust lanes and regions where new stars form. Hubble images these regions at several wavelengths. Webb studied dust around the supernovae SN 2004et and SN 2017eaw. The open cluster NGC 6939 appears nearby in wide views. That cluster lies in our Milky Way, much closer than the Fireworks Galaxy.",
        },
        "sources": [
            {"label": "NASA · Caldwell 12", "url": "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/caldwell-12/"},
            {"label": "ESA · Fireworks Galaxy", "url": "https://www.esa.int/ESA_Multimedia/Images/2021/01/A_galaxy_to_take_your_breath_away"},
            {"label": "NASA · Webb en supernova’s", "url": "https://science.nasa.gov/missions/webb/webb-locates-dust-reservoirs-in-two-supernovae/"},
            {"label": "APOD Nederlands · NGC 6946 en NGC 6939", "url": "https://apod.nl/ap250704_nl.html"},
            {"label": "Wikipedia NL · NGC 6946", "url": "https://nl.wikipedia.org/wiki/NGC_6946"},
            {"label": "DeepSpace · Fireworks Galaxy", "url": "https://deepspace.to/ngc-6946-c12-fireworks-galaxy/"},
        ],
    },
    "NGC_6939": {
        "target": "NGC 6939",
        "name": {"nl": "Sterrenhoop NGC 6939", "en": "Open cluster NGC 6939"},
        "type": {"nl": "Open sterrenhoop", "en": "Open star cluster"},
        "constellation": {"nl": "Cepheus", "en": "Cepheus"},
        "aliases": ["NGC 6939", "OCL 217"],
        "summary": {"nl": "NGC 6939 is een open sterrenhoop in Cepheus. Op brede opnamen deelt hij het beeldveld met het Vuurwerkstelsel NGC 6946.",
                    "en": "NGC 6939 is an open star cluster in Cepheus. In wide photographs it shares the field with the Fireworks Galaxy, NGC 6946."},
        "description": {
            "nl": "De sterrenhoop ligt vanaf de aarde gezien ruim een halve graad ten noordwesten van NGC 6946. Op een foto vormen de sterren van de hoop een compacte groep. Het spiraalstelsel ernaast ligt veel verder weg, buiten onze Melkweg.",
            "en": "As seen from Earth, the cluster lies just over half a degree northwest of NGC 6946. Its stars form a compact group in a photograph. The nearby-looking spiral galaxy lies much farther away, beyond our Milky Way.",
        },
        "sources": [
            {"label": "NASA APOD · NGC 6946 and NGC 6939", "url": "https://apod.nasa.gov/apod/ap250704.html"},
            {"label": "APOD Nederlands · NGC 6946 en NGC 6939", "url": "https://apod.nl/ap250704_nl.html"},
            {"label": "CDS/SIMBAD · NGC 6939", "url": "https://simbad.harvard.edu/simbad/sim-id?Ident=NGC+6939"},
            {"label": "Wikipedia NL · NGC 6939", "url": "https://nl.wikipedia.org/wiki/NGC_6939"},
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
            "target": name, "name": {"nl": name, "en": name}, "type": DEFAULT_TYPE.copy(),
            "constellation": {"nl": "", "en": ""},
            "summary": DEFAULT_SUMMARY.copy(),
            "description": DEFAULT_DESCRIPTION.copy(),
            "sources": [], "aliases": [name], "translation": "pending",
        }
        if entry := catalogue_labels().get(canonical(identifier)):
            result["name"].update(nl=entry.get("nl",name),en=entry.get("en",name))
            if entry.get("type") in TYPES:
                nl, en = TYPES[entry["type"]]
                result["type"] = {"nl":nl,"en":en}
            result["aliases"]=list(dict.fromkeys([name,*result["name"].values(),*entry.get("aliases",[])]))
            if entry.get("source"):
                result["sources"]=[{"label":entry["id"],"url":entry["source"]}]
    data = facts()
    key = fact_id(identifier)
    row = data["objects"].get(key)
    if row and not seed and identifier not in BODIES:
        labels = TYPES.get(row[0])
        if labels:
            result["type"] = dict(zip(("nl","en"),labels))
        code = data["constellations"].get(row[1],row[1])
        result["constellation"] = {"nl":code,"en":code}
        result["sources"].append({"label":"OpenNGC","url":"https://github.com/mattiaverga/OpenNGC/tree/"+data["revision"]})
        designation = key.replace("_"," ")
        nl = f"{designation} staat in OpenNGC als {result['type']['nl'].lower()} in het sterrenbeeld {code}."
        en = f"OpenNGC lists {designation} in {code} ({result['type']['en'].lower()})."
        result["summary"] = {"nl":nl,"en":en}
        if article := data["wikidata"].get(key):
            for lang in ("nl","en"):
                label, brief = article[lang]
                if label and generated_placeholder("name",lang,result["name"][lang],result["target"]):
                    result["name"][lang] = label
                if brief:
                    result["summary"][lang] = brief
            result["sources"].append({"label":"Wikidata · "+article["qid"],
                                      "url":"https://www.wikidata.org/wiki/"+article["qid"]})
        if row[4]:
            size = f"{row[4]:g}" + (f" × {row[5]:g}" if row[5] else "")
            nl += " De schijnbare grootte is "+size.replace(".",",")+" boogminuten."
            en += " Its apparent size is "+size+" arcminutes."
        if row[6] is not None:
            nl += " De V-magnitude is "+format(row[6],"g").replace(".",",")+"."
            en += f" Its V magnitude is {row[6]:g}."
        if distance := data["distances"].get(key):
            nl += " De Updated Nearby Galaxy Catalog (2013) geeft een afstandsschatting van "+str(distance[0]).replace(".",",")+" Mpc."
            en += f" The Updated Nearby Galaxy Catalog (2013) gives a distance estimate of {distance[0]} Mpc."
            result["sources"].append({"label":"Karachentsev et al. · UNGC (2013)",
                                     "url":"https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/AJ/145/101"})
        result["description"] = {"nl":nl,"en":en}
    result["sources"] = list({link["url"]:link for link in result.get("sources",[])+nasa_pages().get(canonical(identifier),[])}.values())
    result["updated_at"] = now()
    return result


def generated_placeholder(field, language, value, target):
    if not value:
        return True
    if field == "name":
        return name_key(value) == name_key(target)
    defaults = {"type":DEFAULT_TYPE, "summary":DEFAULT_SUMMARY, "description":DEFAULT_DESCRIPTION}
    if value == defaults.get(field, {}).get(language):
        return True
    return field in ("summary", "description") and bool(re.fullmatch(
        r"(?:Catalogusidentificatie|Catalogue identification): [^.!?]+(?: \(ICRS [0-9.+° ,\-]+\))?\.",
        value, re.I))


def text_overrides(metadata):
    if "edited_fields" in metadata:
        return set(metadata["edited_fields"])
    if metadata.get("translation") != "admin":
        return set()
    target = metadata.get("target", "")
    generic_name = all(generated_placeholder("name", lang, value, target)
                       for lang, value in metadata.get("name", {}).items())
    # Older Studio versions marked the whole form as manual. Recover only
    # recognisable placeholders when the stored name is still the catalogue ID.
    return {f"{field}.{lang}" for field in TEXT_FIELDS for lang in ("nl", "en")
            if not generic_name or not generated_placeholder(field, lang, metadata.get(field, {}).get(lang), target)}


def use_catalogue_metadata(metadata):
    """Upgrade generated labels without replacing operator-authored text."""
    result = copy.deepcopy(metadata)
    target = result.get("target")
    if not target:
        return result
    known = known_target(target)
    label = catalogue_labels().get(canonical(target))
    if not known and not label:
        return result
    overrides = text_overrides(result)
    lookup_only = (result.get("external") or {}).get("provider") == "CDS/SIMBAD"
    refresh_generated = known and (result.get("translation") != "curated" or lookup_only)
    current = initial_metadata(canonical(target))
    changed = False
    for field in TEXT_FIELDS if known or fact_id(target) in facts()["objects"] else ("name","type"):
        for lang, text in current[field].items():
            value = result.get(field, {}).get(lang)
            if (f"{field}.{lang}" not in overrides and text != value and
                    (refresh_generated or generated_placeholder(field, lang, value, target))):
                result.setdefault(field, {})[lang] = text
                changed = True
    if changed:
        result["sources"] = list({s["url"]:s for s in result.get("sources", [])+current["sources"]}.values())
        if known and not overrides:
            result["translation"] = "curated"
    return result


def retain_metadata_edits(value, previous, same_target):
    baseline = use_catalogue_metadata(previous)
    overrides = text_overrides(previous) if same_target else set()
    overrides.update(f"{field}.{lang}" for field in TEXT_FIELDS for lang in ("nl", "en")
                     if value[field][lang] != baseline.get(field, {}).get(lang, ""))
    value["edited_fields"] = sorted(overrides)
    value["translation"] = "admin" if overrides else baseline.get("translation", "pending") if same_target else "pending"


def clear_source_information(metadata):
    """Remove the cached external entry and restore catalogue attribution."""
    result = use_catalogue_metadata(metadata)
    result.pop("external", None)
    result["sources"] = initial_metadata(canonical(result["target"]))["sources"]
    return result


def renamed_metadata(identifier, *, store=None):
    result = initial_metadata(identifier)
    if identifier in SEEDS or identifier in BODIES:
        return result
    try:
        result = refresh_metadata(result, store=store)
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
    result["updated_at"] = now()
    return result


def clean_text(value):
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def refresh_metadata(metadata, force=False, *, store=None):
    result = clear_source_information(metadata) if force else use_catalogue_metadata(metadata)
    external = result.get("external")
    target = result["target"]
    known = known_target(target)
    if known:
        result["sources"] = list({s["url"]:s for s in result.get("sources", []) + known["sources"]}.values())
    current_dutch = (external or {}).get("text", {}).get("nl")
    from .wikimedia import description as wikipedia_description
    wikipedia = None
    if store is not None and not known and (force or not current_dutch):
        wikipedia = wikipedia_description(store, target)
    found_dutch = wikipedia and wikipedia["text"]["nl"] and not current_dutch
    if external and not force and not found_dutch and not (known and external.get("provider") == "CDS/SIMBAD"):
        age = datetime.now(timezone.utc) - datetime.fromisoformat(external["fetched_at"])
        if age.days < 30:
            if external.get("translation") != "failed":
                translate_description(external)
            return result
    aliases = list(dict.fromkeys([target, *result.get("aliases", []), *(known["aliases"] if known else [])]))
    # Query additional designations, but accept a media caption only when it
    # identifies the target. Caldwell 33 is a wider region than NGC 6992.
    if entry := catalogue_labels().get(canonical(target)):
        aliases = list(dict.fromkeys([*aliases,*[v for v in (entry.get("en"),entry.get("nl")) if v],*entry.get("aliases",[])]))
    queries = list(aliases)
    compact = target.replace(" ", "").replace("_", "")
    if compact != target and compact not in queries:
        queries.append(compact)
    if known is SEEDS["NGC_6992"]:
        queries.extend(["Eastern Veil Nebula", "Caldwell 33"])
    external = wikipedia
    for query in queries if external is None else ():
        try:
            response = external_http.get("https://images-api.nasa.gov/search", params={"q": query, "media_type": "image", "page_size": 30}, headers={"User-Agent": "AstroWeb/0.1"}, timeout=(4, 12))
            response.raise_for_status()
        except requests.RequestException:
            break
        matches = []
        for item in response.json().get("collection", {}).get("items", []):
            data = next(iter(item.get("data", [])), {})
            title = clean_text(data.get("title", ""))
            keywords = {name_key(v) for v in (data.get("keywords") or []) if isinstance(v,str)}
            # NASA full-text results also describe neighbouring objects. Accept
            # a named subject in the title or an explicit catalogue keyword.
            score = sum(2*bool(re.search(r"(?<![a-z0-9])"+re.escape(alias).replace(r"\\ ",r"\\s*")+r"(?![a-z0-9])",title,re.I))
                        + (name_key(alias) in keywords) for alias in aliases)
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
    if external is None and fact_id(target) in facts()["objects"]:
        catalogue = initial_metadata(target)
        external = {"provider":"OpenNGC","title":catalogue["name"]["en"],"text":catalogue["description"],
                    "credit":"OpenNGC · Mattia Verga and contributors · CC BY-SA 4.0",
                    "url":"https://github.com/mattiaverga/OpenNGC/tree/"+facts()["revision"],
                    "sources":catalogue["sources"]}
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
    if names := external.pop("article_names", {}):
        overrides = text_overrides(result)
        for lang, name in names.items():
            if f"name.{lang}" not in overrides and generated_placeholder("name", lang, result["name"][lang], target):
                result["name"][lang] = name
    if extra := external.pop("sources", []):
        result["sources"] = list({s["url"]:s for s in result.get("sources", []) + extra}.values())
    result["external"] = external
    external.update(fetched_at=now(), translation="curated" if external["text"]["nl"] else "unavailable")
    translate_description(external)
    return result


def translate_description(external):
    text = external.get("text", {})
    description = text.get("en")
    translate_url = os.environ.get("ASTROWEB_TRANSLATE_URL", "").rstrip("/")
    if translate_url and description and not text.get("nl"):
        try:
            translated = external_http.post(translate_url + "/translate", json={"q": description, "source": "en", "target": "nl", "format": "text", "api_key": os.environ.get("ASTROWEB_TRANSLATE_KEY", "")}, timeout=(5, 60))
            translated.raise_for_status()
            value = translated.json().get("translatedText", "")
            if isinstance(value, str) and value.strip():
                external["text"]["nl"] = value.strip()[:6000]
                external["translation"] = "machine"
        except (requests.RequestException, ValueError):
            external["translation"] = "failed"
