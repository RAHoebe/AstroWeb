"""Optional Euclid VIS, JWST and Pan-STARRS1 imaging destinations, verified against the capture.

Discovery runs in the existing background worker. Catalogue coverage alone is
never enough: every offered destination has a cached, readable FITS image whose
actual WCS boundary is inside the unchanged original photograph.
"""
import hashlib
import http.client
import gzip
import json
import logging
import re
import time
import uuid

import cv2
import numpy as np
import requests
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS

from . import archive_search, external_http
from .discovery import discover as capture_objects, project
from .hst_archive import inside_capture
from .journey import geometry

EUCLID_TAP = "https://eas.esac.esa.int/tap-server/tap"
EUCLID_CUTOUT = "https://eas.esac.esa.int/sas-cutout/cutout"
MAST_DOWNLOAD = "https://mast.stsci.edu/api/v0.1/Download/file"
JWST_DATA = "https://jwst.esac.esa.int/server/data"
MAX_BYTES = 96 * 1024**2
MAX_PIXELS = 24_000_000
MAX_FIELDS = 3
VERSION = 1
PROVIDERS = ("euclid","jwst","panstarrs","noirlab","colour-search")


class TimedConnections:
    """Astroquery TAP connection factory with a finite socket timeout."""
    def __init__(self, host):
        if host not in {"eas.esac.esa.int", "jwst.esac.esa.int"}:
            raise ValueError("invalid_archive_host")
        self.host = host

    def get_connection(self, *, ishttps=False, cookie=None, verbose=False):
        external_http._check()
        if not ishttps:
            raise ValueError("archive_requires_https")
        return http.client.HTTPSConnection(self.host, 443, timeout=25)

    def get_connection_secure(self, verbose=False):
        return self.get_connection(ishttps=True)


def euclid_rows(corners):
    external_http._check()
    # Do not import the Euclid singleton: it checks remote notifications on import.
    from astroquery.utils.tap import TapPlus
    from astroquery.utils.tap.conn.tapconn import TapConn
    connection = TapConn(True, "eas.esac.esa.int", server_context="tap-server", tap_context="tap",
                         connhandler=TimedConnections("eas.esac.esa.int"))
    client = TapPlus(url=EUCLID_TAP, connhandler=connection)
    ra, dec, radius = archive_search.search_cone(corners)
    rows, errors = [], []
    for release in ("dr1", "q1"):
        query = ("SELECT TOP 160 file_name,file_path,stc_s,tile_index,creation_date "
                 f"FROM {release}.mosaic_product WHERE instrument_name='VIS' "
                 f"AND INTERSECTS(CIRCLE({ra:.8f},{dec:.8f},{radius:.8f}),fov)=1 "
                 "ORDER BY creation_date DESC")
        try:
            table = client.launch_job(query, verbose=False).get_results()
            rows.extend(dict(release=release, **{key: str(row[key]) for key in table.colnames}) for row in table)
        except (OSError, ValueError, requests.RequestException) as exc:
            errors.append(exc)
    if errors and not rows:
        raise ValueError("hubble_unavailable") from errors[0]
    return rows


def jwst_rows(corners):
    external_http._check()
    from astroquery.utils.tap import TapPlus
    from astroquery.utils.tap.conn.tapconn import TapConn
    connection = TapConn(True, "jwst.esac.esa.int", server_context="server", tap_context="tap",
                         connhandler=TimedConnections("jwst.esac.esa.int"))
    client = TapPlus(url="https://jwst.esac.esa.int/server/tap", connhandler=connection)
    ra, dec, radius = archive_search.search_cone(corners)
    query = ("SELECT TOP 160 o.obs_id,o.target_name,o.instrument_name,o.s_ra,o.s_dec,o.s_region,"
             "p.energy_bandpassname AS filters,a.filename,a.artifactid,a.contentlength "
             "FROM ivoa.ObsCore o JOIN jwst.artifact a ON o.planeid=a.planeid "
             "JOIN jwst.plane p ON o.planeid=p.planeid "
             "WHERE o.dataproduct_type='image' AND o.calib_level=3 AND p.\"public\"='true' "
             f"AND a.filename LIKE '%_i2d.fits' AND a.contentlength<{MAX_BYTES} "
             "AND UPPER(o.target_name) NOT LIKE '%BKG%' AND UPPER(o.target_name) NOT LIKE '%BACKGROUND%' "
             f"AND INTERSECTS(CIRCLE('ICRS',{ra:.8f},{dec:.8f},{radius:.8f}),o.s_region)=1 "
             "ORDER BY o.t_exptime DESC")
    try:
        table = client.launch_job(query, verbose=False).get_results()
        return [{key: str(row[key]) for key in table.colnames} for row in table]
    except (OSError, ValueError, requests.RequestException):
        return mast_jwst_rows(corners)


