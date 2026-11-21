"""Find optical HST archive pointings inside the registered capture, and verify FITS WCS."""
import csv
import hashlib
import io
import json
import re
import time
import uuid

import cv2
import numpy as np
import requests
from . import external_http
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS

from .discovery import project
from .journey import geometry
from .galaxy import key, target_entry
from .catalogue import canonical

TAP="https://hst.esac.esa.int/tap-server/tap/sync"
CUTOUT="https://hla.stsci.edu/cgi-bin/fitscut.cgi"
FIELD_ID=re.compile(r"(hst_\d{5}_[a-z0-9]+_(?:wfpc2|wfc3|acs)_[a-z0-9_]*?f(\d{3})([nmw])(?:_[a-z0-9]+)*)$")
SIZE=1800


# Archive target designations associated with documented portions of these
# extended objects. Unrelated objects and untargeted parallels remain field-only.
REGIONS = {
    "NGC7000": ("V1057-CYG","V1057 CYG","CYGNUS WALL","LDN 935"),
    "NGC6992": ("CYGLOOP-NENR","CYGLOOP-NENR1","CYGLOOP-NENR2","NGC6995-A","CYGLOOP-SE-CLOUD","CYGLOOP-SE-CLOUD-TWEAK"),
    "IC1396": ("IC1396A","IC 1396A","IC1396-TAIL","ELEPHANT TRUNK","TRUMPLER 37","TR37","HD206267","HD-206267"),
}


def field_relation(record, name):
    designation = key(canonical(record["metadata"]["target"]))
    known = target_entry(designation)
    aliases = {designation}
    if known:
        aliases.update(key(v) for v in (known["id"], *known.get("aliases", []), known["en"], known["nl"]))
    archive = key(name or "")
    if not archive or archive in {"ANY","NONE","PAR","PARALLEL"}:
        return "field"
    if archive in aliases:
        return "target"
    # A numbered galaxy ID should not match another galaxy (M1 vs M101).
    if any(archive == key(region) for a in aliases for region in REGIONS.get(a, ())):
        return "region"
    return "field"


def inside_capture(uv):
    return uv is not None and np.isfinite(uv).all() and np.all((uv >= 0) & (uv <= 1))


def cutout_contains(store, entry, ra, dec):
    """Check a feature against the already verified FITS, without a download."""
    ident = entry.get("id","")
    if not entry.get("full_footprint") or not FIELD_ID.fullmatch(ident):
        return False
    path = store.path(f"survey-cache/hst-archive/{ident}.fits")
    if not path.is_file():
        return False
    try:
        with fits.open(path,memmap=True) as hdus:
            data = hdus[0].data
            if data.shape!=(SIZE,SIZE):
                return False
            x,y = WCS(hdus[0].header).celestial.world_to_pixel(SkyCoord(ra,dec,unit="deg"))
            if not (np.isfinite(x) and np.isfinite(y) and 1<=x<SIZE-2 and 1<=y<SIZE-2):
                return False
            val = data[round(float(y)),round(float(x))]
            return bool(np.isfinite(val) and val!=0)
    except (OSError,ValueError,TypeError):
        return False


