"""Feathered visual mosaics of unchanged captures using their real raster WCS."""
import math

import cv2
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io.fits import Header
from astropy.wcs import WCS
from astropy.wcs.utils import skycoord_to_pixel
from astropy.wcs.wcsapi import BaseLowLevelWCS, HighLevelWCSWrapper

from .collection import capture_date, date_order, identity
from .comparison import raster_sky
from .journey import geometry, fits_registration
from .render import read_rgb, resize_long


class RasterWCS(BaseLowLevelWCS):
    """Pixel-centre adapter retaining flips, RA wrap and the original distortion."""
    pixel_n_dim = 2
    world_n_dim = 2
    world_axis_physical_types = ["pos.eq.ra", "pos.eq.dec"]
    world_axis_units = ["deg", "deg"]
    world_axis_object_components = [("sky",0,"spherical.lon.degree"),("sky",1,"spherical.lat.degree")]
    world_axis_object_classes = {"sky":(SkyCoord,(),{"unit":"deg","frame":"icrs"})}

    def __init__(self, store, record, shape):
        self.store, self.record, self.field = store, record, geometry(store,record)
        self._shape = shape
        self.native,self.fx,self.fy = None,1,1
        if self.field["kind"]=="wcs":
            self.native,self.fx,self.fy = fits_registration(store.path(record["fits"]),store.path(record["poster"]),record["width"],record["height"])
        elif ((record.get("gaia") or {}).get("wcs_header") and record["gaia"].get("status")=="solved"
              and record["gaia"].get("digest")==record.get("sha256",{}).get("final")):
            self.native=WCS(Header.fromstring(record["gaia"]["wcs_header"],sep="\n"))
        corners=SkyCoord(*np.asarray(self.field["corners"]).T,unit="deg")
        center=SkyCoord(corners.cartesian.mean(),frame="icrs")
        self.tangent=center.skyoffset_frame()
        rays=corners.transform_to(self.tangent).cartesian.xyz.value
        self.inverse=cv2.getPerspectiveTransform(np.float32((rays[1:]/rays[0]).T),np.float32([[0,0],[1,0],[1,1],[0,1]]))

    @property
    def pixel_shape(self):
        return self._shape[::-1]

    def pixel_to_world_values(self, x, y):
        x,y = np.broadcast_arrays(x,y)
        sky = raster_sky(self.store,self.record,self.field,
                         ((x+.5)/self._shape[1]).reshape(1,-1), ((y+.5)/self._shape[0]).reshape(1,-1)).icrs
        return sky.ra.deg.reshape(x.shape),sky.dec.deg.reshape(y.shape)

    def world_to_pixel_values(self, ra, dec):
        ra,dec = np.broadcast_arrays(ra,dec)
        good = np.isfinite(ra)&np.isfinite(dec)&(np.abs(dec)<=90)
        xy = np.full((ra.size,2),np.nan)
        if good.any():
            sky=SkyCoord(ra[good],dec[good],unit="deg")
            if self.native is not None:
                x,y=skycoord_to_pixel(sky,self.native,origin=0)
                uv=np.c_[((x if self.fx==1 else self.record["width"]-1-x)+.5)/self.record["width"],
                          ((y if self.fy==1 else self.record["height"]-1-y)+.5)/self.record["height"]]
            else:
                rays=sky.transform_to(self.tangent).cartesian.xyz.value
                uv=cv2.perspectiveTransform((rays[1:]/rays[0]).T.astype(float)[None],self.inverse)[0]
                uv[rays[0]<=0]=np.nan
            xy[good.ravel()] = uv*[self._shape[1],self._shape[0]]-.5
        return xy[:,0].reshape(ra.shape),xy[:,1].reshape(dec.shape)


def registered(store, records):
    return [r for r in records if not r.get("body") and not r.get("capture_kind")
            and geometry(store,r).get("kind") in {"gaia","wcs"}]


def overlap(store, a, b):
    corners = geometry(store,b)["corners"]
    sky=SkyCoord(*np.asarray(corners).T,unit="deg")
    x,y=RasterWCS(store,a,(a["height"],a["width"])).world_to_pixel_values(sky.ra.deg,sky.dec.deg)
    uv=np.c_[(x+.5)/a["width"],(y+.5)/a["height"]]
    if not np.isfinite(uv).all():
        return False
    hull = cv2.convexHull(np.float32(uv))
    area = cv2.contourArea(hull)
    common,_ = cv2.intersectConvexConvex(hull,np.float32([[0,0],[1,0],[1,1],[0,1]]))
    return area>0 and common>.015*min(area,1)


