"""Public collection footprints in ICRS. Keep unlocated captures in the index."""
from functools import lru_cache
from datetime import datetime, timezone
import json
from .catalogue import group_id
from .journey import geometry
from .sky import CATALOG, star_catalog


def identity(record):
    return {"id":record["id"], "catalog_id":group_id(record), "capture_kind":record.get("capture_kind"),
            "session_name":record.get("session_name",""), "name":record["metadata"]["name"]}


def capture_date(record):
    """Calendar date explicitly supplied, or the normalized FITS/Studio DATE-OBS."""
    return record.get("capture_date") or (record.get("observation") or {}).get("date_obs")


def date_order(record):
    value=capture_date(record)
    if value:
        try:
            stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
            return (True,stamp.astimezone(timezone.utc),record["id"])
        except (ValueError,TypeError):
            pass
    return (False,datetime.min.replace(tzinfo=timezone.utc),record["id"])


def capture_groups(records):
    groups={}
    for r in records:
        groups.setdefault(group_id(r),[]).append(r)
    for group in groups.values():
        group.sort(key=date_order,reverse=True)
    return groups


def gallery(records):
    return sorted((group[0] for group in capture_groups(records).values()), key=date_order, reverse=True)


def date_option(record):
    return {**identity(record),"date":capture_date(record),"published":record["published"]}


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
        captures.append({**identity(r),"field":geometry(store,r),"published":r["published"],
                         "date":capture_date(r),"target":r["metadata"]["target"]})
    return {**atlas_stars(),"captures":captures}
