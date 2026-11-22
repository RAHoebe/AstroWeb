"""Placed planetary labels and measured lunar landmarks in original image coordinates."""
import math
import uuid

import cv2
import numpy as np
import requests

from . import lunar_detail

NASA = "https://science.nasa.gov/"
MAX_LABELS = 40


def feature(id, nl, en, path, journey=None):
    return dict(id=id, name=dict(nl=nl, en=en), source=NASA+path, journey=journey)


PRESETS = {
    "SUN": [
        feature("sunspot", "Zonnevlek", "Sunspot", "sun/facts/"),
        feature("prominence", "Protuberans", "Prominence", "sun/facts/", "NHQ202404080107"),
    ],
    "MERCURY": [feature("caloris", "Calorisbekken", "Caloris Basin", "resource/mercurys-caloris-basin/", "PIA12034")],
    "VENUS": [
        feature("phase", "Verlichte sikkel", "Illuminated crescent", "venus/facts/"),
        feature("clouds", "Wolkenpatronen", "Cloud patterns", "asset/hubble/venus-cloud-tops/", "PIA23791"),
    ],
    "MARS": [
        feature("polar-cap", "Poolkap", "Polar cap", "earth/frozen-ice-on-earth-and-well-beyond/"),
        feature("valles-marineris", "Valles Marineris", "Valles Marineris", "mars/facts/", "PIA01167"),
    ],
    "JUPITER": [
        feature("great-red-spot", "Grote Rode Vlek", "Great Red Spot", "asset/hubble/jupiters-great-red-spot-2/", "PIA21395"),
        feature("cloud-belts", "Wolkenbanden", "Cloud belts", "jupiter/jupiter-facts/"),
        feature("moon-shadow", "Maanschaduw", "Moon shadow", "solar-system/skywatching/night-sky-network/spot-the-king-of-planets-observe-jupiter/"),
        *[feature(en.lower(), nl, en, "resource/family-portrait-of-the-jovian-system/",
                  "PIA00294" if en == "Europa" else None) for nl,en in
          (("Io","Io"),("Europa","Europa"),("Ganymedes","Ganymede"),("Callisto","Callisto"))],
    ],
    "SATURN": [
        feature("rings", "Ringen", "Rings", "saturn/facts/", "PIA11141"),
        feature("cassini-division", "Cassinischeiding", "Cassini Division", "resource/saturns-rings-2/", "PIA11657"),
        feature("titan", "Titan", "Titan", "saturn/moons/titan/facts/"),
        feature("enceladus", "Enceladus", "Enceladus", "saturn/facts/", "PIA11688"),
    ],
    "URANUS": [
        feature("rings", "Ringen", "Rings", "uranus/"),
        feature("miranda", "Miranda", "Miranda", "uranus/", "PIA18185"),
    ],
    "NEPTUNE": [
        feature("dark-vortex", "Donkere storm", "Dark vortex", "asset/hubble/uranus-and-neptune/"),
        feature("triton", "Triton", "Triton", "neptune/moons/facts/"),
    ],
}
PRESETS["MOON"] = [
    {**option, "source":option["coordinate_source"], "journey":option["id"]}
    for option in lunar_detail.options()
]
SUMMARIES = {
    "great-red-spot": ("Een grote, langlevende storm op het zuidelijk halfrond van Jupiter.",
                      "A large, long-lived storm in Jupiter's southern hemisphere."),
    "cloud-belts": ("Donkere en lichte banden in de atmosfeer van Jupiter.",
                    "Dark and light bands in Jupiter's atmosphere."),
    "rings": ("Een schijf van deeltjes die rond de planeet draaien.",
              "A disk of particles orbiting the planet."),
    "cassini-division": ("De opvallende opening tussen de A- en B-ring van Saturnus.",
                        "The prominent gap between Saturn's A and B rings."),
    "polar-cap": ("Helder ijs rond een van de polen van Mars.",
                  "Bright ice around one of the poles of Mars."),
    "caloris": ("Een groot inslagbekken op Mercurius.", "A large impact basin on Mercury."),
    "sunspot": ("Een koelere plek in de fotosfeer die daardoor donkerder lijkt.",
                "A cooler region in the photosphere that appears darker."),
}


def presets(body):
    return PRESETS.get(body, [])


def labelled(position, data, method):
    summary = (
        dict(nl="Gekoppeld aan het ingemeten maanoppervlak.", en="Located with registered lunar surface coordinates.")
        if method == "registered" else
        dict(nl="Op deze opname aangewezen door de beheerder.", en="Marked on this capture by the administrator.")
    )
    if data["id"] in SUMMARIES and data.get("source"):
        nl,en = SUMMARIES[data["id"]]
        summary = dict(nl=nl,en=en)
    return {**data, **position, "type":dict(nl="Onderdeel", en="Feature"),
            "summary":summary, "aliases":[], "placement":method}


