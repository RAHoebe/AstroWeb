"""Supported Solar System capture identifiers and bilingual catalogue metadata."""
from datetime import date, datetime, time, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import math

import astropy.units as u
from astropy.coordinates import EarthLocation, SkyCoord, get_body
from astropy.time import Time
from astropy.utils import iers

CENTRAL_NL = (52.15, 5.38)

BODIES = {
    "SUN":("Zon","Sun","Ster","Star"), "MOON":("Maan","Moon","Natuurlijke satelliet","Natural satellite"),
    "MERCURY":("Mercurius","Mercury","Planeet","Planet"), "VENUS":("Venus","Venus","Planeet","Planet"),
    "MARS":("Mars","Mars","Planeet","Planet"), "JUPITER":("Jupiter","Jupiter","Planeet","Planet"),
    "SATURN":("Saturnus","Saturn","Planeet","Planet"), "URANUS":("Uranus","Uranus","Planeet","Planet"),
    "NEPTUNE":("Neptunus","Neptune","Planeet","Planet"),
}
ALIASES = {alias.upper():key for key,(nl,en,_,_) in BODIES.items() for alias in (key,nl,en)}


# Short gallery summaries and explanations of features visitors can explore.
BODY_TEXT = {
    "MOON": ("De donkere maanzeeën zijn vlakten van gestolde lava.", "The dark lunar seas are plains of solidified lava.",
             "Langs de grens tussen licht en donker werpen kraterranden en bergen lange schaduwen. Vanuit een baan om de Maan kon de Lunar Reconnaissance Orbiter zelfs de landingsplaatsen en de sporen van Apollo-astronauten vastleggen.",
             "Along the boundary between day and night, crater rims and mountains cast long shadows. From lunar orbit, the Lunar Reconnaissance Orbiter could even photograph the Apollo landing sites and the trails left by astronauts."),
    "MERCURY": ("Inslagkraters tekenen het oppervlak van Mercurius.", "Impact craters cover Mercury’s surface.",
                "De grote inslag die het Calorisbekken vormde liet een uitgestrekte laagvlakte achter. Opnamen van MESSENGER tonen jongere kraters binnen dat bekken, waaronder Munch, Sander en Poe.",
                "The impact that formed the Caloris basin left an extensive lowland. MESSENGER images reveal younger craters within the basin, including Munch, Sander and Poe."),
    "VENUS": ("Venus gaat schuil onder een dicht wolkendek.", "Venus is shrouded in a thick cloud deck.",
              "In zichtbaar licht oogt Venus vaak egaal. Ultravioletbeelden onthullen patronen in de hoge wolken. De veranderende sikkel die je vanaf de aarde kunt zien ontstaat doordat Venus binnen de aardbaan om de Zon draait.",
              "Venus often looks nearly featureless in visible light. Ultraviolet images reveal patterns in its high clouds. Its changing crescent as seen from Earth is a consequence of its orbit inside Earth’s own."),
    "MARS": ("Roestkleurig stof bedekt grote delen van Mars.", "Rust-coloured dust coats much of Mars.",
             "Op Mars liggen uitgedoofde vulkanen, poolkappen en het uitgestrekte kloofstelsel Valles Marineris. In de wanden daarvan zijn gesteentelagen blootgelegd. Vanuit een baan om Mars zijn die lagen afzonderlijk te bestuderen.",
             "Mars has volcanoes, polar caps and a vast canyon system called Valles Marineris. Its walls expose layers of rock that spacecraft can study individually from orbit."),
    "JUPITER": ("Lichte zones en donkere banden omspannen de gasreus Jupiter.", "Bright zones and dark belts encircle the gas giant Jupiter.",
                "De Grote Rode Vlek is een langlevende storm op het zuidelijk halfrond. JunoCam fotografeert de wervelingen in het wolkendek van dichtbij. De maan Europa heeft een heel ander oppervlak, met donkere lijnen die haar ijskorst doorkruisen.",
                "The Great Red Spot is a long-lived storm in the southern hemisphere. JunoCam photographs the swirling cloud tops at close range. The moon Europa has a very different surface, with dark lines crossing its icy crust."),
    "SATURN": ("De ringen van Saturnus bestaan vooral uit ijsdeeltjes.", "Saturn’s rings consist mainly of particles of ice.",
               "De donkere Cassinischeiding ligt tussen de A-ring en de B-ring. Soms valt de schaduw van een maan op de ringen. Cassini fotografeerde ook Enceladus, waar pluimen van ijs en waterdamp uit breuken rond de zuidpool opstijgen.",
               "The dark Cassini Division lies between the A and B rings. At times a moon casts its shadow across the rings. Cassini also photographed Enceladus, where plumes of ice and water vapour rise from fractures near its south pole."),
    "URANUS": ("Uranus draait bijna op zijn kant om zijn as.", "Uranus rotates almost on its side.",
               "Methaan in de atmosfeer absorbeert rood licht en draagt bij aan de blauwgroene kleur. Voyager 2 bracht ook de manen in beeld. Op Miranda liggen opvallend verschillende landschappen naast elkaar, met richels, breuken en oude kraters.",
               "Atmospheric methane absorbs red light and contributes to the planet’s blue-green colour. Voyager 2 also imaged its moons. On Miranda, ridges, faults and old craters form strikingly different adjoining terrains."),
    "NEPTUNE": ("In de atmosfeer van Neptunus jagen winden wolken rond de planeet.", "Winds drive clouds around Neptune’s atmosphere.",
                "Voyager 2 fotografeerde in 1989 een grote donkere storm met heldere wolken in de buurt. Donkere vlekken op Neptunus kunnen ontstaan en weer verdwijnen. De detailreis laat de historische Voyager-opname zien.",
                "In 1989 Voyager 2 photographed a large dark storm with bright clouds nearby. Dark spots on Neptune can form and disappear. The detail flight shows the historical Voyager observation."),
}


