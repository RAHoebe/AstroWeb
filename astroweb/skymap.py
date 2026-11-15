"""Discover the uploaded object in NASA's Hubble Skymap and cache its photograph."""
from functools import lru_cache

import hashlib
import io
import logging
import math
import re
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

import cv2
import numpy as np
import requests
from astropy.coordinates import SkyCoord
from PIL import Image

from .catalogue import canonical
from .galaxy import key, target_entry

BASE = "https://science.nasa.gov/specials/apps/hubble-skymap/"
ENTRY_ID = re.compile(r"[CMBE][0-9]{3,5}")
DESIGNATION = re.compile(r"\b(?:NGC|IC|MESSIER|CALDWELL|M|C|ARP|UGC|PGC|SH2)[ -]?\d+[A-Z]?\b", re.I)
DAY = 86400


def target_key(record):
    return canonical(record["metadata"]["target"])


def catalogue(store):
    saved = store.get("settings", "hubble_skymap", {})
    if saved and time.time() - saved["checked"] < 7 * DAY:
        return saved["rows"]
    try:
        reply = requests.get(BASE + "data/data.json", timeout=(4, 10))
        reply.raise_for_status()
        rows = reply.json()
        if not isinstance(rows, list):
            raise ValueError("invalid_skymap_index")
        rows = [r for r in rows if isinstance(r, dict) and isinstance(r.get("name"), str)
                and ENTRY_ID.fullmatch(str(r.get("cm_id", "")))]
        if not rows:
            raise ValueError("invalid_skymap_index")
        store.put("settings", "hubble_skymap", {"checked": time.time(), "rows": rows})
        return rows
    except (requests.RequestException, ValueError):
        if saved:
            return saved["rows"]
        raise


def candidates(record, rows):
    meta = record["metadata"]
    target = target_key(record)
    aliases = {target, meta["target"], *meta.get("aliases", [])}
    known = target_entry(key(target))
    if known:
        aliases.update([known["id"], known["nl"], known["en"], *known.get("aliases", [])])
    names = {key(canonical(a)) for a in aliases if a}
    ranked = []
    for row in rows:
        ident, title = row["cm_id"], row["name"]
        # B and E are internal Skymap numbers, not astronomical designations.
        catalog = key(canonical(ident)) if ident[0] in "MC" else ""
        if catalog and catalog == key(target):
            rank = 0
        elif catalog in names:
            rank = 1
        elif key(canonical(title)) in names or any(key(canonical(m)) in names for m in DESIGNATION.findall(title)):
            rank = 2
        else:
            continue
        ranked.append((rank, ident, row))
    return [row for _, _, row in sorted(ranked, key=lambda v: v[:2])]


def image_file(store, ident, digest):
    return store.path(f"survey-cache/nasa-skymap/{ident.lower()}-{digest}.jpg")


def fetch_image(store, ident):
    # NASA also supplies a lightbox image for entries without a full-size JPEG.
    for folder in ("full_size_image", "lightbox_images"):
        with requests.get(f"{BASE}{folder}/{ident.lower()}.jpg", stream=True, timeout=(4, 12)) as reply:
            if reply.status_code in (404, 410):
                continue
            reply.raise_for_status()
            payload = bytearray()
            for chunk in reply.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > 48 * 1024**2:
                    break
            if len(payload) > 48 * 1024**2:
                continue
        try:
            with Image.open(io.BytesIO(payload), formats=["JPEG"]) as im:
                if im.width * im.height > 48_000_000 or min(im.size) < 128:
                    continue
                im.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
                out = io.BytesIO()
                im.convert("RGB").save(out, format="JPEG", quality=94)
        except (OSError, Image.DecompressionBombError):
            continue
        data = out.getvalue()
        digest = hashlib.sha256(data).hexdigest()[:20]
        path = image_file(store, ident, digest)
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
                temp = Path(tmp.name)
                tmp.write(data)
            try:
                temp.replace(path)
            finally:
                temp.unlink(missing_ok=True)
        return digest
    return None


def lookup(store, record):
    for row in candidates(record, catalogue(store)):
        ident = row["cm_id"]
        digest = fetch_image(store, ident)
        if not digest:
            continue
        link = row.get("url") or ""
        parsed = urlsplit(link)
        if parsed.scheme != "https" or parsed.hostname not in {"science.nasa.gov", "www.nasa.gov", "nasa.gov"}:
            link = BASE + "#" + ident
        option = {"id": "skymap-" + ident.lower(), "relation": "target", "title": row["name"],
                  "credit": "NASA Hubble Skymap", "source": link, "digest": digest}
        try:
            # The interactive map stores Galactic longitude increasing leftwards.
            lon, lat = -float(row["longitude"]), float(row["latitude"])
            if math.isfinite(lon) and -90 <= lat <= 90:
                sky = SkyCoord(l=lon, b=lat, unit="deg", frame="galactic").icrs
                option["center"] = [sky.ra.deg, sky.dec.deg]
        except (KeyError, TypeError, ValueError):
            pass
        return option
    return None


def discover(store, identifier):
    record = store.get("objects", identifier)
    if not record or record.get("body") or not record["metadata"].get("target"):
        return
    target = target_key(record)
    prior = record.get("skymap") or {}
    if prior.get("target") == target and prior.get("option") and cached_option(store, record):
        return
    if prior.get("target") == target and not prior.get("option") and time.time() < prior.get("retry", 0):
        return
    try:
        option = lookup(store, record)
        result = {"target": target, "option": option, "retry": time.time() + 7 * DAY}
    except (requests.RequestException, ValueError, OSError):
        logging.warning("NASA Hubble Skymap lookup unavailable for %s", identifier, exc_info=True)
        result = {"target": target, "option": None, "retry": time.time() + 3600}
    with store.lock:
        latest = store.get("objects", identifier)
        if latest and target_key(latest) == target:
            store.update("objects", identifier, skymap=result)


