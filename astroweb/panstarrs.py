"""Registered Pan-STARRS1 3Pi survey cutouts for named nebular features."""

import hashlib
import io
import json
import re

import cv2
import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS

from . import external_http
from .catalogue import canonical

SERVER = "https://ps1images.stsci.edu/cgi-bin/"
SOURCE = "https://outerspace.stsci.edu/display/PANSTARRS"
FILE = re.compile(
    r"/rings\.v3\.skycell/(\d{4})/(\d{3})/rings\.v3\.skycell\.\1\.\2\.stk\.([gri])\.unconv\.fits"
)
SIZES = (1280, 896, 640)
NEBULAE = {"H II region", "Supernova remnant", "Cluster with nebulosity"}


def nebular(point):
    kind = (point.get("type") or {}).get("en", "")
    return "nebula" in kind.lower() or kind in NEBULAE


def bands(ra, dec):
    reply = external_http.get(
        SERVER + "ps1filenames.py",
        params={"ra": ra, "dec": dec, "filters": "gri", "type": "stack"},
        timeout=(4, 12),
    )
    reply.raise_for_status()
    lines = reply.text.splitlines()
    if not lines or not {"filter", "filename", "badflag", "type"} <= set(
        lines[0].split()
    ):
        raise ValueError("invalid_archive_response")
    groups = {}
    for line in lines[1:]:
        row = dict(zip(lines[0].split(), line.split()))
        match = FILE.fullmatch(row.get("filename", ""))
        if (
            match
            and row.get("type") == "stack"
            and row.get("badflag") == "0"
            and row.get("filter") == match[3]
        ):
            groups.setdefault(match.group(1, 2), {})[match[3]] = row["filename"]
    return next((group for group in groups.values() if len(group) == 3), None)


def candidates(store, record):
    from .discovery import discover
    from .journey import geometry
    from .mission_archive import contains
    from astropy.coordinates import SkyCoord

    corners = geometry(store, record).get("corners")
    if not corners:
        return []
    footprint = SkyCoord(*np.array(corners).T, unit="deg")
    points = [
        p
        for p in discover(store, record, links=False)["objects"]
        if nebular(p) and p["dec"] >= -30
    ]
    primary = canonical(record["metadata"]["target"])
    points.sort(key=lambda p: canonical(p["id"]) != primary)
    # Off-centre panels may contain a bright filament but no catalogue centre.
    # Pick one image feature in a known nebular capture, and derive its sky position.
    if nebular(record["metadata"]):
        from .autozoom import propose_image
        from .comparison import raster_sky

        layer = record.get("assets", {}).get("starless") or record["poster"]
        poster = cv2.imdecode(
            np.fromfile(store.path(layer), np.uint8), cv2.IMREAD_REDUCED_GRAYSCALE_4
        )
        if poster is not None:
            peaks = propose_image(poster, 3)
            for peak in peaks:
                if 0.12 < peak["x"] < 0.88 and 0.12 < peak["y"] < 0.88:
                    sky = raster_sky(
                        store,
                        record,
                        geometry(store, record),
                        np.array([[peak["x"]]]),
                        np.array([[peak["y"]]]),
                    )[0, 0]
                    points.append(
                        dict(
                            id=record["metadata"]["target"] + " · detail",
                            ra=float(sky.ra.deg),
                            dec=float(sky.dec.deg),
                        )
                    )
                    break
    result = []
    failure = None
    for point in points[:5]:
        ra, dec, target = point["ra"], point["dec"], point["id"]
        size = next(
            (n for n in SIZES if contains(footprint, ra, dec, n * 0.25 / 7200)), None
        )
        if not size:
            continue
        try:
            files = bands(ra, dec)
        except requests.RequestException as exc:
            failure = exc
            continue
        if not files:
            continue
        signature = json.dumps([files, ra, dec, size], sort_keys=True)
        result.append(
            dict(
                id="panstarrs-" + hashlib.sha256(signature.encode()).hexdigest()[:24],
                provider="panstarrs",
                target=target,
                relation="region",
                ra=ra,
                dec=dec,
                size=size,
                files=files,
                full_footprint=True,
                filter="g/r/i",
                telescope="Pan-STARRS1",
                title=f"{target} · Pan-STARRS1 · g/r/i",
                source=SOURCE,
                credit="Pan-STARRS1 Surveys / STScI",
            )
        )
    if failure is not None and not result:
        raise failure
    return result


def download(entry, temporary):
    size = entry["size"]
    if size not in SIZES:
        raise ValueError("invalid_archive_product")
    layers = []
    for band in ("r", "g", "i"):
        filename = entry["files"][band]
        match = FILE.fullmatch(filename)
        if not match or match[3] != band:
            raise ValueError("invalid_archive_product")
        params = dict(
            red=filename, ra=entry["ra"], dec=entry["dec"], size=size, format="fits"
        )
        with external_http.get(
            SERVER + "fitscut.cgi", params=params, stream=True, timeout=(5, 25)
        ) as response:
            response.raise_for_status()
            payload = io.BytesIO()
            for chunk in response.iter_content(65536):
                if payload.tell() + len(chunk) > size * size * 8 + 262144:
                    raise ValueError("archive_product_too_large")
                payload.write(chunk)
        payload.seek(0)
        with fits.open(payload, memmap=False) as hdus:
            hdu = hdus[0]
            if hdu.shape != (size, size) or not WCS(hdu.header).has_celestial:
                raise ValueError("hubble_no_field")
            layers.append(
                hdu.copy()
                if band == "r"
                else fits.ImageHDU(hdu.data.copy(), hdu.header, name=band.upper())
            )
    fits.HDUList(layers).writeto(temporary)


