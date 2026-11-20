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

TYPES = {"G":("Sterrenstelsel","Galaxy"), "GPair":("Stelselpaar","Galaxy pair"),
         "GTrpl":("Stelseltrio","Galaxy triplet"), "GGroup":("Groep sterrenstelsels","Galaxy group"),
         "GCl":("Bolhoop","Globular cluster"), "OCl":("Open sterrenhoop","Open cluster"),
         "Cl+N":("Sterrenhoop met nevel","Cluster with nebulosity"), "SNR":("Supernovarest","Supernova remnant"),
         "PN":("Planetaire nevel","Planetary nebula"), "HII":("H II-gebied","H II region"),
         "RfN":("Reflectienevel","Reflection nebula"), "Neb":("Nevel","Nebula"),
         "EmN":("Emissienevel","Emission nebula"), "DrkN":("Donkerwolk","Dark nebula"),
         "*Ass":("Sterassociatie","Stellar association"), "*":("Ster","Star"), "**":("Dubbelster","Double star")}
LOCAL_TYPES = {"IC 1396A":"DrkN","Trumpler 37":"OCl","HD 206267":"*","Sh2-129":"HII",
               "Barnard 352":"DrkN","LDN 935":"DrkN","52 Cyg":"*"}


@lru_cache(maxsize=1)
def entries():
    fields, _ = field_catalog()
    rows = list(landmarks()) + [{"id":v[0],"ra":v[1],"dec":v[2],"type":v[3],"nl":v[0],"en":v[0]} for v in fields]
    return rows, SkyCoord([v["ra"] for v in rows]*u.deg,[v["dec"] for v in rows]*u.deg)


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


def discover(store, record):
    if record.get("body"):
        from .surface_labels import discover as surface_discovery
        return surface_discovery(store,record)
    rows,sky = entries()
    kind,xy = project(store,record,sky)
    objects = []
    if xy is not None:
        for i in np.flatnonzero(((xy>=0)&(xy<=1)).all(axis=1)):
            row = rows[i]
            seed = known_target(row["id"])
            code = row.get("type") or {"S":"*","H":"GCl"}.get(row.get("src")) or LOCAL_TYPES.get(row["id"])
            nl,en = TYPES.get(code,("Catalogusobject","Catalogue object"))
            objects.append({"id":row["id"],"name":{"nl":row["nl"],"en":row["en"]},
                            "type":seed["type"] if seed else {"nl":nl,"en":en},
                            "summary":seed["summary"] if seed else None,
                            "ra":row["ra"],"dec":row["dec"],"aliases":row.get("aliases",[]),
                            "ly":row.get("ly"),"x":round(xy[i,0],8),"y":round(xy[i,1],8),
                            "source":"https://simbad.cds.unistra.fr/simbad/sim-id?Ident="+quote(row["id"])})
    return {"kind":kind,"objects":objects}