def mast_jwst_rows(corners):
    # The bounded MAST request complements Astroquery's TAP client. Avoid the
    # MAST client's schema-discovery/polling sequence on every fresh NAS install.
    ra, dec, radius = archive_search.search_cone(corners)
    filters = [{"paramName": name, "values": values} for name, values in (
        ("obs_collection", ["JWST"]), ("dataproduct_type", ["image"]),
        ("calib_level", ["3"]), ("dataRights", ["PUBLIC"]))]
    query = {"service": "Mast.Caom.Filtered.Position", "format": "json", "pagesize": 200, "page": 1,
             "params": {"columns": "obs_id,target_name,s_ra,s_dec,s_region,instrument_name,filters,dataURL,t_exptime",
                        "filters": filters, "position": f"{ra:.8f},{dec:.8f},{radius:.8f}"}}
    response = external_http.get(archive_search.MAST, params={"request": json.dumps(query)}, timeout=(5,25))
    response.raise_for_status()
    result = response.json()
    if result.get("status") != "COMPLETE" or not isinstance(result.get("data"), list):
        raise ValueError("hubble_unavailable")
    return result["data"]


def image_file(store, entry):
    # IDs are locally generated hashes, never remote filenames or user paths.
    if not re.fullmatch(r"(?:euclid|jwst|panstarrs)-[0-9a-f]{24}", entry["id"]):
        raise ValueError("invalid_archive_product")
    return store.path(f"survey-cache/mission-archive/{entry['id']}.fits")


def download(store, entry):
    if entry.get("provider") not in PROVIDERS or not entry["id"].startswith(entry["provider"]+"-"):
        raise ValueError("invalid_archive_product")
    path = image_file(store, entry)
    if path.is_file():
        return path
    if entry["provider"] == "panstarrs":
        from . import panstarrs
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix("."+uuid.uuid4().hex+".part")
        try:
            panstarrs.download(entry,tmp)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
        return path
    if entry["provider"] == "euclid":
        remote = entry["file_path"].rstrip("/") + "/" + entry["file_name"]
        if (not re.fullmatch(r"/(?:data/)?euclid/repository_(?:dr1|q1|idr)/[A-Za-z0-9_./-]+", remote)
                or ".." in remote.split("/") or not remote.endswith(".fits")):
            raise ValueError("invalid_archive_product")
        url, params = EUCLID_CUTOUT, {"FILEPATH": remote, "POS": f"CIRCLE,{entry['ra']},{entry['dec']},{entry['radius']}",
                                     "COLLECTION":"VIS", "OBSID":entry["tile_index"], "TAPCLIENT": "ASTROQUERY"}
    else:
        artifact = entry.get("artifact_id")
        if artifact:
            if not re.fullmatch(r"[0-9a-f-]{36}", artifact):
                raise ValueError("invalid_archive_product")
            url, params = JWST_DATA, {"ARTIFACTID":artifact, "RETRIEVAL_TYPE":"PRODUCT", "TAPCLIENT":"ASTROQUERY"}
        else:
            uri = entry["data_uri"]
            if not re.fullmatch(r"mast:JWST/product/jw[A-Za-z0-9_-]+_i2d\.fits", uri):
                raise ValueError("invalid_archive_product")
            url, params = MAST_DOWNLOAD, {"uri": uri}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix("." + uuid.uuid4().hex + ".part")
    expanded = tmp.with_suffix(".unpacked")
    try:
        with external_http.get(url, params=params, stream=True, timeout=(5,35)) as reply:
            reply.raise_for_status()
            if int(reply.headers.get("Content-Length", 0)) > MAX_BYTES:
                raise ValueError("archive_product_too_large")
            count = 0
            deadline = time.monotonic() + 45
            with tmp.open("wb") as out:
                for chunk in reply.iter_content(256*1024):
                    if time.monotonic() > deadline:
                        raise requests.Timeout("Archive download time budget exceeded")
                    count += len(chunk)
                    if count > MAX_BYTES:
                        raise ValueError("archive_product_too_large")
                    out.write(chunk)
        with tmp.open("rb") as stream:
            compressed = stream.read(2) == b"\x1f\x8b"
        if compressed:
            count = 0
            with gzip.open(tmp,"rb") as stream, expanded.open("wb") as out:
                while chunk := stream.read(256*1024):
                    count += len(chunk)
                    if count > MAX_BYTES:
                        raise ValueError("archive_product_too_large")
                    out.write(chunk)
            expanded.replace(tmp)
        with tmp.open("rb") as stream:
            if not stream.read(80).startswith(b"SIMPLE"):
                raise ValueError("hubble_no_field")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
        expanded.unlink(missing_ok=True)
    return path


