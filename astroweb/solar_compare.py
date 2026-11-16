"""Dated SDO comparisons with SunPy heliographic coordinates, never guessed north."""
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import logging

import astropy.units as u
import cv2
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time

from . import external_http
from .journey import disk_in_photo
from .render import read_rgb, resize_long
from .solar import observing_time

API = "https://api.helioviewer.org/v2/"
CHANNELS = ((18,"HMI continuum · 6173 Å","visible"),(10,"AIA · 171 Å","EUV"))


def fetch(endpoint, params, limit=2*1024**2):
    with external_http.get(API+endpoint+"/",params=params,stream=True,timeout=(5,25)) as reply:
        reply.raise_for_status()
        if int(reply.headers.get("Content-Length",0))>limit:
            raise ValueError("observatory_solar_unavailable")
        data = bytearray()
        for chunk in reply.iter_content(128*1024):
            data.extend(chunk)
            if len(data)>limit:
                raise ValueError("observatory_solar_unavailable")
        return bytes(data)


def fits_header(xml):
    from astropy.io.fits import Header
    header = Header()
    root = ET.fromstring(xml)
    node = root.find("fits")
    if node is None:
        raise ValueError("observatory_solar_unavailable")
    for field in node:
        name,text = field.tag.upper()," ".join((field.text or "").split())
        if len(name)>8 or not text or name in {"COMMENT","HISTORY"}:
            continue
        value = text
        try:
            number = float(text)
            if np.isfinite(number):value = int(number) if number.is_integer() else number
        except ValueError:
            pass
        if isinstance(value,str) and not value.isascii():
            continue
        header[name] = value
    return header


def grid(header, epoch=None):
    import sunpy.map
    from sunpy.coordinates import frames
    from sunpy.physics.differential_rotation import solar_rotate_coordinate
    width,height = int(header["NAXIS1"]),int(header["NAXIS2"])
    if not (16<=width<=8192 and 16<=height<=8192):
        raise ValueError("observatory_solar_unavailable")
    # Only metadata are needed for coordinate transforms. The archive preview is
    # already north-up; FITS pixel y is converted explicitly to display y.
    reference = sunpy.map.Map(np.zeros((height,width),np.uint8),header)
    epoch_time=Time(datetime.fromisoformat(epoch.replace("Z","+00:00"))) if epoch else reference.date
    lines = []
    for kind in ("latitude","longitude"):
        for fixed in range(-60,61,30):
            varying = np.linspace(-89.5,89.5,91)
            lon,lat = (varying,np.full(91,fixed)) if kind=="latitude" else (np.full(91,fixed),varying)
            points = SkyCoord(lon*u.deg,lat*u.deg,reference.rsun_meters,
                              frame=frames.HeliographicStonyhurst,obstime=epoch_time)
            if epoch and abs((epoch_time-reference.date).to_value(u.s))>1:
                points=solar_rotate_coordinate(points,observer=reference.observer_coordinate).transform_to(frames.HeliographicStonyhurst(obstime=reference.date))
            visible = points.transform_to(frames.Heliocentric(observer=reference.observer_coordinate,obstime=reference.date)).z>0*u.m
            projected = points.transform_to(reference.coordinate_frame)
            x,y = reference.world_to_pixel(projected)
            xy = np.c_[(x.to_value(u.pix)+.5)/width,1-(y.to_value(u.pix)+.5)/height]
            lines.append([p.tolist() if ok and np.isfinite(p).all() else None for p,ok in zip(xy,visible)])
    center = reference.world_to_pixel(SkyCoord(0*u.arcsec,0*u.arcsec,frame=reference.coordinate_frame))
    return dict(lines=lines,center=[float((center.x.value+.5)/width),float(1-(center.y.value+.5)/height)],
                radius=[float(reference.rsun_obs.to_value(u.arcsec)/abs(reference.scale.axis1.to_value(u.arcsec/u.pix))/width),
                        float(reference.rsun_obs.to_value(u.arcsec)/abs(reference.scale.axis2.to_value(u.arcsec/u.pix))/height)])


