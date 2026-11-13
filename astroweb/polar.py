"""Equatorial pole chart in ICRS, independent of observing site and date."""
import json
from functools import lru_cache

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from .galaxy import key, landmarks, target_entry
from .journey import geometry
from .sky import CATALOG, star_catalog

DUTCH = {"UMa":"Grote Beer","UMi":"Kleine Beer","Cas":"Cassiopeia","And":"Andromeda","Per":"Perseus",
         "Cep":"Cepheus","Cyg":"Zwaan","Dra":"Draak","Lyr":"Lier","Her":"Hercules","Aur":"Voerman",
         "Boo":"Ossenhoeder","CrB":"Noorderkroon","Gem":"Tweelingen","Tau":"Stier","Aql":"Arend",
         "Ori":"Orion","Oct":"Octant","Cru":"Zuiderkruis","Car":"Kiel","Cen":"Centaur","Pav":"Pauw",
         "Scl":"Beeldhouwer","Gru":"Kraanvogel","Tuc":"Toekan","Vel":"Zeilen","Pup":"Achtersteven"}


@lru_cache(maxsize=1)
def chart_catalog():
    groups = json.loads((CATALOG/"western.json").read_text(encoding="utf8"))["constellations"]
    groups = [{"name":g["common_name"].get("native") or g["iau"],"nl":DUTCH.get(g["iau"]),
               "lines":g.get("lines",[])} for g in groups if g.get("lines")]
    endpoints={hip for g in groups for line in g["lines"] for hip in line}
    stars=[[s["hip"],s["ra"],s["dec"],s["magnitude"],s["name"]] for s in star_catalog()
           if s["magnitude"]<=5 or s["hip"] in endpoints or s["hip"]==104382]
    objects=[{k:o[k] for k in ("ra","dec","nl","en","id")} for o in landmarks()
             if o["id"].startswith("M") and o["id"][1:].isdigit()]
    return {"stars":stars,"groups":groups,"objects":objects}


def chart(store, record):
    field=geometry(store,record)
    known=target_entry(key(record["metadata"].get("target") or record["id"]))
    corners=field.get("corners",[])
    if known:
        center=[known["ra"],known["dec"]]
    elif corners:
        mean=SkyCoord(SkyCoord(*np.array(corners).T,unit="deg").cartesian.mean(),frame="icrs").spherical
        center=[mean.lon.deg,mean.lat.deg]
    else:
        center=field.get("center")
    target={"ra":center[0],"dec":center[1],"name":record["metadata"]["name"]} if center else None
    return {**chart_catalog(),"target":target,"corners":corners}
