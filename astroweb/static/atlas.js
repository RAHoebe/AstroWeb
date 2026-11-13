import {language, local, t} from './i18n.js';

const $=id=>document.getElementById(id);
const image=new Image();
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let galaxy, title, journey, progress=0, playing=false, previous=0, request=0, videoRequest=0;
const seconds=10;

function canvas(id){
  const el=$(id), box=el.getBoundingClientRect();
  if(!box.width||!box.height)return null;
  const ratio=Math.min(devicePixelRatio||1,2);
  const w=Math.round(box.width*ratio), h=Math.round(box.height*ratio);
  if(el.width!==w||el.height!==h){el.width=w;el.height=h;}
  const ctx=el.getContext('2d');
  ctx.setTransform(ratio,0,0,ratio,0,0);
  ctx.clearRect(0,0,box.width,box.height);
  return {ctx,w:box.width,h:box.height};
}
function labels(ctx,points,w,h){
  const occupied=[];
  ctx.font=(w<500?'11':'13')+'px "Segoe UI", sans-serif';
  ctx.textBaseline='middle';
  for(const {x,y,text,active} of points){
    if(x<8||x>w-8||y<12||y>h-15)continue;
    const width=ctx.measureText(text).width+12;
    for(const [dx,dy] of [[9,-14],[9,14],[-width-9,-14],[-width-9,14]]){
      const l=x+dx,top=y+dy-9;
      if(l<4||top<3||l+width>w-4||top+18>h-4)continue;
      if(occupied.some(b=>l<b[0]+b[2]+4&&l+width>b[0]-4&&top<b[1]+22&&top+18>b[1]-4))continue;
      occupied.push([l,top,width]);
      ctx.fillStyle='rgba(5,10,20,.82)';ctx.fillRect(l,top,width,18);
      ctx.fillStyle=active?'#ffe2a6':'#cfe8f1';ctx.fillText(text,l+6,top+9);
      ctx.beginPath();ctx.arc(x,y,active?3:2,0,2*Math.PI);ctx.fill();
      break;
    }
  }
}
function ring(ctx,x,y){
  ctx.strokeStyle='#ffdc93';ctx.lineWidth=1.5;
  ctx.beginPath();ctx.arc(x,y,7,0,2*Math.PI);ctx.stroke();
  ctx.fillStyle='#fff3d1';ctx.fillRect(x-1.5,y-1.5,3,3);
}
export function drawGalaxy(){
  const layer=canvas('galaxy-canvas');
  if(!layer||!galaxy)return;
  const {ctx,w,h}=layer;
  ctx.fillStyle='#03050a';ctx.fillRect(0,0,w,h);
  const ease=progress*progress*(3-2*progress);
  const side=Math.min(w,h)*Math.pow(13,ease);
  // Interpolate the target on screen so it is always inside the viewport.
  const tx=w/2+(galaxy.xy[0]-.5)*Math.min(w,h)*(1-ease);
  const ty=h/2+(galaxy.xy[1]-.5)*Math.min(w,h)*(1-ease);
  const left=tx-galaxy.xy[0]*side,top=ty-galaxy.xy[1]*side;
  if(image.naturalWidth){
    ctx.imageSmoothingQuality='high';
    ctx.drawImage(image,left,top,side,side);
  }
  ring(ctx,tx,ty);
  if($('galaxy-labels').checked){
    const points=galaxy.points.map(p=>({x:left+p.xy[0]*side,y:top+p.xy[1]*side,text:local(p)}));
    labels(ctx,[{x:tx,y:ty,text:local(title),active:true},...points],w,h);
  }
  const maxLy=Math.min(130,w*.22)*galaxy.ly_per_image/side;
  const step=Math.pow(10,Math.floor(Math.log10(maxLy)));
  const ly=(maxLy/step>=5?5:maxLy/step>=2?2:1)*step;
  const px=ly*side/galaxy.ly_per_image;
  ctx.fillStyle='#e8f1f7';ctx.fillRect(18,h-15,px,1.5);
  ctx.font='11px "Segoe UI", sans-serif';ctx.textBaseline='bottom';
  ctx.fillText(ly.toLocaleString(language)+' '+t('lightYears'),18,h-20);
  $('galaxy-time').value=Math.round(progress*1000);
  $('galaxy-play').textContent=t(playing?'atlasPause':progress>=1?'atlasReplay':'atlasPlay');
  $('galaxy-distance').textContent=t('solarDistance')+' ≈ '+galaxy.ly.toLocaleString(language)+' '+t('lightYears');
}
export function stopGalaxy(){
  playing=false;cancelAnimationFrame(request);drawGalaxy();
}
function animate(){
  if(playing||!galaxy)return;
  if(progress>=1)progress=0;
  playing=true;previous=performance.now();
  function tick(now){
    progress=Math.min(1,progress+(now-previous)/(seconds*1000));previous=now;
    if(progress>=1)playing=false;
    drawGalaxy();
    if(playing)request=requestAnimationFrame(tick);
  }
  request=requestAnimationFrame(tick);
}
export function configureGalaxy(data,name){
  galaxy=data;title=name;
  $('galaxy-tab').hidden=!data;
  if(!data)return;
  const src=$('galaxy-source');src.hidden=!data.source;
  if(data.source)src.href=data.source;
}
export function openGalaxy(){
  if(!image.src){image.onload=drawGalaxy;image.src='/static/galaxy-face-on.webp';}
  drawGalaxy();
  if(!progress&&!reduced.matches)animate();
}
$('galaxy-play').addEventListener('click',()=>playing?stopGalaxy():animate());
$('galaxy-time').addEventListener('input',e=>{
  const next=Number(e.target.value)/1000;
  stopGalaxy();progress=next;drawGalaxy();
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopGalaxy();});
reduced.addEventListener('change',()=>{if(reduced.matches)stopGalaxy();});

