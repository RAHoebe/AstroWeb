"""Light-travel times with an explicit distinction between distance definitions."""
from urllib.parse import quote

import astropy.units as u
import numpy as np
from astropy.cosmology import Planck18

from . import external_http
from .physical import field_scale


def redshift(store, record):
    meta = record["metadata"]
    if meta.get("redshift") is not None:
        return dict(z=meta["redshift"],source=meta["redshift_source"],method="admin")
    name = meta["target"]
    key = "cosmic-ned-v1:"+name.upper()
    cached = store.get("settings",key)
    if cached is not None:
        return cached
    external_http._check()
    from astroquery.ipac.ned import NedClass
    client = NedClass();client.TIMEOUT = 20
    rows = client.query_object(name)
    result = None
    if len(rows)==1 and not np.ma.is_masked(rows["Redshift"][0]):
        z = float(rows["Redshift"][0])
        if np.isfinite(z) and 0<z<=20:
            result = dict(z=z,source="https://ned.ipac.caltech.edu/byname?objname="+quote(name),method="NED")
    if result:
        store.put("settings",key,result)
    return result


def build(store, record):
    if record.get("body") or record.get("capture_kind"):
        raise ValueError("observatory_cosmic_missing")
    physical = field_scale(store,record)
    distance = physical.get("distance_ly")
    if distance:
        return dict(method="catalogue",lookback_years=distance,distance_ly=distance,
                    source=physical.get("source"),physical=physical,
                    model=None,redshift=None,universe_age_years=None)
    try:
        measured = redshift(store,record)
    except Exception as exc:
        raise ValueError("observatory_cosmic_missing") from exc
    if not measured:
        raise ValueError("observatory_cosmic_missing")
    z = measured["z"]
    lookback = float(Planck18.lookback_time(z).to_value(u.yr))
    angular = float(Planck18.angular_diameter_distance(z).to_value(u.lyr))
    return dict(method="redshift",redshift=z,source=measured["source"],model="Planck18",
                lookback_years=lookback,distance_ly=None,physical=None,
                angular_diameter_distance_ly=angular,
                luminosity_distance_ly=float(Planck18.luminosity_distance(z).to_value(u.lyr)),
                comoving_distance_ly=float(Planck18.comoving_distance(z).to_value(u.lyr)),
                universe_age_years=float(Planck18.age(0).to_value(u.yr)),
                age_at_emission_years=float(Planck18.age(z).to_value(u.yr)),
                low_redshift=z<.01,
                model_source="https://docs.astropy.org/en/stable/cosmology/realizations.html")
