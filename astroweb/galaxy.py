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
from .sky import star_catalog

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
def landmarks():
    items = json.loads((Path(__file__).with_name("catalog")/"galactic-objects.json").read_text(encoding="utf8"))
    return [{**row, "xy":face_position(row["ra"], row["dec"], row["ly"])} for row in items]


def galactic_map(record):
    meta = record["metadata"]
    target = key(meta.get("target") or record["id"])
    chosen = next((r for r in landmarks() if target in {key(r["id"]), *map(key, r["aliases"])}), None)
    custom = meta.get("galactic_distance_ly")
    if custom is not None:
        obs = record.get("observation") or {}
        if obs.get("ra") is None or obs.get("dec") is None:
            return None
        chosen = {"id":meta["target"], "ly":custom, "source":None,
                  "xy":face_position(obs["ra"], obs["dec"], custom)}
    if not chosen:
        return None
    points = [{"id":"Sun", "nl":"Zon", "en":"Sun", "xy":SUN},
              {"id":"Sgr A*", "nl":"Galactisch centrum", "en":"Galactic centre", "xy":[.5,.5]}]
    points.extend({k:r[k] for k in ("id","nl","en","xy")} for r in landmarks() if key(r["id"]) != target and r is not chosen)
    return {"xy":chosen["xy"], "ly":chosen["ly"], "source":chosen["source"], "points":points,
            "ly_per_image":LY_PER_IMAGE}


def journey_labels(record, field):
    if field["kind"] == "missing":
        return None
    meridian, footprint, _, _ = journey.field_projection(field)
    candidates = [{"id":r["id"], "nl":r["nl"], "en":r["en"], "ra":r["ra"], "dec":r["dec"]}
                  for r in landmarks()]
    for star in sorted(star_catalog(), key=lambda s:s["magnitude"]):
        if star["name"]:
            candidates.append({"id":str(star["hip"]), "nl":star["name"], "en":star["name"],
                               "ra":star["ra"], "dec":star["dec"]})
    # The active target follows the measured field; exclude its duplicate catalogue name.
    target = key(record["metadata"].get("target") or record["id"])
    known = next((r for r in landmarks() if target in {key(r["id"]), *map(key,r["aliases"])}), None)
    if known:
        candidates = [r for r in candidates if r["id"] != known["id"]]
    gal = SkyCoord([r["ra"] for r in candidates]*u.deg,[r["dec"] for r in candidates]*u.deg).galactic
    projected = journey.hammer((gal.l.radian-meridian+np.pi)%(2*np.pi)-np.pi,gal.b.radian)*[2,1]
    extent = np.ptp(footprint,axis=0)
    end = min(journey.WIDTH*.77/max(extent[0],1e-6),journey.HEIGHT*.73/max(extent[1],1e-6)) if "corners" in field else journey.WIDTH*.46*9
    labels = [{"nl":r["nl"], "en":r["en"], "xy":np.round(xy,7).tolist()} for r,xy in zip(candidates,projected)]
    labels.insert(0, {"nl":record["metadata"]["name"]["nl"], "en":record["metadata"]["name"]["en"],
                      "xy":footprint.mean(axis=0).tolist()})
    frames = []
    # Reuse the movie renderer's actual per-frame camera, including the landing roll.
    for i in range(journey.FRAMES):
        t = i/(journey.FRAMES-1)
        scale, offset = journey.camera_at(t, footprint, journey.WIDTH*.46, end)
        matrix = np.array([[scale,0,offset[0]],[0,scale,offset[1]],[0,0,1]])
        opacity = 1-journey.smooth((t-.64)/.22) if "corners" in field else 1
        if t>.59 and opacity and "corners" in field:
            quad = np.float32(footprint*scale+offset)
            pose,_ = journey.landing(quad,record["width"],record["height"],journey.smooth((t-.59)/.32))
            matrix = cv2.getPerspectiveTransform(quad,pose) @ matrix
        frames.append([*matrix.ravel().round(7).tolist(),round(opacity,4)])
    return {"points":labels,"frames":frames,"fps":journey.FPS,"width":journey.WIDTH,"height":journey.HEIGHT}
