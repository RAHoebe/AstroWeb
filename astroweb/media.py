"""Validated import of the four original exports, without modifying their bytes."""
import hashlib
import re
import shutil
import uuid
import warnings
from pathlib import Path

from PIL import Image

from .metadata import initial_metadata
from .render import Parameters, read_rgb, resize_long, save_jpg
from .store import now

ROLES = ("final", "starless", "stars", "stars_laid")
EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MAX_FILE = 100 * 1024 * 1024
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def normalize_id(value):
    value = re.sub(r"[\s-]+", "_", str(value).strip().upper())
    if not re.fullmatch(r"[A-Z][A-Z0-9]{0,14}_[0-9]{1,8}[A-Z]?", value):
        raise ValueError("invalid_identifier")
    return value


def identify_files(identifier, paths):
    roles = {}
    for path in paths:
        path = Path(path)
        name = path.name
        if path.suffix.lower() not in EXTENSIONS or not name.upper().startswith(identifier + "_"):
            raise ValueError("invalid_filename")
        role = next((r for r in ("stars_laid", "starless", "stars", "final") if path.stem.lower().endswith("_" + r)), None)
        if role is None or role in roles:
            raise ValueError("invalid_files")
        roles[role] = path
    if set(roles) != set(ROLES):
        raise ValueError("four_images_required")
    return roles


def validate_image(path):
    if path.stat().st_size > MAX_FILE:
        raise ValueError("image_too_large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
                if image.format not in {"PNG", "JPEG", "TIFF"} or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("invalid_image")
                if width * height > MAX_PIXELS or min(width, height) < 128:
                    raise ValueError("image_dimensions")
                size = image.size
                image.verify()
            with Image.open(path) as image:
                if image.getexif().get(274, 1) != 1:
                    raise ValueError("image_orientation")
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("invalid_image") from None
    return size


def validate_images(paths):
    sizes = set()
    for path in paths.values():
        sizes.add(validate_image(path))
    if len(sizes) != 1:
        raise ValueError("dimension_mismatch")
    # Force full decoding before any record can enter the queue.
    for path in paths.values():
        read_rgb(path)
    return next(iter(sizes))


def import_object(store, identifier, paths):
    identifier = normalize_id(identifier)
    if store.get("objects", store.current_id(identifier)):
        raise ValueError("object_exists")
    roles = identify_files(identifier, paths)
    width, height = validate_images(roles)
    root = store.path(f"objects/{identifier}")
    # A previous interrupted import must not be reused or silently overwritten.
    folder = root / ("originals-" + uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    assets, hashes = {}, {}
    try:
        for role, source in roles.items():
            dest = folder / source.name
            shutil.copyfile(source, dest)
            assets[role] = dest.relative_to(store.root).as_posix()
            hashes[role] = hashlib.sha256(dest.read_bytes()).hexdigest()
        poster = folder.parent / "poster.jpg"
        save_jpg(poster, resize_long(read_rgb(roles["final"]), 1600))
        record = {"id": identifier, "assets": assets, "sha256": hashes, "poster": poster.relative_to(store.root).as_posix(), "width": width, "height": height, "metadata": initial_metadata(identifier), "params": Parameters().__dict__, "video": None, "render": None, "published": False, "created_at": now()}
        return store.put("objects", identifier, record)
    except BaseException:
        # Remove only this new, checked directory inside the data root.
        if folder.resolve().is_relative_to(store.root):
            shutil.rmtree(folder)
        raise
