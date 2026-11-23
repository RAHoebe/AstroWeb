"""Register licensed NOIRLab optical photographs directly to the user's star field."""

import hashlib
import re
import uuid

import cv2
import numpy as np
import requests
from PIL import Image

from . import external_http
from .catalogue import canonical

PLATES = {
    "noao-ic1396": (
        "IC 1396",
        "IC 1396A",
        "WIYN / KPNO",
        "WIYN/KPNO/NOIRLab/NSF/AURA/T. A. Rector (University of Alaska Anchorage)",
    ),
    "noao-ngc281": (
        "NGC 281",
        "NGC 281",
        "WIYN 0.9 m",
        "T. A. Rector/University of Alaska Anchorage and WIYN/AURA/NSF",
    ),
    "noao-02678": ("M 57", "M57", "Mayall 4 m", "Bill Schoening/KPNO/NOIRLab/NSF/AURA"),
    "noao-ring": ("M 57", "M57", "WIYN 3.5 m", "C. F. Claver/WIYN/NOIRLab/NSF"),
}


def plate(store, slug):
    if slug not in PLATES:
        raise ValueError("invalid_archive_product")
    path = store.path(f"survey-cache/noirlab/{slug}.jpg")
    if not path.exists():
        url = f"https://noirlab.edu/public/media/archives/images/large/{slug}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix("." + uuid.uuid4().hex + ".part")
        try:
            with (
                external_http.get(url, stream=True, timeout=(5, 25)) as reply,
                tmp.open("xb") as out,
            ):
                reply.raise_for_status()
                for chunk in reply.iter_content(65536):
                    if out.tell() + len(chunk) > 24 * 1024**2:
                        raise ValueError("archive_product_too_large")
                    out.write(chunk)
            with Image.open(tmp) as photo:
                if photo.format != "JPEG" or photo.width * photo.height > 24_000_000:
                    raise ValueError("invalid_archive_product")
                photo.verify()
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
    return path


def match_plate(source, capture):
    """Fit a similarity transformation, validating unused stars across the plate."""

    def reduce(image, limit):
        h, w = image.shape
        f = min(1, limit / max(w, h))
        img = cv2.resize(
            image,
            (max(1, round(w * f)), max(1, round(h * f))),
            interpolation=cv2.INTER_AREA,
        )
        scale = np.diag([img.shape[1] / w, img.shape[0] / h, 1.0])
        scale[:2, 2] = (scale.diagonal()[:2] - 1) * 0.5
        return cv2.createCLAHE(2.0, (8, 8)).apply(img), scale

    dest, basis = reduce(capture, 2000)
    sift = cv2.SIFT_create(nfeatures=8000, contrastThreshold=0.015)
    ref, descriptors = sift.detectAndCompute(dest, None)
    if descriptors is None or len(descriptors) < 35:
        raise ValueError("hubble_no_field")
    matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=64))
    matcher.add([descriptors])
    matcher.train()
    for edge in (1400, 700, 350):
        small, src = reduce(source, edge)
        for flip in (False, True):
            view = cv2.flip(small, 1) if flip else small
            features, values = sift.detectAndCompute(view, None)
            if values is None:
                continue
            pairs = matcher.knnMatch(values, k=2)
            unique = {}
            for first, second in pairs:
                if first.distance < 0.76 * second.distance:
                    # Keep the best correspondence per physical star position.
                    key = tuple(round(v / 3) for v in ref[first.trainIdx].pt)
                    if key not in unique or first.distance < unique[key].distance:
                        unique[key] = first
            if len(unique) < 32:
                continue
            a = np.float32([features[m.queryIdx].pt for m in unique.values()])
            b = np.float32([ref[m.trainIdx].pt for m in unique.values()])
            hold = np.arange(len(a)) % 4 == 0
            fit, mask = cv2.estimateAffinePartial2D(
                a[~hold], b[~hold], method=cv2.RANSAC, ransacReprojThreshold=1.6
            )
            if fit is None or mask.sum() < 24:
                continue
            err = np.linalg.norm(cv2.transform(a[None], fit)[0] - b, axis=1) / min(
                basis[0, 0], basis[1, 1]
            )
            check = hold & (err < 2.0)
            if check.sum() < 10 or np.median(err[check]) > 1.2:
                continue
            hull = cv2.convexHull(a[check])
            if cv2.contourArea(hull) < 0.18 * view.size or np.any(
                np.ptp(a[check], axis=0) < 0.52 * np.array(view.shape[::-1])
            ):
                continue
            mirror = (
                np.array([[-1, 0, view.shape[1] - 1], [0, 1, 0], [0, 0, 1.0]])
                if flip
                else np.eye(3)
            )
            matrix = np.linalg.inv(basis) @ np.vstack((fit, [0, 0, 1.0])) @ mirror @ src
            h, w = source.shape
            corners = np.float64(
                [[[-0.5, -0.5], [w - 0.5, -0.5], [w - 0.5, h - 0.5], [-0.5, h - 0.5]]]
            )
            projected = cv2.perspectiveTransform(corners, matrix)[0]
            if np.any(projected < -0.5) or np.any(
                projected > np.array(capture.shape[::-1]) - 0.5
            ):
                continue
            return matrix, dict(
                matches=int((err < 2).sum()),
                verified=int(check.sum()),
                residual_px=round(float(np.median(err[check])), 3),
            )
    raise ValueError("hubble_no_field")


