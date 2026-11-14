"""Look for a fully contained, named HST observation for a registered capture."""
import csv
import hashlib
import io
import json
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
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
MAX_FIELDS = 6
MAX_FAILED_CUTOUTS = 16


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


def region_names(record):
    target = key(canonical(record["metadata"]["target"]))
    return hst_archive.REGIONS.get(target, ())


def esa_search(condition):
    query = (f"SELECT TOP 1000 {COLUMNS} FROM ivoa.ObsCore WHERE {condition} "
             "AND dataproduct_type='image' AND calib_level=3 AND obs_id LIKE 'hst_%' "
             "AND em_min>3.5e-7 AND em_max<1.05e-6 ORDER BY t_exptime DESC")
    reply = requests.get(hst_archive.TAP, params={"REQUEST":"doQuery","LANG":"ADQL",
                         "FORMAT":"csv","QUERY":query}, timeout=(4,20))
    reply.raise_for_status()
    reader = csv.DictReader(io.StringIO(reply.text))
    if not set(COLUMNS.split(",")).issubset(reader.fieldnames or []):
        raise ValueError("invalid_archive_response")
    return list(reader)


def esa_rows(terms):
    values = ",".join("'" + term.replace("'", "''") + "'" for term in terms)
    return esa_search(f"target_name IN ({values})")


def search_cone(corners):
    sky = SkyCoord(*np.asarray(corners).T, unit="deg")
    centre = SkyCoord(sky.cartesian.mean(), frame="icrs")
    radius = float(centre.separation(sky).deg.max()) + .001
    return centre.spherical.lon.deg, centre.spherical.lat.deg, radius


def spatial_rows(corners):
    ra, dec, radius = search_cone(corners)
    return esa_search(f"1=INTERSECTS(s_region,CIRCLE('ICRS',{ra:.8f},{dec:.8f},{radius:.8f}))")


def nasa_rows(terms):
    return mast_search([{"paramName":"target_name","values":terms}])


def mast_spatial_rows(corners):
    ra, dec, radius = search_cone(corners)
    bounds = [{"paramName":"s_dec","values":[{"min":max(-90.,dec-radius),"max":min(90.,dec+radius)}]}]
    if abs(dec)+radius < 90:
        delta = math.degrees(math.asin(math.sin(math.radians(radius))/math.cos(math.radians(dec))))
        lo, hi = (ra-delta)%360, (ra+delta)%360
        ranges = [{"min":lo,"max":hi}] if lo<=hi else [{"min":lo,"max":360.},{"min":0.,"max":hi}]
        bounds.append({"paramName":"s_ra","values":ranges})
    return mast_search(bounds)


def mast_search(filters):
    filters = filters + [{"paramName":name,"values":values} for name, values in (
        ("obs_collection", ["HST","HLA"]), ("dataproduct_type", ["image"]), ("calib_level", ["3"]))]
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


def saved_options(state):
    """Keep single-field results from earlier installations available."""
    if "options" in state:
        return state["options"]
    return [state["option"]] if state.get("option") else []


def same_field(polygon, others):
    # Use camera-plane coordinates (also across RA zero). The smaller area
    # is the denominator so a second filter or a nested chip is not a new stop.
    area = cv2.contourArea(polygon)
    for other in others:
        overlap, _ = cv2.intersectConvexConvex(polygon, other)
        if overlap >= .5 * min(area, cv2.contourArea(other)):
            return True
    return False