const video=$('journey-video');
function drawJourney(time=video.currentTime){
  const layer=canvas('journey-names');
  if(!layer||!journey||!$('journey-labels').checked)return;
  const {ctx,w,h}=layer;
  const frame=journey.frames[Math.min(journey.frames.length-1,Math.max(0,Math.floor(time*journey.fps+.0001)))];
  if(!frame||frame[9]<=0)return;
  const scale=Math.min(w/journey.width,h/journey.height);
  const vw=journey.width*scale,vh=journey.height*scale;
  ctx.save();ctx.translate((w-vw)/2,(h-vh)/2);ctx.globalAlpha=frame[9];
  const points=journey.points.map((point,i)=>{
    const [x,y]=point.xy,d=x*frame[6]+y*frame[7]+frame[8];
    return {x:scale*(x*frame[0]+y*frame[1]+frame[2])/d,
            y:scale*(x*frame[3]+y*frame[4]+frame[5])/d,text:local(point),active:i===0};
  });
  labels(ctx,points,vw,vh);ctx.restore();
}
function syncJourney(){
  if(videoRequest&&video.cancelVideoFrameCallback)video.cancelVideoFrameCallback(videoRequest);
  videoRequest=0;drawJourney();
  if(!$('journey-labels').checked||video.paused||$('journey-panel').hidden||!video.requestVideoFrameCallback)return;
  function frame(now,meta){
    drawJourney(meta.mediaTime);
    videoRequest=video.requestVideoFrameCallback(frame);
  }
  videoRequest=video.requestVideoFrameCallback(frame);
}
export function setJourneyLabels(data){journey=data;syncJourney();}
export function atlasLanguage(){drawGalaxy();drawJourney();}
for(const event of ['playing','pause','seeked','ended','loadedmetadata'])video.addEventListener(event,syncJourney);
video.addEventListener('timeupdate',()=>{if(!video.requestVideoFrameCallback)drawJourney();});
for(const id of ['galaxy','journey']){
  const toggle=$(id+'-labels'),key='astroweb-'+id+'-labels';
  const stored=localStorage.getItem(key);
  if(stored!==null)toggle.checked=stored==='true';
  toggle.addEventListener('change',()=>{
    localStorage.setItem(key,String(toggle.checked));
    if(id==='galaxy')drawGalaxy();else syncJourney();
  });
}
$('journey-fullscreen').addEventListener('click',async()=>{
  const stage=video.parentElement;
  try{
    if(document.fullscreenElement)await document.exitFullscreen();
    else if(stage.requestFullscreen)await stage.requestFullscreen();
    else if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();
  }catch{$('journey-status').textContent=t('fullscreen_error');}
});
new ResizeObserver(drawGalaxy).observe($('galaxy-canvas'));
new ResizeObserver(()=>drawJourney()).observe($('journey-names'));
