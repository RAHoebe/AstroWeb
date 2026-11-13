"""Locally cached optical detail plates from the STScI/CDS DSS2 colour HiPS."""
import hashlib
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import astropy.units as u
import cv2
import numpy as np
import requests
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix

SURVEYS = {"AllWISE":"https://irsa.ipac.caltech.edu/data/hips/CDS/AllWISE/RGB-W4-W2-W1","DSS2":"https://irsa.ipac.caltech.edu/data/hips/CDS/DSS2/color",
           "PanSTARRS":"https://stpubdata.s3.us-east-1.amazonaws.com/mast/skybackgrounds/PanSTARRS"}


def survey_for(field):
    # In IC 1396 the photographic DSS2 plate has long straight scan/plate
    # artifacts. Use independent optical observations throughout this field.
    coords = np.array(field.get("corners") or [field["center"]])
    sky = SkyCoord(coords[:,0]*u.deg,coords[:,1]*u.deg)
    return "PanSTARRS" if np.max(sky.separation(SkyCoord(324.2*u.deg,57.6*u.deg)).deg)<5 else "DSS2"

SIZE = 1536


def tile(store, order, index, survey):
    path = store.path(f"survey-cache/{survey}/{order}/{index}.jpg")
    if path.exists():
        image = cv2.imread(str(path))
        if image is not None and image.shape[:2] == (512,512):
            return image
    url = f"{SURVEYS[survey]}/Norder{order}/Dir{index//10000*10000}/Npix{index}.jpg"
    response = requests.get(url, timeout=(4, 10))
    response.raise_for_status()
    image = cv2.imdecode(np.frombuffer(response.content,np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (512,512):
        raise ValueError("Invalid DSS2 tile")
    path.parent.mkdir(parents=True,exist_ok=True)
    partial = path.with_name(uuid.uuid4().hex+".tmp")
    try:
        partial.write_bytes(response.content)
        os.replace(partial,path)
    finally:
        partial.unlink(missing_ok=True)
    return image


def make_plate(store, target, meridian, span, order, survey):
    """Resample the HiPS into the film's Hammer plane, sharing its exact camera."""
    plane = (np.arange(SIZE)+.5)/SIZE-.5
    x = -(target[0]+plane*span-1)
    y = 1-2*(target[1]+plane[:,None]*span)
    rr=x*x+y*y
    valid=rr<1
    z=np.sqrt(np.maximum(0,1-rr/2))
    lon=2*np.arctan2(np.sqrt(2)*z*x,2*z*z-1)+meridian
    lat=np.arcsin(np.clip(np.sqrt(2)*z*y,-1,1))
    icrs=SkyCoord(l=lon[valid]*u.rad,b=lat[valid]*u.rad,frame="galactic").icrs
    samples = sample_survey(store, icrs, order, survey)
    output=np.zeros((SIZE,SIZE,3),np.uint8)
    output[valid]=samples
    return output


def sample_survey(store, icrs, order, survey):
    hp=HEALPix(nside=2**order,order="nested")
    ids,dx,dy=hp.lonlat_to_healpix(icrs.ra,icrs.dec,return_offsets=True)
    indices=np.unique(ids)
    # In JPEG HiPS, the first local HEALPix axis is the image row.
    rows=np.clip((dx*512).astype(int),0,511)
    cols=np.clip((dy*512).astype(int),0,511)
    samples=np.empty((len(ids),3),np.uint8)
    with ThreadPoolExecutor(max_workers=6) as workers:
        images=workers.map(lambda i:tile(store,order,int(i),survey),indices)
        for index,image in zip(indices,images):
            selected=ids==index
            samples[selected]=image[rows[selected],cols[selected]]
    return samples


def detail_plates(store, target, meridian, extent, survey="DSS2"):
    # Span is expressed in normalized Hammer-plane units (map width = 2).
    small=np.clip(3.4*max(extent),.012,.10)
    plates=[]
    for span in (max(.13,small*3),small):
        order=int(np.clip(round(np.log2(58.6*SIZE/(span*180*512))),1,9))
        key=hashlib.sha256(np.array([*target,meridian,span,order],dtype="<f8").tobytes()).hexdigest()[:24]
        prefix="" if survey=="DSS2" else survey+"-"
        path=store.path(f"survey-cache/plates/{prefix}{key}.jpg")
        image=cv2.imread(str(path)) if path.is_file() else None
        if image is None:
            try:
                image=make_plate(store,target,meridian,span,order,survey)
                path.parent.mkdir(parents=True,exist_ok=True)
                temp=path.with_name(uuid.uuid4().hex+".jpg")
                try:
                    if not cv2.imwrite(str(temp),image,[cv2.IMWRITE_JPEG_QUALITY,95]):
                        raise OSError("Could not save DSS2 plate")
                    os.replace(temp,path)
                finally:
                    temp.unlink(missing_ok=True)
            except (OSError,requests.RequestException,ValueError):
                logging.warning("%s detail unavailable for this field",survey,exc_info=True)
                break
        plates.append((span,image))
    return plates


@lru_cache(maxsize=1)
def feather():
    axis=2*(np.arange(SIZE)+.5)/SIZE-1
    radius=np.hypot(axis[:,None],axis)
    weight=np.clip((1-radius)/.45,0,1)
    return (255*weight*weight*(3-2*weight)).astype(np.uint8)


def blend_details(scene, plates, target, offset, scale):
    used=False
    for span,image in plates:
        side=span*scale
        strength=np.clip((side-200)/650,0,1)
        if strength<=0:
            continue
        xy=(target-span/2)*scale+offset
        matrix=np.float32([[side/SIZE,0,xy[0]],[0,side/SIZE,xy[1]]])
        size=(scene.shape[1],scene.shape[0])
        detail=cv2.warpAffine(image,matrix,size,flags=cv2.INTER_LINEAR)
        alpha=cv2.warpAffine(feather(),matrix,size).astype(np.float32)*np.float32(strength/255)
        scene=cv2.blendLinear(scene,detail,1-alpha,alpha)
        used=True
    return scene,used
