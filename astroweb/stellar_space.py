"""Measured Gaia star sprites for a small, distance-correct observer excursion."""
import math

import cv2
import numpy as np

from .gaia_depth import prepare, split_stars
from .media import REQUIRED_LAYERS
from .render import Parameters, compose, read_rgb, resize_long, select_layers


def build(store, record, folder):
    if not REQUIRED_LAYERS.issubset(record["assets"]):
        raise ValueError("observatory_space_layers")
    measured = prepare(store,record)
    params = Parameters(orientation="original")
    small = {k:resize_long(read_rgb(store.path(v)),640) for k,v in record["assets"].items()}
    choice,_ = select_layers(small,params)
    del small
    starless = resize_long(read_rgb(store.path(record["assets"]["starless"])),1600)
    stars = np.uint16(np.rint(resize_long(read_rgb(store.path(record["assets"][choice["source"]])),1600)*65535))
    sprites,_ = split_stars(stars,measured,False,choice["blend"],interpolate=False)
    h,w = stars.shape[:2]
    # Retain the strongest measured sources for a bounded GPU/Canvas workload.
    sprites.sort(key=lambda p:float(p["pixels"].max()),reverse=True)
    for p in sprites[900:]:
        sh,sw = p["pixels"].shape[:2]
        region = stars[p["y"]:p["y"]+sh,p["x"]:p["x"]+sw]
        region[:] = np.uint16(np.rint(compose(region.astype(np.float32)/65535,p["pixels"],choice["blend"])*65535))
    sprites = sprites[:900]
    bg = compose(starless,stars.astype(np.float32)/65535,choice["blend"])
    cv2.imwrite(str(folder/"space-plane.jpg"),cv2.cvtColor(np.uint8(bg*255),cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,96])
    size,cols = 64,math.ceil(math.sqrt(len(sprites)))
    atlas = np.zeros((math.ceil(len(sprites)/cols)*size,cols*size,3),np.uint8)
    rows = {r["source_id"]:r for r in measured["stars"]}
    points = []
    for i,p in enumerate(sprites):
        sh,sw = p["pixels"].shape[:2]
        sx,sy = (i%cols)*size,(i//cols)*size
        factor = min(1,size/max(sw,sh))
        tw,th = max(1,round(sw*factor)),max(1,round(sh*factor))
        atlas[sy:sy+th,sx:sx+tw] = np.uint8(np.clip(cv2.resize(p["pixels"],(tw,th)),0,1)*255)
        r = rows[p["source_id"]]
        points.append(dict(id=p["source_id"],x=(p["x"]+sw/2)/w,y=(p["y"]+sh/2)/h,width=sw/w,height=sh/h,
                           atlas=[sx,sy,tw,th],distance_pc=p["distance_pc"],error_pc=p["distance_pc"]*r["parallax_error"]/r["parallax"]))
    cv2.imwrite(str(folder/"space-stars.png"),cv2.cvtColor(atlas,cv2.COLOR_RGB2BGR))
    distances = np.array([p["distance_pc"] for p in points])
    return dict(plane="space-plane.jpg",atlas="space-stars.png",width=w,height=h,stars=points,blend=choice["blend"],
                reference_pc=float(np.median(distances)),range_pc=[float(np.min(distances)),float(np.max(distances))],depth_scale='logarithmic distance display',
                epoch=measured["epoch"],source=measured["source"],measured_count=len(points),
                unknown_count_note=True,model="inverse-parallax-snr10-ruwe1.4-no-interpolation")