def ranked_entries(store, record, rows, terms):
    aliases = {key(canonical(term)) for term in terms}
    regions = {key(name) for name in region_names(record)}
    entries = {}
    for row in rows:
        ident = row.get("obs_id") or ""
        match = hst_archive.FIELD_ID.fullmatch(ident)
        target = row.get("target_name") or ""
        if not match or ident in entries:
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
        hull = cv2.convexHull(uv.astype(np.float32))
        if cv2.contourArea(hull) <= 0:
            continue
        # Prefer a broad optical filter and longer exposures within that class.
        designation = key(target)
        if target and key(canonical(target)) in aliases:
            relation, priority = "target", 3
        elif designation in regions:
            relation, priority = "region", 2
        else:
            relation = "field"
            priority = int(designation not in {"", "ANY", "NONE", "PAR", "PARALLEL"})
        score = (priority, match[3] == "w", exposure, ident)
        entries[ident] = (score, {"id":ident, "target":target or "ANY", "relation":relation,
                            "filter":"F"+match[2]+match[3].upper(), "ra":ra, "dec":dec,
                            "full_footprint":True, "footprint":hull.reshape(-1,2).tolist()})
    return [entry for _,entry in sorted(entries.values(), key=lambda item:item[0], reverse=True)]


def lookup(store, record):
    terms = target_names(record)
    rows, errors = [], []
    corners = geometry(store,record).get("corners")
    if not corners:
        return []
    names = sorted(set(terms).union(region_names(record)))
    with ThreadPoolExecutor(max_workers=4) as pool:
        searches = [pool.submit(fn, names) for fn in (nasa_rows, esa_rows)]
        searches.extend(pool.submit(fn, corners) for fn in (spatial_rows, mast_spatial_rows))
        for search in searches:
            try:
                rows.extend(search.result())
            except (requests.RequestException, ValueError) as exc:
                errors.append(exc)
    candidates = ranked_entries(store,record,rows,terms)
    prior = record.get("hst_search") or {}
    previous = saved_options(prior) if prior.get("field")==field_key(store,record) else []
    previous_ids = [e["id"] for e in previous]
    # Retain existing destinations first if they still pass all geometry checks.
    candidates.sort(key=lambda e: previous_ids.index(e["id"]) if e["id"] in previous_ids else len(previous_ids))
    accepted, footprints, cutouts = [], [], []
    failed_cutouts = 0
    edges = np.float32([[[-.5,-.5],[hst_archive.SIZE-.5,-.5],[hst_archive.SIZE-.5,hst_archive.SIZE-.5],[-.5,hst_archive.SIZE-.5]]])
    for entry in candidates:
        if failed_cutouts >= MAX_FAILED_CUTOUTS:
            break
        hull = np.float32(entry["footprint"])
        if same_field(hull, footprints):
            continue
        try:
            _, matrix, _ = hst_archive.registered_cutout(store,record,entry)
        except requests.RequestException as exc:
            errors.append(exc)
            failed_cutouts += 1
            continue
        except (ValueError,OSError):
            failed_cutouts += 1
            continue
        # The small WCS cutout used by the movie can be shared even when the
        # catalogue mosaics have different outlines. Check both.
        cutout = cv2.convexHull(cv2.perspectiveTransform(edges,matrix)[0])
        if cv2.contourArea(cutout) <= 0 or same_field(cutout, cutouts):
            continue
        footprints.append(hull)
        cutouts.append(cutout)
        accepted.append({k:v for k,v in entry.items() if k!="footprint"})
        if len(accepted)==MAX_FIELDS:
            break
    if errors and not accepted:
        raise ValueError("hubble_unavailable") from errors[0]
    return accepted


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
    signature = field_key(store,record)
    if signature is None:
        return
    prior = record.get("hst_search") or {}
    if prior.get("field") == signature and prior.get("spatial") and (prior["options"] or prior.get("retry",0)>time.time()):
        return
    try:
        options = lookup(store,record)
        result = {"field":signature, "spatial":True, "options":options, "retry":time.time()+7*skymap.DAY}
    except (requests.RequestException, OSError, ValueError):
        logging.warning("Hubble archive search incomplete for %s", identifier, exc_info=True)
        if prior.get("field")==signature and saved_options(prior):
            return
        result = {"field":signature, "spatial":True, "options":[], "unavailable":True, "retry":time.time()+3600}
    with store.lock:
        latest = store.get("objects",identifier)
        if latest and field_key(store,latest) == signature:
            store.update("objects",identifier,hst_search=result)
