"""Accurate observation-night tracks, with a reusable Hipparcos/Stellarium sky."""
import json
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import astropy.units as u
import numpy as np
from astropy.coordinates import AltAz, EarthLocation, FK5, SkyCoord, get_sun
from astropy.time import Time
from astropy.utils import iers

iers.conf.auto_download = False
iers.conf.auto_max_age = None
CATALOG = Path(__file__).parent / "catalog"
NAMES = {24608: "Capella", 21421: "Aldebaran", 27989: "Betelgeuse", 24436: "Rigel", 37826: "Pollux", 36850: "Castor", 32349: "Sirius", 37279: "Procyon", 91262: "Vega", 102098: "Deneb", 97649: "Altair", 11767: "Polaris", 69673: "Arcturus", 65474: "Spica", 80763: "Antares", 49669: "Regulus", 113963: "Markab", 677: "Alpheratz", 15863: "Mirfak", 9884: "Hamal", 25336: "Bellatrix", 26727: "Alnitak", 26311: "Alnilam", 25930: "Mintaka", 54061: "Dubhe", 62956: "Alioth", 67301: "Alkaid"}


@lru_cache(maxsize=1)
def star_catalog():
    # Adapted from RAHoebe/RaspAstroDisplay/skykaart_stars.py (MIT).
    stars = []
    for line in (CATALOG / "hipparcos.tsv").read_text(encoding="utf-8").splitlines():
        values = line.split("\t")
        if len(values) != 6 or not values[0].strip().isdigit():
            continue
        try:
            hip, ra, dec, mag = int(values[0]), float(values[1]), float(values[2]), float(values[3])
            stars.append({"hip": hip, "ra": ra, "dec": dec, "magnitude": mag, "pmra": float(values[4].strip() or 0), "pmdec": float(values[5].strip() or 0), "name": NAMES.get(hip, "")})
        except ValueError:
            continue
    if len(stars) < 1000:
        raise ValueError("incomplete_star_catalog")
    return stars


def build_sky(record):
    obs = record.get("observation", {})
    required = ["date_obs", "latitude", "longitude", "ra", "dec"]
    if any(obs.get(key) is None for key in required):
        raise ValueError("sky_metadata_missing")
    payload = _build(obs["date_obs"], float(obs["latitude"]), float(obs["longitude"]), float(obs["ra"]), float(obs["dec"]), obs.get("timezone", "Europe/Amsterdam"), float(obs.get("elevation") or 0))
    # Position is deliberately kept internal unless the owner explicitly publishes it.
    return {**payload, "location": {"latitude": obs["latitude"], "longitude": obs["longitude"]} if obs.get("publish_location") else None, "id": record["id"]}


@lru_cache(maxsize=32)
def _build(stamp, latitude, longitude, ra, dec, zone, elevation):
    observed = datetime.fromisoformat(stamp).astimezone(timezone.utc)
    if not 1950 <= observed.year <= 2100:
        raise ValueError("sky_date_range")
    tz = ZoneInfo(zone)
    local = observed.astimezone(tz)
    evening = (local - timedelta(hours=12)).date()
    noon = datetime.combine(evening, time(12), tz)
    end_noon = noon + timedelta(days=1)
    start_utc, end_utc = noon.astimezone(timezone.utc), end_noon.astimezone(timezone.utc)
    grid = [start_utc + timedelta(minutes=10 * index) for index in range(int((end_utc - start_utc).total_seconds() / 600) + 1)]
    times = Time(grid)
    location = EarthLocation(lat=latitude * u.deg, lon=longitude * u.deg, height=elevation * u.m)
    frame = AltAz(obstime=times, location=location, pressure=0 * u.hPa)
    target = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs").transform_to(frame)
    sun = get_sun(times).transform_to(frame)
    dark = np.flatnonzero(sun.alt.deg < -.833)
    # A polar night/day retains the full noon-to-noon interval and labels its Sun altitude.
    first, last = (max(0, int(dark[0]) - 1), min(len(grid) - 1, int(dark[-1]) + 1)) if len(dark) else (0, len(grid) - 1)
    rows = [{"time": d.timestamp(), "altitude": round(float(a), 4), "azimuth": round(float(z), 4), "sun": round(float(s), 3)} for d, a, z, s in zip(grid, target.alt.deg, target.az.deg, sun.alt.deg)][first:last + 1]
    ref = Time(observed)
    constellations = json.loads((CATALOG / "western.json").read_text(encoding="utf-8"))["constellations"]
    lines = [line for constellation in constellations for line in constellation.get("lines", [])]
    endpoints = {hip for line in lines for hip in line}
    catalog = [star for star in star_catalog() if star["magnitude"] <= 5 or star["hip"] in endpoints]
    years = ref.jyear - 1991.25
    ras = np.array([s["ra"] for s in catalog])
    decs = np.array([s["dec"] for s in catalog])
    ras += np.array([s["pmra"] for s in catalog]) * years / (3_600_000 * np.maximum(np.cos(np.deg2rad(decs)), .001))
    decs += np.array([s["pmdec"] for s in catalog]) * years / 3_600_000
    # Store horizontal positions at each frame: the browser never needs exact site coordinates.
    positions = SkyCoord(ra=ras * u.deg, dec=decs * u.deg).transform_to(AltAz(obstime=Time([r["time"] for r in rows], format="unix")[:, None], location=location, pressure=0 * u.hPa))
    star_rows = [{"hip": s["hip"], "magnitude": s["magnitude"], "name": s["name"]} for s in catalog]
    horizontal = [np.round(np.stack((a, z), axis=-1), 2).tolist() for a, z in zip(positions.alt.deg, positions.az.deg)]
    return {"evening": evening.isoformat(), "timezone": zone, "samples": rows, "stars": star_rows, "positions": horizontal, "lines": lines, "observed_at": observed.timestamp(), "polar": not len(dark) or len(dark) == len(grid), "coordinate_source": "Astropy / ERFA · ICRS → AltAz · no refraction", "star_source": "ESA Hipparcos / CDS I/239; proper motion from J1991.25", "line_source": "Stellarium western sky culture · CC BY-SA 4.0"}