def registered_cutout(store,record,entry):
    folder=store.path("survey-cache/hst-archive")
    folder.mkdir(parents=True,exist_ok=True)
    ident=entry["id"]
    path=folder/f"{ident}.fits"
    if not path.exists():
        r=external_http.get(CUTOUT,params={"red":ident,"format":"fits","size":SIZE,
                                     "RA":entry["ra"],"DEC":entry["dec"]},timeout=(5,35))
        r.raise_for_status()
        if len(r.content)>20*1024**2 or not r.content.startswith(b"SIMPLE"):
            raise ValueError("hubble_no_field")
        with fits.open(io.BytesIO(r.content)) as hdus:
            if hdus[0].data.shape!=(SIZE,SIZE):raise ValueError("hubble_no_field")
        tmp=path.with_suffix("."+uuid.uuid4().hex+".tmp")
        try:
            tmp.write_bytes(r.content);tmp.replace(path)
        finally:tmp.unlink(missing_ok=True)
    with fits.open(path) as hdus:
        data=np.flipud(hdus[0].data).astype(np.float32)
        wcs=WCS(hdus[0].header).celestial
    valid=np.isfinite(data)&(data!=0)
    if valid.mean()<.075 or wcs.pixel_n_dim!=2:raise ValueError("hubble_no_field")
    src=np.float32([[0,0],[SIZE-1,0],[SIZE-1,SIZE-1],[0,SIZE-1]])
    sky=wcs.pixel_to_world(src[:,0],SIZE-1-src[:,1])
    _,uv=project(store,record,sky)
    if uv is None or not np.isfinite(uv).all():
        raise ValueError("hubble_no_field")
    if entry.get("full_footprint"):
        # Test outer pixel edges, not just the centre or the exposed overlap.
        edges = np.float64([[-.5,-.5],[SIZE-.5,-.5],[SIZE-.5,SIZE-.5],[-.5,SIZE-.5]])
        _, boundary = project(store,record,wcs.pixel_to_world(edges[:,0],SIZE-1-edges[:,1]))
        if not inside_capture(boundary):
            raise ValueError("hubble_no_field")
    matrix=cv2.getPerspectiveTransform(src,np.float32(uv*[record["width"],record["height"]]-.5))
    # Restrict the field to the overlap in detector coordinates. Corners of
    # the cutout can fall outside the uploaded image even on a real target.
    cap=np.float32([[0,0],[record["width"]-1,0],[record["width"]-1,record["height"]-1],[0,record["height"]-1]])
    try:
        footprint=cv2.perspectiveTransform(cap[None],np.linalg.inv(matrix))[0]
    except np.linalg.LinAlgError:
        raise ValueError("hubble_no_field") from None
    if not np.isfinite(footprint).all():raise ValueError("hubble_no_field")
    overlap=np.zeros(data.shape,np.uint8)
    cv2.fillConvexPoly(overlap,np.int32(np.clip(np.rint(footprint),-1e6,1e6)),1)
    exposed_overlap = valid & overlap.astype(bool)
    if exposed_overlap.mean()<.075:raise ValueError("hubble_no_field")
    # Stay clear of unexposed WFPC2 chip gaps, choosing an interior location
    # with both good coverage and some structure rather than the centre of a gap.
    coarse=cv2.resize(exposed_overlap.astype(np.float32),(180,180),interpolation=cv2.INTER_AREA)
    padded=np.pad((coarse>.8).astype(np.uint8),1)
    interior=cv2.distanceTransform(padded,cv2.DIST_L2,5)[1:-1,1:-1]
    safe=interior >= min(36,interior.max()*.85)
    if interior.max()<14:raise ValueError("hubble_no_field")
    # Rank coherent structures at a coarser scale to suppress detector noise
    # and isolated hot pixels. Only consider adequately exposed chip interiors.
    low,high=np.percentile(data[valid],[15,99])
    bounded=np.clip(np.nan_to_num(data),low,high)
    thumb=cv2.resize(bounded,(180,180),interpolation=cv2.INTER_AREA)
    smoothed=cv2.GaussianBlur(cv2.medianBlur(thumb.astype(np.float32),5),(0,0),1)
    detail=cv2.GaussianBlur(np.abs(smoothed-cv2.GaussianBlur(smoothed,(0,0),5)),(0,0),7)
    y,x=np.unravel_index(np.argmax(np.where(safe,detail,-1)),interior.shape)
    center=(x*10+5,y*10+5)
    lo,hi=np.percentile(data[valid],[15,99.5])
    if hi<=lo:raise ValueError("hubble_no_field")
    signal=cv2.GaussianBlur(np.nan_to_num(data),(0,0),.7)
    stretch=np.arcsinh(5*np.clip((signal-lo)/(hi-lo),0,1))/np.arcsinh(5)
    img=np.uint8(6+249*stretch)
    img[~valid]=0
    return cv2.cvtColor(img,cv2.COLOR_GRAY2BGR),matrix,center


