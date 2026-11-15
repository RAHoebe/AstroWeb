"""Registered flights into optical HST mosaics, archive data and credited ground-based plates."""
import hashlib
import json
import math
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import requests
from astropy.wcs import WCS

from . import skymap
from .catalogue import canonical
from .discovery import project
from .galaxy import key
from .render import ffmpeg_executable

WIDTH, HEIGHT = 1280, 720
MW, MH = 42208, 9870
TILES = "https://cdn.esahubble.org/archives/images/zoomable/heic2501a"
# Pixel centres projected from OpenNGC NGC 206, M32 and the M31 nucleus.
WINDOWS = {"ngc206": (5325,7244), "m32": (11411,2437), "nucleus": (17461,6476)}
# AVM calibration of the released large JPEGs. Pixel coordinates are top-down.
PLATES = {
    # The released WFPC2 JPEG was matched to 44 stars in the F606W HLA
    # product hst_08216_44_wfpc2_f606w_wf. CD maps bottom-up FITS pixels.
    "c20-wfpc2": dict(target="NGC_7000", size=(1330,1452), focus=(803,558),
                      sky=(314.7059488841667,44.25845019444445), crpix=(762.99314,574.49945),
                      cd=((-1.68198893e-5,2.22780662e-5),(2.22980315e-5,1.68273093e-5)),
                      telescope="HST/WFPC2", archive_id="hst_08216_44_wfpc2_f606w_wf",
                      url="https://science.nasa.gov/wp-content/uploads/2023/04/ngc7000_wfpc2_2flat_final-jpg.webp",
                      source="https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/caldwell-20/",
                      credit="NASA, ESA, K. Stapelfeldt (JPL); processing: Gladys Kober (NASA/CUA)"),
    "ic1396a": dict(target="IC_1396", size=(1200,1200), sky=(324.0,57.4),
                    scale=1/3600, rotation=0, focus=(600,600), survey="PanSTARRS",
                    source="https://catalogs.mast.stsci.edu/panstarrs/",
                    credit="Pan-STARRS1 Surveys (PS1) | STScI / CDS"),
    "heic0510a": dict(target="NGC_7000", size=(3000,3000), sky=(314.303407492,44.5943959784),
                      scale=.00131239402336, rotation=.92, focus=(1170,2210),
                      credit="Davide De Martin (ESA/Hubble), the ESA/ESO/NASA Photoshop FITS Liberator & Digitized Sky Survey 2"),
    "heic0512d": dict(target="M_31", size=(1955,2700), sky=(10.6251469072,41.3265685818),
                      scale=.000868877774835, rotation=-180.44, focus=(900,1050),
                      credit="© 2002 R. Gendler, Photo by R. Gendler"),
}
LOCK = threading.Lock()


def registration():
    # AVM spatial metadata from ESA/Hubble's released JPEG; FITS uses bottom-up y.
    wcs=WCS(naxis=2)
    wcs.wcs.ctype=["RA---TAN","DEC--TAN"]
    wcs.wcs.crval=[10.9324088386,41.3858104149]
    wcs.wcs.crpix=[21104,4935]
    wcs.wcs.cdelt=[-5.551820996312463e-5,5.551820996312463e-5]
    wcs.wcs.crota=[-125.02223862026]*2
    return wcs


def is_andromeda(record):
    return key(record["metadata"]["target"]) in {"M31","MESSIER31","NGC224","ANDROMEDA","ANDROMEDAGALAXY","ANDROMEDASTELSEL"}


def eligible(record):
    if record.get("capture_kind"):
        return False
    state = record.get("skymap") or {}
    has_destination = state.get("option") and state.get("target") == skymap.target_key(record)
    return bool(has_destination or is_andromeda(record) or record.get("fits") or (record.get("gaia") or {}).get("corners"))


