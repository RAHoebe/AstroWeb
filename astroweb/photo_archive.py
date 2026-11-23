"""Find published colour photographs of nebulae and register them to a capture."""

import hashlib
import html
import io
import re
import time
import uuid

import cv2
import numpy as np
import requests
from PIL import Image

from . import external_http, noirlab
from .catalogue import canonical
from .comparison import raster_sky
from .journey import geometry
from .panstarrs import nebular

ARCHIVES = (
    (
        "NOIRLab",
        "https://noirlab.edu/public/images/",
        "https://noirlab.edu/public/media/archives/images/",
    ),
    ("ESO", "https://www.eso.org/public/images/", "https://cdn.eso.org/images/"),
)
UNSUITABLE = re.compile(
    r"\b(montage|collage|comparison|illustration|annotated|artist.s|chart|diagram|four views|compass|inset|simulation)\b",
    re.I,
)
GAS = re.compile(
    r"nebul|supernova remnant|ionised gas|ionized gas|interstellar dust|star.forming region",
    re.I,
)


def read(url, limit, **kwargs):
    with external_http.get(url, stream=True, timeout=(4, 10), **kwargs) as response:
        response.raise_for_status()
        buffer = bytearray()
        for chunk in response.iter_content(65536):
            if len(buffer) + len(chunk) > limit:
                raise ValueError("archive_product_too_large")
            buffer.extend(chunk)
        return bytes(buffer)


def plain(markup):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", markup)).split())


def search_terms(metadata):
    values = [
        metadata["target"].replace("_", " "),
        (metadata.get("name") or {}).get("en"),
        *metadata.get("aliases", []),
    ]
    terms = []
    seen = set()
    for value in values:
        if not value or len(value) > 100:
            continue
        if " · " in value:
            value = value.split(" · ")[-1].strip()
        key = re.sub(r"[^a-z0-9]", "", value.lower())
        if key and key not in seen:
            terms.append(value)
            seen.add(key)
        if len(terms) == 3:
            break
    return terms


def results(page):
    block = re.search(r"\bvar images\s*=\s*\[(.*?)\];", page, re.S)
    if not block:
        if "No images were found." in page:
            return
        raise ValueError("invalid_archive_response")
    for slug, title in re.findall(
        r"\bid:\s*'([a-z0-9-]{2,80})',\s*title:\s*'(.*?)',\s*width:", block[1], re.S
    ):
        if not UNSUITABLE.search(plain(title)):
            yield slug, plain(title)


def description(page, terms):
    if not re.search(r">Type:</td>\s*<td>\s*Observation\s*</td>", page, re.I):
        return None
    credit = re.search(r'<div class="credit">\s*(.*?)</div>', page, re.S)
    main = page.partition("<h1>")[2].partition('class="credit"')[0]
    # Require the archive's own description to identify the intended object,
    # even when the search engine returned an observation of a neighbour.
    subject = plain(main)

    def mentions(term):
        tokens = re.findall(r"[A-Za-z]+|[0-9]+", term)
        pattern = r"[\s_–-]*".join(re.escape(t) for t in tokens)
        return bool(
            tokens and re.search(r"(?<!\w)" + pattern + r"(?!\w)", subject, re.I)
        )

    if (
        not credit
        or not GAS.search(subject)
        or not any(mentions(term) for term in terms)
    ):
        return None
    bands = page.split("Colors & filters</h3>")[-1].split("</table>")[0]
    values = (
        re.findall(r'<span class="band_[^"]+">([^<]+)</span>', bands)
        if "Colors & filters</h3>" in page
        else []
    )
    band = " / ".join(
        dict.fromkeys(
            plain(v)
            for v in values
            if v.lower() in ("optical", "infrared", "ultraviolet", "radio", "x-ray")
        )
    )
    return plain(credit[1]), band or "Colour composite"


# The gas structure in these public plates is off-centre. Hints are in
# archive-image coordinates and are independently registered on every capture.
FEATURES = {
    "noao-04494": (0.58, 0.55, 0.30),
    "noao-ic63bash": (0.516, 0.365, 0.27),
    "noao-ic1805": (0.43, 0.33, 0.72),
    "noao-ngc281": (0.43, 0.55, 0.54),
    "noao-ngc6992": (0.64, 0.50, 0.73),
    "noaoann15004a": (0.49, 0.64, 0.64),
}


def gas_crops(photo, slug=""):
    """Seek extended colour structure, suppressing isolated coloured stars."""
    h, w = photo.shape[:2]
    small = cv2.resize(photo, (160, 160), interpolation=cv2.INTER_AREA)
    diffuse = cv2.GaussianBlur(cv2.medianBlur(small, 7).astype(np.float32), (0, 0), 3)
    chroma = np.ptp(diffuse, axis=2)
    if np.percentile(chroma, 90) < 7:
        return
    score = chroma * np.minimum(1, np.max(diffuse, axis=2) / 45)
    y, x = np.unravel_index(np.argmax(score[20:-20, 20:-20]), (120, 120))
    cx, cy = (x + 20.5) / 160, (y + 20.5) / 160
    choices = [(cx, cy, 0.78), (cx, cy, 0.42)]
    if slug in FEATURES:
        choices.insert(0, FEATURES[slug])
    for cx, cy, scale in choices:
        cw, ch = round(w * scale), round(h * scale)
        left = min(max(0, round(w * cx - cw / 2)), w - cw)
        top = min(max(0, round(h * cy - ch / 2)), h - ch)
        yield photo[top : top + ch, left : left + cw], (w * cx - left, h * cy - top)


