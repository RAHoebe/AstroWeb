"""Projected galaxy neighbourhood. Angular proximity alone is not membership."""
from functools import lru_cache
from urllib.parse import quote

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord

from .discovery import entries, TYPES
from .galaxy import key, target_entry
from .journey import geometry

NASA="https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/"
DISTANCES={"M31":2.5,"M32":2.5,"M110":2.7,"M51":31.}
# Each entry has a published association; no grouping by angular proximity.
RELATIONS={frozenset(("M31","M32")):("satellite","M32"),
           frozenset(("M31","M110")):("satellite","M110"),
           frozenset(("M51","NGC5195")):("interacting","M51")}
GALAXY_TYPES={"G","GPair","GGroup","GTrpl"}


@lru_cache(maxsize=1)
def galaxies():
    rows,coords=entries()
    indices=[i for i,row in enumerate(rows) if row.get("type") in GALAXY_TYPES]
    return [rows[i] for i in indices],coords[indices]


def target_galaxy(record):
    name=key(record["metadata"]["target"])
    row=target_entry(name)
    if row and row.get("type") in GALAXY_TYPES:
        return row
    return next((r for r in galaxies()[0] if key(r["id"])==name),None)


def neighbourhood(store,record):
    target=target_galaxy(record)
    if not target:
        raise ValueError("environment_missing")
    center=SkyCoord(target["ra"]*u.deg,target["dec"]*u.deg)
    frame=center.skyoffset_frame()
    def offset(sky):
        p=sky.transform_to(frame)
        return np.column_stack((-p.lon.deg,-p.lat.deg))
    corners=geometry(store,record).get("corners")
    outline=offset(SkyCoord(*np.array(corners).T,unit="deg")).tolist() if corners else []
    radius=max(2.,1.4*max((np.hypot(*p) for p in outline),default=0))
    rows,coords=galaxies()
    sep=center.separation(coords).deg
    result=[]
    chosen=key(target["id"])
    for i in np.argsort(sep):
        if sep[i]>radius:break
        row=rows[i];ident=key(row["id"])
        relation,ref=RELATIONS.get(frozenset((chosen,ident)),("projected",None))
        if ident==chosen:relation="target"
        url=NASA+"messier-"+ref[1:]+"/" if ref else None
        nl,en=TYPES[row["type"]]
        result.append({"id":row["id"],"nl":row["nl"],"en":row["en"],"type":{"nl":nl,"en":en},
                       "offset":offset(coords[i:i+1])[0].tolist(),"angle":float(sep[i]),
                       "relation":relation,"relation_source":url,"distance":DISTANCES.get(ident),
                       "distance_source":NASA+"messier-"+ident[1:]+"/" if ident in DISTANCES else None,
                       "source":"https://ned.ipac.caltech.edu/byname?objname="+quote(row["id"])})
    return {"radius":radius,"outline":outline,"objects":result,"target":target["id"]}