def manual(record):
    saved = record.get("surface_labels") or {}
    return saved.get("points", []) if saved.get("body") == record.get("body") else []


def lunar_points(store, record):
    photo = cv2.imread(str(store.path(record["poster"])))
    if photo is None:
        return []
    height,width = photo.shape[:2]
    matrix,view,center,radius = lunar_detail.registered_view(store,record,photo)
    inverse = np.linalg.inv(matrix)
    locations = []
    for preset in presets("MOON"):
        lon,lat,*_ = lunar_detail.SITES[preset["id"]]
        xy,depth = lunar_detail.project(lon,lat,view,center,radius)
        if depth <= .1:
            continue
        # Avoid labelling features on the unlit side of a partially lit disk.
        if view.get("subsolar_lon") is not None and view.get("subsolar_lat") is not None:
            solar_view = {**view, "subearth_lon":view["subsolar_lon"], "subearth_lat":view["subsolar_lat"]}
            _,sunlight = lunar_detail.project(lon,lat,solar_view,center,radius)
            if sunlight <= .02:
                continue
        pixel = cv2.perspectiveTransform(xy.reshape(1,1,2),inverse)[0,0]
        x,y = (pixel+.5)/[width,height]
        if 0 <= x <= 1 and 0 <= y <= 1:
            locations.append(labelled(dict(x=float(x),y=float(y)),preset,"registered"))
    return locations


def discover(store, record):
    body = record["body"]
    points = {}
    alignment_error = None
    if body == "MOON" and record.get("poster"):
        try:
            points = {point["id"]:point for point in lunar_points(store,record)}
        except (OSError, requests.RequestException):
            alignment_error = "lunar_reference_unavailable"
        except (ValueError, cv2.error, np.linalg.LinAlgError):
            alignment_error = "lunar_unmatched"
    known = {p["id"]:p for p in presets(body)}
    saved = manual(record)
    if body == "SATURN" and record.get("poster") and not any(p["id"]=="rings" for p in saved):
        from .solar_detail import saturn_ring_point
        photo = cv2.imread(str(store.path(record["poster"])))
        measured = saturn_ring_point(photo) if photo is not None else None
        if measured is not None:
            x,y = map(float,measured)
            points["rings"] = labelled(dict(x=x,y=y),known["rings"],"ring-axis")
    for point in saved:
        info = known.get(point["preset"]) if point.get("preset") else None
        if info is None:
            info = dict(id=point["id"],name=dict(nl=point["name"],en=point["name"]),source=None,journey=None)
        points[point["id"]] = labelled(dict(x=point["x"],y=point["y"]),info,"manual")
    result = {"kind":"surface","objects":list(points.values())}
    if alignment_error and not points:
        result["alignment_error"] = alignment_error
    return result


def save(store, record, payload):
    body = record.get("body")
    if body not in PRESETS:
        raise ValueError("invalid_surface_label")
    points = manual(record)
    id = payload.get("id")
    if payload.get("remove") is True:
        if not isinstance(id,str) or not any(p["id"] == id for p in points):
            raise ValueError("invalid_surface_label")
        points = [p for p in points if p["id"] != id]
    else:
        preset = payload.get("preset", "")
        name = payload.get("name", "")
        if not isinstance(preset,str) or not isinstance(name,str):
            raise ValueError("invalid_surface_label")
        name = name.strip()
        if preset and not any(p["id"] == preset for p in presets(body)):
            raise ValueError("invalid_surface_label")
        if not preset and (not 1 <= len(name) <= 100 or not name.isprintable()):
            raise ValueError("invalid_surface_label")
        if id is not None and (not isinstance(id,str) or not any(p["id"] == id for p in points)):
            raise ValueError("invalid_surface_label")
        coords = {k:payload.get(k) for k in ("x","y")}
        if any(type(v) not in (int,float) or not 0 <= v <= 1 or not math.isfinite(v) for v in coords.values()):
            raise ValueError("invalid_surface_label")
        point = {"id":preset or id or "mark-"+uuid.uuid4().hex, "preset":preset, "name":name if not preset else "",
                 **{k:round(v,8) for k,v in coords.items()}}
        # Each named preset has one location per capture. An edit can replace it.
        points = [p for p in points if p["id"] not in (id,point["id"])] + [point]
        if len(points) > MAX_LABELS:
            raise ValueError("surface_label_limit")
        id = point["id"]
    store.update("objects",record["id"],surface_labels={"body":body,"points":points})
    return id