def registered_cutout(store, record, entry):
    if entry["provider"] in ("noirlab", "colour-plate"):
        from . import noirlab
        return noirlab.registered_cutout(store,record,entry)
    path = download(store, entry)
    with fits.open(path, memmap=True) as hdus:
        # JWST calibrated images have SCI; Euclid cutouts use the primary HDU.
        hdu = hdus["SCI"] if "SCI" in hdus else hdus[0]
        shape = hdu.shape
        if len(shape) != 2 or min(shape) < 32 or np.prod(shape) > MAX_PIXELS:
            raise ValueError("hubble_no_field")
        wcs = WCS(hdu.header, hdus).celestial
        if not wcs.has_celestial:
            raise ValueError("hubble_no_field")
        height, width = shape
        # Sample every edge to include WCS distortion, not only corner positions.
        t = np.linspace(0, 1, 25)
        edges = np.vstack((np.c_[t*width-.5, np.full(25, -.5)],
                           np.c_[np.full(25, width-.5), t*height-.5],
                           np.c_[t*width-.5, np.full(25, height-.5)],
                           np.c_[np.full(25, -.5), t*height-.5]))
        _, boundary = project(store, record, wcs.pixel_to_world(edges[:,0], height-1-edges[:,1]).icrs)
        if not inside_capture(boundary):
            raise ValueError("hubble_no_field")
        src = np.float32([[0,0], [width-1,0], [width-1,height-1], [0,height-1]])
        _, uv = project(store, record, wcs.pixel_to_world(src[:,0], height-1-src[:,1]).icrs)
        if not inside_capture(uv):
            raise ValueError("hubble_no_field")
        matrix = cv2.getPerspectiveTransform(src, np.float32(uv*[record["width"],record["height"]]-.5))
        # A TAN-to-TAN mapping is a homography. Reject products with distortion
        # that would visibly misregister the final zoom; never silently ignore it.
        gx, gy = np.meshgrid(np.linspace(0,width-1,5),np.linspace(0,height-1,5))
        grid = np.c_[gx.ravel(),gy.ravel()]
        _, sample = project(store,record,wcs.pixel_to_world(grid[:,0],height-1-grid[:,1]).icrs)
        if not inside_capture(sample):
            raise ValueError("hubble_no_field")
        try:
            recovered = cv2.perspectiveTransform((sample*[record["width"],record["height"]]-.5)[None],np.linalg.inv(matrix))[0]
        except np.linalg.LinAlgError:
            raise ValueError("hubble_no_field") from None
        if not np.isfinite(recovered).all() or np.max(np.linalg.norm(recovered-grid,axis=1)) > .5:
            raise ValueError("hubble_no_field")
        if entry["provider"]=="panstarrs":
            from .panstarrs import colour
            image,valid = colour(hdus)
        else:
            data = np.flipud(hdu.data).astype(np.float32)
            valid = np.isfinite(data) & (data != 0)
            if valid.mean() < .5:
                raise ValueError("hubble_no_field")
            lo, hi = np.percentile(data[valid], [15, 99.7])
            if not np.isfinite([lo,hi]).all() or hi <= lo:
                raise ValueError("hubble_no_field")
            signal = np.nan_to_num(data, nan=lo, posinf=hi, neginf=lo)
            signal = cv2.GaussianBlur(signal,(0,0),.65)
            stretch = np.arcsinh(6*np.clip((signal-lo)/(hi-lo),0,1))/np.arcsinh(6)
            img = np.uint8(6+249*stretch)
            img[~valid] = 0
            image = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    # End on the requested named feature when possible; never on an unexposed gap.
    x, y = wcs.world_to_pixel(SkyCoord(entry["ra"], entry["dec"], unit="deg"))
    focus = (float(x), float(height-1-y))
    if not np.isfinite(focus).all() or not (0 <= focus[0] < width and 0 <= focus[1] < height):
        raise ValueError("hubble_no_field")
    if not valid[int(round(min(height-1,focus[1]))), int(round(min(width-1,focus[0])))]:
        raise ValueError("hubble_no_field")
    return image, matrix, focus


