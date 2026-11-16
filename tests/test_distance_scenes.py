import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from astroweb import solar_detail


def test_partial_eclipse_disk_matches_the_full_own_disk():
    photo=np.zeros((300,300,3),np.uint8);cv2.circle(photo,(150,150),110,(210,210,210),-1)
    eclipse=np.full((350,350,3),50,np.uint8);cv2.circle(eclipse,(-25,20),300,(0,0,0),-1)
    matrix,center,ratio=solar_detail.limb_registration(photo,eclipse)
    np.testing.assert_allclose(center,[-25,20],atol=2)
    theta=np.linspace(0,2*np.pi,12)
    points=np.c_[150+110*np.cos(theta),150+110*np.sin(theta)]
    mapped=cv2.perspectiveTransform(points[None],matrix)[0]
    np.testing.assert_allclose(np.linalg.norm(mapped-center,axis=1),110*ratio,atol=1)


def test_disk_matching_corrects_small_ellipticity_without_rotating_the_photo():
    photo=np.zeros((300,300,3),np.uint8);cv2.ellipse(photo,(150,150),(110,104),0,0,360,(210,210,210),-1)
    eclipse=np.full((350,350,3),50,np.uint8);cv2.circle(eclipse,(-25,20),300,(0,0,0),-1)
    matrix,center,_=solar_detail.limb_registration(photo,eclipse)
    theta=np.linspace(0,2*np.pi,40);points=np.c_[150+110*np.cos(theta),150+104*np.sin(theta)]
    mapped=cv2.perspectiveTransform(points[None],matrix)[0]
    radii=np.linalg.norm(mapped-center,axis=1)
    assert radii.max()-radii.min()<3
    assert abs(matrix[0,1])<.01


def test_cropped_eclipse_does_not_leave_a_bright_rectangular_photosphere(monkeypatch):
    monkeypatch.setattr(solar_detail,'WIDTH',320);monkeypatch.setattr(solar_detail,'HEIGHT',180)
    monkeypatch.setattr(solar_detail,'limb_registration',lambda *args:(np.eye(3),np.array([200.,200.]),1.))
    photo=np.full((400,400,3),200,np.uint8);eclipse=np.zeros((100,100,3),np.uint8)
    sequence=solar_detail.aligned_limb_frames(photo,eclipse,(.5,.5))
    for _ in range(145):frame=next(sequence)
    assert 70<frame.max()<110  # The entire disk fades, including outside the reference rectangle.


def test_distance_map_reveals_depth_and_light_pulse_moves_between_object_and_earth():
    module=(Path(__file__).resolve().parents[1]/'astroweb/static/distance-scenes.js').as_uri()
    script="""
      import {spaceLayout,starPoint,lightJourney} from MODULE;
      const data={width:640,height:480,stars:[{x:.5,y:.5,distance_pc:100},{x:.5,y:.5,distance_pc:1000}]};
      const flat=spaceLayout(data,960,540,1,0,0),side=spaceLayout(data,960,540,1,0,1);
      const initial=data.stars.map(s=>starPoint(flat,s)),spatial=data.stars.map(s=>starPoint(side,s));
      const circles=[],words=[];
      const context=new Proxy({}, {get(target,key){if(key==='createLinearGradient'||key==='createRadialGradient')return ()=>({addColorStop(){}});if(key==='arc')return (x,y,r)=>{if(r===5)circles.push(x)};if(key==='fillText')return value=>words.push(value);return ()=>{};},set(){return true;}});
      for(const p of [.2,.7,.99])lightJourney(context,{lookback_years:2500000},{width:640,height:480},p,960,540,k=>k,String,'2026-11-03');
      console.log(JSON.stringify({initial,spatial,circles,words}));
    """.replace('MODULE',json.dumps(module))
    result=subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True,check=True)
    data=json.loads(result.stdout)
    np.testing.assert_allclose(data['initial'][0],data['initial'][1])
    assert np.linalg.norm(np.subtract(*data['spatial']))>100
    assert data['circles'][1]>data['circles'][0]+100
    assert {'obs_light_departure','obs_earth','obs_light_arrived'}.issubset(data['words'])