def fields(store,record):
    if record.get("capture_kind"):
        return []
    options=[]
    preferred = skymap.cached_option(store, record)
    if is_andromeda(record):
        options.extend({"id":name,"relation":"region"} for name in WINDOWS if window_geometry(store,record,name) is not None)
    for name, plate in PLATES.items():
        if canonical(record["metadata"]["target"]) == plate["target"] or (is_andromeda(record) and plate["target"]=="M_31"):
            if window_geometry(store,record,name) is not None:
                options.append({"id":name,"relation":"region","credit":plate["credit"],
                                "telescope":plate.get("telescope"),
                                "source":plate.get("source",f"https://esahubble.org/images/{name}/")})
    search = record.get("hst_search")
    if search:
        from .archive_search import field_key, saved_options
        if search["field"] == field_key(store,record):
            archived = saved_options(search)
            if archived:
                # A published colour plate and its contributing archive product
                # represent the same destination for a capture that contains both.
                represented = {PLATES[o["id"]].get("archive_id") for o in options if o["id"] in PLATES}
                additional = [e for e in archived if e["id"] not in represented]
                options = ([e for e in additional if e.get("relation") != "field"] + options
                           + [e for e in additional if e.get("relation") == "field"])
            elif search.get("unavailable") and not options and not preferred:
                raise ValueError("hubble_unavailable")
    if not options and not search:
        from .hst_archive import find_fields
        try:
            options = find_fields(store,record)
        except (requests.RequestException, ValueError, OSError):
            if not preferred or skymap.focus_point(store, record, preferred) is None:
                raise
    if preferred and skymap.focus_point(store, record, preferred) is not None:
        return [preferred, *options]
    return options


def plate_wcs(plate):
    wcs=WCS(naxis=2)
    wcs.wcs.ctype=["RA---TAN","DEC--TAN"]
    wcs.wcs.crval=plate["sky"]
    if "cd" in plate:
        wcs.wcs.crpix=plate["crpix"]
        wcs.wcs.cd=plate["cd"]
        return wcs
    wcs.wcs.crpix=[length/2 for length in plate["size"]]
    wcs.wcs.cdelt=[-plate["scale"],plate["scale"]]
    wcs.wcs.crota=[plate["rotation"]]*2
    return wcs


