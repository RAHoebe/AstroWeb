"""Gaia DR3 distance-driven stellar sprites. Camera travel remains artistic."""
import hashlib
import io
import json
import warnings
from datetime import datetime

import astropy.units as u
import cv2
import numpy as np
import requests
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.time import Time
from scipy.spatial import cKDTree, Delaunay, QhullError

from . import external_http
from .discovery import project
from .journey import geometry
from .store import now


def catalogue(store, field):
    sky = SkyCoord(*np.asarray(field["corners"]).T, unit="deg")
    center = SkyCoord(sky.cartesian.mean(), frame="icrs")
    radius = float(center.separation(sky).max().deg) + .01
    key = "gaia-depth-dr3-v1:" + hashlib.sha256(json.dumps(field, sort_keys=True).encode()).hexdigest()
    cached = store.get("settings", key)
    if cached is not None:
        return cached
    query = (
        "SELECT TOP 20000 source_id,ra,dec,ref_epoch,pmra,pmdec,parallax,parallax_error,ruwe "
        "FROM gaiadr3.gaia_source WHERE "
        f"1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{center.ra.deg:.8f},{center.dec.deg:.8f},{radius:.7f})) "
        "AND phot_g_mean_mag<14"
    )
    try:
        response = external_http.get("https://gaia.aip.de/tap/sync",
            params={"REQUEST": "doQuery", "LANG": "ADQL", "QUERY": query, "FORMAT": "votable"},
            timeout=(5, 60))
        response.raise_for_status()
        table = Table.read(io.BytesIO(response.content), format="votable", use_names_over_ids=True)
    except (requests.RequestException, ValueError, OSError) as error:
        raise ValueError("gaia_depth_unavailable") from error
    rows = []
    for row in table:
        try:
            keys = ("ra", "dec", "ref_epoch", "pmra", "pmdec", "parallax", "parallax_error", "ruwe")
            if any(np.ma.is_masked(row[k]) for k in keys):
                continue
            item = {k: float(row[k]) for k in keys}
            if not all(np.isfinite(list(item.values()))) or item["parallax_error"] <= 0:
                continue
            if item["parallax"]/item["parallax_error"] < 10 or item["ruwe"] <= 0 or item["ruwe"] >= 1.4:
                continue
            rows.append({**item, "source_id": str(row["source_id"])})
        except (ValueError, TypeError):
            continue
    # A truncated catalogue would silently exclude faint stars. Ask for a smaller field.
    if len(table) == 20000:
        raise ValueError("gaia_depth_large_field")
    store.put("settings", key, rows)
    return rows