def body_metadata(key):
    nl,en,kind_nl,kind_en=BODIES[key]
    metadata = {"target":en,"name":{"nl":nl,"en":en},"type":{"nl":kind_nl,"en":kind_en},
            "constellation":{"nl":"","en":""},"aliases":[en],"translation":"curated"}
    if key=="SUN":
        metadata.update(
            summary={"nl":"De Zon is onze dichtstbijzijnde ster. In zichtbaar licht kijk je naar de fotosfeer, waar koelere zonnevlekken donker afsteken.",
                     "en":"The Sun is our nearest star. In visible light we see its photosphere, where cooler sunspots appear dark against their surroundings."},
            description={
                "nl":"Het licht van de Zon doet er gemiddeld acht minuten en twintig seconden over om de aarde te bereiken. De energie ontstaat in de kern, waar waterstof samensmelt tot helium. Het zichtbare licht dat je fotografeert komt uit de fotosfeer, een laag van ongeveer 5.500 °C.\n\nDonkere zonnevlekken zijn gebieden waar sterke magneetvelden het transport van warmte naar het oppervlak remmen. Hun aantal verandert tijdens een activiteitencyclus van ongeveer elf jaar. De buitenste atmosfeer, de corona, is veel heter dan de fotosfeer. In de detailreis laat NASA’s Solar Dynamics Observatory in extreem ultraviolet zien hoe een zonnevlam in een actief gebied oplicht.",
                "en":"Sunlight takes about eight minutes and twenty seconds to reach Earth. The Sun produces energy in its core by fusing hydrogen into helium. The visible light in a photograph comes from the photosphere, a layer at about 5,500 °C.\n\nSunspots appear dark where strong magnetic fields inhibit the transport of heat to the surface. Their number varies over a roughly eleven-year activity cycle. The outer atmosphere, the corona, is much hotter than the photosphere. The detail flight uses extreme-ultraviolet images from NASA’s Solar Dynamics Observatory to show a flare brightening in an active region."},
            sources=[{"label":"NASA · Sun facts","url":"https://science.nasa.gov/sun/facts/"},
                     {"label":"NASA · Solar Dynamics Observatory","url":"https://science.nasa.gov/mission/sdo/"}])
    else:
        short_nl,short_en,long_nl,long_en=BODY_TEXT[key]
        metadata.update(summary={"nl":short_nl,"en":short_en},
                        description={"nl":long_nl,"en":long_en},
                        sources=[{"label":"NASA · "+en,"url":f"https://science.nasa.gov/{en.lower()}/facts/"}])
    return metadata