def window_geometry(store,record,name):
    if name in PLATES:
        p=PLATES[name]
        width,height=p["size"]
        wcs=plate_wcs(p)
        x,y=p["focus"]
        half=100
    else:
        x,y=WINDOWS[name]
        height=MH
        wcs=registration()
        half=1000
    square=np.array([[x-half,y-half],[x+half,y-half],[x+half,y+half],[x-half,y+half]])
    if name in PLATES and PLATES[name].get("telescope"):
        # A small focus area can fit even when the rest of the published
        # photograph crosses the upload boundary. Require all four corners.
        square=np.array([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
    sky=wcs.pixel_to_world(square[:,0],height-1-square[:,1])
    _,uv=project(store,record,sky)
    if uv is None or not np.isfinite(uv).all() or np.any((uv<0)|(uv>1)):
        return None
    points=uv*[record["width"],record["height"]]-.5
    return cv2.getPerspectiveTransform(square.astype(np.float32),points.astype(np.float32))


def tile(store,level,col,row):
    path=store.path(f"survey-cache/heic2501a/{level}/{col}-{row}.jpg")
    sizes=[(math.ceil(MW/2**p),math.ceil(MH/2**p)) for p in range(8,-1,-1)]
    w,h=sizes[level]
    expected=(min(256,h-256*row),min(256,w-256*col))
    if path.is_file():
        image=cv2.imread(str(path))
        if image is not None and image.shape[:2]==expected:
            return image
    prefix=sum(math.ceil(a/256)*math.ceil(b/256) for a,b in sizes[:level])
    group=(prefix+row*math.ceil(w/256)+col)//256
    response=requests.get(f"{TILES}/TileGroup{group}/{level}-{col}-{row}.jpg",timeout=(5,20))
    response.raise_for_status()
    image=cv2.imdecode(np.frombuffer(response.content,np.uint8),cv2.IMREAD_COLOR)
    if image is None or image.shape[:2]!=expected:
        raise ValueError("hubble_unavailable")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(response.content)
    return image


def patch(store,x,y,level,side):
    # Each tier is cropped on whole tile boundaries; matrix maps its actual pixels
    # back to the full-resolution mosaic. The image pyramid is dyadic.
    step=2**(8-level)
    tile_span=256*step
    left=max(0,(x-side//2)//tile_span)
    top=max(0,(y-side//2)//tile_span)
    right=min(math.ceil(MW/tile_span),math.ceil((x+side//2)/tile_span))
    bottom=min(math.ceil(MH/tile_span),math.ceil((y+side//2)/tile_span))
    addresses=[(i,j) for j in range(top,bottom) for i in range(left,right)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        images=list(pool.map(lambda ij:tile(store,level,*ij),addresses))
    nx=right-left
    image=np.vstack([np.hstack(images[k:k+nx]) for k in range(0,len(images),nx)])
    transform=np.array([[step,0,left*tile_span+(step-1)/2],[0,step,top*tile_span+(step-1)/2],[0,0,1.]])
    return image,transform


def capture_bounds(photo, basis):
    corners=skymap.raster_corners(photo.shape[1],photo.shape[0])
    mapped=cv2.perspectiveTransform(corners[None].astype(float),basis)[0]
    lo,hi=mapped.min(axis=0),mapped.max(axis=0)
    return (lo+hi)/2, min(WIDTH/(hi[0]-lo[0]+1), HEIGHT/(hi[1]-lo[1]+1))


def aligned_skymap_frames(photo,image,registration):
    # Keep both layers in the destination's native pixel coordinate system.
    basis=np.linalg.inv(registration)
    origin,start=capture_bounds(photo,basis)
    h,w=image.shape[:2]; target=np.array([(w-1)/2,(h-1)/2]); end=min(WIDTH/w,HEIGHT/h)
    for i in range(288):
        t=np.clip((i/287-.04)/.72,0,1); ease=t*t*(3-2*t)
        scale=start*(end/start)**ease; x,y=origin+(target-origin)*ease
        cam=np.array([[scale,0,(WIDTH-1)/2-scale*x],[0,scale,(HEIGHT-1)/2-scale*y],[0,0,1.]])
        alpha=np.clip((i/287-.50)/.35,0,1); alpha=alpha*alpha*(3-2*alpha)
        if alpha<1:source=cv2.warpPerspective(photo,cam@basis,(WIDTH,HEIGHT))
        if alpha>0:dest=cv2.warpPerspective(image,cam,(WIDTH,HEIGHT))
        yield dest if alpha>=1 else source if alpha<=0 else cv2.addWeighted(source,1-alpha,dest,alpha,0)


def tv_credit(option):
    if option.get("credit"):
        return option["credit"]
    if option.get("filter"):
        return "NASA/ESA Hubble | STScI/HLA | "+option["filter"]
    return "Hubble: NASA, ESA, B. Williams (University of Washington)"


def render(store,record,name,registration_matrix,path,archive=None,tv=False):
    photo=cv2.imdecode(np.fromfile(store.path(record["assets"]["final"]),np.uint8),cv2.IMREAD_COLOR)
    if photo is None:
        raise ValueError("invalid_image")
    if name in PLATES:
        plate=PLATES[name]
        x,y=plate["focus"]
        path_jpg=store.path(f"survey-cache/optical-plates/{name}.jpg")
        if not path_jpg.is_file():
            if "survey" in plate:
                from .survey import sample_survey
                width,height=plate["size"]
                yy,xx=np.mgrid[:height,:width]
                sky=plate_wcs(plate).pixel_to_world(xx.ravel(), height-1-yy.ravel())
                pixels=sample_survey(store, sky, 9, plate["survey"]).reshape(height,width,3)
                ok,encoded=cv2.imencode(".jpg",pixels,[cv2.IMWRITE_JPEG_QUALITY,96])
                if not ok:raise ValueError("hubble_unavailable")
                payload=encoded.tobytes()
            else:
                url=plate.get("url",f"https://cdn.esahubble.org/archives/images/large/{name}.jpg")
                reply=requests.get(url,timeout=(5,30))
                reply.raise_for_status()
                payload=reply.content
                decoded=cv2.imdecode(np.frombuffer(payload,np.uint8),cv2.IMREAD_COLOR)
                if decoded is None or decoded.shape[1::-1]!=plate["size"]:
                    raise ValueError("hubble_unavailable")
            path_jpg.parent.mkdir(parents=True,exist_ok=True)
            tmp=path_jpg.with_suffix(".part")
            try:
                tmp.write_bytes(payload)
                tmp.replace(path_jpg)
            finally:
                tmp.unlink(missing_ok=True)
        image=cv2.imread(str(path_jpg))
        if image is None or image.shape[1::-1]!=plate["size"]:
            raise ValueError("hubble_unavailable")
        layers=[((image,np.eye(3)),8)]
        credit=plate["credit"].replace("©","(c)")
    elif archive is None:
        x,y=WINDOWS[name]
        layers=[(patch(store,x,y,level,extent),level) for level,extent in ((5,10000),(7,5500),(8,2400))]
        credit="Hubble: NASA, ESA, B. Williams (University of Washington)"
    else:
        from .hst_archive import registered_cutout
        image,registration_matrix,(x,y)=registered_cutout(store,record,archive)
        layers=[((image,np.eye(3)),8)]
        credit="NASA/ESA Hubble | STScI/HLA | "+archive["filter"]
    basis=np.linalg.inv(registration_matrix) if tv else np.eye(3)
    plane=basis@registration_matrix
    centre=cv2.perspectiveTransform(np.float64([[[x,y],[x+1,y],[x,y+1]]]),plane)[0]
    origin,start=capture_bounds(photo,basis)
    sampling={"m32":.24,"nucleus":.21}.get(name,1.10 if archive else 1.05)
    end=sampling/min(np.linalg.norm(centre[i]-centre[0]) for i in (1,2))
    masks={}
    for (image,_),level in layers:
        h,w=image.shape[:2]
        yy,xx=np.ogrid[:h,:w]
        edge=np.minimum(np.minimum(yy,h-1-yy),np.minimum(xx,w-1-xx))
        # Unobserved mosaic pixels are black. Feather both coverage and patch
        # boundaries so no rectangular tile border is visible during the flight.
        valid=(image.max(axis=2)>3).astype(np.uint8)
        interior=cv2.distanceTransform(valid,cv2.DIST_L2,3)
        masks[level]=np.uint8(255*np.clip(np.minimum(edge,interior)/min(64,min(h,w)*.05),0,1))
    def frames():
        for i in range(288):
            t=min(1,max(0,(i/287-.05)/.87))
            ease=t*t*(3-2*t)
            scale=start*(end/start)**ease
            focus=(1-ease)*origin+ease*centre[0]
            cam=np.array([[scale,0,(WIDTH-1)/2-scale*focus[0]],[0,scale,(HEIGHT-1)/2-scale*focus[1]],[0,0,1.]])
            scene=cv2.warpPerspective(photo,cam@basis,(WIDTH,HEIGHT))
            for (image,transform),level in layers:
                # Crossfade between real resolution levels while their native
                # pixels approach display size, preserving registration at every frame.
                native=scale*np.linalg.norm(centre[1]-centre[0])*2**(8-level)
                fade=np.clip((native-(.18 if level==5 else .35))/(.55 if level==5 else .4),0,1)
                if fade<=0:continue
                matrix=cam@plane@transform
                overlay=cv2.warpPerspective(image,matrix,(WIDTH,HEIGHT))
                mask=cv2.warpPerspective(masks[level],matrix,(WIDTH,HEIGHT))
                alpha=mask.astype(np.float32)*np.float32(fade/255)
                scene=cv2.blendLinear(scene,overlay,1-alpha,alpha)
            yield scene
    encode(frames(), credit, path, burn_credit=not tv)


def encode(frames, credit, path, burn_credit=True):
    cmd=[ffmpeg_executable(),"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","bgr24","-s","1280x720",
         "-r","24","-i","pipe:0","-an","-c:v","libx264","-threads","2","-preset","veryfast","-crf","18",
         "-pix_fmt","yuv420p","-movflags","+faststart","-metadata","comment="+credit,str(path)]
    process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        for scene in frames:
            if burn_credit:
                cv2.putText(scene,credit,(20,HEIGHT-18),
                            cv2.FONT_HERSHEY_SIMPLEX,.46,(12,12,12),3,cv2.LINE_AA)
                cv2.putText(scene,credit,(20,HEIGHT-18),
                            cv2.FONT_HERSHEY_SIMPLEX,.46,(220,225,232),1,cv2.LINE_AA)
            process.stdin.write(scene.tobytes())
        process.stdin.close()
        if process.wait(timeout=60):raise RuntimeError("hubble_unavailable")
    finally:
        if process.poll() is None:process.kill();process.wait()
        if not process.stdin.closed:process.stdin.close()


def movie(store,record,name,tv=False):
    archive=None
    preferred = None
    if name.startswith("skymap-"):
        preferred = skymap.cached_option(store, record)
        if not preferred or preferred["id"] != name:
            raise ValueError("hubble_no_field")
        focus = skymap.focus_point(store, record, preferred)
        if focus is None:
            raise ValueError("hubble_no_field")
        signature = ["nasa-skymap-v1", record["sha256"]["final"], name, preferred["digest"], focus]
        if tv:
            matrix=skymap.tv_registration(store,record,preferred)
            if matrix is None:raise ValueError("hubble_no_field")
            signature.append(matrix.tolist())
    elif (name in WINDOWS and is_andromeda(record)) or (name in PLATES and any(v["id"]==name for v in fields(store,record))):
        matrix=window_geometry(store,record,name)
        if matrix is None:raise ValueError("hubble_no_field")
        signature=["registered-feature-v3",record["sha256"]["final"],matrix.tolist(),name]
    else:
        archive=next((v for v in fields(store,record) if v["id"]==name),None)
        if not archive:raise ValueError("hubble_no_field")
        from .journey import geometry
        matrix=None
        signature=["hst-optical-v6-structure",record["sha256"]["final"],geometry(store,record),name]
    if tv:signature.append("tv-destination-frame-v2")
    digest=hashlib.sha256(json.dumps(signature).encode()).hexdigest()[:20]
    folder=store.path(f"objects/{record.get('storage_id',record['id'])}/hubble")
    output=folder/f"{digest}.mp4"
    with LOCK:
        if not output.is_file():
            folder.mkdir(parents=True,exist_ok=True)
            tmp=folder/f"{uuid.uuid4().hex}.part.mp4"
            try:
                if preferred:
                    image = cv2.imread(str(skymap.image_file(store, name[7:], preferred["digest"])))
                    photo = cv2.imdecode(np.fromfile(store.path(record["assets"]["final"]), np.uint8), cv2.IMREAD_COLOR)
                    if image is None or photo is None:
                        raise ValueError("hubble_unavailable")
                    frames = (aligned_skymap_frames(photo,image,matrix) if tv else
                              skymap.render_frames(photo,image,focus,WIDTH,HEIGHT))
                    encode(frames, preferred["credit"] + " | " + name[7:].upper(), tmp, burn_credit=not tv)
                else:
                    render(store,record,name,matrix,tmp,archive,tv=tv)
                tmp.replace(output)
            finally:
                tmp.unlink(missing_ok=True)
    return output
