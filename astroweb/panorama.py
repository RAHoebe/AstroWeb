"""Panorama markers are stored in normalized coordinates of the original photo."""
import math

import numpy as np
from astropy.coordinates import SkyCoord

from .collection import gallery
from .journey import geometry, panorama_pixels


def settings(store, record, private=False):
    config = record.get("panorama") or {}
    pins = []
    for pin in config.get("pins", []):
        ident = store.current_id(pin["target"])
        target = store.get("objects", ident)
        if target and (private or target["published"]):
            pins.append({**pin, "target":ident, "name":target["metadata"]["name"]})
    return {"wrap":config.get("wrap", False), "pins":pins}


def validate(store, record, body):
    pins, wrap = body.get("pins"), body.get("wrap")
    if type(wrap) is not bool or not isinstance(pins,list):
        raise ValueError("invalid_panorama")
    result = []
    seen = set()
    for pin in pins:
        if not isinstance(pin,dict) or not isinstance(pin.get("target"),str):
            raise ValueError("invalid_panorama")
        target = store.current_id(pin["target"])
        if target in seen or target == record["id"] or not store.get("objects",target):
            raise ValueError("invalid_panorama")
        x,y = pin.get("x"),pin.get("y")
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in (x,y)):
            raise ValueError("invalid_panorama")
        result.append({"target":target,"x":x,"y":y})
        seen.add(target)
    return {"wrap":wrap,"pins":result}


def overview(store):
    pins=[]
    for record in gallery(r for r in store.all("objects") if r["published"] and not r.get("body") and not r.get("capture_kind")):
        field=geometry(store,record)
        if field.get("corners"):
            corners=SkyCoord(*np.asarray(field["corners"]).T,unit="deg")
            sky=SkyCoord(corners.cartesian.mean(),frame="icrs")
        elif field.get("center"):
            sky=SkyCoord(*field["center"],unit="deg")
        else:
            continue
        gal=sky.galactic
        x,y=panorama_pixels(gal.l.radian,gal.b.radian,6000,3000)
        pins.append({"target":record["id"],"name":record["metadata"]["name"],
                     "x":float((x+.5)/6000)%1,"y":float((y+.5)/3000)})
    return {"image":"/media/panorama/eso0932a.jpg","wrap":True,"pins":pins}
