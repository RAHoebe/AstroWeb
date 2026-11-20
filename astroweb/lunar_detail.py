"""Registered flights across real, map-projected LROC imagery.

The dated SVS reference establishes the capture's orientation and libration.
Lunaserv tiles retain lunar longitude/latitude through every resolution level;
an oblique publicity photograph is never treated as a map projection.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse, urlencode

import cv2
import numpy as np
import requests

from . import external_http
from .camera import FocusZoom
from .collection import capture_date
from .journey import disk_in_photo, smooth

CREDIT = "NASA/GSFC/ASU / LROC; NASA SVS / Ernie Wright"
VERSION = "lunar-registered-v4"
WMS = "https://wms.im-ldi.com/"
# East-positive longitude, planetocentric latitude, final map span in degrees.
# Apollo: NASA NSSDCA lunar_sites.html; named features: IAU/USGS Gazetteer.
SITES = {
    "PIA12909": (23.47314, .67416, .04, "11", "Landingsplaats Apollo 11", "Apollo 11 landing site"),
    "PIA12922": (-23.4219, -3.0128, .04, "12", "Landingsplaats Apollo 12", "Apollo 12 landing site"),
    "PIA12897": (-17.47194, -3.64589, .20, "14", "Apollo 14 en de Cone-krater", "Apollo 14 and Cone crater"),
    "GSFC_20171208_Archive_e001828": (-11.22, -43.30, 7., None, "Tycho-krater", "Tycho crater"),
    "moon-copernicus": (-20.08, 9.62, 7., None, "Copernicus-krater", "Copernicus crater"),
    "moon-plato": (-9.38, 51.62, 10., None, "Plato-krater", "Plato crater"),
    "moon-aristarchus": (-47.49, 23.73, 4., None, "Aristarchus-krater", "Aristarchus crater"),
    "moon-clavius": (-14.73, -58.62, 20., None, "Clavius-krater", "Clavius crater"),
    "moon-tranquillitatis": (30.83, 8.35, 40., None, "Mare Tranquillitatis · Zee der Rust", "Mare Tranquillitatis · Sea of Tranquility"),
    "moon-imbrium": (-14.91, 34.72, 55., None, "Mare Imbrium · Regenzee", "Mare Imbrium · Sea of Showers"),
}
GAZETTEER = dict(zip(list(SITES)[3:], (6163,1296,4757,380,1236,3691,3678)))


def options():
    return [dict(id=id, name=dict(nl=s[4], en=s[5]), credit=CREDIT,
                 source="https://data.lroc.im-ldi.com/lroc/?" + urlencode(dict(c_lon=s[0], c_lat=s[1])),
                 coordinate_source="https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html" if s[3]
                 else "https://planetarynames.wr.usgs.gov/Feature/"+str(GAZETTEER[id]), alignment="lunar-map")
            for id, s in SITES.items()]


def cache_image(store, key, url, params=None, shape=None):
    path = store.path("survey-cache/lunar/" + hashlib.sha256(key.encode()).hexdigest() + ".png")
    image = cv2.imread(str(path)) if path.is_file() else None
    if image is not None and (shape is None or image.shape[:2] == shape):
        return image
    for attempt in range(2 if url == WMS else 1):
        try:
            reply = external_http.get("https://wms1.im-ldi.com/" if attempt else url, params=params, timeout=(5, 25))
            reply.raise_for_status()
            break
        except requests.RequestException:
            if url != WMS or attempt:
                raise
    image = cv2.imdecode(np.frombuffer(reply.content, np.uint8), cv2.IMREAD_COLOR)
    if image is None or (shape is not None and image.shape[:2] != shape):
        raise ValueError("solarDetailUnavailable")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(uuid.uuid4().hex + ".png")
    try:
        if not cv2.imwrite(str(tmp), image):
            raise OSError("lunar cache write failed")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return image


def reference(store, record):
    try:
        stamp = datetime.fromisoformat(capture_date(record).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        hour = stamp.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat(timespec="minutes")[:16]
    except (AttributeError, TypeError, ValueError):
        raise ValueError("solarDetailAlignment") from None
    key = "lunar-reference:" + hour
    data = store.get("settings", key)
    if data is None:
        reply = external_http.get("https://svs.gsfc.nasa.gov/api/dialamoon/" + hour, timeout=(5, 25))
        reply.raise_for_status()
        data = reply.json()
    try:
        url = urlparse(data["image"]["url"])
        if (data["time"] != hour or url.hostname != "svs.gsfc.nasa.gov" or not url.path.startswith("/vis/")
                or not all(np.isfinite(float(data[k])) for k in ("subearth_lon", "subearth_lat", "posangle"))):
            raise ValueError("solarDetailUnavailable")
    except (KeyError, TypeError, AttributeError):
        raise ValueError("solarDetailUnavailable") from None
    store.put("settings", key, data)
    image = cache_image(store, key, "https://svs.gsfc.nasa.gov" + url.path, shape=(730, 730))
    center, radius = disk_in_photo(image)
    if radius is None:
        raise ValueError("solarDetailAlignment")
    return image, data, center, radius


def register(photo, reference):
    """Fit rotation/scale (or reflection), with independent, distributed checks."""
    def reduced(image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        factor = min(1, 1100/max(gray.shape))
        gray = cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
        scale = np.diag([gray.shape[1]/image.shape[1], gray.shape[0]/image.shape[0], 1.])
        scale[:2, 2] = (np.diag(scale)[:2]-1)/2
        return cv2.createCLAHE(2., (8, 8)).apply(gray), scale
    own, basis = reduced(photo)
    dest, target_basis = reduced(reference)
    sift = cv2.SIFT_create(nfeatures=3000)
    keys, desc = sift.detectAndCompute(own, None)
    if desc is None:
        raise ValueError("solarDetailAlignment")
    for mirrored in (False, True):
        trial = cv2.flip(dest, 1) if mirrored else dest
        other, values = sift.detectAndCompute(trial, None)
        if values is None or len(values)<2:
            continue
        pairs = cv2.BFMatcher().knnMatch(desc, values, k=2)
        good = {m.trainIdx:m for m,n in pairs if m.distance < .72*n.distance}
        if len(good)<32:
            continue
        a = np.float32([keys[m.queryIdx].pt for m in good.values()])
        b = np.float32([other[m.trainIdx].pt for m in good.values()])
        hold = np.arange(len(a))%4 == 0
        fit, mask = cv2.estimateAffinePartial2D(a[~hold], b[~hold], method=cv2.RANSAC, ransacReprojThreshold=2.5)
        if fit is None or mask.sum()<24:
            continue
        error = np.linalg.norm(cv2.transform(a[None], fit)[0]-b, axis=1)
        check = hold & (error<3.)
        if check.sum()<10 or np.ptp(b[check], axis=0).min()<min(dest.shape)*.25:
            continue
        mirror = np.array([[-1,0,dest.shape[1]-1],[0,1,0],[0,0,1.]]) if mirrored else np.eye(3)
        matrix = np.linalg.inv(target_basis) @ mirror @ np.vstack((fit,[0,0,1.])) @ basis
        report = dict(matches=int((error<3).sum()), verified=int(check.sum()), median_px=float(np.median(error[check])))
        return matrix, report
    raise ValueError("solarDetailAlignment")


def project(lon, lat, data, center, radius):
    lon, lat, lon0, lat0, angle = np.deg2rad([lon,lat,data["subearth_lon"],data["subearth_lat"],data["posangle"]])
    x = np.cos(lat)*np.sin(lon-lon0)
    y = np.cos(lat0)*np.sin(lat)-np.sin(lat0)*np.cos(lat)*np.cos(lon-lon0)
    z = np.sin(lat0)*np.sin(lat)+np.cos(lat0)*np.cos(lat)*np.cos(lon-lon0)
    return center + radius*np.array([np.cos(angle)*x-np.sin(angle)*y, -np.sin(angle)*x-np.cos(angle)*y]), z


def unproject(x, y, data, center, radius):
    a = np.deg2rad(data["posangle"])
    dx,dy = (x-center[0])/radius, (y-center[1])/radius
    east = np.cos(a)*dx-np.sin(a)*dy
    north = -np.sin(a)*dx-np.cos(a)*dy
    z = np.sqrt(np.maximum(0, 1-east*east-north*north))
    lat0 = np.deg2rad(data["subearth_lat"])
    lat = np.arcsin(np.clip(north*np.cos(lat0)+z*np.sin(lat0), -1, 1))
    lon = np.deg2rad(data["subearth_lon"]) + np.arctan2(east, z*np.cos(lat0)-north*np.sin(lat0))
    return np.rad2deg(lon), np.rad2deg(lat), east*east+north*north<=1


def tiles(store, site):
    lon,lat,last,apollo,*_ = site
    spans = [max(40.,last)]
    while spans[-1]/5 > last*1.2:
        spans.append(spans[-1]/5)
    if spans[-1] > last*1.2:
        spans.append(last)
    global_params = dict(SERVICE="WMS",VERSION="1.1.1",REQUEST="GetMap",LAYERS="luna_wac_global",STYLES="",
                         SRS="IAU2000:30100",BBOX="-180,-90,180,90",WIDTH=2048,HEIGHT=1024,
                         FORMAT="image/png",BGCOLOR="0x000000")
    globe = cache_image(store,json.dumps(global_params,sort_keys=True),WMS,global_params,(1024,2048))
    result = [(globe,(-180.,-90.,180.,90.))]
    for span in spans:
        bounds = (lon-span/2, lat-span/2, lon+span/2, lat+span/2)
        layers = "luna_wac_global"
        if apollo and span<4:
            layers = f"luna_apollo_{apollo}_high_resolution_nac_mosaic"
        params = dict(SERVICE="WMS",VERSION="1.1.1",REQUEST="GetMap",LAYERS=layers,STYLES="",
                      SRS="IAU2000:30100",BBOX=",".join(f"{v:.8f}" for v in bounds),
                      WIDTH=1024,HEIGHT=1024,FORMAT="image/png",BGCOLOR="0x000000")
        image = cache_image(store, json.dumps(params,sort_keys=True), WMS, params, (1024,1024))
        result.append((image,bounds))
    return result


def coverage(image):
    """Feather only the map coverage; retain real black crater shadows inside it."""
    black = np.uint8((image.max(axis=2)<=3)|(image.min(axis=2)>=252))
    _, labels = cv2.connectedComponents(black)
    outside = np.unique(np.r_[labels[0],labels[-1],labels[:,0],labels[:,-1]])
    outside = outside[outside!=0]
    valid = np.uint8(~np.isin(labels,outside))
    # Pad to include the finite tile boundary in the feather distance.
    distance = cv2.distanceTransform(np.pad(valid,1),cv2.DIST_L2,3)[1:-1,1:-1]
    return np.clip(distance/35,0,1).astype(np.float32)


def frames(photo, registration, data, center, radius, layers, site, width, height, count=384):
    target,z = project(site[0],site[1],data,center,radius)
    if z<=.1:
        raise ValueError("solarDetailAlignment")
    own_target = cv2.perspectiveTransform(target[None,None].astype(float),np.linalg.inv(registration))[0,0]
    if not (0<=own_target[0]<photo.shape[1] and 0<=own_target[1]<photo.shape[0]):
        raise ValueError("solarDetailAlignment")
    # End with the entire feature, allowing for screen aspect, rotation and foreshortening.
    last = layers[-1][1]
    edge = np.array([project(lon,lat,data,center,radius)[0] for lon,lat in
                     [(last[0],last[1]),(last[2],last[1]),(last[2],last[3]),(last[0],last[3])]])
    own_edge = cv2.perspectiveTransform(edge[None],np.linalg.inv(registration))[0]
    extent = np.ptp(own_edge,axis=0)
    start = min(width/photo.shape[1],height/photo.shape[0])
    end = .83*min(width/extent[0],height/extent[1])
    masks = [coverage(image) for image,_ in layers]
    if site[3]:
        # NAC mosaics are narrow observation footprints. Finish inside their
        # measured coverage instead of displaying strip edges or empty margins.
        corners=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
        for _ in range(30):
            check_cam=np.array([[end,0,width/2-end*own_target[0]],
                                [0,end,height/2-end*own_target[1]],[0,0,1.]])
            rays=cv2.perspectiveTransform(corners[None],registration@np.linalg.inv(check_cam))[0]
            lon,lat,good=unproject(rays[:,0],rays[:,1],data,center,radius)
            mx=((lon-last[0])/(last[2]-last[0])*1024-.5).astype(np.float32)[None]
            my=((last[3]-lat)/(last[3]-last[1])*1024-.5).astype(np.float32)[None]
            if good.all() and cv2.remap(masks[-1],mx,my,cv2.INTER_LINEAR).min()>.98:
                break
            end*=1.15
        else:
            raise ValueError("solarDetailAlignment")
    camera = FocusZoom(np.array(photo.shape[1::-1])/2,own_target,start,max(start,end),width,height)
    opacities=np.zeros(len(layers))
    yy,xx = np.indices((height,width),dtype=np.float32)
    for i in range(count):
        phase = i/(count-1)
        scale,cam = camera.at(smooth((phase-.05)/.87))
        scene = cv2.warpPerspective(photo,cam,(width,height))
        if phase<=.08:
            yield scene;continue
        inverse = registration @ np.linalg.inv(cam)
        rx = inverse[0,0]*xx+inverse[0,1]*yy+inverse[0,2]
        ry = inverse[1,0]*xx+inverse[1,1]*yy+inverse[1,2]
        lon,lat,visible = unproject(rx,ry,data,center,radius)
        # Fade each resolution level as its pixel footprint approaches display size.
        for index,((image,bounds),mask) in enumerate(zip(layers,masks)):
            span = bounds[2]-bounds[0]
            native = scale/np.sqrt(abs(np.linalg.det(registration[:2,:2])))*radius*np.deg2rad(span)/image.shape[1]
            fade = smooth((native-.035)/.16)*smooth((phase-.08)/.18)
            if fade<=0:
                continue
            mx = ((lon-bounds[0])/span*image.shape[1]-.5).astype(np.float32)
            my = ((bounds[3]-lat)/(bounds[3]-bounds[1])*image.shape[0]-.5).astype(np.float32)
            patch = cv2.remap(image,mx,my,cv2.INTER_LINEAR)
            sampled = cv2.remap(mask,mx,my,cv2.INTER_LINEAR)
            if site[3] and span<4:
                # Only dissolve to a NAC observation when the view lies inside
                # it. Otherwise a small bright strip would appear on the globe.
                if sampled.min()>.98:
                    opacities[index]=min(1,opacities[index]+1/30)
                fade*=smooth(opacities[index])
            alpha = (fade*visible*sampled).astype(np.float32)
            scene = cv2.blendLinear(scene,patch,1-alpha,alpha)
        yield scene


def sequence(store, record, ident, photo, width, height):
    ref,data,center,radius = reference(store,record)
    key = VERSION+":"+record["sha256"]["final"]+":"+str(data["time"])
    measured = store.get("settings",key)
    if measured is None:
        matrix,report = register(photo,ref)
        measured = dict(matrix=matrix.tolist(),report=report)
        store.put("settings",key,measured)
    site = SITES[ident]
    return frames(photo,np.array(measured["matrix"]),data,center,radius,tiles(store,site),site,width,height)