def find_fields(store,record):
    field=geometry(store,record)
    if "corners" not in field:return []
    token=hashlib.sha256(json.dumps(["features-v3",record["metadata"]["target"],field["corners"]]).encode()).hexdigest()[:20]
    cache=store.path(f"survey-cache/hst-archive/fields-{token}.json")
    if cache.exists():
        saved=json.loads(cache.read_text(encoding="utf8"))
        if saved or time.time()-cache.stat().st_mtime<86400:return saved
    sky=SkyCoord(*np.array(field["corners"]).T,unit="deg")
    c=SkyCoord(sky.cartesian.mean(),frame="icrs")
    ra,dec=c.spherical.lon.deg,c.spherical.lat.deg
    radius=c.separation(sky).deg.max()+.10
    query=(f"SELECT TOP 180 obs_id,target_name,s_ra,s_dec,t_exptime FROM ivoa.ObsCore WHERE "
           f"1=CONTAINS(POINT('ICRS',s_ra,s_dec),CIRCLE('ICRS',{ra:.7f},{dec:.7f},{radius:.7f})) "
           "AND dataproduct_type='image' AND calib_level=3 AND em_min>3.5e-7 AND em_max<1.05e-6 "
           "AND s_xel1>350 AND s_xel2>350 AND obs_id LIKE 'hst_%' ORDER BY t_exptime DESC")
    designation=key(canonical(record["metadata"]["target"]))
    entry=target_entry(designation)
    terms={designation,record["metadata"]["target"].upper()}
    if entry:terms.update([entry["id"].upper(),*(a.upper() for a in entry.get("aliases",[]))])
    regions=set()
    for term in terms:
        regions.update(REGIONS.get(key(term),()))
    def target_sql(term):
        return "'"+term.replace("'","''")+"'"
    terms.update(term.replace(" ","-") for term in list(terms))
    terms.update(regions)
    clause=" AND target_name IN ("+",".join(target_sql(k) for k in sorted(terms))+")"
    def search(statement):
        r=external_http.get(TAP,params=dict(REQUEST="doQuery",LANG="ADQL",FORMAT="csv",QUERY=statement),timeout=(6,55))
        r.raise_for_status()
        reader=csv.DictReader(r.text.splitlines())
        if not reader.fieldnames or 'obs_id' not in reader.fieldnames:raise ValueError("hubble_unavailable")
        results=[]
        for row in reader:
            match=FIELD_ID.fullmatch(row["obs_id"])
            if match:
                results.append(dict(id=row["obs_id"],target=row["target_name"],filter="F"+match[2]+match[3].upper(),
                                    relation=field_relation(record,row["target_name"]),ra=float(row["s_ra"]),dec=float(row["s_dec"])))
        return results
    rows=search(query.replace(" ORDER BY",clause+" ORDER BY"))
    rows.extend(search(query))
    # Prefer intended extended targets, including a named planetary nebula in
    # projection. Anonymous parallels and isolated stars are poor destinations.
    rows=[e for e in {e["id"]:e for e in rows}.values()
          if e["relation"] != "field" or re.match(r"^(?:PN[- ]?G|NGC[- ]?\d|IC[- ]?\d|MESSIER[- ]?\d)",e["target"] or "",re.I)]
    rows=[e for e in rows if key(e["target"]) not in {"HD206267","V1057CYG"}]
    rows.sort(key=lambda e:({"target":0,"region":1,"field":2}[e["relation"]],
                             e["target"].upper() in {"ANY","NONE",""},len(e["id"].split("_")),e["id"].endswith("_pc")))
    if rows:
        _,pos=project(store,record,SkyCoord([e["ra"] for e in rows],[e["dec"] for e in rows],unit="deg"))
        if pos is None:return []
        rows=[e for e,p in zip(rows,pos) if np.all((p>-.08)&(p<1.08))]
    accepted=[];errors=[]
    for entry in rows[:16]:
        if any(abs(entry["ra"]-o["ra"])*np.cos(np.deg2rad(dec))<.035 and abs(entry["dec"]-o["dec"])<.035 for o in accepted):continue
        try:registered_cutout(store,record,entry)
        except requests.RequestException as exc:
            errors.append(exc);continue
        except (ValueError,OSError):continue
        accepted.append(entry)
        if len(accepted)==2:break
    if errors and not accepted:raise ValueError("hubble_unavailable")
    cache.parent.mkdir(parents=True,exist_ok=True)
    tmp=cache.with_suffix("."+uuid.uuid4().hex+".tmp")
    try:
        tmp.write_text(json.dumps(accepted),encoding="utf8");tmp.replace(cache)
    finally:tmp.unlink(missing_ok=True)
    return accepted