def star_match(source, capture, anchor):
    from scipy.spatial import cKDTree
    from .gaia import seed_transform, correspondences

    def stars(image):
        gray = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
        signal = gray - cv2.GaussianBlur(gray, (0, 0), 4.0)
        yy, xx = np.where(
            (signal == cv2.dilate(signal, np.ones((7, 7), np.uint8)))
            & (signal > max(1.0, np.percentile(signal, 95)))
        )
        order = np.argsort(-signal[yy, xx])[:600]
        pts = np.column_stack((xx[order], yy[order]))
        _, unique = np.unique(np.round(pts / 4), axis=0, return_index=True)
        return pts[np.sort(unique)].astype(float)

    h, w = source.shape
    factor = min(1, 900 / max(h, w))
    small = cv2.resize(source, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
    scale = np.diag([small.shape[1] / w, small.shape[0] / h, 1.0])
    scale[:2, 2] = (scale.diagonal()[:2] - 1) * 0.5
    points = stars(small)
    hold = np.arange(len(points)) % 4 == 0
    if len(points) < 40:
        raise ValueError("hubble_no_field")
    x, y = map(round, anchor)
    for radius in (128, 320, 800, 1800):
        left, top = max(0, x - radius), max(0, y - radius)
        window = capture[top : y + radius, left : x + radius]
        dest = stars(window)[:350] + [left, top]
        if len(dest) < 40:
            continue
        seed = seed_transform(points[~hold], dest, (0.035, 4.0))
        if seed is None:
            continue
        linear, offset, _ = seed
        tree = cKDTree(dest)
        train = points[~hold]
        ii, jj = correspondences(tree, train @ linear.T + offset, 2.5)
        if len(ii) < 24:
            continue
        parity = np.diag([1.0, np.sign(np.linalg.det(linear))])
        fit, mask = cv2.estimateAffinePartial2D(
            train[ii] @ parity, dest[jj], method=cv2.RANSAC, ransacReprojThreshold=1.5
        )
        if fit is None or mask.sum() < 24:
            continue
        matrix = np.vstack((fit, [0, 0, 1.0])) @ np.diag([1.0, parity[1, 1], 1.0])
        check = points[hold]
        predicted = cv2.perspectiveTransform(check[None], matrix)[0]
        a, b = correspondences(tree, predicted, 2.0)
        independent = ~np.isin(b, jj[mask.ravel().astype(bool)])
        a, b = a[independent], b[independent]
        if len(a) < max(10, int(0.24 * len(check))):
            continue
        residual = float(np.median(np.linalg.norm(predicted[a] - dest[b], axis=1)))
        if (
            residual > 1.2
            or cv2.contourArea(cv2.convexHull(check[a].astype(np.float32)))
            < 0.18 * small.size
        ):
            continue
        matrix = matrix @ scale
        corners = np.float64(
            [[[-0.5, -0.5], [w - 0.5, -0.5], [w - 0.5, h - 0.5], [-0.5, h - 0.5]]]
        )
        field = cv2.perspectiveTransform(corners, matrix)[0]
        if np.all(field >= -0.5) and np.all(
            field <= np.array(capture.shape[::-1]) - 0.5
        ):
            return matrix, dict(
                matches=int(mask.sum() + len(a)),
                verified=len(a),
                residual_px=round(residual, 3),
            )
    raise ValueError("hubble_no_field")


def candidates(store, record):
    from .discovery import discover

    options = []
    failure = None
    for slug, (parent, target, telescope, credit) in PLATES.items():
        if canonical(parent) != canonical(record["metadata"]["target"]):
            continue
        points = discover(store, record, links=False)["objects"]
        point = next(
            (p for p in points if canonical(p["id"]) == canonical(target)), None
        )
        if point is None:
            continue
        try:
            path = plate(store, slug)
        except requests.RequestException as exc:
            failure = exc
            continue
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        own = cv2.imdecode(
            np.fromfile(store.path(record["assets"]["final"]), np.uint8),
            cv2.IMREAD_GRAYSCALE,
        )
        if image is None or own is None:
            continue
        try:
            matrix, report = match_plate(image, own)
        except ValueError:
            try:
                matrix, report = star_match(
                    image, own, (point["x"] * own.shape[1], point["y"] * own.shape[0])
                )
            except ValueError:
                continue
        h, w = own.shape
        focus = cv2.perspectiveTransform(
            np.float64([[[point["x"] * w - 0.5, point["y"] * h - 0.5]]]),
            np.linalg.inv(matrix),
        )[0, 0]
        if not np.all((focus >= 1) & (focus < np.array(image.shape[::-1]) - 1)):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        ident = (
            "noirlab-"
            + hashlib.sha256(
                (slug + digest + record["sha256"]["final"]).encode()
            ).hexdigest()[:24]
        )
        options.append(
            dict(
                id=ident,
                provider="noirlab",
                target=target,
                relation="region",
                title=f"{target} · {telescope}",
                telescope=telescope,
                filter="optical",
                source=f"https://noirlab.edu/public/images/{slug}/",
                credit=credit + " · CC BY 4.0",
                slug=slug,
                digest=digest,
                capture_digest=record["sha256"]["final"],
                ra=point["ra"],
                dec=point["dec"],
                full_footprint=True,
                matrix=matrix.tolist(),
                focus=focus.tolist(),
                **report,
            )
        )
    if failure is not None and not options:
        raise failure
    return options


def registered_cutout(store, record, entry):
    if entry["provider"] == "colour-plate":
        digest = entry["digest"]
        if not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("invalid_archive_product")
        path = store.path(f"survey-cache/colour-plates/{digest}.jpg")
        if not path.is_file():
            raise ValueError("hubble_no_field")
    else:
        path = plate(store, entry["slug"])
    if (
        record["sha256"]["final"] != entry["capture_digest"]
        or hashlib.sha256(path.read_bytes()).hexdigest() != entry["digest"]
    ):
        raise ValueError("hubble_no_field")
    image = cv2.imread(str(path))
    matrix = np.asarray(entry["matrix"], dtype=float)
    focus = np.asarray(entry["focus"], dtype=float)
    if (
        image is None
        or matrix.shape != (3, 3)
        or focus.shape != (2,)
        or not np.isfinite(matrix).all()
        or not np.isfinite(focus).all()
    ):
        raise ValueError("hubble_no_field")
    h, w = image.shape[:2]
    corners = np.float64(
        [[[-0.5, -0.5], [w - 0.5, -0.5], [w - 0.5, h - 0.5], [-0.5, h - 0.5]]]
    )
    footprint = cv2.perspectiveTransform(corners, matrix)[0]
    if (
        np.any(focus < 0)
        or np.any(focus >= [w, h])
        or np.any(footprint < -0.5)
        or np.any(footprint > np.array([record["width"], record["height"]]) - 0.5)
    ):
        raise ValueError("hubble_no_field")
    return image, matrix, tuple(focus)