def seeds(store, record):
    objects = capture_objects(store, record)["objects"]
    objects = [o for o in objects if o["type"]["en"] not in {"Star", "Double star"}]
    result = [(float(o["ra"]), float(o["dec"]), o["id"]) for o in objects]
    corners = geometry(store, record)["corners"]
    ra, dec, radius = archive_search.search_cone(corners)
    result.append((ra, dec, record["metadata"]["target"]))
    return result[:12], radius


def contains(polygon, ra, dec, radius=0):
    if polygon is None:
        return False
    centre = SkyCoord(ra, dec, unit="deg")
    # Gnomonic plane avoids RA wrapping and works at the celestial poles.
    vectors = polygon.transform_to(centre.skyoffset_frame()).cartesian.xyz.value
    if np.any(vectors[0] <= 0):
        return False
    margin = cv2.pointPolygonTest(np.float32((vectors[1:]/vectors[0]).T), (0.,0.), True)
    return margin >= np.tan(np.deg2rad(radius))*np.sqrt(2)


def candidates(store, record, provider):
    if provider=="noirlab":
        from . import noirlab
        return noirlab.candidates(store,record)
    if provider=="panstarrs":
        from . import panstarrs
        return panstarrs.candidates(store,record)
    corners = geometry(store, record)["corners"]
    if provider == "euclid":
        rows = euclid_rows(corners)
        targets, span = seeds(store, record)
        options = []
        for ra, dec, target in targets:
            # Native VIS pixels are ~0.1 arcsec. A modest bounded patch reveals
            # structure; tiny captures use a correspondingly smaller patch.
            radius = min(.018, span*.12)
            releases = set()
            for row in rows:
                if row["release"] in releases or not contains(archive_search.polygon(row["stc_s"]), ra, dec, radius):
                    continue
                token = [row["release"],row["file_name"],ra,dec,radius]
                ident = "euclid-" + hashlib.sha256(json.dumps(token).encode()).hexdigest()[:24]
                options.append(dict(id=ident, provider=provider, target=target, relation="region",
                                    title=f"{target} · Euclid VIS · {row['release'].upper()}",
                                    telescope="Euclid / VIS", filter="VIS", ra=ra, dec=dec,
                                    radius=radius, file_path=row["file_path"], file_name=row["file_name"],
                                    release=row["release"], tile_index=row["tile_index"], full_footprint=True,
                                    source="https://euclid.esac.esa.int/",
                                    credit="ESA / Euclid / Euclid Consortium · VIS"))
                releases.add(row["release"])
        return options
    result = []
    for row in jwst_rows(corners):
        filename = row.get("filename") or ""
        uri = row.get("dataURL") or ("mast:JWST/product/"+filename if filename else "")
        if not re.fullmatch(r"mast:JWST/product/jw[A-Za-z0-9_-]+_i2d\.fits", uri):
            continue
        footprint = archive_search.polygon(row.get("s_region"))
        if footprint is None:
            continue
        _, uv = project(store, record, footprint)
        if not inside_capture(uv):
            continue
        try:
            ra, dec = float(row["s_ra"]), float(row["s_dec"])
            if not np.isfinite([ra,dec]).all():
                continue
        except (KeyError, ValueError, TypeError):
            continue
        artifact = row.get("artifactid")
        ident = "jwst-" + hashlib.sha256((artifact or uri).encode()).hexdigest()[:24]
        target = row.get("target_name") or record["metadata"]["target"]
        instrument = row.get("instrument_name") or "JWST"
        band = row.get("filters") or ""
        result.append(dict(id=ident, provider=provider, target=target, relation="field", title=f"{target} · JWST · {band}",
                           telescope=f"JWST / {instrument}", filter=band, ra=ra, dec=dec, data_uri=uri,
                           artifact_id=artifact,
                           footprint=cv2.convexHull(np.float32(uv)).reshape(-1,2).tolist(),
                           full_footprint=True, source="https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html",
                           credit=f"NASA / ESA / CSA · JWST · {instrument} · {band}"))
    return result


