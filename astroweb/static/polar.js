import {local,t,language} from './i18n.js';
const $=id=>document.getElementById(id);
const canvas=$('polar-canvas'),context=canvas.getContext('2d'),reduced=matchMedia('(prefers-reduced-motion: reduce)');
let data=null,promise=null,progress=0,centred=false,anim=0,last=0,visible=false;
const rad=Math.PI/180;
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
  const point=ownSide()?position(data.target.ra,data.target.dec,side):[0,0];
  const corners=ownSide()?data.corners.map(([a,d])=>position(a,d,side)):[];
  const extent=corners.length?Math.max(...corners.map(q=>Math.hypot(q[0]-point[0],q[1]-point[1]))):.05;
  const zoom=Math.pow(Math.min(45,Math.max(3,.62/Math.max(extent,.01))),ease);
  const r=base*zoom;
  const cx=w/2+point[0]*base*(1-ease)-point[0]*r;
  const cy=h/2+point[1]*base*(1-ease)-point[1]*r;
  const project=([x,y])=>[cx+x*r,cy+y*r];
  c.setTransform(dpr,0,0,dpr,0,0);c.fillStyle='#070c18';c.fillRect(0,0,w,h);
  c.save();c.beginPath();c.arc(cx,cy,r,0,2*Math.PI);c.clip();
  const glow=c.createRadialGradient(w*.42,h*.38,0,w*.5,h*.5,Math.max(w,h)*.65);
  glow.addColorStop(0,'#242b4b');glow.addColorStop(1,'#0c1429');c.fillStyle=glow;c.fillRect(0,0,w,h);
  c.strokeStyle='#7284af50';c.lineWidth=.8;c.setLineDash([2,5]);
  for(let deg=15;deg<=90;deg+=15){c.beginPath();c.arc(cx,cy,r*deg/90,0,Math.PI*2);c.stroke();}
  for(let hr=0;hr<24;hr+=2){const [x,y]=project(position(hr*15,0,side));c.beginPath();c.moveTo(cx,cy);c.lineTo(x,y);c.stroke();}
  c.setLineDash([]);c.strokeStyle='#8bacc979';c.lineWidth=1;
  const stars=new Map(),names=[];
  for(const [hip,ra,dec,mag,name] of data.stars){
    if(dec*side<0)continue;
    const [x,y]=project(position(ra,dec,side));stars.set(hip,[x,y]);
    if(x < -10||x>w+10||y < -10||y>h+10)continue;
    const pole=hip===(side>0?11767:104382);
    const size=pole?3.5:Math.max(.55,2.25-.34*mag);
    c.fillStyle=pole?'#a7efff':mag<2?'#fff4cf':'#c5d6ee';c.beginPath();c.arc(x,y,size,0,2*Math.PI);c.fill();
    if(pole||name&&mag<1.8)names.push({x,y,text:pole?(side>0?t('polaris'):'σ Octantis'):name,priority:pole?1:3});
  }
  c.strokeStyle='#8bacc979';
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
    const [x,y]=project(point);
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
  $('polar-time').value=Math.round(progress*1000);
  $('polar-play').disabled=$('polar-time').disabled=!ownSide();
  $('polar-play').textContent=t(anim?'atlasPause':progress>=1?'atlasReplay':'polarZoom');
  $('polar-status').textContent=!data.target?t('polarMissing'):!ownSide()?t('polarOther'):'';
}
function pause(){cancelAnimationFrame(anim);anim=0;drawPolar();}
function play(){
  if(!ownSide())return;
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
  if(!centred){$('polar-side').value=data.target?.dec<0?'south':'north';centred=true;}
  drawPolar();
}
export function closePolar(){visible=false;pause();}
$('polar-side').addEventListener('change',()=>{progress=0;pause();});
$('polar-play').addEventListener('click',()=>anim?pause():play());
$('polar-time').addEventListener('input',e=>{progress=+e.target.value/1000;pause();});
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
reduced.addEventListener('change',()=>{if(reduced.matches)pause();});
new ResizeObserver(drawPolar).observe(canvas);
