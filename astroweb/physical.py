"""Approximate projected size of a registered field at the target's distance."""
from datetime import datetime
import math
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord,get_body
from astropy.time import Time
from .galaxy import key,target_entry
from .environment import DISTANCES,NASA
from .journey import geometry


def field_scale(store,record):
    meta=record["metadata"]
    result={"distance_ly":None,"width_ly":None,"height_ly":None,"source":None}
    if record.get("body"):
        # Only use a recorded observing instant, never the upload time.
        stamp=(record.get("observation") or {}).get("date_obs")
        if stamp:
            try:
                body=get_body(record["body"].lower(),Time(datetime.fromisoformat(stamp.replace("Z","+00:00"))),ephemeris="builtin")
                result.update(distance_ly=body.distance.to_value(u.lyr),distance_km=body.distance.to_value(u.km),
                              source="https://docs.astropy.org/en/stable/coordinates/solarsystem.html")
            except (ValueError,TypeError,KeyError):
                pass
        return result
    row=target_entry(key(meta["target"])) or {}
    distance=meta.get("galactic_distance_ly")
    if distance is None:
        ident=key(row.get("id",meta["target"]))
        if ident in DISTANCES:
            distance=DISTANCES[ident]*1e6
            result["source"]=NASA+"messier-"+ident[1:]+"/"
        else:
            distance=row.get("ly")
            result["source"]=row.get("source") if distance else None
    if not distance:return result
    result["distance_ly"]=distance
    corners=geometry(store,record).get("corners")
    if corners:
        sky=SkyCoord(*np.array(corners).T,unit="deg")
        # Opposite edge averages retain the original (possibly mirrored)
        # raster orientation. Width and height refer to the target plane.
        for label,(a,b,c,d) in (("width_ly",(0,1,3,2)),("height_ly",(0,3,1,2))):
            angle=(sky[a].separation(sky[b]).radian+sky[c].separation(sky[d]).radian)/2
            result[label]=2*distance*math.tan(angle/2)
    return result
