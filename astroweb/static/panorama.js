import {local,language,setLanguage,t} from './i18n.js';

const $=id=>document.getElementById(id),stage=$('pano-stage');
const capture=new URLSearchParams(location.search).get('capture');
const memory='astroweb-panorama-'+(capture||'overview');
const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
let scene,img,tiles=[],links=[],x=.5,y=.5,zoom=1,drag=null;
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
  tiles.forEach((tile,i)=>{
    tile.style.width=sw+'px';tile.style.height=sh+'px';
    tile.style.transform='translate('+(left+(scene.wrap?i-1:0)*sw)+'px,'+top+'px)';
  });
  links.forEach((link,i)=>{
    const pin=scene.pins[i];
    let dx=pin.x-x;
    if(scene.wrap)dx-=Math.round(dx);
    const px=w/2+sw*dx,py=top+sh*pin.y;
    link.hidden=!$('pano-labels').checked||px<0||px>w||py<0||py>h;
    link.style.left=px+'px';link.style.top=py+'px';
    link.classList.toggle('pano-pin-left',px>w*.63);
  });
  $('pano-zoom').textContent=zoom.toFixed(1)+'×';
  $('pano-out').disabled=zoom<=1;$('pano-in').disabled=zoom>=8;
}
function zoomAt(value,ox=0,oy=0){
  if(!img?.naturalWidth)return;
  const old=dimensions();zoom=clamp(value,1,8);const next=dimensions();
  x+=ox*(1/old.sw-1/next.sw);y+=oy*(1/old.sh-1/next.sh);draw();
}
function pan(dx,dy){
  if(!img?.naturalWidth)return;
  const {sw,sh}=dimensions();x+=dx/sw;y+=dy/sh;draw();
}
function languageUI(){
  setLanguage(language);
  if(!scene)return;
  $('pano-heading').textContent=scene.name?local(scene.name):t('panoSkyTitle');
  document.title=$('pano-heading').textContent+' · AstroWeb';
  links.forEach((link,i)=>{link.textContent=local(scene.pins[i].name);});
  const jump=$('pano-jump'),value=jump.value;
  jump.replaceChildren(new Option(t('panoChoose'),''),...scene.pins.map(p=>new Option(local(p.name),p.target)));
  jump.value=value;
}
for(const button of document.querySelectorAll('[data-lang]'))button.addEventListener('click',()=>{setLanguage(button.dataset.lang);languageUI();draw();});
$('pano-jump').onchange=e=>{
  const pin=scene.pins.find(p=>p.target===e.target.value);if(!pin)return;
  x=pin.x;y=pin.y;zoom=Math.max(zoom,2);$('pano-labels').checked=true;draw();
  links[scene.pins.indexOf(pin)].focus({preventScroll:true});
};
$('pano-labels').onchange=draw;
$('pano-reset').onclick=()=>{$('pano-jump').value='';startView();};
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
  drag={id:e.pointerId,x:e.clientX,y:e.clientY};stage.setPointerCapture(e.pointerId);
  stage.focus({preventScroll:true});stage.classList.add('dragging');
};
stage.onpointermove=e=>{
  if(drag?.id!==e.pointerId)return;
  pan(drag.x-e.clientX,drag.y-e.clientY);drag.x=e.clientX;drag.y=e.clientY;
};
stage.onlostpointercapture=()=>{drag=null;stage.classList.remove('dragging');};
stage.onkeydown=e=>{
  const step=stage.clientWidth*.12;
  const keys={ArrowLeft:[-step,0],ArrowRight:[step,0],ArrowUp:[0,-step],ArrowDown:[0,step]};
  if(keys[e.key]){e.preventDefault();pan(...keys[e.key]);}
  else if(['+','=','-','Home'].includes(e.key)){e.preventDefault();if(e.key==='Home')$('pano-reset').click();else zoomAt(e.key==='-'?zoom/1.4:zoom*1.4);}
};
new ResizeObserver(draw).observe(stage);
window.addEventListener('pagehide',()=>{if(img?.naturalWidth)sessionStorage.setItem(memory,JSON.stringify({x,y,zoom}));});

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
    return a;
  });
  $('pano-markers').replaceChildren(...links);
  $('pano-jump').disabled=$('pano-labels').disabled=!links.length;
  languageUI();
  img=new Image();img.src=scene.image;await img.decode();
  tiles=Array.from({length:scene.wrap?3:1},()=>{const el=img.cloneNode();el.alt='';el.draggable=false;return el;});
  $('pano-tiles').replaceChildren(...tiles);
  startView();
  const saved=JSON.parse(sessionStorage.getItem(memory)||'null');
  if(saved&&[saved.x,saved.y,saved.zoom].every(Number.isFinite)){({x,y,zoom}=saved);zoom=clamp(zoom,1,8);}
  draw();
}
init().catch(()=>{$('pano-notice').textContent=t('panoUnavailable');});