def colour(hdus):
    shape = hdus[0].shape
    reference = WCS(hdus[0].header).celestial
    x, y = np.meshgrid(np.linspace(0, shape[1] - 1, 5), np.linspace(0, shape[0] - 1, 5))
    sky = reference.pixel_to_world(x, y)
    channels = []
    for hdu in (hdus["G"], hdus[0], hdus["I"]):  # OpenCV uses BGR order.
        if hdu.shape != shape:
            raise ValueError("hubble_no_field")
        px, py = WCS(hdu.header).celestial.world_to_pixel(sky)
        residual = np.hypot(px - x, py - y)
        if not np.isfinite(residual).all() or residual.max() > 0.1:
            raise ValueError("hubble_no_field")
        channels.append(np.flipud(hdu.data).astype(np.float32))
    valid = np.logical_and.reduce([np.isfinite(c) & (c != 0) for c in channels])
    if valid.mean() < 0.98:
        raise ValueError("hubble_no_field")
    stretched = []
    for c in channels:
        lo, hi = np.percentile(c[valid], [8, 99.7])
        if not hi > lo:
            raise ValueError("hubble_no_field")
        values = np.arcsinh(
            8 * np.clip((np.where(valid, c, lo) - lo) / (hi - lo), 0, 1)
        ) / np.arcsinh(8)
        stretched.append(np.where(valid, 6 + 249 * values, 0).astype(np.uint8))
    return cv2.merge(stretched), valid


def verify_texture(store, record, image, matrix):
    """Measure the residual displacement on the actual capture, in its native pixels."""
    corners = np.float64(
        [
            [
                [0, 0],
                [image.shape[1] - 1, 0],
                [image.shape[1] - 1, image.shape[0] - 1],
                [0, image.shape[0] - 1],
            ]
        ]
    )
    quad = cv2.perspectiveTransform(corners, matrix)[0]
    extent = min(np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[3] - quad[0]))
    side = round(extent)
    if not 40 <= side <= image.shape[0]:
        raise ValueError("hubble_no_field")
    own = cv2.imdecode(
        np.fromfile(store.path(record["assets"]["final"]), np.uint8),
        cv2.IMREAD_GRAYSCALE,
    )
    if own is None:
        raise ValueError("invalid_image")
    ratio = image.shape[1] / side
    native = np.array(
        [[ratio, 0, (ratio - 1) / 2], [0, ratio, (ratio - 1) / 2], [0, 0, 1.0]]
    )
    crop = cv2.warpPerspective(
        own,
        matrix @ native,
        (side, side),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
    )
    patch = cv2.resize(
        cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),
        (side, side),
        interpolation=cv2.INTER_AREA,
    )

    def texture(a):
        smooth = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 0.7)
        return smooth - cv2.GaussianBlur(smooth, (0, 0), 3)

    a, b = texture(crop)[3:-3, 3:-3].copy(), texture(patch)[3:-3, 3:-3].copy()
    shift, quality = cv2.phaseCorrelate(
        a.copy(), b.copy(), cv2.createHanningWindow(a.shape[::-1], cv2.CV_32F)
    )
    residual = float(np.hypot(*shift))
    if np.isfinite([residual, quality]).all() and quality >= 0.32 and residual <= 1.5:
        return round(residual, 3)
    # Bright nebulae can look very different through different filters. Check
    # the independently predicted positions of distributed point sources.
    from scipy.spatial import cKDTree
    from .gaia import correspondences

    def peaks(values):
        maxima = (values >= cv2.dilate(values, np.ones((5, 5), np.uint8))) & (
            values > np.percentile(values, 90)
        )
        y, x = np.nonzero(maxima)
        order = np.argsort(-values[y, x])[:140]
        return np.column_stack((x[order], y[order])).astype(float)

    first, second = peaks(a), peaks(b)
    if min(len(first), len(second)) >= 12:
        tree = cKDTree(first)
        ii, jj = correspondences(tree, second, 1.6)
        controls = max(
            len(correspondences(tree, second + offset, 1.6)[0])
            for offset in ((9, 0), (-9, 0), (0, 9), (0, -9))
        )
        if len(ii) >= max(10, 2 * controls + 3):
            hull = cv2.convexHull(second[ii].astype(np.float32))
            error = np.median(np.linalg.norm(second[ii] - first[jj], axis=1))
            if cv2.contourArea(hull) > 0.15 * a.size and error <= 1.25:
                return round(float(error), 3)
    raise ValueError("hubble_no_field")
