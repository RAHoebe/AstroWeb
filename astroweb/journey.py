"""A locally rendered, astrometrically registered flight from the all-sky atlas."""
import hashlib
import json
import math
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import pixel_to_skycoord

from .render import ffmpeg_executable

CATALOG = Path(__file__).with_name("catalog")
SOLUTIONS = json.loads((CATALOG / "footprints.json").read_text())
RENDER_LOCK = threading.Lock()
WIDTH, HEIGHT, FPS, FRAMES = 1280, 720, 24, 264


def fits_registration(path, poster, width, height):
    """Check raster row order against the actual final export before using WCS."""
    try:
        with fits.open(path, memmap=True, do_not_scale_image_data=True) as hdus:
            hdu = hdus[0]
            header = hdu.header
            if not any(key in header for key in ("CD1_1", "CD1_2", "CDELT1")):
                return None
            wcs = WCS(header, naxis=2).celestial
            if wcs.pixel_n_dim != 2 or (header["NAXIS1"], header["NAXIS2"]) != (width, height):
                return None
            data = hdu.data
            if data.ndim == 3:
                data = data[0]
            if data.ndim != 2:
                return None
            yy = np.linspace(0, height-1, 96).round().astype(int)
            xx = np.linspace(0, width-1, 96).round().astype(int)
            photo = cv2.imread(str(poster), cv2.IMREAD_GRAYSCALE)
            thumb = cv2.resize(photo, (96, 96), interpolation=cv2.INTER_AREA)
            # Rank correlation tolerates the stretch of a processed FITS export.
            def ranks(a):
                return np.argsort(np.argsort(np.nan_to_num(a).ravel(), kind="stable"), kind="stable")
            ranked = ranks(thumb)
            raw = data[np.ix_(yy, xx)]
            scores = [(np.corrcoef(ranked, ranks(raw[::y, ::x]))[0, 1], x, y)
                      for x in (1, -1) for y in (1, -1)]
            scores.sort(reverse=True)
            score, flip_x, flip_y = scores[0]
            if score < .45 or score - scores[1][0] < .12:
                return None
            return wcs, flip_x, flip_y
    except (OSError, TypeError, KeyError, ValueError, IndexError, cv2.error):
        return None


def fits_footprint(path, poster, width, height):
    registration = fits_registration(path, poster, width, height)
    if registration is None:
        return None
    wcs, flip_x, flip_y = registration
    x = np.array([-.5, width-.5, width-.5, -.5])
    y = np.array([-.5, -.5, height-.5, height-.5])
    sky = pixel_to_skycoord(x if flip_x == 1 else width-1-x,
                            y if flip_y == 1 else height-1-y, wcs, origin=0).icrs
    corners = np.column_stack((sky.ra.deg, sky.dec.deg))
    return corners.tolist() if np.isfinite(corners).all() else None


def geometry(store, record):
    digest = record.get("sha256", {}).get("final")
    solved = record.get("gaia") or {}
    if solved.get("status") != "solved" or solved.get("digest") != digest:
        solved = SOLUTIONS.get(digest)
    corners = solved["corners"] if solved else None
    if not corners and record.get("fits"):
        corners = fits_footprint(store.path(record["fits"]), store.path(record["poster"]),
                                 record["width"], record["height"])
    if corners:
        return {"kind": "gaia" if solved else "wcs", "corners": corners}
    obs = record.get("observation") or {}
    if obs.get("ra") is not None and obs.get("dec") is not None:
        return {"kind": "point", "center": [obs["ra"], obs["dec"]]}
    return {"kind": "missing"}


def hammer(lon, lat):
    """Normalized Hammer map, longitude increasing to the left."""
    den = np.sqrt(1 + np.cos(lat) * np.cos(lon / 2))
    return np.stack((.5 - .5*np.cos(lat)*np.sin(lon/2)/den, .5 - .5*np.sin(lat)/den), axis=-1)


# Galactic Cartesian directions -> photographic plate axes of ESO/S. Brunier
# eso0932a. Rigid rotation fitted to Hipparcos peaks on the bundled 6000x3000 plate.
ATLAS_ROTATION = np.array([[.997977,.056263,-.029617],
                           [-.055707,.998262,.019251],
                           [.030649,-.017562,.999376]], dtype=np.float32)


def panorama_pixels(lon, lat, w, h):
    cl = np.cos(lat)
    x, y, z = cl*np.cos(lon), cl*np.sin(lon), np.sin(lat)
    rx, ry, rz = (a*x+b*y+c*z for a,b,c in ATLAS_ROTATION)
    return ((.5-np.arctan2(ry,rx)/(2*np.pi))*w-.5).astype(np.float32), (
        (.5-np.arctan2(rz,np.hypot(rx,ry))/np.pi)*h-.5).astype(np.float32)