def cached_option(store, record):
    state = record.get("skymap") or {}
    option = state.get("option")
    if option and state["target"] == target_key(record):
        ident = option["id"].removeprefix("skymap-")
        if image_file(store, ident, option["digest"]).is_file():
            return option
    return None


def focus_point(store, record, option):
    from .discovery import project
    if "center" in option:
        ra, dec = option["center"]
        _, uv = project(store, record, SkyCoord([ra], [dec], unit="deg"))
        if uv is not None:
            if not np.isfinite(uv).all() or np.any((uv < 0) | (uv > 1)):
                return None
            return uv[0].tolist()
    # Without registration, show the whole capture before revealing NASA's image.
    return []


def render_frames(photo, destination, focus, width, height):
    """Approach the map position and dissolve into the complete NASA composition.

    Skymap coordinates locate the object, not the corners of the released JPEG.
    """
    h, w = photo.shape[:2]
    scale = min(width/w, height/h)
    middle = np.array([(w-1)/2, (h-1)/2])
    target = np.asarray(focus) * [w-1, h-1] if focus else middle
    dh, dw = destination.shape[:2]
    fit = min(width/dw, height/dh)
    dst = cv2.resize(destination, (max(1,round(dw*fit)), max(1,round(dh*fit))), interpolation=cv2.INTER_AREA)
    back = np.zeros((height, width, 3), np.uint8)
    y, x = (height-dst.shape[0])//2, (width-dst.shape[1])//2
    back[y:y+dst.shape[0], x:x+dst.shape[1]] = dst
    for i in range(288):
        t = np.clip((i/287 - .05)/.78, 0, 1)
        ease = t*t*(3-2*t)
        zoom = scale * 2.2**ease if focus else scale
        cx, cy = middle + ease*(target-middle)
        camera = np.array([[zoom,0,(width-1)/2-zoom*cx],[0,zoom,(height-1)/2-zoom*cy]])
        alpha = np.clip((i/287-.44)/.39, 0, 1)
        if alpha >= 1:
            yield back.copy()
            continue
        frame = cv2.warpAffine(photo, camera, (width,height))
        alpha = alpha*alpha*(3-2*alpha)
        yield cv2.addWeighted(frame, 1-alpha, back, alpha, 0)

# ICRS at the four corners (top left clockwise) of these specific NASA JPEGs.
# Matched to calibrated ESA/Hubble AVM reference rasters, not to the Skymap pin.
# M031: heic1502a, 765 inliers; C033: heic0712c, 1573 inliers.
CALIBRATED_CORNERS = {
    ("skymap-m031", "13d122946078e3c56936"): (
        (11.120894241,40.989126903),(12.087797649,42.240422007),
        (11.483697012,42.499583311),(10.524611888,41.243294242)),
    ("skymap-c033", "8b5033e8b28e21c3f0e9"): (
        (314.102317885,30.367090182),(314.057985435,30.382795348),
        (314.048824857,30.363535340),(314.093150048,30.347833266)),
}

def raster_corners(w,h):
    return np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])

def tv_registration(store,record,option):
    from .discovery import project
    path=image_file(store, option["id"][7:], option["digest"])
    corners=CALIBRATED_CORNERS.get((option["id"],option["digest"]))
    if corners:
        _,uv=project(store, record, SkyCoord(*np.asarray(corners).T,unit="deg"))
        if uv is not None and np.isfinite(uv).all():
            with Image.open(path) as im:
                source=raster_corners(*im.size)
            return cv2.getPerspectiveTransform(source,np.float32(uv*[record["width"],record["height"]]-.5))
    return match_images(str(store.path(record["assets"]["final"])),str(path),record["sha256"]["final"])

@lru_cache(maxsize=32)
def match_images(upload_path,destination_path,upload_digest):
    """Use only well-distributed, consistent matches, including mirrored captures."""
    def reduced(path):
        image=cv2.imread(path,cv2.IMREAD_GRAYSCALE)
        if image is None:return None,None
        h,w=image.shape;scale=min(1,1600/max(w,h))
        small=cv2.resize(image,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_AREA)
        sx,sy=small.shape[1]/w,small.shape[0]/h
        return small,np.array([[sx,0,(sx-1)/2],[0,sy,(sy-1)/2],[0,0,1.]])
    upload,uf=reduced(upload_path);dest,df=reduced(destination_path)
    if upload is None or dest is None:return None
    sift=cv2.SIFT_create(nfeatures=4000,contrastThreshold=.015)
    uk,ud=sift.detectAndCompute(upload,None)
    if ud is None or len(ud)<12:return None
    for flip in (False,True):
        dk,dd=sift.detectAndCompute(cv2.flip(dest,1) if flip else dest,None)
        if dd is None:continue
        pairs=cv2.BFMatcher().knnMatch(dd,ud,k=2)
        good={a.trainIdx:a for a,b in pairs if a.distance<.7*b.distance}
        if len(good)<12:continue
        src=np.float32([dk[m.queryIdx].pt for m in good.values()])
        dst=np.float32([uk[m.trainIdx].pt for m in good.values()])
        affine,mask=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=2.)
        if affine is None:continue
        use=mask.ravel().astype(bool)
        if use.sum()<max(12,.5*len(src)) or cv2.contourArea(cv2.convexHull(src[use]))<.08*dest.size:continue
        mirror=np.array([[-1,0,dest.shape[1]-1],[0,1,0],[0,0,1.]]) if flip else np.eye(3)
        return np.linalg.inv(uf)@np.vstack((affine,[0,0,1]))@mirror@df
    return None
