"""Propose editable focus stops from registered objects and image structure."""
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from .catalogue import canonical, catalogue_labels, name_key
from .discovery import discover
from .metadata import initial_metadata, known_target


def target_identity(identifier):
    if not identifier:
        return None
    identifier = canonical(identifier)
    entry = catalogue_labels().get(identifier)
    seed = known_target(identifier)
    return {"id":identifier,"known":bool(entry or seed),"name":initial_metadata(identifier)["name"]}


def validate_count(count):
    if type(count) is not int or not 1 <= count <= 8:
        raise ValueError("invalid_parameters")


def propose(store, record, count, *, image=None):
    validate_count(count)
    if image is None:
        image = cv2.imread(str(store.path(record["poster"])), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("invalid_image")
    if record.get("capture_kind"):
        return {"points":propose_image(image, count), "alignment":"landscape"}
    guide = discover(store, record, links=False)
    target = canonical(record.get("metadata", {}).get("target") or record["id"])
    return {"points":propose_image(image, count, guide["objects"], target), "alignment":guide["kind"]}


def draft(store, preview, image, count, identifier, fits, stars):
    """Use WCS or measured stellar matches to name stops before the real import."""
    from .gaia import solve
    from .media import MAX_PIXELS, normalize_id, validate_image
    from .observation import read_observation

    validate_count(count)
    if not (fits or stars):
        return {"points":propose_image(image, count), "alignment":"missing"}
    target = canonical(normalize_id(identifier)) if identifier else ""
    height, width = image.shape

    def same_aspect(w, h):
        return w > 0 and h > 0 and abs(w*height-h*width) <= max(w, h)

    with TemporaryDirectory(prefix="zoom-", dir=store.root) as directory:
        folder = Path(directory)
        poster = folder/"preview.jpg"
        poster.write_bytes(preview)
        record = {"id":target, "metadata":initial_metadata(target), "poster":poster.relative_to(store.root).as_posix(),
                  "width":width, "height":height, "sha256":{"final":"draft"}}
        if fits:
            source = folder/"capture.fits"
            fits.save(source)
            observation = read_observation(source)
            header = observation["header"]
            w, h = header.get("NAXIS1",0), header.get("NAXIS2",0)
            if isinstance(w,int) and isinstance(h,int) and w*h <= MAX_PIXELS and same_aspect(w,h):
                record.update(fits=source.relative_to(store.root).as_posix(),
                              observation=observation, width=w, height=h)
                route = propose(store, record, count, image=image)
                if route["alignment"] != "missing":
                    return route
        if stars and target in catalogue_labels():
            source = folder/"stars"
            stars.save(source)
            w, h = validate_image(source)
            if same_aspect(w,h):
                record.update(width=w,height=h,assets={"stars":source.relative_to(store.root).as_posix()})
                record["gaia"] = solve(store, record, timeout=(2,7))
                route = propose(store, record, count, image=image)
                if route["alignment"] == "missing" and record["gaia"]["status"] == "unavailable":
                    route["alignment"] = "unavailable"
                return route
    return {"points":propose_image(image, count), "alignment":"missing"}


def propose_image(image, count, objects=(), target=None):
    validate_count(count)
    scale=640/max(image.shape)
    size = tuple(max(1, round(n*scale)) for n in reversed(image.shape))
    small=cv2.resize(image,size,interpolation=cv2.INTER_AREA).astype(np.float32)
    h,w=small.shape
    # Smooth point sources before ranking extended bright ridges, dust edges
    # and star concentrations. Separation is measured in the original aspect.
    blur=cv2.GaussianBlur(small,(0,0),max(1,min(h,w)/150))
    bg=cv2.GaussianBlur(blur,(0,0),max(4,min(h,w)/10))
    contrast=cv2.GaussianBlur(np.abs(blur-bg),(0,0),max(2,min(h,w)/35))
    spread=float(np.percentile(contrast,99))
    candidates=[]
    for obj in objects:
        x,y=obj["x"],obj["y"]
        strength=contrast[min(h-1,int(y*h)),min(w-1,int(x*w))]
        ident = canonical(obj["id"])
        labels = obj["name"]
        named = any(name_key(label) != name_key(obj["id"]) for label in labels.values())
        priority = 0 if ident == target else 1 if named else 3 if ident.startswith("HIP_") else 2
        candidates.append((priority,float(strength)+spread,x,y,obj["id"],"catalog",labels))
    if spread>.3:
        peaks=cv2.dilate(contrast,np.ones((17,17),np.uint8))
        yy,xx=np.where((contrast==peaks)&(contrast>max(.3,spread*.12)))
        for i in np.argsort(-contrast[yy,xx])[:500]:
            candidates.append((3,float(contrast[yy[i],xx[i]]),(xx[i]+.5)/w,(yy[i]+.5)/h,"","structure",None))
    points=[]
    for _,score,x,y,name,kind,labels in sorted(candidates, key=lambda c:(c[0],-c[1])):
        if any(np.hypot((x-p["x"])*w,(y-p["y"])*h)<min(h,w)*.14 for p in points):
            continue
        points.append({"x":round(x,5),"y":round(y,5),"zoom":round(min(4.5,2+score/max(spread,1)),2),
                       "name":name,"label":labels,"kind":kind})
        if len(points)==count:break
    return points
