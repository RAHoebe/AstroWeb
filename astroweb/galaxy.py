"""Face-on Galactic positions and time-synchronised sky annotations."""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

import astropy.units as u
import cv2
import numpy as np
from astropy.coordinates import SkyCoord

from . import journey

# Normalized pixel positions on PIA10748, calibrated to the annotated ESO map.
SUN = (.5, .69)
LY_PER_IMAGE = 26700 / (SUN[1] - .5)


def key(value):
    return re.sub(r"[\s_-]+", "", value.upper())


def face_position(ra, dec, ly):
    gal = SkyCoord(ra*u.deg, dec*u.deg).galactic
    distance = ly * math.cos(gal.b.radian) / LY_PER_IMAGE
    return [SUN[0]-distance*math.sin(gal.l.radian), SUN[1]-distance*math.cos(gal.l.radian)]


@lru_cache(maxsize=1)
def expanded_catalog():
    path = Path(__file__).with_name("catalog") / "atlas-landmarks.json"
    return json.loads(path.read_text(encoding="utf8"))


@lru_cache(maxsize=1)
def landmarks():
    path = Path(__file__).with_name("catalog") / "galactic-objects.json"
    items = json.loads(path.read_text(encoding="utf8"))
    extra = expanded_catalog()
    # Preserve bright-star priority on the all-sky view while giving the
    # landmarks near the current gallery fields first choice of space.
    for row in extra["objects"]:
        items.append({**row, "nl":row.get("nl", row["en"]), "aliases":row.get("aliases", []),
                      "source":row.get("source", extra["sources"][row["src"]])})
    gal = SkyCoord([r["ra"] for r in items]*u.deg,[r["dec"] for r in items]*u.deg).galactic
    for row, lon, lat in zip(items, gal.l.radian, gal.b.radian):
        if "ly" in row:
            length = row["ly"]*math.cos(lat)/LY_PER_IMAGE
            row["xy"] = [SUN[0]-length*math.sin(lon), SUN[1]-length*math.cos(lon)]
    return items


def target_entry(target):
    return next((r for r in landmarks() if target in
                 {key(r["id"]), key(r["nl"]), key(r["en"]), *map(key,r["aliases"])}), None)


@lru_cache(maxsize=1)
def field_catalog():
    rows = expanded_catalog()["field_objects"]
    return rows, SkyCoord([r[1] for r in rows]*u.deg,[r[2] for r in rows]*u.deg)


def galactic_map(record):
    meta = record["metadata"]
    target = key(meta.get("target") or record["id"])
    known = target_entry(target)
    chosen = known
    custom = meta.get("galactic_distance_ly")
    if custom is not None and not record.get("body"):
        obs = record.get("observation") or {}
        if obs.get("ra") is None or obs.get("dec") is None:
            return None
        chosen = {"id":meta["target"], "ly":custom, "source":None,
                  "xy":face_position(obs["ra"], obs["dec"], custom)}
    if record.get("body"):
        chosen = {"xy":list(SUN),"ly":0,"source":None}
    if not chosen or "xy" not in chosen:
        return None
    points = [{"id":"Sun", "nl":"Zon", "en":"Sun", "xy":SUN},
              {"id":"Sgr A*", "nl":"Galactisch centrum", "en":"Galactic centre", "xy":[.5,.5]}]
    points.extend({k:r[k] for k in ("id","nl","en","xy")} for r in landmarks() if "xy" in r and r is not known)
    return {"solar":bool(record.get("body")),"xy":chosen["xy"], "ly":chosen["ly"], "source":chosen["source"], "points":points,
            "ly_per_image":LY_PER_IMAGE}


def journey_labels(record, field):
    if field["kind"] == "missing":
        return None
    meridian, footprint, _, _ = journey.field_projection(field)
    candidates = [{"id":r["id"], "nl":r["nl"], "en":r["en"], "ra":r["ra"], "dec":r["dec"]}
                  for r in landmarks()]
    # Add regional NGC/IC labels for the zoom, without shipping an all-sky list to the browser.
    coords = np.array(field["corners"] if "corners" in field else [field["center"]])
    center = SkyCoord(*coords.T,unit="deg").cartesian.mean()
    rows, sky = field_catalog()
    sep = SkyCoord(center,frame="icrs").separation(sky).deg
    for index in np.flatnonzero(sep < 12):
        name,ra,dec = rows[index][:3]
        candidates.append({"id":name,"nl":name,"en":name,"ra":ra,"dec":dec,"detail":True})
    target = key(record["metadata"].get("target") or record["id"])
    known = target_entry(target)
    if known:
        candidates = [r for r in candidates if r["id"] != known["id"]]
    candidates = [r for r in candidates if key(r["id"]) != target]
    gal = SkyCoord([r["ra"] for r in candidates]*u.deg,[r["dec"] for r in candidates]*u.deg).galactic
    projected = journey.hammer((gal.l.radian-meridian+np.pi)%(2*np.pi)-np.pi,gal.b.radian)*[2,1]
    extent = np.ptp(footprint,axis=0)
    end = min(journey.WIDTH*.77/max(extent[0],1e-6),journey.HEIGHT*.73/max(extent[1],1e-6)) if "corners" in field else journey.WIDTH*.46*9
    labels = [{"nl":r["nl"], "en":r["en"], "xy":np.round(xy,7).tolist(), "detail":r.get("detail",False)} for r,xy in zip(candidates,projected)]
    # The pointing or mosaic centre need not coincide with the catalogue object.
    marker = footprint.mean(axis=0)
    if known:
        obj = SkyCoord(known["ra"]*u.deg,known["dec"]*u.deg).galactic
        marker = journey.hammer((obj.l.radian-meridian+np.pi)%(2*np.pi)-np.pi,obj.b.radian)*[2,1]
    labels.insert(0, {"nl":record["metadata"]["name"]["nl"], "en":record["metadata"]["name"]["en"],
                      "xy":marker.tolist()})
    quarter=journey.nearest_quarter(footprint) if "corners" in field else None
    frames = []
    # Reuse the movie renderer's actual per-frame camera, including the landing roll.
    for i in range(journey.FRAMES):
        t = i/(journey.FRAMES-1)
        scale, offset = journey.camera_at(t, footprint, journey.WIDTH*.46, end)
        matrix = np.array([[scale,0,offset[0]],[0,scale,offset[1]],[0,0,1]])
        if t>.59 and "corners" in field:
            quad = np.float32(footprint*scale+offset)
            pose,mirrored = journey.landing(quad,record["width"],record["height"],journey.smooth((t-.59)/.32),quarter)
            # During the parity crossfade, follow the dominant sky image.
            if mirrored and t >= .89+.055/2:
                pose=pose[[3,2,1,0]]
            matrix = cv2.getPerspectiveTransform(quad,pose) @ matrix
        opacity = 1-journey.smooth((t-.69)/.22) if field.get("solar") else 1.0
        frames.append([*matrix.ravel().round(7).tolist(),opacity])
    return {"points":labels,"frames":frames,"fps":journey.FPS,"width":journey.WIDTH,"height":journey.HEIGHT}
