"""Public collection footprints in ICRS. Keep unlocated captures in the index."""
from functools import lru_cache
import json
from .journey import geometry
from .sky import CATALOG, star_catalog


def identity(record):
    return {"id":record["id"], "catalog_id":record.get("catalog_id",record["id"]),
            "session_name":record.get("session_name",""), "name":record["metadata"]["name"]}


def neighbours(records, identifier):
    ids=[r["id"] for r in records]
    if len(ids)<2 or identifier not in ids:
        return {}
    i=ids.index(identifier)
    return {"previous":identity(records[(i-1)%len(ids)]), "next":identity(records[(i+1)%len(ids)])}


@lru_cache(maxsize=1)
def atlas_stars():
    groups=json.loads((CATALOG/"western.json").read_text(encoding="utf8"))["constellations"]
    lines=[line for g in groups for line in g.get("lines",[])]
    ends={hip for line in lines for hip in line}
    stars=[[s["hip"],s["ra"],s["dec"],s["magnitude"]] for s in star_catalog()
           if s["magnitude"]<4.8 or s["hip"] in ends]
    return {"stars":stars,"lines":lines}


def atlas_data(store, include_private=False):
    captures=[]
    for r in store.all("objects"):
        if not r["published"] and not include_private:
            continue
        observation=r.get("observation") or {}
        captures.append({**identity(r),"field":geometry(store,r),"published":r["published"],
                         "date":observation.get("date_obs"),"target":r["metadata"]["target"]})
    return {**atlas_stars(),"captures":captures}
