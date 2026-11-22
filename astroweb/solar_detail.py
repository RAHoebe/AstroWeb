"""Flights from a user's capture into credited spacecraft observations."""
import hashlib
import threading
import uuid

import cv2
import numpy as np
from . import external_http

from .hubble import HEIGHT, WIDTH, encode
from .journey import smooth, disk_in_photo
from .camera import FocusZoom

LOCK = threading.Lock()
CASSINI = "NASA/JPL/Space Science Institute"
SATURN_OVERVIEW = "PIA11141"
SATURN_RINGS = "PIA11657"
ENCELADUS = "PIA11688"
# Relative coordinates measured on the PIA11141 Cassini mosaic.
SATURN_DISK_CENTER = (.504,.507)
SATURN_RING_SPAN = .848
SATURN_RING_FOCUS = (.84,.494)
SATURN_SOURCES = {
    SATURN_OVERVIEW: "https://science.nasa.gov/resource/saturn-four-years-on/",
    SATURN_RINGS: "https://science.nasa.gov/photojournal/mimas-and-the-great-division/",
    ENCELADUS: "https://science.nasa.gov/resource/bursting-at-the-seams/",
}

# The focus is measured on the published mission image, never on the upload.
FEATURES = {
    "SUN": [
        ("NHQ202404080107","orig.jpg","Protuberans aan de zonsrand · eclips van 8 april 2024","Solar limb prominence · eclipse of 8 April 2024","NASA / Keegan Barber",.214,.835)],
    "MERCURY":[("PIA12034","orig.jpg","Drie inslagkraters in Caloris","Three impact craters in Caloris","NASA/JHUAPL/Carnegie Institution of Washington",.55,.52)],
    "VENUS":[("PIA23791","orig.jpg","Wolkenbanden in ultraviolet","Cloud bands in ultraviolet","Mariner 10 · NASA/JPL-Caltech",.73,.50)],
    "MARS":[("PIA01167","large.jpg","Gesteentelagen in Valles Marineris","Rock layers in Valles Marineris","NASA/JPL/Malin Space Science Systems",.83,.52)],
    "JUPITER":[("PIA21395","medium.jpg","De Grote Rode Vlek","The Great Red Spot","NASA/JPL-Caltech/SwRI/MSSS · Kevin M. Gill (CC BY)",.62,.5),
               ("PIA00294","orig.jpg","Het gebarsten ijs van Europa","The fractured ice of Europa","Galileo · NASA/JPL",.52,.51)],
    "SATURN":[(SATURN_OVERVIEW,"orig.jpg","Saturnus en zijn ringen","Saturn and its rings",CASSINI,*SATURN_RING_FOCUS),
              (SATURN_RINGS,"orig.jpg","De Cassinischeiding en de schaduw van Mimas","Cassini Division and the shadow of Mimas",CASSINI,.64,.49),
              ("PIA11688","orig.jpg","IJsfonteinen op Enceladus","Ice plumes on Enceladus",CASSINI,.53,.65)],
    "URANUS":[("PIA18185","orig.jpg","Het ijslandschap van Miranda","The icy terrain of Miranda","Voyager 2 · NASA/JPL-Caltech",.54,.62)],
    "NEPTUNE":[("PIA00052","orig.jpg","De Grote Donkere Vlek in 1989","The Great Dark Spot in 1989","Voyager 2 · NASA/JPL",.50,.49)],
}


def options(body):
    if body == "MOON":
        from .lunar_detail import options as lunar_options
        return lunar_options()
    results = []
    for ident, _, nl, en, credit, _, _ in FEATURES.get(body, []):
        result = {"id":ident,"name":{"nl":nl,"en":en},"credit":credit,
                  "source":SATURN_SOURCES.get(ident,"https://images.nasa.gov/details/"+ident)}
        if ident in (SATURN_OVERVIEW,SATURN_RINGS):
            result["alignment"] = "saturn-ring-axis"
        elif ident==ENCELADUS:
            result["alignment"] = "separate-moon"
        results.append(result)
    return results


