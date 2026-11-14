import {drawFootprintImage,loadPoster} from './footprint.js';
import {local,language,setLanguage,t} from './i18n.js';

const $=id=>document.getElementById(id),stage=$('pano-stage');
const capture=new URLSearchParams(location.search).get('capture');
const memory='astroweb-panorama-'+(capture||'overview');
const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
const canvas=$('pano-sky'),ctx=canvas.getContext('2d');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const shortest=delta=>delta-Math.round(delta);
let scene,img,links=[],x=.5,y=.5,zoom=1,drag=null,flight=null,hit=[];
let redraw=0;
function posterLoaded(){
  if(!redraw)redraw=requestAnimationFrame(()=>{redraw=0;draw();});
}
function pinName(pin){
  return [local(pin.name),pin.detail].filter(Boolean).join(' · ');
}
function startView(){
  x=(!capture&&scene.pins.length)?scene.pins[0].x:.5;
  y=(!capture&&scene.pins.length)?scene.pins[0].y:.5;
  zoom=1;draw();
}

function dimensions(){
  const w=stage.clientWidth,h=stage.clientHeight;
  const fit=img.naturalWidth>img.naturalHeight||scene.wrap?h/img.naturalHeight:Math.min(w/img.naturalWidth,h/img.naturalHeight);
  const scale=(scene.wrap?Math.max(fit,w/img.naturalWidth):fit)*zoom;
  return {w,h,sw:img.naturalWidth*scale,sh:img.naturalHeight*scale};
}
function draw(){
  if(!img?.naturalWidth)return;
  const {w,h,sw,sh}=dimensions();
  if(!w||!h)return;
  if(scene.wrap)x=((x%1)+1)%1;
  else x=sw<=w ? .5 : clamp(x,w/(2*sw),1-w/(2*sw));
  y=sh<=h ? .5 : clamp(y,h/(2*sh),1-h/(2*sh));
  const left=w/2-x*sw,top=h/2-y*sh;
  const dpr=Math.min(devicePixelRatio||1,2);
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){
    canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  }
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  ctx.save();
  if(flight){
    ctx.translate(w/2,h/2);ctx.rotate(flight.angle);ctx.translate(-w/2,-h/2);
  }
  for(const tile of scene.wrap?[-1,0,1]:[0]){
    ctx.drawImage(img,left+tile*sw,top,sw,sh);
  }
  hit=[];
  for(const pin of scene.pins){
    if(!pin.corners||(!$('pano-photos').checked&&flight?.pin!==pin))continue;
    const cx=w/2+shortest(pin.x-x)*sw;
    for(const offset of [-sw,0,sw]){
      const quad=pin.corners.map(([px,py])=>[cx+offset+shortest(px-pin.x)*sw,top+py*sh]);
      if(!flight && (quad.every(([u])=>u<0)||quad.every(([u])=>u>w)||quad.every(([,v])=>v<0)||quad.every(([,v])=>v>h)))continue;
      const path=new Path2D();path.moveTo(...quad[0]);
      for(const point of quad.slice(1))path.lineTo(...point);
      path.closePath();
      drawFootprintImage(ctx,pin.target,quad,posterLoaded);
      ctx.strokeStyle=flight?.pin===pin?'#ffdc94':'rgba(240,206,144,.92)';
      ctx.lineWidth=1.25;ctx.stroke(path);
      hit.push({path,pin});
    }
  }
  ctx.restore();
  if(flight?.blend>0){
    const photo=loadPoster(flight.pin.target);
    if(photo.naturalWidth){
      ctx.save();ctx.globalAlpha=flight.blend;
      ctx.fillStyle='#05060a';ctx.fillRect(0,0,w,h);
      const fit=Math.min(w/photo.naturalWidth,h/photo.naturalHeight);
      const pw=photo.naturalWidth*fit,ph=photo.naturalHeight*fit;
      ctx.drawImage(photo,(w-pw)/2,(h-ph)/2,pw,ph);ctx.restore();
    }
  }
  links.forEach((link,i)=>{
    const pin=scene.pins[i];
    let dx=pin.x-x;
    if(scene.wrap)dx-=Math.round(dx);
    const px=w/2+sw*dx,py=top+sh*pin.y;
    link.hidden=!!flight||!$('pano-labels').checked||px<0||px>w||py<0||py>h;
    link.style.left=px+'px';link.style.top=py+'px';
    link.classList.toggle('pano-pin-left',px>w*.63);
  });
  $('pano-zoom').textContent=zoom.toFixed(1)+'×';
  $('pano-out').disabled=zoom<=1;$('pano-in').disabled=zoom>=8;
}
function hitAt(e){
  const r=stage.getBoundingClientRect();
  const px=(e.clientX-r.left)*canvas.width/r.width,py=(e.clientY-r.top)*canvas.height/r.height;
  return hit.slice().reverse().find(item=>ctx.isPointInPath(item.path,px,py))?.pin;
}
function cancelFlight(){
  if(!flight)return;
  cancelAnimationFrame(flight.frame);
  ({x,y,zoom}=flight.origin);flight=null;draw();
}
function visit(pin){
  const url=links[scene.pins.indexOf(pin)].href;
  if(!pin.corners||reduced.matches){location.assign(url);return;}
  cancelFlight();
  const origin={x,y,zoom};
  const f={pin,origin,angle:0,blend:0,frame:0};flight=f;
  const photo=loadPoster(pin.target);
  // Keep normal navigation available if a preview cannot be decoded.
  photo.decode().then(()=>{
    if(flight!==f)return;
    const {w,h,sw,sh}=dimensions();
    const box=pin.corners.map(([u,v])=>[shortest(u-pin.x)*sw/zoom,(v-pin.y)*sh/zoom]);
    const [a,b,,d]=box,angle=-Math.atan2(b[1]-a[1],b[0]-a[0]);
    const width=Math.hypot(b[0]-a[0],b[1]-a[1]),height=Math.hypot(d[0]-a[0],d[1]-a[1]);
    const end=Math.min(w/Math.max(.01,width),h/Math.max(.01,height))*.94;
    const dx=shortest(pin.x-origin.x);
    const start=performance.now();
    function tick(now){
      const t=clamp((now-start)/1650,0,1);
      const ease=t*t*(3-2*t);
      zoom=origin.zoom*Math.pow(end/origin.zoom,ease);
      // Interpolate the marker in screen space to keep it in frame during the approach.
      x=pin.x-dx*(1-ease)*origin.zoom/zoom;
      y=pin.y-(pin.y-origin.y)*(1-ease)*origin.zoom/zoom;
      f.angle=angle*ease;
      const fade=clamp((t-.74)/.24,0,1);f.blend=fade*fade*(3-2*fade);
      draw();
      if(t===1)location.assign(url);else f.frame=requestAnimationFrame(tick);
    }
    f.frame=requestAnimationFrame(tick);
  }).catch(()=>{if(flight===f)location.assign(url);});
}
function zoomAt(value,ox=0,oy=0){
  if(!img?.naturalWidth)return;
  cancelFlight();const old=dimensions();zoom=clamp(value,1,8);const next=dimensions();
  x+=ox*(1/old.sw-1/next.sw);y+=oy*(1/old.sh-1/next.sh);draw();
}
function pan(dx,dy){
  if(!img?.naturalWidth)return;
  cancelFlight();const {sw,sh}=dimensions();x+=dx/sw;y+=dy/sh;draw();
}
function languageUI(){
  setLanguage(language);
  if(!scene)return;
  $('pano-heading').textContent=scene.name?local(scene.name):t('panoSkyTitle');
  document.title=$('pano-heading').textContent+' · AstroWeb';
  links.forEach((link,i)=>{link.textContent=pinName(scene.pins[i]);});
  const jump=$('pano-jump'),value=jump.value;
  jump.replaceChildren(new Option(t('panoChoose'),''),...scene.pins.map(p=>new Option(pinName(p),p.target)));
  jump.value=value;
}
for(const button of document.querySelectorAll('[data-lang]'))button.addEventListener('click',()=>{setLanguage(button.dataset.lang);languageUI();draw();});
$('pano-jump').onchange=e=>{
  const pin=scene.pins.find(p=>p.target===e.target.value);if(!pin)return;
  cancelFlight();x=pin.x;y=pin.y;zoom=Math.max(zoom,2);$('pano-labels').checked=true;draw();
  links[scene.pins.indexOf(pin)].focus({preventScroll:true});
};
$('pano-labels').onchange=draw;
$('pano-photos').onchange=draw;
$('pano-reset').onclick=()=>{cancelFlight();$('pano-jump').value='';startView();};
$('pano-out').onclick=()=>zoomAt(zoom/1.4);
$('pano-in').onclick=()=>zoomAt(zoom*1.4);
$('pano-full').onclick=async()=>{
  try{if(document.fullscreenElement)await document.exitFullscreen();else await document.querySelector('.pano-shell').requestFullscreen();}
  catch{$('pano-notice').textContent=t('fullscreen_error');}
};
stage.addEventListener('wheel',e=>{
  if(!img?.naturalWidth)return;e.preventDefault();
  const r=stage.getBoundingClientRect();
  zoomAt(zoom*Math.exp(-clamp(e.deltaY*(e.deltaMode===1?16:1),-250,250)*.003),e.clientX-r.left-r.width/2,e.clientY-r.top-r.height/2);
},{passive:false});
stage.onpointerdown=e=>{
  if(!img?.naturalWidth||drag||e.button!==0||e.target.closest('a'))return;
  cancelFlight();drag={id:e.pointerId,x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,moved:false};stage.setPointerCapture(e.pointerId);
  stage.focus({preventScroll:true});stage.classList.add('dragging');
};
stage.onpointermove=e=>{
  if(drag?.id!==e.pointerId)return;
  if(!drag.moved&&Math.hypot(e.clientX-drag.startX,e.clientY-drag.startY)<4)return;
  drag.moved=true;pan(drag.x-e.clientX,drag.y-e.clientY);drag.x=e.clientX;drag.y=e.clientY;
};
stage.onpointerup=e=>{
  if(drag?.id!==e.pointerId||drag.moved)return;
  const pin=hitAt(e);if(pin)visit(pin);
};
stage.onlostpointercapture=()=>{drag=null;stage.classList.remove('dragging');};
stage.onkeydown=e=>{
  if(e.key==='Escape'){cancelFlight();return;}
  const step=stage.clientWidth*.12;
  const keys={ArrowLeft:[-step,0],ArrowRight:[step,0],ArrowUp:[0,-step],ArrowDown:[0,step]};
  if(keys[e.key]){e.preventDefault();pan(...keys[e.key]);}
  else if(['+','=','-','Home'].includes(e.key)){e.preventDefault();if(e.key==='Home')$('pano-reset').click();else zoomAt(e.key==='-'?zoom/1.4:zoom*1.4);}
};
new ResizeObserver(draw).observe(stage);
window.addEventListener('pagehide',()=>{if(img?.naturalWidth)sessionStorage.setItem(memory,JSON.stringify(flight?.origin||{x,y,zoom}));});