def match(store, record, photo, own, anchors, deadline, slug):
    for crop, focus in gas_crops(photo, slug):
        if time.monotonic() > deadline:
            break
        grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        try:
            matrix, report = noirlab.match_plate(grey, own)
        except ValueError:
            for anchor in anchors:
                if time.monotonic() > deadline:
                    return None
                try:
                    matrix, report = noirlab.star_match(grey, own, anchor)
                except ValueError:
                    continue
                break
            else:
                continue
        ok, jpeg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 96])
        if not ok:
            continue
        digest = hashlib.sha256(jpeg).hexdigest()
        uv = (cv2.perspectiveTransform(np.float64([[focus]]), matrix)[0, 0] + 0.5) / [
            record["width"],
            record["height"],
        ]
        sky = raster_sky(
            store,
            record,
            geometry(store, record),
            np.array([[uv[0]]]),
            np.array([[uv[1]]]),
        )[0, 0]
        if not np.isfinite([sky.ra.deg, sky.dec.deg]).all():
            continue
        path = store.path(f"archive-photos/{digest}.jpg")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
            try:
                tmp.write_bytes(jpeg.tobytes())
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)
        return dict(
            digest=digest,
            provider="colour-plate",
            capture_digest=record["sha256"]["final"],
            matrix=matrix.tolist(),
            focus=focus,
            end_height=0.72,
            full_footprint=True,
            relation="region",
            ra=float(sky.ra.deg),
            dec=float(sky.dec.deg),
            **report,
        )


def lookup(store, record):
    meta = record["metadata"]
    from .discovery import discover

    points = [p for p in discover(store, record, links=False)["objects"] if nebular(p)]
    if not nebular(meta) and not any(
        canonical(p["id"]) == canonical(meta["target"]) for p in points
    ):
        return []
    points.sort(key=lambda p: canonical(p["id"]) != canonical(meta["target"]))
    anchors = [
        (p["x"] * record["width"], p["y"] * record["height"]) for p in points[:2]
    ]
    if not anchors:
        anchors = [(record["width"] / 2, record["height"] / 2)]
    terms = search_terms(meta)
    own = cv2.imdecode(
        np.fromfile(store.path(record["assets"]["final"]), np.uint8),
        cv2.IMREAD_GRAYSCALE,
    )
    if own is None:
        return []
    existing = {
        e.get("source")
        for e in record.get("colour_plates", [])
        if e.get("capture_digest") == record["sha256"]["final"]
    }
    existing.update(
        e.get("source")
        for e in (record.get("mission_search") or {})
        .get("noirlab", {})
        .get("options", [])
    )
    deadline = time.monotonic() + 100
    seen = set()
    accepted = []
    failure = None
    for term in terms:
        # Give both archives time to return an actual observation.
        for archive, base, images in ARCHIVES:
            if time.monotonic() >= deadline:
                break
            try:
                page = read(base, 2 * 1024**2, params={"search": term}).decode(
                    "utf8", "replace"
                )
                hits = sorted(results(page), key=lambda pair: pair[0] not in FEATURES)
            except (requests.RequestException, ValueError) as exc:
                failure = exc
                continue
            archive_deadline = min(deadline, time.monotonic() + 28)
            for slug, title in hits[:3]:
                url = base + slug + "/"
                if (
                    url in existing
                    or url in seen
                    or time.monotonic() >= archive_deadline
                ):
                    continue
                seen.add(url)
                try:
                    info = description(
                        read(url, 2 * 1024**2).decode("utf8", "replace"), terms
                    )
                    if not info:
                        continue
                    payload = read(
                        images + "publicationjpg/" + slug + ".jpg", 22 * 1024**2
                    )
                    with Image.open(io.BytesIO(payload)) as original:
                        if (
                            original.format != "JPEG"
                            or original.width * original.height > 25_000_000
                        ):
                            continue
                        original.thumbnail((2300, 2300), Image.Resampling.LANCZOS)
                        photo = cv2.cvtColor(
                            np.asarray(original.convert("RGB")), cv2.COLOR_RGB2BGR
                        )
                    if min(photo.shape[:2]) < 200:
                        continue
                    option = match(
                        store, record, photo, own, anchors, archive_deadline, slug
                    )
                    if not option:
                        continue
                    credit, band = info
                    option.update(
                        id="colour-auto-" + archive.lower() + "-" + slug,
                        title=title + " · " + archive,
                        telescope=archive,
                        target=meta["target"],
                        filter=band,
                        source=url,
                        credit=credit + " · CC BY 4.0",
                    )
                    accepted.append(option)
                    if len(accepted) == 3:
                        return accepted
                    break
                except requests.RequestException as exc:
                    failure = exc
                except OSError as exc:
                    if exc.errno is not None:
                        raise
                    continue
                except (ValueError, cv2.error):
                    continue
    if not accepted and failure:
        raise ValueError("hubble_unavailable") from failure
    return accepted
