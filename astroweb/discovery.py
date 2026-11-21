"""Project catalog centres onto the unchanged final raster, in display order."""
from functools import lru_cache
from urllib.parse import quote

import astropy.units as u
import cv2
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io.fits import Header
from astropy.wcs import WCS
from astropy.wcs.utils import skycoord_to_pixel

from .galaxy import landmarks, field_catalog
from .journey import SOLUTIONS, fits_registration
from .metadata import known_target
from .catalogue import canonical,name_key

TYPES = {"G":("Sterrenstelsel","Galaxy"), "GPair":("Stelselpaar","Galaxy pair"),
         "GTrpl":("Stelseltrio","Galaxy triplet"), "GGroup":("Groep sterrenstelsels","Galaxy group"),
         "GCl":("Bolhoop","Globular cluster"), "OCl":("Open sterrenhoop","Open cluster"),
         "Cl+N":("Sterrenhoop met nevel","Cluster with nebulosity"), "SNR":("Supernovarest","Supernova remnant"),
         "PN":("Planetaire nevel","Planetary nebula"), "HII":("H II-gebied","H II region"),
         "RfN":("Reflectienevel","Reflection nebula"), "Neb":("Nevel","Nebula"),
         "EmN":("Emissienevel","Emission nebula"), "DrkN":("Donkerwolk","Dark nebula"),
         "*Ass":("Sterassociatie","Stellar association"), "*":("Ster","Star"), "**":("Dubbelster","Double star")}
LOCAL_TYPES = {"IC 1396A":"DrkN","Trumpler 37":"OCl","HD 206267":"*","Sh2-129":"HII",
               "Barnard 352":"DrkN","LDN 935":"DrkN","52 Cyg":"*","NGC 1432":"RfN","NGC 1435":"RfN"}
PLEIADES_STARS = {"HIP 17702","HIP 17847","HIP 17499","HIP 17573","HIP 17608","HIP 17531","HIP 17851","HIP 17489","HIP 17579"}
MEROPE_NOTE = {"nl":"Merope verlicht de kleine reflectienevel IC 349. Op de Hubble-foto staat de ster net buiten het beeld.",
               "en":"Merope illuminates the small reflection nebula IC 349. The star is just outside the Hubble photograph."}


@lru_cache(maxsize=1)
def entries():
    fields, _ = field_catalog()
    rows = list(landmarks()) + [{"id":v[0],"ra":v[1],"dec":v[2],"type":v[3],"nl":v[0],"en":v[0]} for v in fields]
    return rows, SkyCoord([v["ra"] for v in rows]*u.deg,[v["dec"] for v in rows]*u.deg)


@lru_cache(maxsize=1)
def bright_stars():
    from .sky import star_catalog
    supported = sorted((s for s in star_catalog() if s["magnitude"]<=8),key=lambda s:s["magnitude"])
    rows = [dict(id=f"HIP {s['hip']}",ra=s["ra"],dec=s["dec"],type="*",
                 nl=s["name"] or f"HIP {s['hip']}",en=s["name"] or f"HIP {s['hip']}") for s in supported]
    return rows,SkyCoord([v["ra"] for v in rows],[v["dec"] for v in rows],unit="deg")


def in_frame(store,record,rows,sky):
    _,points = project(store,record,sky)
    if points is not None:
        for i in np.flatnonzero(((points>=0)&(points<=1)).all(axis=1)):
            yield rows[i],points[i]


def add_catalogue_points(store,record,objects,search):
    from .guide_catalogue import rows as simbad_rows
    remote,status = simbad_rows(store,record,search)
    known = {name_key(canonical(o["id"])) for o in objects}
    # Keep existing named labels. A second catalogue identifier for the same
    # point should not create an overlapping button.
    positions = [(o["ra"],o["dec"]) for o in objects]
    extra = []
    if remote:
        coords = SkyCoord([r["ra"] for r in remote],[r["dec"] for r in remote],unit="deg")
        extra.extend(list(in_frame(store,record,remote,coords)))
    offline,sky = bright_stars()
    extra.extend(list(in_frame(store,record,offline,sky))[:50])
    added = 0
    for row,uv in extra:
        ident = name_key(canonical(row["id"]))
        if ident in known:
            continue
        ra,dec = float(row["ra"]),float(row["dec"])
        cos_dec = np.cos(np.deg2rad(dec))
        if any((((ra-a+180)%360-180)*cos_dec)**2+(dec-b)**2<(5/3600)**2 for a,b in positions):
            continue
        nl,en = TYPES[row["type"]]
        objects.append({"id":row["id"],"name":{"nl":row["nl"],"en":row["en"]},"type":{"nl":nl,"en":en},
                        "summary":None,"ra":ra,"dec":dec,"aliases":[],"ly":None,
                        "x":round(float(uv[0]),8),"y":round(float(uv[1]),8),
                        "source":"https://simbad.cds.unistra.fr/simbad/sim-id?Ident="+quote(row["id"])})
        known.add(ident)
        positions.append((ra,dec))
        added += 1
        if added>=36:
            break
    return status