def mission_image(store, ident, file):
    path = store.path(f"survey-cache/solar-system/{ident}-{file}")
    if path.is_file():
        cached = cv2.imread(str(path))
        if cached is not None:
            return cached
    url = f"https://images-assets.nasa.gov/image/{ident}/{ident}~{file}"
    reply = external_http.get(url, timeout=(5, 25))
    reply.raise_for_status()
    image = cv2.imdecode(np.frombuffer(reply.content, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("solarDetailUnavailable")
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix(".part")
    try:
        tmp.write_bytes(reply.content)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return image


def view(image, focus, amount, keep_edges=False):
    h,w=image.shape[:2]
    scale=min(WIDTH/w,HEIGHT/h)*(1+amount)
    cx=(.5+(focus[0]-.5)*min(1,amount/.6))*w
    cy=(.5+(focus[1]-.5)*min(1,amount/.6))*h
    if keep_edges:
        half_w,half_h=WIDTH/(2*scale),HEIGHT/(2*scale)
        cx=w/2 if 2*half_w>=w else np.clip(cx,half_w,w-half_w)
        cy=h/2 if 2*half_h>=h else np.clip(cy,half_h,h-half_h)
    matrix=np.float32([[scale,0,WIDTH/2-scale*cx],[0,scale,HEIGHT/2-scale*cy]])
    return cv2.warpAffine(image,matrix,(WIDTH,HEIGHT),flags=cv2.INTER_LINEAR)


def frames(photo, image, focus, keep_edges=False):
    for i in range(288):
        t=i/287
        fade=smooth((t-.22)/.23)
        if fade<1:
            source=view(photo,(.5,.5),.16*smooth(t/.45))
        if fade>0:
            destination=view(image,focus,(1.5 if keep_edges else .6)*smooth((t-.40)/.52),keep_edges)
        if fade<=0:
            yield source
        elif fade>=1:
            yield destination
        else:
            yield cv2.addWeighted(source,1-fade,destination,fade,0)


def saturn_ring_geometry(photo):
    """Measure the centre, major axis and span of Saturn's visible silhouette."""
    gray = cv2.cvtColor(photo,cv2.COLOR_BGR2GRAY)
    peak = int(gray.max())
    if peak < 30:
        return None
    count,labels,stats,_ = cv2.connectedComponentsWithStats(np.uint8(gray > .18*peak))
    if count < 2:
        return None
    component = 1+int(stats[1:,cv2.CC_STAT_AREA].argmax())
    x,y,w,h,area = stats[component]
    if area < 25 or min(x,y) < 2 or x+w > gray.shape[1]-2 or y+h > gray.shape[0]-2:
        return None
    points = np.column_stack(np.where(labels==component))[:,::-1]
    values,vectors = np.linalg.eigh(np.cov(points.T))
    if values[0] <= 0 or values[1] < 1.65*values[0]:
        return None
    axis = vectors[:,1]
    if axis[0] < 0:
        axis = -axis
    span = np.ptp(points@axis)
    weights = np.maximum(0,gray[labels==component].astype(float)-.55*peak)
    center = np.average(points,axis=0,weights=weights) if weights.sum() else points.mean(axis=0)
    return center,axis,span,points


def saturn_ring_point(photo):
    """Find a visible ring wing using the same axis as the detail journey."""
    geometry = saturn_ring_geometry(photo)
    if geometry is None:
        return None
    center,axis,span,points = geometry
    distances = points-center
    across = np.array([-axis[1],axis[0]])
    along = distances@axis
    heights = distances@across
    wing_fraction = (SATURN_RING_FOCUS[0]-SATURN_DISK_CENTER[0])/SATURN_RING_SPAN
    # A broad disk flanked by two thinner wings is required. This avoids
    # marking a plain elongated disk or a line from a blurred exposure.
    sections = [heights[np.abs(along-span*f)<.045*span] for f in (0,-wing_fraction,wing_fraction)]
    if any(len(section)<5 for section in sections):
        return None
    widths = [np.ptp(np.quantile(section,[.1,.9])) for section in sections]
    if widths[0] < .27*span or max(widths[1:]) > .58*widths[0]:
        return None
    point = center+wing_fraction*span*axis+np.median(sections[2])*across
    # Choose an actual illuminated pixel on that ring wing.
    closest = points[np.argmin(np.sum((points-point)**2,axis=1))]
    return (closest+.5)/np.array(photo.shape[1::-1])


def saturn_registration(photo, overview):
    """Fit the measured silhouette against the Cassini mosaic's ring axis."""
    geometry = saturn_ring_geometry(photo)
    if geometry is None:
        return None
    center,axis,span,_ = geometry
    height,width = overview.shape[:2]
    scale = span/(SATURN_RING_SPAN*width)
    transform = np.eye(3)
    transform[:2,:2] = scale*np.column_stack((axis,[-axis[1],axis[0]]))
    transform[:2,2] = center-transform[:2,:2]@(np.array(SATURN_DISK_CENTER)*[width,height])
    return transform


def moon_cut_frames(photo, image, focus):
    """Dissolve through space into a different body which is unresolved in the capture."""
    for i in range(288):
        phase = i/287
        if phase < .38:
            scene = view(photo,(.5,.5),.3*smooth(phase/.38))
            gain = 1-smooth((phase-.21)/.17)
        else:
            scene = view(image,focus,.6*smooth((phase-.38)/.54))
            gain = smooth((phase-.38)/.21)
        yield cv2.convertScaleAbs(scene,alpha=gain)


def saturn_frames(photo, overview, detail=None, focus=None):
    registration = saturn_registration(photo,overview)
    if registration is None:
        yield from frames(photo,detail if detail is not None else overview,focus or SATURN_RING_FOCUS)
        return
    start = min(WIDTH/photo.shape[1],HEIGHT/photo.shape[0])
    target = np.array(SATURN_RING_FOCUS)*[overview.shape[1],overview.shape[0]]
    wing = registration@np.r_[target,1.]
    camera = FocusZoom(np.array(photo.shape[1::-1])/2,wing[:2],start,start*(8 if detail is not None else 5),WIDTH,HEIGHT)
    if detail is not None:
        height,width = detail.shape[:2]
        target = np.array(focus)*[width,height]
        margin = np.minimum(target,[width,height]-target)
        cover = max(WIDTH/(2*margin[0]),HEIGHT/(2*margin[1]))
        closeup = FocusZoom(target,target,cover,cover*1.24,WIDTH,HEIGHT)
    for i in range(336):
        phase = i/335
        _,cam = camera.at(smooth((phase-.05)/(.69 if detail is not None else .85)))
        fade = smooth((phase-.22)/.24)
        archive_fade = smooth((phase-.64)/.17) if detail is not None else 0.
        if archive_fade<1:
            if fade<1:
                original = cv2.warpPerspective(photo,cam,(WIDTH,HEIGHT))
            if fade>0:
                wide = cv2.warpPerspective(overview,cam@registration,(WIDTH,HEIGHT))
            scene = (original if fade<=0 else wide if fade>=1 else
                     cv2.addWeighted(original,1-fade,wide,fade,0))
        if archive_fade>0:
            _,cam_close = closeup.at(smooth((phase-.63)/.31))
            archive = cv2.warpPerspective(detail,cam_close,(WIDTH,HEIGHT))
            scene = archive if archive_fade>=1 else cv2.addWeighted(scene,1-archive_fade,archive,archive_fade,0)
        yield scene


def limb_circle(image):
    """Fit the visible lunar/solar limb even when most of the disk is cropped."""
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);h,w=gray.shape
    candidates=[]
    for threshold in (6,10,16,24,32):
        contours,_=cv2.findContours(np.uint8(gray<threshold)*255,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
        if not contours:continue
        points=max(contours,key=cv2.contourArea).reshape(-1,2).astype(float)
        points=points[(points[:,0]>2)&(points[:,0]<w-3)&(points[:,1]>2)&(points[:,1]<h-3)]
        if len(points)<50:continue
        if len(points)>3000:points=points[::max(1,len(points)//3000)]
        good=np.ones(len(points),bool)
        for _ in range(5):
            p=points[good];x,y=p.T
            values=np.linalg.lstsq(np.c_[2*x,2*y,np.ones(len(p))],x*x+y*y,rcond=None)[0]
            center=values[:2];radius=np.sqrt(max(0,values[2]+center@center))
            residual=np.abs(np.linalg.norm(points-center,axis=1)-radius)
            good=residual<max(2.,3*np.median(residual))
        error=float(np.median(residual[good]))
        if radius>min(w,h)*.2 and good.sum()>50 and error<3:
            candidates.append((error,center,float(radius)))
    if not candidates:raise ValueError('solarDetailMissing')
    _,center,radius=min(candidates,key=lambda v:v[0])
    # Align luminous limb to luminous limb, rather than the inner threshold
    # contour of the dark lunar disk. The visible edge is slightly farther out.
    theta=np.linspace(0,2*np.pi,720,endpoint=False);radii=np.linspace(radius-15,radius+15,241)
    xx=(center[0]+np.cos(theta)[:,None]*radii).astype(np.float32);yy=(center[1]+np.sin(theta)[:,None]*radii).astype(np.float32)
    valid=(xx.min(axis=1)>2)&(xx.max(axis=1)<w-3)&(yy.min(axis=1)>2)&(yy.max(axis=1)<h-3)
    profiles=cv2.remap(cv2.GaussianBlur(gray.astype(np.float32),(0,0),.6),xx,yy,cv2.INTER_LINEAR)
    gradient=np.gradient(profiles,radii,axis=1);indices=gradient.argmax(axis=1)
    accepted=valid&(gradient[np.arange(len(theta)),indices]>2)
    if accepted.sum()>50:radius=float(np.median(radii[indices[accepted]]))
    return center,radius


def limb_registration(photo,image):
    source,radius=disk_in_photo(photo)
    if not radius:raise ValueError('solarDetailMissing')
    # Otsu is a useful disk locator, but limb darkening makes that mask too
    # small. Fit the strongest outward intensity gradient for the true edge.
    gray=cv2.GaussianBlur(cv2.cvtColor(photo,cv2.COLOR_BGR2GRAY).astype(np.float32),(0,0),.7)
    angles=np.linspace(0,2*np.pi,720,endpoint=False);radii=np.linspace(.9*radius,1.1*radius,201)
    xx=(source[0]+np.cos(angles)[:,None]*radii).astype(np.float32)
    yy=(source[1]+np.sin(angles)[:,None]*radii).astype(np.float32)
    profiles=cv2.remap(gray,xx,yy,cv2.INTER_LINEAR)
    edge=radii[np.argmax(-np.gradient(profiles,axis=1),axis=1)]
    points=np.float32(np.c_[source[0]+np.cos(angles)*edge,source[1]+np.sin(angles)*edge])
    center,axes,angle=cv2.fitEllipse(points[:,None])
    source=np.asarray(center);axes=np.asarray(axes)/2
    destination,other=limb_circle(image)
    theta=np.deg2rad(angle);rotation=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    linear=rotation@np.diag(other/axes)@rotation.T
    ratio=float(np.sqrt(np.linalg.det(linear)))
    matrix=np.eye(3);matrix[:2,:2]=linear;matrix[:2,2]=destination-linear@source
    return matrix,destination,ratio


def aligned_limb_frames(photo,image,focus):
    registration,origin,ratio=limb_registration(photo,image)
    h,w=image.shape[:2];target=np.array(focus)*[w,h]
    start=min(WIDTH/photo.shape[1],HEIGHT/photo.shape[0])/ratio
    margin=np.maximum(1,np.minimum(target,[w,h]-target))
    end=max(start*4,1.06*max(WIDTH/(2*margin[0]),HEIGHT/(2*margin[1])))
    camera=FocusZoom(origin,target,start,end,WIDTH,HEIGHT)
    yy,xx=np.ogrid[:h,:w]
    edge=np.minimum(np.minimum(yy,h-1-yy),np.minimum(xx,w-1-xx))
    mask=np.uint8(255*np.clip(edge/35,0,1))
    for i in range(288):
        phase=i/287;_,cam=camera.at(smooth((phase-.08)/.85))
        source=cv2.warpPerspective(photo,cam@registration,(WIDTH,HEIGHT))
        fade=smooth((phase-.25)/.5)
        if fade<=0:yield source;continue
        dest=cv2.warpPerspective(image,cam,(WIDTH,HEIGHT))
        alpha=cv2.warpPerspective(mask,cam,(WIDTH,HEIGHT)).astype(np.float32)*(fade/255)
        # Fade the full photosphere uniformly. A spatially varying source
        # weight would imprint the rectangular boundary of this cropped image.
        blended=source.astype(np.float32)*(1-fade)+dest.astype(np.float32)*alpha[:,:,None]
        yield np.uint8(np.clip(blended,0,255))


def movie_spec(store,record,ident):
    lunar = record.get("body") == "MOON"
    saturn = record.get("body") == "SATURN" and ident in (SATURN_OVERVIEW,SATURN_RINGS)
    if lunar:
        from . import lunar_detail
        from .collection import capture_date
        if ident not in lunar_detail.SITES:
            raise ValueError("solarDetailMissing")
        item = lunar_detail.SITES[ident]
        signature = (lunar_detail.VERSION,item,record["sha256"]["final"],capture_date(record))
    else:
        item=next((f for f in FEATURES.get(record.get("body"),[]) if f[0]==ident),None)
        if not item:
            raise ValueError("solarDetailMissing")
        version = ("saturn-rings-v1" if saturn else "limb-registered-v6" if ident=="NHQ202404080107"
                   else "separate-moon-v1" if ident==ENCELADUS else "solar-tour-v1")
        signature = (version,item,record["sha256"]["final"])
    key=hashlib.sha256(str(signature).encode()).hexdigest()[:20]
    folder=store.path(f"objects/{record.get('storage_id',record['id'])}/solar-system")
    return folder/(key+".mp4"), item


def missing_destinations(store, record):
    ids = [item["id"] for item in options(record.get("body"))]
    missing = [ident for ident in ids if not movie_spec(store,record,ident)[0].is_file()]
    if missing and record.get("body") == "MOON":
        from .surface_labels import lunar_points
        visible = {point["journey"] for point in lunar_points(store,record)}
        missing = [ident for ident in missing if ident in visible]
    return missing


def movie(store,record,ident):
    output,item = movie_spec(store,record,ident)
    # Only complete, atomically renamed MP4s are visible at this path.
    if output.is_file():
        return output
    lunar = record.get("body") == "MOON"
    saturn = record.get("body") == "SATURN" and ident in (SATURN_OVERVIEW,SATURN_RINGS)
    limb = ident == "NHQ202404080107"
    if lunar:
        from . import lunar_detail
        credit = lunar_detail.CREDIT
    else:
        _,file,_,_,credit,x,y = item
    folder = output.parent
    with LOCK:
        if not output.is_file():
            if not lunar:
                image=mission_image(store,ident,file)
            photo=cv2.imread(str(store.path(record["poster"])))
            if photo is None:
                raise ValueError("invalid_image")
            folder.mkdir(parents=True,exist_ok=True)
            tmp=folder/(uuid.uuid4().hex+".part.mp4")
            try:
                if saturn:
                    overview = image if ident==SATURN_OVERVIEW else mission_image(store,SATURN_OVERVIEW,"orig.jpg")
                sequence=(lunar_detail.sequence(store,record,ident,photo,WIDTH,HEIGHT) if lunar else
                          saturn_frames(photo,overview,image if ident==SATURN_RINGS else None,(x,y)) if saturn else
                          moon_cut_frames(photo,image,(x,y)) if ident==ENCELADUS else
                          aligned_limb_frames(photo,image,(x,y)) if limb and disk_in_photo(photo)[1] is not None else frames(photo,image,(x,y),keep_edges=limb))
                encode(sequence,credit.replace(" · "," / "),tmp)
                tmp.replace(output)
            finally:
                tmp.unlink(missing_ok=True)
    return output