def displayed_metadata(body, metadata):
    """Upgrade original placeholder fields in old captures while retaining user edits."""
    if body not in BODIES:
        return metadata
    curated=body_metadata(body)
    value=dict(metadata)
    nl,en,_,_=BODIES[body]
    placeholders={"description":(f"{nl} in ons zonnestelsel.",f"{en} in our Solar System."),
                  "summary":(f"Eigen opname van {nl}.",f"A capture of {en}.")}
    for field, old in placeholders.items():
        texts=dict(value.get(field) or {})
        for lang, previous in zip(("nl","en"),old):
            if texts.get(lang)==previous:
                texts[lang]=curated[field][lang]
        value[field]=texts
    sources=list(value.get("sources") or [])
    urls={link["url"] for link in sources}
    value["sources"]=sources+[link for link in curated["sources"] if link["url"] not in urls]
    return value


# Mean body radii in km (JPL planetary/satellite physical parameters; nominal solar radius).
RADIUS_KM = dict(SUN=695700, MOON=1737.4, MERCURY=2439.4, VENUS=6051.8, MARS=3389.5,
                 JUPITER=69911, SATURN=58232, URANUS=25362, NEPTUNE=24622)


def observing_site(obs):
    if obs.get("latitude") is None or obs.get("longitude") is None:
        return (*CENTRAL_NL, 0., True)
    return (obs["latitude"], obs["longitude"], obs.get("elevation") or 0., False)


def observing_time(record):
    obs = record.get("observation") or {}
    stamp = obs.get("date_obs")
    if stamp and not obs.get("date_only") and len(stamp)>10:
        return stamp, False
    value = stamp or record.get("capture_date")
    if value:
        day = date.fromisoformat(value[:10])
        return datetime.combine(day, time(12), ZoneInfo(obs.get("timezone") or "Europe/Amsterdam")).isoformat(), True
    return None, False


@lru_cache(maxsize=128)
def apparent_disk(body, stamp, lat, lon, height):
    when = Time(datetime.fromisoformat(stamp))
    site = EarthLocation.from_geodetic(lon*u.deg, lat*u.deg, height*u.m)
    with iers.conf.set_temp("auto_download", False), iers.conf.set_temp("auto_max_age", None):
        apparent = get_body(body.lower(), when, location=site, ephemeris="builtin")
        # Transform a unit direction so the origin change retains the observed line of sight.
        ray = SkyCoord(apparent.ra, apparent.dec, frame=apparent.frame.replicate_without_data()).icrs
    diameter = 2*math.degrees(math.asin(RADIUS_KM[body.upper()]/apparent.distance.to_value(u.km)))
    return float(ray.ra.deg), float(ray.dec.deg), diameter


def pointing(record):
    stamp, approximate = observing_time(record)
    if not stamp:
        return {"kind":"missing"}
    lat, lon, height, assumed = observing_site(record.get("observation") or {})
    ra,dec,diameter=apparent_disk(record["body"],stamp,lat,lon,height)
    return {"kind":"point", "center":[ra,dec], "diameter_deg":diameter,
            "utc":datetime.fromisoformat(stamp).astimezone(timezone.utc).isoformat(),
            "constellation":SkyCoord(ra*u.deg,dec*u.deg).get_constellation(short_name=True),
            "solar":True, "default_site":assumed, "day_only":approximate}
