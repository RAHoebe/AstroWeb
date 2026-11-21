"""Match a raster star layer to Gaia DR3 in a cone near its pointing coordinates."""
import io
import itertools
import logging
import math
import xml.etree.ElementTree as ET
from urllib.parse import quote

import astropy.units as u
import cv2
import numpy as np
import requests
from . import external_http
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.wcs.utils import fit_wcs_from_points
from scipy.spatial import cKDTree

from .store import now


def image_stars(path):
    gray = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_ANYDEPTH)
    gray = cv2.GaussianBlur(gray.astype(np.float32), (5, 5), 1.1)
    maxima = (cv2.dilate(gray, np.ones((13, 13), np.uint8)) == gray) & (gray > np.percentile(gray, 98))
    y, x = np.nonzero(maxima)
    order = np.argsort(-gray[y, x])
    points = np.column_stack((x[order], y[order])).astype(float)
    _, first = np.unique((points / 8).round().astype(int), axis=0, return_index=True)
    return points[np.sort(first)[:450]]


def triangles(points):
    neighbors = cKDTree(points).query(points, k=10)[1]
    indices = np.array(sorted({tuple(sorted((i, a, b))) for i, row in enumerate(neighbors)
                               for a, b in itertools.combinations(row[1:], 2)}))
    vertices = points[indices]
    sides = np.linalg.norm(vertices[:, [1, 2, 0]] - vertices[:, [2, 0, 1]], axis=-1)
    order = sides.argsort(axis=1)
    sides = np.take_along_axis(sides, order, axis=1)
    keep = (sides[:, 0] > .15*sides[:, 2]) & (sides[:, 0]+sides[:, 1] > 1.08*sides[:, 2])
    return np.take_along_axis(indices, order, axis=1)[keep], sides[keep, :2]/sides[keep, 2:3], sides[keep, 2]


def seed_transform(pixels, coords, scales):
    # Triangle side ratios are invariant to translation, rotation and reflection.
    image_idx, ratios, lengths = triangles(pixels[:120])
    cat_idx, cat_ratios, cat_lengths = triangles(coords[:350])
    votes = {}
    for i, candidates in enumerate(cKDTree(cat_ratios).query_ball_point(ratios, .006)):
        a, b, c = pixels[image_idx[i]]
        for j in candidates:
            scale = cat_lengths[j]/lengths[i]
            if not scales[0] < scale < scales[1]:
                continue
            d, e, f = coords[cat_idx[j]]
            parity = np.sign(np.linalg.det([b-a, c-a])*np.linalg.det([e-d, f-d]))
            delta = (b-a)*[1, parity]
            angle = np.arctan2(*(e-d)[::-1])-np.arctan2(*delta[::-1])
            cs, sn = scale*np.cos(angle), scale*np.sin(angle)
            matrix = np.array([[cs, -parity*sn], [sn, parity*cs]])
            offset = d-matrix@a
            key = tuple(np.rint([cs/.035, sn/.035, parity, offset[0]/80, offset[1]/80]))
            count = votes.get(key, (0,))[0]
            votes[key] = (count+1, matrix, offset, scale)
    tree = cKDTree(coords)
    best, seed = 0, None
    for _, matrix, offset, scale in sorted(votes.values(), key=lambda v: -v[0])[:800]:
        dist, idx = tree.query(pixels[:160]@matrix.T+offset)
        score = len(np.unique(idx[dist < min(12, max(2, scale*3))]))
        if score > best:
            best, seed = score, (matrix, offset, scale)
    return seed if best >= 22 else None


def correspondences(tree, prediction, tolerance):
    dist, indices = tree.query(prediction)
    valid = np.flatnonzero(dist < tolerance)
    near = valid[np.argsort(dist[valid])]
    _, first = np.unique(indices[near], return_index=True)
    return near[first], indices[near[first]]


def fit_field(pixels, catalog, center, width, height, scales):
    if min(len(pixels), len(catalog)) < 50:
        return None
    stars = SkyCoord(catalog[:, 0]*u.deg, catalog[:, 1]*u.deg)
    ref = SkyCoord(*center, unit="deg").skyoffset_frame()

    def plane(sky):
        local = sky.transform_to(ref)
        return np.column_stack((local.lon.arcsec, local.lat.arcsec))

    coords = plane(stars)
    # Keep every fourth detection out of both triangle voting and fitting.
    hold = np.arange(len(pixels)) % 4 == 3
    train = pixels[~hold]
    seed = seed_transform(train, coords, scales)
    if seed is None:
        return None
    matrix, offset, scale = seed
    predicted = train@matrix.T+offset
    tree = cKDTree(coords)
    for factor in (4, 2.5, 1.7):
        tolerance = np.clip(scale*factor, 1.5, 12)
        ii, jj = correspondences(tree, predicted, tolerance)
        if len(ii) < 26:
            return None
        pix = train[ii]
        wcs = fit_wcs_from_points((pix[:, 0], pix[:, 1]), stars[jj], projection="TAN")
        predicted = plane(wcs.pixel_to_world(train[:, 0], train[:, 1]))
    check = pixels[hold]
    ii_check, jj_check = correspondences(tree, plane(wcs.pixel_to_world(check[:, 0], check[:, 1])), tolerance)
    independent = ~np.isin(jj_check, jj)
    check = check[ii_check[independent]]
    required = max(10, math.ceil(.30 * hold.sum()))
    if len(check) < required or np.any(np.ptp(check, axis=0) < .45*np.array([width, height])):
        return None
    residuals = wcs.pixel_to_world(*check.T).separation(stars[jj_check[independent]]).arcsec
    # Guard against chance nearest-neighbour hits in dense fields.
    random_fraction = math.pi*tolerance**2*len(coords)/max(1, np.prod(np.ptp(coords, axis=0)))
    if len(check)/hold.sum() < 5*random_fraction or np.median(residuals) > min(3, scale):
        return None
    corners = wcs.pixel_to_world(np.array([-.5,width-.5,width-.5,-.5]), np.array([-.5,-.5,height-.5,height-.5]))
    vertices = np.column_stack((corners.ra.deg, corners.dec.deg))
    if not np.isfinite(vertices).all():
        return None
    return {"wcs_header":wcs.to_header().tostring(sep="\n", endcard=False, padding=False), "corners":vertices.tolist(), "matches":len(pix)+len(check), "verified":len(check),
            "median_arcsec":round(float(np.median(residuals)), 2)}


