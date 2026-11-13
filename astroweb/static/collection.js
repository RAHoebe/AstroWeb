import {drawFootprintImage,posterURL} from './footprint.js';
import {t,language,local,setLanguage} from './i18n.js';
const $=id=>document.getElementById(id);
const canvas=$('collection-sky'),c=canvas.getContext('2d');
let items=[],stars=new Map(),lines=[],selected=null,peer=null,ra=180,dec=0,zoom=1,hit=[],drag=null,failed=false;
const wrap=x=>((x+180)%360+360)%360-180;
const clamp=(x,l,h)=>Math.max(l,Math.min(h,x));
const displayId=v=>(v.catalog_id||v.id).replace('_',' ');
const label=v=>[displayId(v),v.session_name,local(v.name)].filter(Boolean).join(' · ');
function center(v){
  if(v.field.center)return v.field.center;
  if(!v.field.corners)return null;
  const p=v.field.corners,base=p[0][0];
  return [base+p.reduce((s,q)=>s+wrap(q[0]-base),0)/p.length,p.reduce((s,q)=>s+q[1],0)/p.length];
}
function select(v){
  selected=v;peer=null;
  const pt=center(v);
  if(pt){
    ra=pt[0];dec=pt[1];
    const corners=v.field.corners||[];
    const sx=Math.max(2,...corners.map(q=>2*Math.abs(wrap(q[0]-ra))));
    const sy=Math.max(2,...corners.map(q=>2*Math.abs(q[1]-dec)));
    zoom=clamp(Math.min(360/sx,180/sy)*.52,1,64);
  }
  if(!pt){ra=180;dec=0;zoom=1;}
  render();
}
let imageFrame=0;
function imageLoaded(){if(!imageFrame)imageFrame=requestAnimationFrame(()=>{imageFrame=0;draw();});}
function draw(){
  const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
  const dpr=Math.min(devicePixelRatio||1,2);
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
  c.setTransform(dpr,0,0,dpr,0,0);
  const g=c.createLinearGradient(0,0,0,h);g.addColorStop(0,'#080d1a');g.addColorStop(.55,'#14213a');g.addColorStop(1,'#080e1b');c.fillStyle=g;c.fillRect(0,0,w,h);
  const sx=w/360*zoom,sy=h/180*zoom,period=w*zoom;
  const xy=q=>[w/2-wrap(q[0]-ra)*sx,h/2-(q[1]-dec)*sy];
  // Unwrap each edge before drawing. Repeat across the RA seam at the map boundary.
  function path(coords,close){
    if(!coords.length)return;
    let x;
    const points=coords.map(q=>{const p=xy(q);if(x!==undefined)p[0]+=Math.round((x-p[0])/period)*period;x=p[0];return p;});
    for(const shift of [-period,0,period]){
      c.beginPath();points.forEach(([a,b],i)=>i?c.lineTo(a+shift,b):c.moveTo(a+shift,b));
      if(close){c.closePath();c.fill();}c.stroke();
    }
  }
  const step=zoom>25?1:zoom>8?5:zoom>2?10:30;
  c.strokeStyle='#687d9a36';c.lineWidth=.7;c.font='10px Segoe UI';c.fillStyle='#99aabe';
  for(let a=0;a<360;a+=step){const [x]=xy([a,0]);if(x<0||x>w)continue;c.beginPath();c.moveTo(x,0);c.lineTo(x,h);c.stroke();c.fillText('RA '+a+'°',x+3,h-6);}
  for(let d=-90;d<=90;d+=step){const [,y]=xy([0,d]);if(y<0||y>h)continue;c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke();c.fillText(d+'°',4,y-3);}
  c.strokeStyle='#708da245';for(const line of lines)path(line.map(id=>stars.get(id)).filter(Boolean),false);
  c.fillStyle='#e0e7f8';for(const star of stars.values()){const [x,y]=xy(star);if(x<0||x>w||y<0||y>h)continue;c.beginPath();c.arc(x,y,Math.max(.55,1.8-star[2]*.27),0,2*Math.PI);c.fill();}
  if($('atlas-photos').checked){
    for(const v of [...items].reverse().sort((a,b)=>Number(a===selected)-Number(b===selected))){
      if(!v.field.corners)continue;
      const [x]=xy(center(v));
      const verts=v.field.corners.map(q=>{const [a,b]=xy(q);return [a+Math.round((x-a)/period)*period,b];});
      for(const shift of [-period,0,period])drawFootprintImage(c,v.id,verts.map(([a,b])=>[a+shift,b]),imageLoaded);
    }
  }
  hit=[];const boxes=[];
  for(const v of [...items].sort((a,b)=>Number(b===selected)-Number(a===selected))){
    const pt=center(v);if(!pt)continue;
    const [x,y]=xy(pt),active=v===selected,other=v===peer;
    c.strokeStyle=active?'#ffdb94':other?'#f4a5d0':'#99dfeb';c.fillStyle=active?'#f9cd721f':other?'#ea7bb326':'#90dbe81c';c.lineWidth=active||other?2:1.3;
    if(v.field.corners){
      path(v.field.corners,true);
      const polygon=new Path2D();
      const verts=v.field.corners.map(q=>{
        const [a,b]=xy(q);return [a+Math.round((x-a)/period)*period,b];
      });
      for(const shift of [-period,0,period]){
        verts.forEach(([a,b],i)=>i?polygon.lineTo(a+shift,b):polygon.moveTo(a+shift,b));polygon.closePath();
      }
      hit.push({x,y,v,polygon});
    }
    else{c.beginPath();c.moveTo(x-5,y);c.lineTo(x+5,y);c.moveTo(x,y-5);c.lineTo(x,y+5);c.stroke();}
    if(x<0||x>w||y<0||y>h)continue;
    c.fillStyle=c.strokeStyle;c.beginPath();c.arc(x,y,active?3.5:2.5,0,2*Math.PI);c.fill();if(!v.field.corners)hit.push({x,y,v});
    if(!$('atlas-labels').checked)continue;
    const text=[displayId(v),v.session_name].filter(Boolean).join(' · ');
    c.font='12px Segoe UI';const len=c.measureText(text).width+10;
    for(const dy of [-22,5,25,-42]){
      const bx=clamp(x+6,2,Math.max(2,w-len-2)),by=y+dy;
      if(by<1||by+18>h||boxes.some(b=>bx<b.x+b.w&&bx+len>b.x&&by<b.y+19&&by+19>b.y))continue;
      boxes.push({x:bx,y:by,w:len});c.fillStyle='#080d19e3';c.fillRect(bx,by,len,18);c.fillStyle=c.strokeStyle;c.fillText(text,bx+5,by+13);break;
    }
  }
  $('atlas-scale').value=Math.log2(zoom);
}
function info(v){return [v.date?.slice(0,10),v.published?'':t('unpublished'),t('atlas_'+v.field.kind)].filter(Boolean).join(' · ');}
function render(){
  setLanguage(language);document.title=t('collectionAtlas')+' · AstroWeb';
  $('atlas-status').textContent=failed?t('network_error'):items.length?String(items.length)+' '+t('captures').toLowerCase():t('emptyAtlas');
  $('atlas-list').replaceChildren();
  for(const item of items){
    const btn=document.createElement('button');btn.type='button';btn.className='atlas-row';btn.setAttribute('aria-pressed',String(item===selected));
    const title=document.createElement('strong');title.textContent=label(item);
    const meta=document.createElement('small');meta.textContent=info(item);btn.append(title,meta);btn.onclick=()=>select(item);$('atlas-list').append(btn);
  }
  $('atlas-detail').hidden=!selected;
  if(selected){
    $('atlas-title').textContent=label(selected);$('atlas-meta').textContent=info(selected);
    $('atlas-open').href='/viewer/'+encodeURIComponent(selected.id)+'#original';
    $('atlas-compare').hidden=items.length<2;
    const choices=$('atlas-peer');choices.replaceChildren(new Option(t('chooseCapture'),''));
    for(const v of items.filter(v=>v!==selected))choices.add(new Option(label(v),v.id));
    choices.value=peer?.id||'';$('atlas-pair').replaceChildren();
    for(const v of [selected,peer].filter(Boolean)){
        const a=document.createElement('a');a.href='/viewer/'+encodeURIComponent(v.id)+'#original';const im=new Image();im.src=posterURL(v.id);im.alt=label(v);const txt=document.createElement('span');txt.textContent=label(v);a.append(im,txt);$('atlas-pair').append(a);
    }
  }
  draw();
}
$('atlas-peer').onchange=e=>{
  peer=items.find(v=>v.id===e.target.value)||null;
  if(peer&&center(peer)&&center(selected)){
    const corners=[...(selected.field.corners||[center(selected)]),...(peer.field.corners||[center(peer)])];
    const base=center(selected)[0],xs=corners.map(v=>wrap(v[0]-base)),ys=corners.map(v=>v[1]);
    ra=base+(Math.min(...xs)+Math.max(...xs))/2;dec=(Math.min(...ys)+Math.max(...ys))/2;
    zoom=clamp(Math.min(360/Math.max(2,Math.max(...xs)-Math.min(...xs)),180/Math.max(2,Math.max(...ys)-Math.min(...ys)))*.70,1,64);
  }
  render();
};
function overview(){ra=180;dec=0;zoom=1;draw();}
$('atlas-photos').onchange=draw;
$('atlas-reset').onclick=overview;$('atlas-labels').onchange=draw;
function setZoom(value,x=0,y=0){
  const next=clamp(value,1,64);
  // x and y are fractions of the canvas measured from its centre.
  const delta=1/next-1/zoom;
  ra=(ra+360*x*delta+360)%360;
  dec=clamp(dec+180*y*delta,-90+90/next,90-90/next);
  zoom=next;
  draw();
}
$('atlas-scale').oninput=e=>setZoom(2**Number(e.target.value));
canvas.addEventListener('wheel',event=>{
  if(event.ctrlKey||!event.deltaY||drag)return;
  const rect=canvas.getBoundingClientRect();
  const unit=event.deltaMode===1?16:event.deltaMode===2?rect.height:1;
  const next=clamp(zoom*Math.exp(clamp(-event.deltaY*unit*.002,-1,1)),1,64);
  if(next===zoom)return;
  event.preventDefault();
  setZoom(next,(event.clientX-rect.left)/rect.width-.5,(event.clientY-rect.top)/rect.height-.5);
},{passive:false});
canvas.addEventListener('pointerdown',e=>{if(e.button!==0||!e.isPrimary)return;drag={id:e.pointerId,x:e.clientX,y:e.clientY,ra,dec};canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{if(!drag||drag.id!==e.pointerId||Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<4)return;ra=(drag.ra+(e.clientX-drag.x)*360/(canvas.clientWidth*zoom)+360)%360;dec=clamp(drag.dec+(e.clientY-drag.y)*180/(canvas.clientHeight*zoom),-90+90/zoom,90-90/zoom);draw();});
canvas.addEventListener('pointerup',e=>{
  if(!drag||drag.id!==e.pointerId)return;
  if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<5){
    const rect=canvas.getBoundingClientRect(),dist=p=>Math.hypot(e.clientX-rect.left-p.x,e.clientY-rect.top-p.y);
    const near=hit.slice().sort((a,b)=>dist(a)-dist(b));
    const best=near.find(p=>dist(p)<24)||near.find(p=>p.polygon&&c.isPointInPath(p.polygon,(e.clientX-rect.left)*canvas.width/rect.width,(e.clientY-rect.top)*canvas.height/rect.height));
    if(best)select(best.v);
  }
  canvas.releasePointerCapture(e.pointerId);
});
canvas.addEventListener('lostpointercapture',()=>{drag=null;});
document.querySelectorAll('[data-lang]').forEach(b=>b.onclick=()=>{setLanguage(b.dataset.lang);render();});
new ResizeObserver(draw).observe(canvas);
async function load(){
  try{
    const resp=await fetch('/api/atlas');if(!resp.ok)throw Error();
    const data=await resp.json();items=data.captures;stars=new Map(data.stars.map(([id,...values])=>[id,values]));lines=data.lines;
    const id=new URLSearchParams(location.search).get('capture');const initial=items.find(v=>v.id===id);
    if(initial){select(initial);return;}
    selected=items[0]||null; // Show the first thumbnail without zooming away from the all-sky overview.
  }catch{failed=true;}
  render();
}
setLanguage(language);load();