def reference(stamp, channel, label, spectrum, folder):
    import json
    requested = datetime.fromisoformat(stamp.replace("Z","+00:00"))
    if requested.tzinfo is None:requested=requested.replace(tzinfo=timezone.utc)
    query_time = requested.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = json.loads(fetch("getClosestImage",{"date":query_time,"sourceId":channel}))
    actual = datetime.fromisoformat(result["date"].replace(" ","T").replace("Z","+00:00"))
    if actual.tzinfo is None:actual=actual.replace(tzinfo=timezone.utc)
    delta = abs((actual-requested).total_seconds())
    if delta>12*3600:
        raise ValueError("observatory_solar_no_match")
    identifier = str(result["id"])
    if not identifier.isdigit():
        raise ValueError("observatory_solar_unavailable")
    header = fits_header(fetch("getJP2Header",{"id":identifier}))
    (folder/f"solar-{channel}.hdr").write_text(header.tostring(sep="\n"),encoding="ascii")
    if header.get("DATE-OBS"):
        actual=datetime.fromisoformat(str(header["DATE-OBS"]).replace("Z","+00:00"))
        if actual.tzinfo is None:actual=actual.replace(tzinfo=timezone.utc)
        delta=abs((actual-requested).total_seconds())
        if delta>12*3600:raise ValueError("observatory_solar_no_match")
    calibration = grid(header,stamp)
    payload = fetch("downloadImage",{"id":identifier,"width":1536,"type":"png"},20*1024**2)
    image = cv2.imdecode(np.frombuffer(payload,np.uint8),cv2.IMREAD_COLOR)
    if image is None or max(image.shape[:2])>1600:
        raise ValueError("observatory_solar_unavailable")
    filename = f"solar-{channel}.webp"
    if not cv2.imwrite(str(folder/filename),image,[cv2.IMWRITE_WEBP_QUALITY,96]):
        raise ValueError("observatory_failed")
    return dict(image=filename,channel=channel,name=label,spectrum=spectrum,time=actual.isoformat(),
                delta_seconds=delta,grid=calibration,credit="NASA / SDO / "+("HMI" if channel==18 else "AIA")+" · Helioviewer",
                source="https://helioviewer.org/?date="+actual.strftime("%Y-%m-%dT%H:%M:%SZ"),north_up=True)


def build(store, record, folder):
    if record.get("body")!="SUN":
        raise ValueError("observatory_solar_only")
    stamp,approximate = observing_time(record)
    if not stamp:
        raise ValueError("observatory_solar_date")
    import sunpy.coordinates.sun as sun
    requested = datetime.fromisoformat(stamp.replace("Z","+00:00")).astimezone(timezone.utc)
    when = Time(requested)
    rgb = np.uint8(np.clip(resize_long(read_rgb(store.path(record["assets"]["final"])),1600),0,1)*255)
    image = cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(folder/"solar-own.webp"),image,[cv2.IMWRITE_WEBP_QUALITY,97])
    center,radius = disk_in_photo(image)
    own = dict(image="solar-own.webp",center=(center/[image.shape[1],image.shape[0]]).tolist(),
               radius=[radius/image.shape[1],radius/image.shape[0]] if radius else None,orientation="unknown")
    references,errors = [],[]
    for channel,label,spectrum in CHANNELS:
        try:
            references.append(reference(requested.isoformat(),channel,label,spectrum,folder))
        except Exception:
            logging.warning("Solar comparison channel %s unavailable",channel,exc_info=True)
            errors.append(channel)
    return dict(own=own,references=references,unavailable_channels=errors,time=requested.isoformat(),day_only=approximate,
                p_angle=float(sun.P(when).to_value(u.deg)),b0=float(sun.B0(when).to_value(u.deg)),
                l0=float(sun.L0(when).to_value(u.deg)),rotation=float(sun.carrington_rotation_number(when)),
                source="SunPy / NASA SDO / Helioviewer",alignment="disk-size-only-no-assumed-orientation")


def surface_point(header, x=None, y=None, landmark=None):
    """Select or propagate a solar surface coordinate, not a recognised sunspot."""
    import sunpy.map
    from sunpy.coordinates import frames
    from sunpy.physics.differential_rotation import solar_rotate_coordinate
    reference=sunpy.map.Map(np.zeros((1,1),np.uint8),header)
    width,height=int(header["NAXIS1"]),int(header["NAXIS2"])
    if landmark:
        epoch=datetime.fromisoformat(landmark["epoch"].replace("Z","+00:00"))
        if epoch.tzinfo is None or not 1950<=epoch.year<=2100:
            raise ValueError("invalid_parameters")
        original=SkyCoord(landmark["lon"]*u.deg,landmark["lat"]*u.deg,reference.rsun_meters,
                          frame=frames.HeliographicStonyhurst,obstime=Time(epoch))
        original=original.transform_to(frames.Helioprojective(observer="earth",obstime=Time(epoch)))
        coordinate=SkyCoord(solar_rotate_coordinate(original,observer=reference.observer_coordinate))
    else:
        coordinate=SkyCoord(reference.pixel_to_world((x*width-.5)*u.pix,(height-.5-y*height)*u.pix).make_3d())
        surface=coordinate.transform_to(frames.HeliographicStonyhurst(obstime=reference.date))
        if not np.isfinite([surface.lon.deg,surface.lat.deg,surface.radius.to_value(u.m)]).all():
            raise ValueError("obs_off_sun")
        landmark=dict(lon=float(surface.lon.deg),lat=float(surface.lat.deg),epoch=reference.date.isot+"Z")
    visible=coordinate.transform_to(frames.Heliocentric(observer=reference.observer_coordinate,obstime=reference.date)).z>0*u.m
    px,py=reference.world_to_pixel(coordinate)
    surface=coordinate.transform_to(frames.HeliographicStonyhurst(obstime=reference.date))
    if not np.isfinite([px.value,py.value,surface.lon.deg,surface.lat.deg]).all():
        raise ValueError("obs_off_sun")
    return dict(landmark=landmark,x=float((px.value+.5)/width),y=float(1-(py.value+.5)/height),
                lat=float(surface.lat.deg),lon=float(surface.lon.deg),visible=bool(visible),
                time=reference.date.isot+"Z",model="SunPy Howard differential rotation; surface coordinate only")