def prepare(store, record):
    field = geometry(store, record)
    if field.get("kind") not in {"gaia", "wcs"}:
        raise ValueError("gaia_depth_alignment")
    rows = catalogue(store, field)
    if not rows:
        raise ValueError("gaia_depth_no_stars")
    stamp = (record.get("observation") or {}).get("date_obs") or record.get("capture_date")
    if not stamp:
        raise ValueError("gaia_depth_date")
    epoch = Time(datetime.fromisoformat(stamp.replace("Z", "+00:00")))
    coords = SkyCoord(ra=[r["ra"] for r in rows]*u.deg, dec=[r["dec"] for r in rows]*u.deg,
        pm_ra_cosdec=[r["pmra"] for r in rows]*u.mas/u.yr, pm_dec=[r["pmdec"] for r in rows]*u.mas/u.yr,
        distance=[1000/r["parallax"] for r in rows]*u.pc,
        radial_velocity=np.zeros(len(rows))*u.km/u.s,
        obstime=Time([r["ref_epoch"] for r in rows], format="jyear"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", u.UnitsWarning)
        coords = coords.apply_space_motion(new_obstime=epoch)
    _, xy = project(store, record, SkyCoord(coords.ra, coords.dec))
    if xy is None:
        raise ValueError("gaia_depth_alignment")
    stars = [{**r, "x": float(x), "y": float(y), "distance_pc": 1000/r["parallax"]}
             for r, (x, y) in zip(rows, xy) if np.isfinite([x, y]).all() and 0 <= x <= 1 and 0 <= y <= 1]
    if not stars:
        raise ValueError("gaia_depth_no_stars")
    return {"stars": stars, "epoch": float(epoch.jyear), "checked_at": now(),
            "source": "Gaia DR3 / ESA / AIP", "distance_method": "inverse parallax, SNR >= 10, RUWE < 1.4",
            "source_size": [record["width"], record["height"]]}


def split_stars(stars, data, rotated, blend, interpolate=False):
    """Lift isolated measured stars into small crops, keeping unmeasured light in the rest layer."""
    h, w = stars.shape[:2]
    mask = (stars.max(axis=2) > .025*65535).astype(np.uint8)
    count, labels, boxes, centers = cv2.connectedComponentsWithStats(mask)
    valid = np.flatnonzero((boxes[:, cv2.CC_STAT_AREA] >= 2) & (boxes[:, cv2.CC_STAT_AREA] <= 2000))
    valid = valid[valid != 0]
    if not len(valid):
        raise ValueError("gaia_depth_no_stars")
    xy = np.array([[1-r["y"], r["x"]] if rotated else [r["x"], r["y"]] for r in data["stars"]])
    tree = cKDTree(centers[valid])
    distances, matches = tree.query(xy*[w, h]-.5, k=min(2, len(valid)))
    if distances.ndim == 1:
        distances = distances[:, None]
        matches = matches[:, None]
    source_width, source_height = data["source_size"]
    tolerance = max(1.5, 3*max(w, h)/max(source_width, source_height))
    candidates = {}
    for i, row in enumerate(data["stars"]):
        if distances[i, 0] > tolerance:
            continue
        if distances.shape[1] > 1 and distances[i, 1] < max(2*distances[i, 0], tolerance):
            continue
        candidates.setdefault(int(valid[matches[i, 0]]), []).append(row)
    unique = [(label, rows[0]) for label, rows in candidates.items() if len(rows) == 1]
    if not unique:
        raise ValueError("gaia_depth_no_stars")
    reference = float(np.median([r["distance_pc"] for _, r in unique]))
    if interpolate:
        unique += local_estimates(unique, valid, centers, boxes, stars, w, h)
    sprites, used = [], np.zeros((h, w), np.uint8)
    for label, row in unique:
        x, y, width, height, _ = boxes[label]
        x0, y0, x1, y1 = max(0, x-5), max(0, y-5), min(w, x+width+5), min(h, y+height+5)
        region = labels[y0:y1, x0:x1]
        support = cv2.dilate((region == label).astype(np.uint8), np.ones((5, 5), np.uint8))
        support = cv2.GaussianBlur(support.astype(np.float32), (5, 5), .8)
        support[(region != 0) & (region != label)] = 0
        if np.any((support > .001) & (used[y0:y1, x0:x1] != 0)):
            continue
        used[y0:y1, x0:x1] |= (support > .001).astype(np.uint8)
        light = stars[y0:y1, x0:x1].astype(np.float32)/65535
        lifted = light*support[:, :, None]
        rest = (light-lifted)/np.maximum(1-lifted, 1/65535) if blend == "screen" else light-lifted
        stars[y0:y1, x0:x1] = np.rint(np.clip(rest, 0, 1)*65535)
        # Bounded inverse-distance ordering. The median measured distance is the neutral plane.
        factor = float(np.clip(reference/row["distance_pc"], .5, 2))
        sprites.append({"pixels": lifted, "x": x0, "y": y0, "factor": factor, "source_id": row["source_id"],
                        "distance_pc": row["distance_pc"], "estimated":row.get("estimated", False)})
    if not sprites:
        raise ValueError("gaia_depth_no_stars")
    report = {k: v for k, v in data.items() if k not in {"stars", "source_size"}}
    measured = [p for p in sprites if not p["estimated"]]
    if not measured:
        raise ValueError("gaia_depth_no_stars")
    report.update(matched=len(measured), estimated=len(sprites)-len(measured), catalogue_stars=len(data["stars"]),
                  reference_pc=reference, min_pc=min(p["distance_pc"] for p in measured),
                  max_pc=max(p["distance_pc"] for p in measured), artistic_camera=True)
    return sprites, report


def local_estimates(measured, valid, centers, boxes, stars, width, height):
    """Interpolate visual motion only within a consistent measured neighbourhood."""
    if len(measured)<4:
        return []
    points=np.array([centers[label] for label,_ in measured])
    try:
        hull=Delaunay(points)
    except QhullError:
        return []
    tree=cKDTree(points)
    known={label for label,_ in measured}
    labels=np.array([label for label in valid if label not in known])
    if not len(labels):
        return []
    distances,indices=tree.query(centers[labels],k=min(6,len(points)))
    radius=.06*np.hypot(width,height)
    inverse=np.array([1/row["distance_pc"] for _,row in measured])
    estimates=[]
    inside=hull.find_simplex(centers[labels])>=0
    for i,label in enumerate(labels):
        use=distances[i]<=radius
        if not inside[i] or use.sum()<4:
            continue
        values=inverse[indices[i,use]]
        weights=1/np.maximum(distances[i,use],1)**2
        weights/=weights.sum()
        logs=np.log(values)
        spread=np.sqrt(np.sum(weights*(logs-np.sum(weights*logs))**2))
        if spread>.35:
            continue
        distance=1/float(np.sum(weights*values))
        x,y,w,h,_=boxes[label]
        peak=int(stars[y:y+h,x:x+w].max())
        estimates.append((peak,int(label),{"source_id":"local-estimate-"+str(label),
                         "distance_pc":distance,"estimated":True}))
    # Limit preparation and frame costs in dense fields.
    return [(label,row) for _,label,row in sorted(estimates,reverse=True)[:3000]]