def lookup(store, record, provider):
    if provider == "colour-search":
        from . import photo_archive
        return photo_archive.lookup(store, record)
    accepted, footprints, catalogue_footprints, errors = [], [], [], []
    deadline = time.monotonic() + 90
    for entry in candidates(store, record, provider)[:8]:
        if time.monotonic() > deadline:
            errors.append(requests.Timeout("Archive search time budget exceeded"))
            break
        catalogue = np.float32(entry["footprint"]) if entry.get("footprint") else None
        if catalogue is not None and archive_search.same_field(catalogue, catalogue_footprints):
            continue
        try:
            image, matrix, _ = registered_cutout(store, record, entry)
            if provider == "panstarrs":
                from .panstarrs import verify_texture
                entry["residual_px"] = verify_texture(store,record,image,matrix)
        except requests.RequestException as exc:
            errors.append(exc)
            continue
        except (ValueError, OSError):
            continue
        h, w = image.shape[:2]
        edges = np.float32([[[-.5,-.5],[w-.5,-.5],[w-.5,h-.5],[-.5,h-.5]]])
        hull = cv2.convexHull(cv2.perspectiveTransform(edges,matrix)[0])
        if cv2.contourArea(hull) <= 0 or archive_search.same_field(hull, footprints):
            continue
        footprints.append(hull)
        if catalogue is not None:
            catalogue_footprints.append(catalogue)
        accepted.append({k:v for k,v in entry.items() if k != "footprint"})
        if len(accepted) == MAX_FIELDS:
            break
    if errors and not accepted:
        raise ValueError("hubble_unavailable") from errors[0]
    return accepted


def cached_options(store, record):
    state = record.get("mission_search") or {}
    options = []
    if state and state.get("field") == archive_search.field_key(store, record):
        options.extend(item for provider in PROVIDERS for item in state.get(provider, {}).get("options", []))
    # These independently registered photographs use coordinates in the original
    # raster. Refreshing a telescope catalogue does not invalidate the star fit.
    digest = (record.get("sha256") or {}).get("final")
    options.extend(item for item in record.get("colour_plates", [])
                   if digest and item.get("capture_digest") == digest)
    return options


def discover(store, identifier, force=False):
    record = store.get("objects", identifier)
    if not record or record.get("body") or record.get("capture_kind"):
        return
    signature = archive_search.field_key(store, record)
    if signature is None:
        return
    for provider in PROVIDERS:
        state = record.get("mission_search") or {}
        prior = state.get(provider, {}) if state.get("field") == signature else {}
        if not force and prior.get("version") == VERSION and prior.get("retry",0) > time.time():
            continue
        try:
            options = lookup(store, record, provider)
            if provider == "colour-search":
                # Keep verified colour photographs when an archive returns fewer results.
                combined = {item["id"]:item for item in prior.get("options", [])}
                combined.update({item["id"]:item for item in options})
                options = list(combined.values())
            result = dict(options=options, retry=time.time()+7*86400, version=VERSION)
        except Exception:
            # A malformed optional response, including a TAP/FITS parser error,
            # must not prevent the other telescope from being searched.
            logging.warning("Optional %s archive search unavailable for %s", provider, identifier, exc_info=True)
            result = dict(options=prior.get("options", []), unavailable=True, retry=time.time()+3600, version=VERSION)
        with store.lock:
            latest = store.get("objects", identifier)
            if not latest or archive_search.field_key(store, latest) != signature:
                return
            state = latest.get("mission_search") or {}
            if state.get("field") != signature:
                state = {"field":signature}
            state[provider] = result
            record = store.update("objects", identifier, mission_search=state)