window.addEventListener('pageshow',e=>{if(e.persisted)cancelFlight();});
async function init(){
  languageUI();
  const r=await fetch('/api/panorama'+(capture?'?capture='+encodeURIComponent(capture):''));
  if(!r.ok)throw Error();
  scene=await r.json();
  if(capture){
    $('pano-back').dataset.i18n='panoBackPhoto';$('pano-back').href='/viewer/'+encodeURIComponent(scene.id)+'#original';
    $('pano-credit').hidden=true;
  }
  links=scene.pins.map(pin=>{
    const a=document.createElement('a');a.className='pano-pin';
    const query=new URLSearchParams({from:'panorama'});if(capture)query.set('scene',scene.id);
    a.href='/viewer/'+encodeURIComponent(pin.target)+'?'+query+'#original';
    a.addEventListener('click',event=>{
      if(!pin.corners||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button!==0)return;
      event.preventDefault();visit(pin);
    });
    return a;
  });
  $('pano-markers').replaceChildren(...links);
  $('pano-jump').disabled=$('pano-labels').disabled=!links.length;
  languageUI();
  img=new Image();img.src=scene.image;await img.decode();
  $('pano-photo-control').hidden=!scene.pins.some(p=>p.corners);
  startView();
  const saved=JSON.parse(sessionStorage.getItem(memory)||'null');
  if(saved&&[saved.x,saved.y,saved.zoom].every(Number.isFinite)){({x,y,zoom}=saved);zoom=clamp(zoom,1,8);}
  draw();
}
init().catch(()=>{$('pano-notice').textContent=t('panoUnavailable');});
