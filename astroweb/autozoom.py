"""Propose editable focus stops from registered objects and image structure."""
import cv2
import numpy as np
from .discovery import discover


def propose(store,record,count):
    image=cv2.imread(str(store.path(record["poster"])),cv2.IMREAD_GRAYSCALE)
    objects = [] if record.get("capture_kind") else discover(store, record)["objects"]
    return propose_image(image, count, objects)


def propose_image(image, count, objects=()):
    if type(count) is not int or not 1<=count<=8:
        raise ValueError("invalid_parameters")
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
        candidates.append((float(strength)+spread,x,y,obj["id"],"catalog"))
    if spread>.3:
        peaks=cv2.dilate(contrast,np.ones((17,17),np.uint8))
        yy,xx=np.where((contrast==peaks)&(contrast>max(.3,spread*.12)))
        for i in np.argsort(-contrast[yy,xx])[:500]:
            candidates.append((float(contrast[yy[i],xx[i]]),(xx[i]+.5)/w,(yy[i]+.5)/h,"","structure"))
    points=[]
    for score,x,y,name,kind in sorted(candidates, key=lambda c:-c[0]):
        if any(np.hypot((x-p["x"])*w,(y-p["y"])*h)<min(h,w)*.14 for p in points):
            continue
        points.append({"x":round(x,5),"y":round(y,5),"zoom":round(min(4.5,2+score/max(spread,1)),2),
                       "name":name,"kind":kind})
        if len(points)==count:break
    return points
