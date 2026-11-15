"""Read-only viewing modes for the television, using local media and ephemerides."""
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import uuid
from zoneinfo import ZoneInfo

import astropy.units as u
import cv2
import numpy as np
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body
from astropy.time import Time
from PIL import Image

from . import hubble, journey
from .solar import observing_site, observing_time


def program(store, record):
    field = journey.geometry(store, record)
    sky = field["kind"] != "missing" and journey.movie(store, record, field, cached_only=True)
    options = []
    if hubble.eligible(record):
        try:
            options = hubble.fields(store, record, local_only=True)
        except ValueError:
            pass
    trips = []
    for item in options:
        try:
            cached = hubble.movie(store, record, item["id"], tv=True, cached_only=True, options=options)
        except ValueError:
            continue
        if cached:
            trips.append({"id": item["id"], "credit": hubble.tv_credit(item),
                          "url": f"/media/{record['id']}/hubble/{item['id']}?view=tv&cached=1"})
    return {"journey": f"/media/{record['id']}/journey?cached=1" if sky else None, "trips": trips}


def registration_matrix(reference, other, size, source_size):
    """Pixel-centre homography via a shared TAN plane, including RA wrap and reflection."""
    corners = SkyCoord(*np.asarray(reference).T, unit="deg")
    basis = SkyCoord(corners.cartesian.mean(), frame="icrs").skyoffset_frame()
    def to_plane(points, dims):
        rays = points.transform_to(basis).cartesian.xyz.value
        if np.min(rays[0]) <= 0:
            raise ValueError("no_overlap")
        plane = np.float32((rays[1:] / rays[0]).T)
        pixels = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]) * np.float32(dims) - .5
        return cv2.getPerspectiveTransform(pixels, plane)
    return np.linalg.solve(to_plane(corners, size), to_plane(SkyCoord(*np.asarray(other).T, unit="deg"), source_size))


def aligned_photo(store, reference, other):
    a, b = [journey.geometry(store, r) for r in (reference, other)]
    if any(f.get("kind") not in {"gaia", "wcs"} for f in (a, b)):
        raise ValueError("registration_missing")
    ratio = min(1, 2560 / max(reference["width"], reference["height"]))
    size = tuple(max(1, round(reference[k] * ratio)) for k in ("width", "height"))
    signature = ["aligned-v2", a, b, size, reference["sha256"]["final"], other["sha256"]["final"]]
    key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    folder = store.path("survey-cache/tv-aligned")
    result = folder / (key + ".webp")
    if result.is_file():
        return result
    path = store.path(other["assets"]["final"])
    # Preserve the tonal range of 16-bit captures when converting to a TV display image.
    raster = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if raster is None:
        raise ValueError("invalid_image")
    if raster.dtype == np.uint16:
        raster = cv2.convertScaleAbs(raster, alpha=1/257)
    color = cv2.COLOR_GRAY2RGBA if raster.ndim == 2 else (
        cv2.COLOR_BGRA2RGBA if raster.shape[2] == 4 else cv2.COLOR_BGR2RGBA)
    matrix = registration_matrix(a["corners"], b["corners"], size, raster.shape[1::-1])
    layer = cv2.warpPerspective(cv2.cvtColor(raster, color), matrix, size, flags=cv2.INTER_LINEAR)
    if not layer[:, :, 3].any():
        raise ValueError("no_overlap")
    folder.mkdir(exist_ok=True, parents=True)
    tmp = folder / (uuid.uuid4().hex + ".webp")
    try:
        Image.fromarray(layer).save(tmp, quality=94, method=2)
        tmp.replace(result)
    finally:
        tmp.unlink(missing_ok=True)
    return result


@lru_cache(maxsize=64)
def track(day, zone, lat, lon, height, body, ra, dec):
    tz = ZoneInfo(zone)
    start = datetime.combine(day, time(0 if body == "sun" else 12), tz)
    begin, end = start.timestamp(), (start + timedelta(days=1)).timestamp()
    stamps = np.arange(begin, end + 1, 600)
    times = Time(stamps, format="unix")
    site = EarthLocation.from_geodetic(lon*u.deg, lat*u.deg, height*u.m)
    frame = AltAz(obstime=times, location=site, pressure=0*u.hPa)
    def horizontal(name):
        return get_body(name, times, location=site, ephemeris="builtin").transform_to(frame)
    positions = {}
    for name in ("moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "sun"):
        obj = horizontal(name)
        positions[name] = np.round(np.column_stack((obj.az.deg, obj.alt.deg)), 2).tolist()
    if body in positions:
        target = positions[body]
    else:
        obj = horizontal(body) if body else SkyCoord(ra*u.deg, dec*u.deg).transform_to(frame)
        target = np.round(np.column_stack((obj.az.deg, obj.alt.deg)), 2).tolist()
    # Altitudes below zero stay in the data so polar day and invisible objects are unambiguous.
    visible_hours = [i for i, sun in enumerate(positions["sun"]) if body == "sun" or sun[1] < -0.833]
    return {"day": day.isoformat(), "start": begin, "step": 600, "target": target, "bodies": positions,
            "hours": visible_hours, "peak": max(visible_hours, key=lambda i: target[i][1], default=None)}


def night_comparison(record, now=None):
    obs = record.get("observation") or {}
    body = (record.get("body") or "").lower()
    stamp, day_only = observing_time(record)
    if not stamp or (not body and any(obs.get(k) is None for k in ("ra", "dec", "latitude", "longitude"))):
        raise ValueError("sky_metadata_missing")
    lat, lon, height, default = observing_site(obs)
    zone = obs.get("timezone") or "Europe/Amsterdam"
    tz = ZoneInfo(zone)
    captured = datetime.fromisoformat(stamp).astimezone(tz)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    def night(t):
        # Before noon, show the observing night still in progress.
        return t.date() if body == "sun" else (t - timedelta(hours=12)).date()
    args = (zone, lat, lon, height, body, obs.get("ra"), obs.get("dec"))
    return {"capture": track(night(captured), *args), "tonight": track(night(now), *args),
            "timezone": zone, "observed": captured.timestamp(), "now": now.timestamp(),
            "day_only": day_only, "default_site": default}
