"""Register an AllWISE colour cutout to the final raster, including parity."""
import hashlib
import json
import math
import os
import threading
import uuid

import cv2
import numpy as np
from astropy.coordinates import SkyCoord, CartesianRepresentation
from astropy.io.fits import Header
from astropy.wcs import WCS

from .journey import fits_registration, geometry
from .survey import sample_survey

LOCK = threading.Lock()


def raster_sky(store, record, field, x, y):
    """ICRS at normalized pixel centres measured from the displayed top left."""
    width, height = record["width"], record["height"]
    solved = record.get("gaia") or {}
    if field["kind"] == "wcs":
        wcs, fx, fy = fits_registration(store.path(record["fits"]),store.path(record["poster"]),width,height)
        return wcs.pixel_to_world((x if fx==1 else 1-x)*width-.5,
                                  (y if fy==1 else 1-y)*height-.5).icrs
    if solved.get("wcs_header") and solved.get("digest")==record["sha256"]["final"] and solved.get("status")=="solved":
        wcs=WCS(Header.fromstring(solved["wcs_header"],sep="\n"))
        return wcs.pixel_to_world(x*width-.5,y*height-.5).icrs
    corners=SkyCoord(*np.array(field["corners"]).T,unit="deg")
    center=SkyCoord(corners.cartesian.mean(),frame="icrs")
    local=center.skyoffset_frame()
    xyz=corners.transform_to(local).cartesian.xyz.value
    tangent=np.float32((xyz[1:]/xyz[0]).T)
    matrix=cv2.getPerspectiveTransform(np.float32([[0,0],[1,0],[1,1],[0,1]]),tangent)
    uv=cv2.perspectiveTransform(np.stack((x,y),axis=-1),matrix)
    vectors=CartesianRepresentation(np.ones_like(x),uv[:,:,0],uv[:,:,1])
    return SkyCoord(vectors,frame=local).icrs


def comparison_image(store,record):
    field=geometry(store,record)
    if "corners" not in field:
        raise ValueError("comparison_missing")
    factor=min(1,1536/max(record["width"],record["height"]))
    w,h=[max(2,round(record[k]*factor)) for k in ("width","height")]
    corners=SkyCoord(*np.array(field["corners"]).T,unit="deg")
    arcsec=corners[0].separation(corners[1]).arcsec/w
    order=int(np.clip(round(math.log2(58.6*3600/(512*max(.01,arcsec)))),0,8))
    signature=[field,(record.get("gaia") or {}).get("wcs_header"),record.get("fits"),w,h]
    key=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()[:24]
    path=store.path(f"objects/{record.get('storage_id',record['id'])}/comparison/allwise-{key}.jpg")
    with LOCK:
        if not path.exists():
            y,x=np.mgrid[:h,:w]
            sky=raster_sky(store,record,field,(x+.5)/w,(y+.5)/h)
            image=sample_survey(store,sky.ravel(),order,"AllWISE").reshape(h,w,3)
            path.parent.mkdir(parents=True,exist_ok=True)
            tmp=path.with_name(uuid.uuid4().hex+".jpg")
            try:
                if not cv2.imwrite(str(tmp),image,[cv2.IMWRITE_JPEG_QUALITY,95]):
                    raise OSError("AllWISE cutout could not be saved")
                os.replace(tmp,path)
            finally:
                tmp.unlink(missing_ok=True)
    return path,arcsec
