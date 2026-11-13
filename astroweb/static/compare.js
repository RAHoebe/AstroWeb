import {language,local,t} from './i18n.js';
const $=id=>document.getElementById(id);
const image=$('ir-image'),windowEl=$('ir-window'),line=$('ir-line'),toggle=$('ir-toggle');
let source=null,loaded=null,pending=false,scale=null,problem=null,environment=null,selected=null;

export function setComparisonObject(id){source=id;}
export function layoutComparison(){
  const active=toggle.checked&&loaded&&image.naturalWidth;
  windowEl.hidden=line.hidden=!active;
  if(!active)return;
  const cut=Number($('ir-split').value);
  windowEl.style.clipPath='inset(0 '+(100-cut)+'% 0 0)';
  line.style.left=cut+'%';
  const original=$('viewer-original');
  image.style.width=original.style.width;image.style.height=original.style.height;
  image.style.transform=original.style.transform;
}
function moveWipe(event){
  const box=$('original-stage').getBoundingClientRect();
  $('ir-split').value=Math.max(0,Math.min(100,100*(event.clientX-box.left)/box.width));
  layoutComparison();
}
line.addEventListener('pointerdown',e=>{
  if(!e.isPrimary||e.button!==0)return;
  e.stopPropagation();line.setPointerCapture(e.pointerId);moveWipe(e);
});
line.addEventListener('pointermove',e=>{if(line.hasPointerCapture(e.pointerId))moveWipe(e);});
line.addEventListener('dblclick',e=>e.stopPropagation());
export function comparisonText(){
  $('ir-status').textContent=problem?t(problem):pending?t('irLoading'):scale!==null?
    '3.4 / 4.6 / 22 μm · '+Number(scale).toLocaleString(language,{maximumFractionDigits:2})+' '+t('irScale'):'';
  if(environment)drawEnvironment();
}
async function toggleComparison(){
  $('ir-controls').hidden=!toggle.checked;
  layoutComparison();
  if(!toggle.checked||pending||loaded||!source)return;
  pending=true;problem=null;comparisonText();
  let url;
  try{
    const response=await fetch('/media/'+encodeURIComponent(source)+'/allwise');
    if(!response.ok){const error=await response.json();throw Error(error.error);}
    const sampling=Number(response.headers.get('X-Arcsec-Per-Pixel'));
    url=URL.createObjectURL(await response.blob());
    image.src=url;await image.decode();loaded=url;scale=sampling;
  }catch(e){
    if(url)URL.revokeObjectURL(url);
    problem=e.message==='comparison_missing'?e.message:'comparison_unavailable';
  }finally{pending=false;comparisonText();layoutComparison();}
}
toggle.addEventListener('change',toggleComparison);
$('ir-split').addEventListener('input',layoutComparison);

export async function openEnvironment(id){
  if(!environment){
    try{
      const resp=await fetch('/api/objects/'+encodeURIComponent(id)+'/environment');
      if(!resp.ok)throw Error();
      environment=await resp.json();selected=environment.target;
    }catch{$('environment-info').textContent=t('network_error');return;}
  }
  drawEnvironment();
}
function link(text,url){
  const a=document.createElement('a');a.textContent=text+' ↗';a.href=url;a.target='_blank';a.rel='noopener';return a;
}
function drawEnvironment(){
  const data=environment,map=$('environment-map'),select=$('environment-list');
  if(!data||$('environment-panel').hidden)return;
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  const W=800,H=560,unit=235/data.radius;
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  function shape(tag,attrs,text){
    const el=document.createElementNS(ns,tag);
    for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);
    if(text)el.textContent=text;svg.append(el);return el;
  }
  for(const f of [.5,1])shape('circle',{cx:400,cy:280,r:235*f,class:'env-grid'});
  shape('path',{d:'M400 30V530 M150 280H650',class:'env-grid'});
  shape('text',{x:400,y:24,class:'env-dir'},'N');
  shape('text',{x:126,y:284,class:'env-dir'},language==='nl'?'O':'E');
  shape('text',{x:22,y:535,class:'env-dir'},t('envScale')+' '+data.radius.toLocaleString(language,{maximumFractionDigits:2})+'°');
  if(data.outline.length)shape('polygon',{class:'env-footprint',points:data.outline.map(([x,y])=>(400+x*unit)+','+(280+y*unit)).join(' ')});
  select.replaceChildren();const boxes=[];
  const sorted=[...data.objects].sort((a,b)=>Number(b.id===selected)-Number(a.id===selected));
  for(const obj of data.objects)select.add(new Option(local(obj)===obj.id?obj.id:obj.id+' · '+local(obj),obj.id));
  select.value=selected;
  for(const obj of sorted){
    const x=400+obj.offset[0]*unit,y=280+obj.offset[1]*unit,active=obj.id===selected;
    const mark=shape('circle',{cx:x,cy:y,r:active?7:4,class:'env-mark '+(active?'active':''),role:'button',tabindex:0,'aria-label':obj.id});
    const pick=()=>{selected=obj.id;drawEnvironment();select.focus({preventScroll:true});};
    mark.addEventListener('click',pick);mark.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}});
    if(active||!boxes.some(([bx,by])=>Math.abs(bx-x)<75&&Math.abs(by-y)<18)){
      shape('text',{x:x+10,y:y-6,class:'env-label'},obj.id);boxes.push([x,y]);
    }
  }
  map.replaceChildren(svg);
  const obj=data.objects.find(o=>o.id===selected),info=$('environment-info');
  const relation={target:'envTarget',satellite:'envSatellite',interacting:'envInteracting',projected:'envProjected'};
  const format=n=>n.toLocaleString(language,{maximumFractionDigits:3});
  const p=document.createElement('p');p.textContent=[local(obj.type),t(relation[obj.relation]),t('envAngle')+' '+format(obj.angle)+'°'].join(' · ');
  info.replaceChildren(p);
  const distance=document.createElement('p');
  distance.textContent=obj.distance?t('envDistance')+' ≈ '+format(obj.distance*1e6)+' '+t('lightYears'):t('envUnknown');info.append(distance);
  info.append(link('NASA/IPAC NED',obj.source));
  if(obj.distance_source)info.append(link(t('distanceSource'),obj.distance_source));
  if(obj.relation_source&&obj.relation_source!==obj.distance_source)info.append(link('NASA',obj.relation_source));
}
$('environment-list').addEventListener('change',e=>{selected=e.target.value;drawEnvironment();});
