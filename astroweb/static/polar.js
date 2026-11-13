import {drawFootprintImage} from './footprint.js';
import {local,t,language} from './i18n.js';
const $=id=>document.getElementById(id);
const canvas=$('polar-canvas'),context=canvas.getContext('2d'),reduced=matchMedia('(prefers-reduced-motion: reduce)');
let data=null,promise=null,progress=0,centred=false,anim=0,last=0,visible=false;
const rad=Math.PI/180;
let years=0,clock=0,clockStart=0;
function skyAt(vec,epoch){
  const dt=epoch-2000;
  const x=vec[0]+dt*vec[3], y=vec[1]+dt*vec[4], z=vec[2]+dt*vec[5];
  return [Math.atan2(y,x)/rad, Math.atan2(z,Math.hypot(x,y))/rad];
}
function stopTime(){
  cancelAnimationFrame(clock);clock=0;
}
function setYears(value){
  years=Math.round(value);
  $('polar-years').value=years;
  drawPolar();
}
function playTime(){
  if(!data)return;
  if(clock){stopTime();drawPolar();return;}
  pause();
  const start=years>=50000?-50000:years;
  clockStart=performance.now();
  function tick(now){
    const year=Math.min(50000,start+(now-clockStart)*4);
    clock=year<50000?requestAnimationFrame(tick):0;
    setYears(year);
  }
  clock=requestAnimationFrame(tick);
}
$('polar-years').addEventListener('input',e=>{stopTime();setYears(+e.target.value);});
$('epoch-play').addEventListener('click',playTime);
$('epoch-reset').addEventListener('click',()=>{stopTime();setYears(0);});
$('epoch-trails').addEventListener('change',drawPolar);
function position(ra,dec,side){
  const a=ra*rad,r=(90-side*dec)/90;
  return [-r*Math.sin(a)*side,-r*Math.cos(a)];
}
function smooth(x){x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);}
function hemisphere(){return $('polar-side').value==='south'?-1:1;}
function ownSide(){return data?.target&&data.target.dec*hemisphere()>=0;}
export function drawPolar(){
  if(!visible||!data)return;
  const w=canvas.clientWidth,h=canvas.clientHeight;
  if(!w||!h)return;
  const dpr=Math.min(devicePixelRatio||1,2);
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
  const c=context,side=hemisphere(),ease=smooth(progress),base=Math.max(1,Math.min(w,h)/2-26);
  const region=$('epoch-region').value;
  const preset=region==='dipper'?{ra:183,dec:56,zoom:3.3}:region==='crux'?{ra:187,dec:-60,zoom:4.5}:null;
  const point=preset?position(preset.ra,preset.dec,side):ownSide()?position(data.target.ra,data.target.dec,side):[0,0];
  const corners=ownSide()?data.corners.map(([a,d])=>position(a,d,side)):[];
  const extent=corners.length?Math.max(...corners.map(q=>Math.hypot(q[0]-point[0],q[1]-point[1]))):.05;
  const zoom=preset?preset.zoom:Math.pow(Math.min(45,Math.max(3,.62/Math.max(extent,.01))),ease);
  const r=base*zoom;
  const cx=w/2+(preset?0:point[0]*base*(1-ease))-point[0]*r;
  const cy=h/2+(preset?0:point[1]*base*(1-ease))-point[1]*r;
  const project=([x,y])=>[cx+x*r,cy+y*r];
  c.setTransform(dpr,0,0,dpr,0,0);c.fillStyle='#070c18';c.fillRect(0,0,w,h);
  c.save();c.beginPath();c.arc(cx,cy,r,0,2*Math.PI);c.clip();
  const glow=c.createRadialGradient(w*.42,h*.38,0,w*.5,h*.5,Math.max(w,h)*.65);
  glow.addColorStop(0,'#242b4b');glow.addColorStop(1,'#0c1429');c.fillStyle=glow;c.fillRect(0,0,w,h);
  if(corners.length&&$('polar-photo').checked)drawFootprintImage(c,data.capture,corners.map(project),drawPolar);
  c.strokeStyle='#7284af50';c.lineWidth=.8;c.setLineDash([2,5]);
  for(let deg=15;deg<=90;deg+=15){c.beginPath();c.arc(cx,cy,r*deg/90,0,Math.PI*2);c.stroke();}
  for(let hr=0;hr<24;hr+=2){const [x,y]=project(position(hr*15,0,side));c.beginPath();c.moveTo(cx,cy);c.lineTo(x,y);c.stroke();}
  c.setLineDash([]);c.strokeStyle='#8bacc979';c.lineWidth=1;
  const stars=new Map(),names=[];
  for(const [hip,ra0,dec0,mag,name] of data.stars){
    const vec=data.motion[hip];
    const [ra,dec]=vec?skyAt(vec,data.epoch+years):[ra0,dec0];
    if(dec*side<0)continue;
    const [x,y]=project(position(ra,dec,side));stars.set(hip,[x,y]);
    if(x < -10||x>w+10||y < -10||y>h+10)continue;
    if(vec&&years&&$('epoch-trails').checked){
      const initial=skyAt(vec,data.epoch),start=project(position(...initial,side));
      if(Math.hypot(x-start[0],y-start[1])>2){
        c.strokeStyle='rgba(146,206,231,.5)';c.lineWidth=.9;c.beginPath();
        let pen=false;
        for(let j=0;j<=12;j++){
          const q=skyAt(vec,data.epoch+years*j/12);
          if(q[1]*side<0){pen=false;continue;}
          const pt=project(position(...q,side));if(pen)c.lineTo(...pt);else c.moveTo(...pt);pen=true;
        }
        c.stroke();
      }
    }
    const pole=hip===(side>0?11767:104382);
    const size=pole?3.5:Math.max(.55,2.25-.34*mag);
    c.fillStyle=pole?'#a7efff':mag<2?'#fff4cf':'#c5d6ee';c.beginPath();c.arc(x,y,size,0,2*Math.PI);c.fill();
    if(pole||name&&mag<1.8)names.push({x,y,text:pole?(side>0?t('polaris'):'σ Octantis'):name,priority:pole?1:3});
  }
  c.strokeStyle='#8bacc979';c.lineWidth=1;
  for(const group of data.groups){
    let xsum=0,ysum=0,n=0;
    for(const path of group.lines){
      c.beginPath();let previous=false;
      for(const id of path){const p=stars.get(id);if(!p){previous=false;continue;}
        if(previous)c.lineTo(...p);else c.moveTo(...p);previous=true;xsum+=p[0];ysum+=p[1];n++;}
      c.stroke();
    }
    if(n)names.push({x:xsum/n,y:ysum/n,text:(language==='nl'?group.nl:null)||group.name,priority:4});
  }
  for(const p of data.objects){
    if(p.dec*side<0)continue;
    const [x,y]=project(position(p.ra,p.dec,side));
    if(x<0||x>w||y<0||y>h)continue;
    c.strokeStyle='#a99ac488';c.strokeRect(x-2,y-2,4,4);
    if(!data.target||local(p)!==local(data.target.name))names.push({x,y,text:local(p),priority:5});
  }
  if(ownSide()){
    const [x,y]=project(position(data.target.ra,data.target.dec,side));
    if(corners.length){c.strokeStyle='#e4bc7f';c.beginPath();corners.forEach((p,i)=>i?c.lineTo(...project(p)):c.moveTo(...project(p)));c.closePath();c.stroke();}
    c.strokeStyle='#ffdd93';c.lineWidth=1.6;c.beginPath();c.arc(x,y,8,0,2*Math.PI);c.stroke();
    names.push({x,y,text:local(data.target.name),priority:0});
  }
  c.restore();c.strokeStyle='#6d85aa';c.lineWidth=1;c.beginPath();c.arc(cx,cy,r,0,2*Math.PI);c.stroke();
  c.font='11px "Segoe UI",sans-serif';c.textBaseline='middle';c.fillStyle='#aabdd6';
  for(let hr=0;hr<24;hr+=2){const p=position(hr*15,0,side),x=cx+p[0]*(r+13),y=cy+p[1]*(r+13);c.textAlign='center';c.fillText(hr+'h',x,y);}
  c.textAlign='left';const boxes=[];
  for(const label of names.sort((a,b)=>a.priority-b.priority)){
    const x=label.x+7,y=label.y-8,tw=c.measureText(label.text).width;
    if(x<4||x+tw>w-4||y<6||y>h-8||boxes.some(b=>x<b.x+b.w+5&&x+tw>b.x-5&&Math.abs(y-b.y)<14))continue;
    boxes.push({x,y,w:tw});c.lineWidth=3;c.strokeStyle='#12192d';c.strokeText(label.text,x,y);
    c.fillStyle=['#ffdd93','#a7efff','#fff','#e7eef9','#b3cae0','#c4b3d8'][label.priority];c.fillText(label.text,x,y);
  }
  $('polar-year').textContent=(years>0?'+':'')+years.toLocaleString(language)+' '+t('epochYears')+' · '+Math.floor(data.epoch+years);
  $('epoch-play').textContent=t(clock?'atlasPause':'epochPlay');
  $('epoch-reset').textContent=t(data.capture_epoch?'epochReset':'epochNow');
  $('polar-time').value=Math.round(progress*1000);
  $('polar-play').disabled=$('polar-time').disabled=!!preset||!ownSide();
  $('polar-play').textContent=t(anim?'atlasPause':progress>=1?'atlasReplay':'polarZoom');
  $('polar-status').textContent=!data.target?t('polarMissing'):!ownSide()&&!preset?t('polarOther'):'';
}
function pause(){cancelAnimationFrame(anim);anim=0;drawPolar();}
function play(){
  if(!ownSide())return;
  stopTime();
  if(progress>=1)progress=0;last=performance.now();
  function tick(now){progress=Math.min(1,progress+(now-last)/9000);last=now;anim=progress<1?requestAnimationFrame(tick):0;drawPolar();}
  anim=requestAnimationFrame(tick);
}
export async function openPolar(id){
  visible=true;
  if(!data){
    try{
      promise??=fetch('/api/objects/'+encodeURIComponent(id)+'/polar').then(r=>{if(!r.ok)throw Error();return r.json();});
      data=await promise;
    }catch{promise=null;$('polar-status').textContent=t('network_error');return;}
  }
  if(!visible)return;
  $('polar-photo').disabled=!data.corners.length;
  if(!centred){$('polar-side').value=data.target?.dec<0?'south':'north';centred=true;}
  drawPolar();
}
$('polar-photo').addEventListener('change',drawPolar);
export function closePolar(){visible=false;stopTime();pause();}
$('epoch-region').addEventListener('change',e=>{
  const region=e.target.value;
  $('polar-side').value=region==='capture'?(data?.target?.dec<0?'south':'north'):region==='crux'?'south':'north';
  progress=0;pause();
});
$('polar-side').addEventListener('change',()=>{$('epoch-region').value='capture';progress=0;pause();});
$('polar-play').addEventListener('click',()=>anim?pause():play());
$('polar-time').addEventListener('input',e=>{progress=+e.target.value/1000;pause();});
document.addEventListener('visibilitychange',()=>{if(document.hidden){stopTime();pause();}});
reduced.addEventListener('change',()=>{if(reduced.matches){stopTime();pause();}});
new ResizeObserver(drawPolar).observe(canvas);