def catalog_stars(store, ra, dec, radius, *, timeout=(5,35)):
    key = f"gaia-dr3:{ra:.6f}:{dec:.6f}:{radius:.4f}"
    cached = store.get("settings", key)
    if cached is not None:
        return np.asarray(cached).reshape(-1, 3)
    query = (f"SELECT TOP 10000 ra,dec,phot_g_mean_mag FROM gaiadr3.gaia_source WHERE "
             f"1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra:.7f},{dec:.7f},{radius:.6f})) "
             "AND phot_g_mean_mag<14 ORDER BY phot_g_mean_mag")
    errors = []
    for endpoint in ("https://gaia.aip.de/tap/sync", "https://gea.esac.esa.int/tap-server/tap/sync"):
        try:
            response = external_http.get(endpoint, params={"REQUEST":"doQuery","LANG":"ADQL",
                                        "QUERY":query, "FORMAT":"votable"}, timeout=timeout)
            response.raise_for_status()
            table = Table.read(io.BytesIO(response.content), format="votable", use_names_over_ids=True)
            values = np.asarray(np.column_stack([np.ma.filled(table[k], np.nan)
                                for k in ("ra","dec","phot_g_mean_mag")]), dtype=float)
            values = values[np.isfinite(values).all(axis=1)]
            values = values[values[:, 2].argsort()]
        except (requests.RequestException, ValueError, KeyError, ET.ParseError, OSError) as error:
            errors.append(error)
            continue
        store.put("settings", key, values.tolist())
        return values
    raise requests.ConnectionError("Gaia alignment catalogues unavailable") from errors[-1]


def pointing(record):
    obs = record.get("observation") or {}
    if obs.get("ra") is not None and obs.get("dec") is not None:
        return float(obs["ra"]), float(obs["dec"])
    name = record["metadata"].get("target") or record["id"].replace("_", " ")
    from .catalogue import catalogue_position
    if position := catalogue_position(name):
        return position
    response = external_http.get("https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?"+quote(name,safe=""), timeout=(4,12))
    response.raise_for_status()
    for resolver in ET.fromstring(response.content).iter("Resolver"):
        ra, dec = resolver.findtext("jradeg"), resolver.findtext("jdedeg")
        if ra and dec:
            return float(ra), float(dec)
    return None


def solve(store, record, *, timeout=(5,35)):
    result = {"status":"no_match", "digest":record["sha256"]["final"], "checked_at":now()}
    from .journey import SOLUTIONS
    if result["digest"] in SOLUTIONS:
        return {**result, **SOLUTIONS[result["digest"]], "status":"solved"}
    points = image_stars(store.path(record["assets"]["stars"]))
    if len(points) < 50 and record["assets"].get("stars_laid"):
        points = image_stars(store.path(record["assets"]["stars_laid"]))
    if len(points) < 50:
        return result
    try:
        center = pointing(record)
        if center is None:
            return {**result, "status":"no_pointing"}
        header = (record.get("observation") or {}).get("header", {})
        focal, pitch = float(header.get("FOCALLEN") or 0), float(header.get("XPIXSZ") or 0)
        scale = 206.265*pitch/focal if focal>0 and pitch>0 else None
        diagonal = math.hypot(record["width"],record["height"])
        radius = np.clip(diagonal*scale/7200*1.25,.15,8) if scale else 1.5
        bounds = (scale/3, scale*3) if scale else (.08, 35)
        catalog = catalog_stars(store, *center, radius, timeout=timeout)
    except (requests.RequestException, ValueError, KeyError, ET.ParseError, OSError):
        logging.warning("Gaia catalog or name lookup unavailable for %s", record["id"], exc_info=True)
        return {**result, "status":"unavailable"}
    fit = fit_field(points, catalog, center, record["width"], record["height"], bounds)
    return {**result, **fit, "status":"solved"} if fit else result