def project_atlas(meridian):
    image = cv2.imread(str(CATALOG / "milky-way.jpg"))
    h, w = image.shape[:2]
    out = np.empty_like(image)
    x = ((np.arange(w, dtype=np.float32) + .5) / w - .5) * -2
    for row in range(0, h, 96):
        y = (.5 - (np.arange(row, min(row+96,h), dtype=np.float32)[:,None]+.5) / h)*2
        radius = x*x + y*y
        z = np.sqrt(np.maximum(0, 1-radius/2))
        lon = 2*np.arctan2(np.sqrt(2)*z*x, 2*z*z-1) + meridian
        lat = np.arcsin(np.clip(np.sqrt(2)*z*y, -1, 1))
        mx, my = panorama_pixels(lon,lat,w,h)
        my = np.clip(my,0,h-1)
        band = cv2.remap(image, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        band[radius>1] = (12, 8, 6)
        out[row:row+len(band)] = band
    return out


def smooth(t):
    t = max(0, min(1, t))
    return t*t*(3-2*t)


def draw_label(image, text, xy, size=.50, color=(215,222,229)):
    cv2.putText(image, text, xy, cv2.FONT_HERSHEY_SIMPLEX, size, (12,10,8), 3, cv2.LINE_AA)
    cv2.putText(image, text, xy, cv2.FONT_HERSHEY_SIMPLEX, size, color, 1, cv2.LINE_AA)


def field_projection(field):
    has_frame = "corners" in field
    coords = np.array(field["corners"] if has_frame else [field["center"]])
    gal = SkyCoord(coords[:,0]*u.deg, coords[:,1]*u.deg).galactic
    lon = gal.l.wrap_at(180*u.deg).radian
    lat = gal.b.radian
    # Move the seam away from a field that crosses the Galactic anticentre.
    mean_lon = np.angle(np.exp(1j*lon).mean())
    meridian = mean_lon if abs(mean_lon)>np.deg2rad(145) else 0.
    points = hammer((lon-meridian+np.pi)%(2*np.pi)-np.pi, lat)*[2,1]
    return meridian, points, mean_lon, lat


def camera_at(t, points, start_scale, end_scale):
    target = points.mean(axis=0)
    scale = start_scale*(end_scale/start_scale)**smooth((t-.13)/.69)
    # Interpolate the target position on screen. Interpolating in sky
    # coordinates first multiplies the remaining pan distance by the zoom.
    screen_target = np.array([WIDTH/2, HEIGHT/2-3]) + (target-[1.,.5])*start_scale*(1-smooth((t-.08)/.59))
    return scale, screen_target-target*scale


def landing(quad, width, height, progress):
    """Level the registered photo around its centre, then fit all four corners."""
    center = quad.mean(axis=0)
    edge = quad[1] - quad[0]
    angle = -math.atan2(edge[1], edge[0]) * progress
    cs, sn = math.cos(angle), math.sin(angle)
    rotation = np.array([[cs, -sn], [sn, cs]])
    upright = (quad-center) @ rotation.T
    # Interpolate shape in the levelled coordinate system so a 180-degree
    # camera roll never collapses the quadrilateral halfway through the shot.
    full_angle = -math.atan2(edge[1], edge[0])
    cs, sn = math.cos(full_angle), math.sin(full_angle)
    full_rotation = np.array([[cs, -sn], [sn, cs]])
    fit = min((WIDTH-1)/(width-1), (HEIGHT-1)/(height-1))
    half = np.array([width-1, height-1]) * fit/2
    mirrored = np.linalg.det(np.stack((edge,quad[3]-quad[0]))) < 0
    dest = np.array([[-1,-1],[1,-1],[1,1],[-1,1]])*half
    if mirrored:
        dest[:,1] *= -1
    correction = (dest - (quad-center) @ full_rotation.T) @ full_rotation
    return np.float32(upright + progress*(correction @ rotation.T)
                      + (1-progress)*center + progress*np.array([(WIDTH-1)/2,(HEIGHT-1)/2])), mirrored


def render_journey(store, record, field, output, plates):
    from .survey import blend_details, survey_for
    credit = "Pan-STARRS1 / CDS" if survey_for(field) == "PanSTARRS" else "DSS2 / STScI / CDS"
    has_frame = "corners" in field
    meridian, points, mean_lon, lat = field_projection(field)
    target = points.mean(axis=0)
    atlas = project_atlas(meridian)
    overview = cv2.resize(atlas,(1280,640),interpolation=cv2.INTER_AREA)
    photo = cv2.imread(str(store.path(record["poster"])))
    ph,pw = photo.shape[:2]
    src = np.float32([[0,0],[pw-1,0],[pw-1,ph-1],[0,ph-1]])
    start_scale = WIDTH*.46
    extent = np.ptp(points,axis=0)
    end_scale = min(WIDTH*.77/max(extent[0],1e-6),HEIGHT*.73/max(extent[1],1e-6)) if has_frame else start_scale*9
    command = [ffmpeg_executable(),"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","bgr24",
               "-s",f"{WIDTH}x{HEIGHT}","-r",str(FPS),"-i","pipe:0","-an","-c:v","libx264","-threads","2",
               "-preset","veryfast","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(output)]
    process = subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE,
                               creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    try:
        for frame in range(FRAMES):
            t = frame/(FRAMES-1)
            scale, offset = camera_at(t, points, start_scale, end_scale)
            texture = overview if scale<800 else atlas
            fac = scale/texture.shape[0]
            matrix = np.float32([[fac,0,offset[0]],[0,fac,offset[1]]])
            quad = (points*scale+offset).astype(np.float32)
            cx,cy = np.rint(quad.mean(axis=0)).astype(int)
            pose=quad
            mirrored=False
            roll=None
            if has_frame and t>.59:
                pose,mirrored=landing(quad,pw,ph,smooth((t-.59)/.32))
                roll=cv2.getPerspectiveTransform(quad,pose)
            def background(transform):
                # Project the full atlas and plates directly into the final
                # viewport, including sky outside the pre-roll video rectangle.
                if transform is None:
                    sky=cv2.warpAffine(texture,matrix,(WIDTH,HEIGHT),borderValue=(12,8,6))
                else:
                    sky=cv2.warpPerspective(texture,transform @ np.vstack((matrix,[0,0,1])),
                                            (WIDTH,HEIGHT),borderValue=(12,8,6))
                return blend_details(sky,plates,target,offset,scale,transform)
            scene,detailed=background(roll)
            if mirrored and t>.89:
                upright=cv2.getPerspectiveTransform(quad,pose[[3,2,1,0]])
                other,_=background(upright)
                flip=smooth((t-.89)/.055)
                scene=cv2.addWeighted(scene,1-flip,other,flip,0)
            if has_frame and t>.22:
                overlay = cv2.warpPerspective(photo,cv2.getPerspectiveTransform(src,pose),(WIDTH,HEIGHT))
                if mirrored and t>.89:
                    # A reflection cannot be reached by a continuous camera roll.
                    normal = cv2.warpPerspective(photo,cv2.getPerspectiveTransform(src,pose[[3,2,1,0]]),(WIDTH,HEIGHT))
                    flip = smooth((t-.89)/.055)
                    overlay = cv2.addWeighted(overlay,1-flip,normal,flip,0)
                mask = np.zeros((HEIGHT,WIDTH),np.uint8)
                polygon = np.rint(pose).astype(np.int32)
                cv2.fillConvexPoly(mask,polygon,255,cv2.LINE_AA)
                alpha = smooth((t-.49)/.34)
                region = mask>0
                scene[region] = cv2.addWeighted(scene,1-alpha,overlay,alpha,0)[region]
                border = 1-smooth((t-.67)/.19)
                if border:
                    framed = scene.copy()
                    cv2.polylines(framed,[polygon],True,(140,204,244),1,cv2.LINE_AA)
                    scene = cv2.addWeighted(framed,border,scene,1-border,0)
            if .06<t<.53 or not has_frame:
                radius=round(9+10*(1-smooth((t-.06)/.32)))
                for angle in (0,90,180,270):
                    cv2.ellipse(scene,(cx,cy),(radius,radius),0,angle+12,angle+74,(165,214,238),1,cv2.LINE_AA)
            # Fade the map typography with the atlas; the final hold is the complete photo.
            opacity = 1-smooth((t-.64)/.22) if has_frame else 1
            if opacity:
                labelled = scene.copy()
                draw_label(labelled,record.get("catalog_id",record["id"]).replace("_"," "),(32,47),.82)
                draw_label(labelled,f"l {np.rad2deg(mean_lon)%360:06.2f}   b {np.rad2deg(lat.mean()):+.2f}",
                           (33,70),.44,(177,190,202))
                if detailed:
                    draw_label(labelled,credit,(32,HEIGHT-25),.5)
                draw_label(labelled,"ESO/S. Brunier",(WIDTH-163,HEIGHT-25),.5)
                scene = cv2.addWeighted(labelled,opacity,scene,1-opacity,0)
            process.stdin.write(scene.tobytes())
        process.stdin.close()
        if process.wait(timeout=60):
            raise RuntimeError("journey_failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stderr.close()


def movie(store, record, field):
    from .survey import survey_for
    survey = survey_for(field)
    digest = hashlib.sha256(json.dumps(["atlas-v8-surroundings",survey,record.get("sha256",{}).get("final"),field],
                                       sort_keys=True).encode()).hexdigest()[:20]
    folder = store.path(f"objects/{record.get('storage_id', record['id'])}/journeys")
    if record.get("storage_id", record["id"]) != record["id"]:
        digest += "-" + record["id"]
    target = folder / f"{digest}.mp4"
    if target.is_file():
        return target
    with RENDER_LOCK:
        if target.is_file():
            return target
        fallback = target.with_suffix(".overview.mp4")
        if fallback.is_file() and time.time()-fallback.stat().st_mtime < 3600:
            return fallback
        from .survey import detail_plates
        meridian, points, _, _ = field_projection(field)
        plates = detail_plates(store, points.mean(axis=0), meridian, np.ptp(points,axis=0), survey)
        folder.mkdir(parents=True,exist_ok=True)
        temp = folder / f"{uuid.uuid4().hex}.part.mp4"
        try:
            render_journey(store,record,field,temp,plates)
            output = target if len(plates)==2 else fallback
            os.replace(temp,output)
            return output
        finally:
            temp.unlink(missing_ok=True)
