import cv2
import numpy as np
import pytest

from astroweb import lunar_detail as lunar


@pytest.mark.parametrize("angle", [0, 90, 338.523])
def test_lunar_projection_roundtrip_with_libration_and_position_angle(angle):
    data=dict(subearth_lon=-4.262,subearth_lat=-5.215,posangle=angle)
    for lon,lat,*_ in lunar.SITES.values():
        xy,z=lunar.project(lon,lat,data,np.array([365.,365.]),334.)
        assert z>.1
        a,b,visible=lunar.unproject(*xy,data,np.array([365.,365.]),334.)
        assert visible
        np.testing.assert_allclose([a,b],[lon,lat],atol=1e-10)


@pytest.mark.parametrize("mirrored", [False, True])
def test_registration_recovers_rotated_or_mirrored_surface_with_held_out_features(mirrored):
    random=np.random.default_rng(44)
    image=np.zeros((600,600,3),np.uint8)
    for x,y,r,value in random.integers([90,90,2,50],[510,510,13,255],size=(280,4)):
        cv2.circle(image,(int(x),int(y)),int(r),(int(value),)*3,-1)
    expected=np.vstack([cv2.getRotationMatrix2D((300,300),43,.85),[0,0,1.]])
    if mirrored:expected=expected@np.array([[-1,0,599],[0,1,0],[0,0,1.]])
    photo=cv2.warpPerspective(image,expected,(600,600))
    matrix,report=lunar.register(photo,image)
    points=np.float32([[[200,200],[400,200],[400,400],[200,400]]])
    np.testing.assert_allclose(cv2.perspectiveTransform(points,matrix@expected),points,atol=1.)
    assert report['verified']>=10 and report['median_px']<2


def test_featureless_surface_cannot_be_misrepresented_as_registered():
    with pytest.raises(ValueError,match='solarDetailAlignment'):
        lunar.register(np.zeros((300,300,3),np.uint8),np.zeros((730,730,3),np.uint8))


def test_destination_stays_at_same_pixel_through_original_and_map_fade():
    data=dict(subearth_lon=0.,subearth_lat=0.,posangle=0.)
    photo=np.zeros((200,200,3),np.uint8)
    cv2.circle(photo,(100,100),85,(45,45,45),-1)
    cv2.circle(photo,(100,100),4,(255,255,255),-1)
    tile=np.full((1024,1024,3),45,np.uint8)
    cv2.circle(tile,(512,512),30,(255,255,255),-1)
    layers=[(tile,(-10,-10,10,10))]
    sequence=list(lunar.frames(photo,np.eye(3),data,np.array([100.,100.]),85.,layers,(0,0,20,None),320,180,count=40))
    for frame in sequence:
        ys,xs=np.where(frame[:,:,0]>180)
        assert len(xs)>0
        assert abs(xs.mean()-159.5)<2 and abs(ys.mean()-89.5)<2
    assert sequence[-1][90,160,0]>230


def test_options_use_map_sources_and_include_craters_and_seas():
    options=lunar.options()
    assert len(options)==10
    assert all(o['alignment']=='lunar-map' and o['source'].startswith('https://data.lroc.') for o in options)
    assert {'moon-copernicus','moon-plato','moon-imbrium','moon-tranquillitatis'}<={o['id'] for o in options}


def test_nac_flight_finishes_inside_rotated_coverage_without_empty_margins():
    photo=np.full((200,200,3),45,np.uint8)
    tile=np.full((1024,1024,3),170,np.uint8)
    tile[:,:150]=255;tile[:,-150:]=0
    data=dict(subearth_lon=0.,subearth_lat=0.,posangle=35.)
    sequence=list(lunar.frames(photo,np.eye(3),data,np.array([100.,100.]),85.,
                              [(tile,(-10,-10,10,10))],(0,0,20,'11'),320,180,count=120))
    assert sequence[-1].min()>150
    assert sequence[0].max()==45
