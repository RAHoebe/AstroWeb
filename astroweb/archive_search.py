"""Look for a fully contained, named HST observation after a Skymap miss."""
import csv
import hashlib
import io
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests
from astropy.coordinates import SkyCoord

from . import hst_archive, skymap
from .catalogue import canonical
from .discovery import project
from .galaxy import key, target_entry
from .journey import geometry

MAST = "https://mast.stsci.edu/api/v0/invoke"
COLUMNS = "obs_id,target_name,s_ra,s_dec,s_region,t_exptime"


def target_names(record):
    meta = record["metadata"]
    target = meta["target"]
    names = {target, *meta.get("aliases", [])}
    known = target_entry(key(canonical(target)))
    if known:
        names.update([known["id"], known["nl"], known["en"], *known.get("aliases", [])])
    terms = set()
    for name in names:
        if not name or not name.strip():
            continue
        upper = name.strip().upper()
        terms.update((upper, upper.replace(" ", "-")))
        match = re.fullmatch(r"([A-Z]+)[_ -]*0*(\d+)([A-Z]?)", upper)
        if match:
            number = str(int(match[2])) + match[3]
            terms.update(match[1] + sep + number for sep in ("", " ", "-", "_"))
    return sorted(terms)


def esa_rows(terms):
    values = ",".join("'" + term.replace("'", "''") + "'" for term in terms)
    query = (f"SELECT TOP 400 {COLUMNS} FROM ivoa.ObsCore WHERE target_name IN ({values}) "
             "AND dataproduct_type='image' AND calib_level=3 AND obs_id LIKE 'hst_%' "
             "AND em_min>3.5e-7 AND em_max<1.05e-6 ORDER BY t_exptime DESC")
    reply = requests.get(hst_archive.TAP, params={"REQUEST":"doQuery","LANG":"ADQL",
                         "FORMAT":"csv","QUERY":query}, timeout=(4,20))
    reply.raise_for_status()
    reader = csv.DictReader(io.StringIO(reply.text))
    if not set(COLUMNS.split(",")).issubset(reader.fieldnames or []):
        raise ValueError("invalid_archive_response")
    return list(reader)


def nasa_rows(terms):
    filters = [{"paramName":name,"values":values} for name, values in (
        ("obs_collection", ["HST","HLA"]), ("target_name", terms),
        ("dataproduct_type", ["image"]), ("calib_level", ["3"]))]
    query = {"service":"Mast.Caom.Filtered","params":{"columns":COLUMNS,"filters":filters},
             "format":"json","pagesize":1000,"page":1}
    reply = requests.get(MAST, params={"request":json.dumps(query)}, timeout=(4,20))
    reply.raise_for_status()
    result = reply.json()
    if result.get("status") != "COMPLETE" or not isinstance(result.get("data"), list):
        raise ValueError("invalid_archive_response")
    return result["data"]


def polygon(region):
    # Only accept a complete STC-S polygon in a known equatorial frame.
    tokens = (region or "").upper().split()
    if not tokens or tokens.pop(0) != "POLYGON":
        return None
    if tokens and tokens[0] in ("ICRS","J2000","FK5"):
        frame = tokens.pop(0)
    else:
        frame = "ICRS"
    try:
        vertices = np.array(tokens, dtype=float).reshape(-1,2)
        if (len(np.unique(vertices,axis=0)) < 3 or not np.isfinite(vertices).all()
                or np.any((vertices[:,0] < 0) | (vertices[:,0] > 360))
                or np.any(np.abs(vertices[:,1]) > 90)):
            return None
        return SkyCoord(*vertices.T, unit="deg", frame="fk5" if frame in ("FK5","J2000") else "icrs").icrs
    except ValueError:
        return None


def ranked_entries(store, record, rows, terms):
    aliases = {key(canonical(term)) for term in terms}
    entries = {}
    for row in rows:
        ident = row.get("obs_id") or ""
        match = hst_archive.FIELD_ID.fullmatch(ident)
        target = row.get("target_name") or ""
        if not match or ident in entries or not target or key(canonical(target)) not in aliases:
            continue
        # Only calibrated optical imaging products supported by the FITS renderer.
        if "_ir_" in ident or not 350 <= int(match[2]) <= 1000:
            continue
        footprint = polygon(row.get("s_region"))
        if footprint is None:
            continue
        _, uv = project(store, record, footprint)
        if not hst_archive.inside_capture(uv):
            continue
        try:
            ra, dec = float(row["s_ra"]), float(row["s_dec"])
            exposure = float(row.get("t_exptime") or 0)
            if not np.isfinite([ra,dec,exposure]).all() or not (0<=ra<=360 and -90<=dec<=90):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        # Prefer a broad optical filter and longer exposures within that class.
        score = (match[3] == "w", exposure, ident)
        entries[ident] = (score, {"id":ident, "target":target, "relation":"target",
                            "filter":"F"+match[2]+match[3].upper(), "ra":ra, "dec":dec,
                            "full_footprint":True})
    return [entry for _,entry in sorted(entries.values(), key=lambda item:item[0], reverse=True)]


def lookup(store, record):
    terms = target_names(record)
    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        searches = [pool.submit(fn, terms) for fn in (nasa_rows, esa_rows)]
        for search in searches:
            try:
                rows.extend(search.result())
            except (requests.RequestException, ValueError) as exc:
                errors.append(exc)
    for entry in ranked_entries(store,record,rows,terms)[:12]:
        try:
            hst_archive.registered_cutout(store,record,entry)
        except requests.RequestException as exc:
            errors.append(exc)
            continue
        except (ValueError, OSError):
            continue
        return entry
    if errors:
        raise ValueError("hubble_unavailable") from errors[0]
    return None


def field_key(store, record):
    field = geometry(store, record)
    if "corners" not in field:
        return None
    values = [field, target_names(record), record.get("sha256",{}).get("final"),
              (record.get("gaia") or {}).get("wcs_header"),record.get("fits")]
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def discover(store, identifier):
    record = store.get("objects", identifier)
    state = (record or {}).get("skymap") or {}
    if not state or record.get("body") or state.get("target") != skymap.target_key(record):
        return
    preferred = skymap.cached_option(store,record)
    if preferred and skymap.focus_point(store,record,preferred) is not None:
        return
    signature = field_key(store,record)
    if signature is None:
        return
    prior = record.get("hst_search") or {}
    if prior.get("field") == signature and (prior.get("option") or prior.get("retry",0)>time.time()):
        return
    try:
        option = lookup(store,record)
        result = {"field":signature, "option":option, "retry":time.time()+7*skymap.DAY}
    except (requests.RequestException, OSError, ValueError):
        logging.warning("Hubble archive search incomplete for %s", identifier, exc_info=True)
        result = {"field":signature, "option":None, "unavailable":True, "retry":time.time()+3600}
    with store.lock:
        latest = store.get("objects",identifier)
        if latest and field_key(store,latest) == signature:
            store.update("objects",identifier,hst_search=result)
