"""Optional CDS catalogue lookup for a measured celestial footprint."""
import csv
import hashlib
import io
import json
import math
import os
import threading
import time

import requests

from . import external_http

SERVERS = (
    "https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
    "https://simbad.cfa.harvard.edu/simbad/sim-tap/sync",
)
SEARCH = threading.Lock()
TYPES = {"G":"G","RfN":"RfN","PN":"PN","HII":"HII","OpC":"OCl","GlC":"GCl",
         "EmN":"EmN","SNR":"SNR","DNe":"DrkN","Ne":"Neb","Cl*":"OCl"}


def fetch(ra, dec, radius):
    wanted = ",".join(f"'{name}'" for name in TYPES)
    query = ("SELECT TOP 80 main_id, ra, dec, otype, nbref FROM basic WHERE "
             f"1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra:.7f},{dec:.7f},{radius:.7f})) "
             f"AND (otype IN ({wanted}) OR main_id LIKE 'NAME %') ORDER BY nbref DESC")
    for url in SERVERS:
        try:
            reply = external_http.get(url,params=dict(REQUEST="doQuery",LANG="ADQL",FORMAT="csv",QUERY=query),
                                      timeout=(3,12))
            reply.raise_for_status()
            reader = csv.DictReader(io.StringIO(reply.text))
            if not {"main_id","ra","dec","otype"}.issubset(reader.fieldnames or ()):
                continue
            rows = []
            for raw in reader:
                ident = " ".join((raw.get("main_id") or "").split())
                try:
                    x,y = float(raw["ra"]),float(raw["dec"])
                except (TypeError,ValueError):
                    continue
                if not (0<=x<360 and -90<=y<=90 and 1<=len(ident)<=80 and ident.isprintable()):
                    continue
                code = TYPES.get(raw["otype"])
                if not code and ident.startswith("NAME "):
                    code = "*" if raw["otype"] in ("*","**","V*","PM*","SB*","Sy*","Be*","Pec","s*b") else None
                if code:
                    rows.append(dict(id=ident,ra=x,dec=y,type=code,nl=ident.removeprefix("NAME "),en=ident.removeprefix("NAME ")))
            return rows[:80]
        except (requests.RequestException,ValueError):
            continue
    return None


def rows(store,record,search=False):
    from .journey import geometry
    from .archive_search import search_cone
    if store is None:
        return [],"local"
    corners = geometry(store,record).get("corners")
    if not corners:
        return [],"local"
    stamp = hashlib.sha256(json.dumps(corners).encode()).hexdigest()[:24]
    key = "guide-simbad-v1:"+stamp
    saved = store.get("settings",key,{})
    if saved.get("until",0)>time.time() or not search or os.environ.get("ASTROWEB_OFFLINE")=="1":
        return saved.get("rows",[]),saved.get("status","local")
    ra,dec,radius = search_cone(corners)
    if not all(map(math.isfinite,(ra,dec,radius))) or not 0<radius<=4:
        return saved.get("rows",[]),"local"
    if not SEARCH.acquire(blocking=False):
        return saved.get("rows",[]),"busy"
    try:
        saved = store.get("settings",key,{})
        if saved.get("until",0)>time.time():
            return saved.get("rows",[]),saved["status"]
        found = fetch(ra,dec,radius)
        status = "ready" if found is not None else "unavailable"
        data = found if found is not None else saved.get("rows",[])
        store.put("settings",key,dict(rows=data,status=status,until=time.time()+(30*86400 if found is not None else 300)))
        return data,status
    finally:
        SEARCH.release()