def groups(store, records):
    remaining = sorted(registered(store,records),key=date_order,reverse=True)
    result = []
    while remaining:
        component = [remaining.pop(0)]
        for a in component:
            for b in remaining[:]:
                if overlap(store,a,b) or overlap(store,b,a):
                    component.append(b);remaining.remove(b)
        result.append(component)
    return result


def build(store, records, folder):
    from reproject import reproject_interp
    from reproject.mosaicking import find_optimal_celestial_wcs
    records = sorted(records,key=date_order)  # newest exposure is the tonal reference last
    if not records or len(records)>32:
        raise ValueError("observatory_mosaic_limit")
    inputs = []
    for record in records:
        factor = min(1,1536/max(record["width"],record["height"]))
        shape = tuple(max(2,int(record[k]*factor)//2*2) for k in ("height","width"))
        inputs.append((shape,HighLevelWCSWrapper(RasterWCS(store,record,shape))))
    target,shape = find_optimal_celestial_wcs(inputs,auto_rotate=False,negative_lon_cdelt=True)
    # Raster y increases downwards: keep celestial north at the top of the WebP.
    target.wcs.cdelt[1] *= -1
    target.wcs.crpix[1] = shape[0]+1-target.wcs.crpix[1]
    factor = min(1,4096/max(shape),math.sqrt(6_000_000/np.prod(shape)))
    if factor<1:
        shape = tuple(max(2,math.ceil(v*factor)) for v in shape)
        target.wcs.crpix = (target.wcs.crpix-.5)*factor+.5
        target.wcs.cdelt /= factor
    total = np.zeros((*shape,3),np.float32)
    weights = np.zeros(shape,np.float32)
    captures = []
    for record,(source_shape,wcs) in zip(records,inputs):
        rgb = resize_long(read_rgb(store.path(record["assets"]["final"])),1536)
        assert rgb.shape[:2]==source_shape
        h,w = source_shape
        yy,xx = np.ogrid[:h,:w]
        feather = np.clip(np.minimum(np.minimum(yy+.5,h-.5-yy),np.minimum(xx+.5,w-.5-xx)) / (.12*min(h,w)),.01,1).astype(np.float32)
        def sample(data):
            image,footprint = reproject_interp((data,wcs),target,shape_out=shape,order="bilinear",
                                               roundtrip_coords=False,block_size=(256,256))
            return np.where(np.isfinite(image)&(footprint>0),image,0).astype(np.float32)
        weight = sample(feather)
        layer = np.stack([sample(rgb[:,:,i]*feather) for i in range(3)],axis=-1)
        # Visual exposure matching is bounded and does not change any source file.
        common = (weights>.5)&(weight>.5)
        indices = np.flatnonzero(common.ravel())[::max(1,int(common.sum()/50000))]
        if len(indices)>256:
            old = total.reshape(-1,3)[indices]/weights.ravel()[indices,None]
            new = layer.reshape(-1,3)[indices]/weight.ravel()[indices,None]
            for i in range(3):
                good = (new[:,i]>.025)&(new[:,i]<.9)&(old[:,i]>.025)&(old[:,i]<.9)
                if good.sum()>128:
                    layer[:,:,i] *= np.clip(np.median(old[good,i]/new[good,i]),.6,1.67)
        total += layer;weights += weight
        sky = SkyCoord(*np.asarray(geometry(store,record)["corners"]).T,unit="deg")
        x,y = target.world_to_pixel(sky)
        captures.append({**identity(record),"date":capture_date(record),
                         "corners":np.c_[(x+.5)/shape[1],(y+.5)/shape[0]].tolist()})
    alpha = weights>0
    total /= np.maximum(weights[:,:,None],1e-9)
    rgba = np.dstack((np.uint8(np.clip(total,0,1)*255),np.uint8(alpha)*255))
    if not cv2.imwrite(str(folder/"mosaic.webp"),cv2.cvtColor(rgba,cv2.COLOR_RGBA2BGRA),[cv2.IMWRITE_WEBP_QUALITY,95]):
        raise ValueError("observatory_failed")
    return dict(image="mosaic.webp",width=shape[1],height=shape[0],captures=captures,
                source="Astropy WCS / reproject",visual_only=True)
