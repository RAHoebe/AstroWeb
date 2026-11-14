"""Validated import of the four original exports, without modifying their bytes."""
import hashlib
import re
import shutil
import uuid
import warnings
from pathlib import Path

from PIL import Image

from .catalogue import canonical,group_id,notation,belongs
from .solar import ALIASES, BODIES
from .metadata import initial_metadata
from .render import Parameters, read_rgb, resize_long, save_jpg
from .store import now

NIGHTSCAPES = {"startrails": ("Sterrensporen", "Star trails"), "milkyway": ("Melkwegfoto", "Milky Way photograph")}
ROLES = ("final", "starless", "stars", "stars_laid")
EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MAX_FILE = 100 * 1024 * 1024
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def normalize_id(value):
    value = re.sub(r"[\s-]+", "_", str(value).strip().upper())
    if value in ALIASES:
        return ALIASES[value]
    value=notation(value)
    if not re.fullmatch(r"[A-Z][A-Z0-9]{0,14}_[0-9]{1,8}[A-Z]?", value):
        raise ValueError("invalid_identifier")
    return value


def file_prefix(filename):
    stem = Path(filename).stem
    for separator in re.finditer("_", stem):
        try:
            return normalize_id(stem[:separator.start()])
        except ValueError:
            continue
    return None


def fits_target(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return normalize_id(value)
    except ValueError:
        from .galaxy import key, target_entry
        entry = target_entry(key(value))
        if entry:
            try:
                return normalize_id(entry["id"])
            except ValueError:
                pass
    return None


def upload_identity(names, object_value, fallback=""):
    target = fits_target(object_value)
    prefix = next((prefix for name in names if (prefix := file_prefix(name))), None)
    if target:
        return target, "fits", prefix
    if prefix:
        return prefix, "prefix", prefix
    return normalize_id(fallback) if fallback else None, "manual", None


def identify_files(identifier, paths):
    roles = {}
    export_stems = set()
    for path in paths:
        path = Path(path)
        name = path.name
        if path.suffix.lower() not in EXTENSIONS or (identifier and not belongs(name,identifier)):
            raise ValueError("invalid_filename")
        role = next((r for r in ("stars_laid", "starless", "stars", "final") if path.stem.lower().endswith("_" + r)), None)
        if role is None or role in roles:
            raise ValueError("invalid_files")
        export_stems.add(path.stem[:-len(role)-1].casefold())
        roles[role] = path
    if set(roles) != set(ROLES):
        raise ValueError("four_images_required")
    if not identifier and (len(export_stems) != 1 or "" in export_stems):
        raise ValueError("invalid_filename")
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


def import_object(store, identifier, paths, session_name="", *, repeat=False, capture_date=None, source_prefix=None, allow_export_prefix=False, nightscape=None, title=""):
    if nightscape:
        if nightscape not in NIGHTSCAPES:
            raise ValueError("capture_kind_mismatch")
        title = title.strip()
        if len(title)>100 or any(ord(ch)<32 for ch in title):
            raise ValueError("invalid_capture_title")
        # Each landscape is its own gallery entry, including repeated nights of the same type.
        identifier = nightscape.upper()+"~"+uuid.uuid4().hex
    else:
        identifier = normalize_id(identifier)
    catalog_id = identifier
    session_name = session_name.strip()
    if len(session_name)>80 or any(ord(c)<32 for c in session_name):
        raise ValueError("invalid_session")
    existing = store.get("objects",store.current_id(identifier))
    catalog_id=group_id(existing) if existing else canonical(identifier)
    siblings=[r for r in store.all("objects") if group_id(r)==catalog_id]
    separate=not nightscape and bool(session_name or (repeat and siblings))
    if session_name:
        if any(r.get("session_name","").casefold()==session_name.casefold() for r in siblings):
            raise ValueError("session_exists")
    elif siblings and not repeat:
        raise ValueError("object_exists")
    solar=catalog_id in BODIES
    if solar or nightscape:
        paths=list(paths)
        if len(paths)!=1 or Path(paths[0]).suffix.lower() not in EXTENSIONS:
            raise ValueError("single_image_required")
        roles={"final":Path(paths[0])}
    else:
        roles=identify_files(source_prefix if allow_export_prefix else identifier, paths)
    width, height = validate_images(roles)
    identifier=catalog_id
    if separate:
        identifier = catalog_id+"~"+uuid.uuid4().hex[:12]
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
        record = {"id": identifier, "assets": assets, "sha256": hashes, "poster": poster.relative_to(store.root).as_posix(), "width": width, "height": height, "metadata": initial_metadata(catalog_id), "params": Parameters().__dict__, "video": None, "render": None, "published": False, "created_at": now()}
        if nightscape:
            nl,en=NIGHTSCAPES[nightscape]
            record["metadata"].update(target=en, name={"nl":title or nl,"en":title or en},
                                      type={"nl":nl,"en":en},summary={"nl":"","en":""},
                                      description={"nl":"","en":""},translation="curated",aliases=[],sources=[])
            record.update(capture_kind=nightscape,session_name=session_name)
        if solar:
            record["body"]=catalog_id
        if solar or nightscape:
            record.update(gaia={"status":"not_applicable"},params=Parameters(method="kenburns",orientation="original").__dict__)
        if capture_date:
            record["capture_date"]=capture_date
        if separate:
            record.update(catalog_id=catalog_id,session_name=session_name)
            if siblings:
                import copy
                record["metadata"] = copy.deepcopy((existing or siblings[0])["metadata"])
        return store.put("objects", identifier, record)
    except BaseException:
        # Remove only this new, checked directory inside the data root.
        if folder.resolve().is_relative_to(store.root):
            shutil.rmtree(folder)
        raise
