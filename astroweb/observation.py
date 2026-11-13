"""Read relevant primary-HDU FITS metadata without loading or changing image data."""
import copy
import math
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from astropy.io import fits
from astropy.time import Time

from .store import now

FIELDS = ["DATE-OBS", "DATE-END", "TIMESYS", "OBJECT", "TELESCOP", "INSTRUME", "FILTER", "RA", "DEC", "CRVAL1", "CRVAL2", "CTYPE1", "CTYPE2", "OBJCTRA", "OBJCTDEC", "SITELAT", "SITELONG", "SITEELEV", "OBSGEO-B", "OBSGEO-L", "OBSGEO-H", "EXPTIME", "EXPOSURE", "LIVETIME", "NCOMBINE", "WZNSUBS", "WZNOTE", "WZCENTRE", "FOCALLEN", "XPIXSZ", "YPIXSZ", "GAIN", "CCD-TEMP", "NAXIS1", "NAXIS2"]


def finite(value, low=-1e12, high=1e12):
    try:
        number = float(value)
        return number if math.isfinite(number) and low <= number <= high else None
    except (TypeError, ValueError):
        return None


def read_observation(path):
    path = Path(path)
    if path.suffix.lower() not in {".fits", ".fit", ".fts"} or path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError("invalid_fits")
    try:
        with path.open("rb") as stream:
            if stream.read(9) != b"SIMPLE  =":
                raise ValueError("invalid_fits")
        with fits.open(path, mode="readonly", memmap=True, lazy_load_hdus=True) as hdus:
            header = hdus[0].header
            raw = {key: header[key] for key in FIELDS if key in header}
            date_comment = header.comments["DATE-OBS"] if "DATE-OBS" in header else ""
    except (OSError, IndexError, KeyError, TypeError):
        raise ValueError("invalid_fits") from None
    date_obs = None
    scale = str(raw.get("TIMESYS", "UTC")).strip().lower()
    if raw.get("DATE-OBS") and scale in {"utc", "tai", "tt"}:
        try:
            date_obs = Time(str(raw["DATE-OBS"]), scale=scale).utc.to_datetime().isoformat() + "+00:00"
        except (ValueError, TypeError):
            pass
    ra = finite(raw.get("RA"), 0, 360)
    dec = finite(raw.get("DEC"), -90, 90)
    coord_source = "RA/DEC"
    if "RA" in str(raw.get("CTYPE1", "")) and "DEC" in str(raw.get("CTYPE2", "")):
        ra, dec = finite(raw.get("CRVAL1"), 0, 360), finite(raw.get("CRVAL2"), -90, 90)
        coord_source = "WCS CRVAL"
    if ra is None and raw.get("OBJCTRA") and raw.get("OBJCTDEC"):
        from astropy.coordinates import SkyCoord
        import astropy.units as u
        try:
            position = SkyCoord(str(raw["OBJCTRA"]), str(raw["OBJCTDEC"]), unit=(u.hourangle, u.deg))
            ra, dec = float(position.ra.deg), float(position.dec.deg)
            coord_source = "OBJCTRA/OBJCTDEC"
        except ValueError:
            pass
    exposure = finite(raw.get("EXPTIME", raw.get("EXPOSURE")), 0, 1e7)
    frames = finite(raw.get("NCOMBINE", raw.get("WZNSUBS")), 1, 1e8)
    integration = finite(raw.get("LIVETIME"), 0, 1e10)
    integration_source = "LIVETIME"
    if integration is None and exposure is not None and frames is not None:
        integration = exposure * frames
        integration_source = "EXPTIME × NCOMBINE"
    return {"source": "FITS", "filename": path.name, "date_obs": date_obs, "time_source": "DATE-OBS", "time_comment": date_comment, "time_scale": scale.upper(), "time_scale_assumed": "TIMESYS" not in raw, "ra": ra, "dec": dec, "coordinate_source": coord_source, "latitude": finite(raw.get("SITELAT", raw.get("OBSGEO-B")), -90, 90), "longitude": finite(raw.get("SITELONG", raw.get("OBSGEO-L")), -180, 180), "elevation": finite(raw.get("SITEELEV", raw.get("OBSGEO-H", 0)), -500, 9000), "timezone": "Europe/Amsterdam", "exposure": exposure, "frames": int(frames) if frames else None, "integration": integration, "integration_source": integration_source, "telescope": str(raw.get("TELESCOP", "")).split("_")[0], "filter": str(raw.get("FILTER", "")).strip(), "mosaic": str(raw.get("WZNOTE", "")), "publish_location": False, "header": raw, "read_at": now()}


def attach_fits(store, record, source, observation=None):
    observation = observation or read_observation(source)
    dest = store.path(f"objects/{record.get('storage_id', record['id'])}/fits-{uuid.uuid4().hex[:10]}/{Path(source).name}")
    dest.parent.mkdir(parents=True)
    shutil.copyfile(source, dest)
    return store.update("objects", record["id"], fits=dest.relative_to(store.root).as_posix(), observation=observation)


def public_observation(observation):
    result = {key: observation.get(key) for key in ["source", "date_obs", "time_source", "time_comment", "time_scale", "time_scale_assumed", "ra", "dec", "coordinate_source", "timezone", "exposure", "frames", "integration", "integration_source", "telescope", "filter", "mosaic"]}
    if observation.get("publish_location"):
        result.update(latitude=observation.get("latitude"), longitude=observation.get("longitude"))
    return result


def observation_overrides(original, raw):
    allowed = {"date_obs", "latitude", "longitude", "ra", "dec", "timezone", "publish_location"}
    if set(raw) - allowed:
        raise ValueError("invalid_observation")
    result = copy.deepcopy(original)
    for key, low, high in [("latitude", -90, 90), ("longitude", -180, 180), ("ra", 0, 360), ("dec", -90, 90)]:
        if key in raw:
            number = finite(raw[key], low, high)
            if number is None:
                raise ValueError("invalid_observation")
            result[key] = number
    if "timezone" in raw:
        try:
            ZoneInfo(raw["timezone"])
        except (KeyError, TypeError):
            raise ValueError("invalid_observation") from None
        result["timezone"] = raw["timezone"]
    if "date_obs" in raw:
        try:
            stamp = datetime.fromisoformat(raw["date_obs"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError()
            result["date_obs"] = stamp.isoformat()
        except (ValueError, TypeError, AttributeError):
            raise ValueError("invalid_observation") from None
    if "publish_location" in raw:
        if not isinstance(raw["publish_location"], bool):
            raise ValueError("invalid_observation")
        result["publish_location"] = raw["publish_location"]
    result["source"] = "FITS + admin" if original.get("source", "").startswith("FITS") else "admin"
    result["modified_at"] = now()
    return result