def attach_journeys(store,record,objects):
    from .hubble import fields
    from .hst_archive import cutout_contains
    try:
        options = fields(store,record,local_only=True)
    except ValueError:
        return
    for point in objects:
        if point.get("journey"):
            continue
        names = {name_key(canonical(alias)) for alias in [point["id"],*point["aliases"]]}
        for option in options:
            if name_key(canonical(option.get("target",""))) not in names:
                continue
            if cutout_contains(store,option,point["ra"],point["dec"]):
                point["journey"] = option["id"]
                break


def project(store, record, sky):
    width,height = record["width"],record["height"]
    digest = record.get("sha256",{}).get("final")
    solved = record.get("gaia") or {}
    if solved.get("status") != "solved" or solved.get("digest") != digest:
        solved = SOLUTIONS.get(digest) or {}
    wcs = None
    fx = fy = 1
    kind = "gaia"
    if solved.get("wcs_header"):
        wcs = WCS(Header.fromstring(solved["wcs_header"],sep="\n"))
    elif solved.get("corners"):
        # Existing Gaia TAN fits saved only their corners. Between two tangent
        # planes the mapping is a homography, including rotation and reflection.
        corners = SkyCoord(*np.array(solved["corners"]).T,unit="deg")
        center = SkyCoord(corners.cartesian.mean(),frame="icrs").icrs
        frame = center.skyoffset_frame()
        def tangent(coords):
            vectors = coords.transform_to(frame).cartesian.xyz.value
            return (vectors[1:]/vectors[0]).T
        transform = cv2.getPerspectiveTransform(np.float32(tangent(corners)),
                                                np.float32([[0,0],[1,0],[1,1],[0,1]]))
        near = center.separation(sky) <= 1.1*center.separation(corners).max()
        xy = np.full((len(sky),2), np.nan)
        if near.any():
            xy[near] = cv2.perspectiveTransform(tangent(sky[near]).astype(float)[None],transform)[0]
        return kind,xy
    elif record.get("fits"):
        reg = fits_registration(store.path(record["fits"]),store.path(record["poster"]),width,height)
        if reg:
            wcs,fx,fy = reg
            kind = "wcs"
    if wcs is None:
        return "missing",None
    center = wcs.pixel_to_world((width-1)/2,(height-1)/2).icrs
    corners = wcs.pixel_to_world([-.5,width-.5,width-.5,-.5],[-.5,-.5,height-.5,height-.5]).icrs
    near = center.separation(sky) <= 1.1*center.separation(corners).max()
    xy = np.full((len(sky),2),np.nan)
    if near.any():
        x,y = skycoord_to_pixel(sky[near],wcs,origin=0)
        xy[near,0] = ((x if fx==1 else width-1-x)+.5)/width
        xy[near,1] = ((y if fy==1 else height-1-y)+.5)/height
    return kind,xy


def discover(store, record, *, search=False, links=True):
    if record.get("body"):
        from .surface_labels import discover as surface_discovery
        return surface_discovery(store,record)
    rows,sky = entries()
    kind,xy = project(store,record,sky)
    objects = []
    from . import skymap
    pleiades = canonical((record.get("metadata") or {}).get("target") or record.get("id",""))=="M_45"
    journey = skymap.merope_journey(store,record) if pleiades and xy is not None and store is not None else None
    if xy is not None:
        for i in np.flatnonzero(((xy>=0)&(xy<=1)).all(axis=1)):
            row = rows[i]
            seed = known_target(row["id"])
            code = LOCAL_TYPES.get(row["id"]) or row.get("type") or {"S":"*","H":"GCl"}.get(row.get("src"))
            nl,en = TYPES.get(code,("Catalogusobject","Catalogue object"))
            item = {"id":row["id"],"name":{"nl":row["nl"],"en":row["en"]},
                            "type":seed["type"] if seed else {"nl":nl,"en":en},
                            "summary":seed["summary"] if seed else None,
                            "ra":row["ra"],"dec":row["dec"],"aliases":row.get("aliases",[]),
                            "ly":row.get("ly"),"x":round(xy[i,0],8),"y":round(xy[i,1],8),
                            "source":"https://simbad.cds.unistra.fr/simbad/sim-id?Ident="+quote(row["id"])}
            if pleiades and row["id"] in PLEIADES_STARS:
                item["label"] = True
            if pleiades and row["id"] in ("HIP 17608","IC 349"):
                item["summary"] = MEROPE_NOTE
                if journey:
                    item["journey"] = journey
            objects.append(item)
    result = {"kind":kind,"objects":objects}
    if xy is not None and store is not None and not record.get("capture_kind"):
        status = add_catalogue_points(store,record,objects,search)
        if links:
            attach_journeys(store,record,objects)
        if search:
            result["catalogue"] = status
    return result
