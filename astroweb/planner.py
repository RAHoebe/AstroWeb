"""Local-calendar observing windows, computed once on the server with Astroplan."""
import calendar
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import astropy.units as u
import numpy as np
from astroplan import Observer, moon_illumination
from astropy.coordinates import EarthLocation, SkyCoord, get_body, get_sun
from astropy.time import Time
from astropy.utils import iers

from .journey import geometry
from .solar import CENTRAL_NL

STEP = 1800


def site(record, private=False):
    obs = record.get("observation") or {}
    allowed = private or obs.get("publish_location")
    known = allowed and obs.get("latitude") is not None and obs.get("longitude") is not None
    latitude,longitude = (obs["latitude"],obs["longitude"]) if known else CENTRAL_NL
    # Do not reveal a private site through public curves or derived rise/set times.
    height = (obs.get("elevation") or 0) if known else 0
    zone = (obs.get("timezone") or "Europe/Amsterdam") if known else "Europe/Amsterdam"
    return EarthLocation.from_geodetic(longitude*u.deg,latitude*u.deg,height*u.m),ZoneInfo(zone),not known


def coordinates(store, record):
    if record.get("body") or record.get("capture_kind"):
        raise ValueError("observatory_planner_missing")
    field = geometry(store,record)
    if field.get("corners"):
        points = SkyCoord(*np.asarray(field["corners"]).T,unit="deg")
        return SkyCoord(points.cartesian.mean(),frame="icrs")
    if field.get("center"):
        return SkyCoord(*field["center"],unit="deg")
    raise ValueError("observatory_planner_missing")


def samples(days, zone):
    starts,ends,midpoints,ranges = [],[],[],[]
    for day in days:
        start = datetime.combine(day,time(12),zone).timestamp()
        end = datetime.combine(day+timedelta(days=1),time(12),zone).timestamp()
        stamps = np.arange(start,end,STEP)
        ranges.append((len(starts),len(starts)+len(stamps)))
        starts.extend(stamps);ends.extend(np.minimum(stamps+STEP,end))
        midpoints.extend((stamps+np.minimum(stamps+STEP,end))/2)
    return np.array(starts),np.array(ends),np.array(midpoints),ranges


def nights(observer, target, days, zone):
    starts,ends,mids,ranges = samples(days,zone)
    times = Time(mids,format="unix")
    with iers.conf.set_temp("auto_download",False),iers.conf.set_temp("auto_max_age",None):
        frame = observer.altaz(times)
        alt = target.transform_to(frame).alt.deg if target is not None else None
        sun = get_sun(times).transform_to(frame).alt.deg
        moon = get_body("moon",times,observer.location)
        moon_alt = moon.transform_to(frame).alt.deg
        moon_sep = target.transform_to(moon.frame).separation(moon).deg if target is not None else None
        phase = moon_illumination(times)
    good = ((alt>=30)&(sun<=-18)&((moon_alt<=0)|(moon_sep>=35))) if target is not None else sun<=-18
    rows = []
    for day,(a,b) in zip(days,ranges):
        indices = np.flatnonzero(good[a:b])+a
        windows = []
        if len(indices):
            for group in np.split(indices,np.flatnonzero(np.diff(indices)>1)+1):
                windows.append([float(starts[group[0]]),float(ends[group[-1]])])
        nighttime = np.flatnonzero(sun[a:b]<=-18)+a
        peak = int(nighttime[np.argmax(alt[nighttime])]) if len(nighttime) and alt is not None else None
        rows.append(dict(date=day.isoformat(),windows=windows,hours=round(float(np.sum(ends[indices]-starts[indices])/3600),2),
                         peak_altitude=round(float(alt[peak]),1) if peak is not None else None,
                         peak_time=float(mids[peak]) if peak is not None else None,
                         moon_illumination=round(float(phase[(a+b)//2]),3),
                         dark_hours=round(float(np.sum(ends[nighttime]-starts[nighttime])/3600),2)))
    return rows


def build(store, record, month, private=False):
    year,number = map(int,month.split("-"))
    target = coordinates(store,record)
    location,zone,assumed = site(record,private)
    observer = Observer(location=location,timezone=zone,pressure=0*u.hPa)
    days = [date(year,number,i) for i in range(1,calendar.monthrange(year,number)[1]+1)]
    rows = nights(observer,target,days,zone)
    seasons = nights(observer,target,[date(year,i,15) for i in range(1,13)],zone)
    best = sorted((r for r in rows if r["hours"]>0),key=lambda r:(-r["hours"],r["moon_illumination"],r["date"]))[:3]
    return dict(month=month,timezone=zone.key,default_site=assumed,days=rows,seasons=seasons,best=[r["date"] for r in best],
                thresholds=dict(altitude=30,sun=-18,moon_separation=35),step_minutes=30,
                source="Astroplan / Astropy / ERFA",weather=False)


def collection_calendar(month):
    year,number=map(int,month.split('-'))
    zone=ZoneInfo('Europe/Amsterdam')
    location=EarthLocation.from_geodetic(CENTRAL_NL[1]*u.deg,CENTRAL_NL[0]*u.deg,0*u.m)
    observer=Observer(location=location,timezone=zone,pressure=0*u.hPa)
    days=[date(year,number,i) for i in range(1,calendar.monthrange(year,number)[1]+1)]
    rows=nights(observer,None,days,zone)
    seasons=nights(observer,None,[date(year,i,15) for i in range(1,13)],zone)
    best=sorted((r for r in rows if r['hours']>0),key=lambda r:(r['moon_illumination'],-r['hours']))[:3]
    return dict(month=month,timezone=zone.key,default_site=True,days=rows,seasons=seasons,best=[r['date'] for r in best],
                kind='collection',step_minutes=30,thresholds=dict(sun=-18),source='Astroplan / Astropy / ERFA',weather=False)
