import {language,local,setLanguage,t,formatDate} from './i18n.js';
import {enablePinch} from './pinch.js';
import {SpaceStars} from './space-gl.js';
import {spaceLayout,starPoint,distanceScaffold,lightJourney} from './distance-scenes.js';

const $=id=>document.getElementById(id), query=new URLSearchParams(location.search);
const tv=query.get('tv')==='1', reduced=matchMedia('(prefers-reduced-motion: reduce)');
const embedded=query.get('embed')==='1',calendarPage=location.pathname==='/calendar';
document.body.classList.toggle('tv',tv);
document.body.classList.toggle('embedded',embedded);document.body.classList.toggle('calendar-page',calendarPage);
if(['nl','en'].includes(query.get('lang')))setLanguage(query.get('lang'));
const modes=['mosaic','space','cosmic','planner','solar'];
const cards=[...document.querySelectorAll('.mode-card')];
const surface=$('obs-surface'),canvas=$('obs-canvas'),ctx=canvas.getContext('2d'),glCanvas=$('obs-gl');
// Calendar, solar and mosaic views do not need to reserve a WebGL context.
let gpu=null,gpuAttempted=false;
glCanvas.addEventListener('webglcontextlost',()=>{gpu=null;gpuAttempted=true;glCanvas.hidden=true;schedule();});
let captures=[],capture=null,mode=null,data=null,images={},modeIndex=0,frameIndex=0,referenceIndex=0;
let generation=0,aborter=null,pollTimer=0,frame=0,lastTime=0,lastReadout=0,clock=0,playing=false,active=true;
let zoom=1,targetZoom=1,pan=[.5,.5],targetPan=[.5,.5],progress=0,targetProgress=0,orbit=0,rotation=0,selectedDay=0;
let drag=null,dragMoved=false,selectedStar=null,forceRetry=false;
let statusKey='',statusError=false;
let solarMarker=null,solarProjection=null,solarMenu=-1,solarPicking=false,pointRequest=0,solarStatusTimer=0;
let solarLandmark=null;
let calendarTarget='',dayView=false,photoIndex=0,calendarInitial=true,requestedDay=null;
let calendarRestore=null;
try{if(tv&&calendarPage)calendarRestore=JSON.parse(localStorage.getItem('astroweb-calendar-position'));}catch{}
if(query.has('day')||(query.has('month')&&query.get('month')!==calendarRestore?.month))calendarRestore=null;
let calendarMonthData=null,calendarMonthLanguage=null,calendarDayData=null,calendarDayIndex=-1,calendarDayLanguage=null;
try{const p=JSON.parse(localStorage.getItem('astroweb-solar-landmark'));if(p&&Number.isFinite(p.lat)&&Number.isFinite(p.lon)&&typeof p.epoch==='string')solarLandmark=p;}catch{}
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const ease=n=>{n=clamp(n,0,1);return n*n*(3-2*n);};
const currentName=()=>capture?local(capture.name):'';
const number=(value,digits=1)=>new Intl.NumberFormat(language,{maximumFractionDigits:digits}).format(value);
const count=value=>new Intl.NumberFormat(language,{notation:'compact',maximumFractionDigits:2}).format(value);
const dateLabel=value=>value?formatDate(value.slice(0,10)+'T12:00:00Z',{timeZone:'UTC'}) :t('unknownDate');
const captureLabel=c=>local(c.name)+' · '+dateLabel(c.date);
const label=mode=>t('obs_'+mode);
const textNode=(tag,text,cls)=>{const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;};
function route(value){
  if(calendarPage){const params=new URLSearchParams(location.search);params.delete('capture');params.delete('mode');params.set('month',$('obs-month').value);if(dayView&&data?.days[selectedDay])params.set('day',data.days[selectedDay].date);else params.delete('day');if(calendarTarget)params.set('target',calendarTarget);else params.delete('target');history.replaceState(null,'',location.pathname+'?'+params);if(data)localStorage.setItem('astroweb-calendar-position',JSON.stringify({month:data.month,day:data.days[selectedDay]?.date,dayView,photoIndex,target:calendarTarget}));return;}
  if(!capture)return;const params=new URLSearchParams(location.search);params.set('capture',capture.id);
  if(value)params.set('mode',value);else params.delete('mode');
  if(value==='planner')params.set('month',$('obs-month').value);else params.delete('month');
  if(params.has('lang'))params.set('lang',language);
  history.replaceState(null,'',location.pathname+'?'+params);
}

function message(text,error=false,key=''){
  statusKey=key;statusError=error;
  $('obs-loading').hidden=!text;$('obs-status').textContent=text;
  $('obs-loading').classList.toggle('failed',error);$('obs-retry').hidden=!error;
}
async function json(url,signal){
  const response=await fetch(url,{signal});
  if(!response.ok){let value;try{value=await response.json();}catch{}throw Error(value?.error||'network_error');}
  return response.json();
}
function image(url){
  return new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=()=>reject(Error('obs_image_error'));i.src=url;});
}
function hub(){
  generation++;aborter?.abort();clearTimeout(pollTimer);playing=false;data=null;images={};mode=null;
  document.body.dataset.mode='';$('obs-hub').hidden=false;$('obs-scene').hidden=true;glCanvas.hidden=true;
  delete document.body.dataset.ready;
  document.body.classList.remove('obs-full');
  solarMenu=-1;solarPicking=false;$('obs-solar-options').hidden=true;
  route(null);
  if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});
  selectCard(modeIndex);schedule();
}
function selectCard(index){
  modeIndex=(index+modes.length)%modes.length;
  cards.forEach((c,i)=>{c.classList.toggle('selected',i===modeIndex);c.setAttribute('aria-current',String(i===modeIndex));});
  if(tv)$('obs-hub-help').textContent=t('obs_tv_hub');
}
function selectCapture(id){
  capture=captures.find(c=>c.id===id)||captures[0];
  if(!capture)return;
  $('obs-capture').value=capture.id;$('obs-backdrop').src=capture.poster;
  if(query.has('capture')&&!calendarPage){const link=$('obs-return');link.href='/viewer/'+encodeURIComponent(capture.id);link.dataset.i18n='obs_return_capture';link.textContent=t('obs_return_capture');}
  for(const card of cards){
    const available=!!capture.features[card.dataset.mode];card.setAttribute('aria-disabled',String(!available));
    card.querySelector('.card-state').textContent=t(available?'obs_available':'obs_not_available');
  }
  $('obs-hub-status').textContent='';
  if(!mode&&!capture.features[modes[modeIndex]])selectCard(Math.max(0,modes.findIndex(m=>capture.features[m])));
  route(mode);
  if(mode)open(mode);
}
function sceneText(){
  if(!mode)return;
  $('obs-scene-title').textContent=calendarPage?t('captureCalendar'):label(mode);$('obs-object').textContent=mode==='mosaic'&&data?mosaicDates():capture?captureLabel(capture):'';
  $('obs-open').href='/viewer/'+encodeURIComponent(data?.captures?.[frameIndex]?.id||capture?.id||'');
  $('obs-progress-name').textContent=t(mode==='space'?'obs_depth':mode==='cosmic'?'obs_time_progress':'obs_mosaic_focus');
  $('obs-note').textContent=t('obs_'+mode+'_note');
  if(mode==='planner'&&data){$('obs-note').textContent=t(data.kind==='collection'?'calendarCollectionNote':'obs_planner_note')+' '+t(data.default_site?'obs_default_site':'obs_capture_site');}
  if(mode==='solar'&&data)$('obs-note').textContent+=' '+t(data.day_only?'obs_date_only':'obs_solar_time');
  if(mode==='cosmic'&&data)$('obs-note').textContent+=' '+t(data.method==='redshift'?'obs_redshift_note':'obs_distance_note');
  $('obs-remote-help').textContent=mode==='planner'?t(dayView?'calendarTvDay':'calendarTvMonth'):t('obs_tv_'+mode);
  if(mode==='solar'&&solarPicking)$('obs-remote-help').textContent=t('obs_tv_solar_pick');
  if(data){const ref=mode==='solar'?data.references[referenceIndex]:null;$('obs-remote-help').textContent+='\n'+(ref?.credit||data.source||'');}
  $('obs-credit').replaceChildren();
  const credits=mode==='solar'?data?.references||[]:[{credit:mode==='cosmic'?t('obs_distance_source'):data?.source,source:mode==='cosmic'?data?.source:mode==='space'?'https://www.cosmos.esa.int/web/gaia/dr3':mode==='mosaic'?'https://reproject.readthedocs.io/en/stable/':'https://astroplan.readthedocs.io/en/stable/'}];
  for(const credit of credits){
    if(!credit.credit)continue;
    const a=textNode('a',credit.credit+' ↗');
    if(/^https:\/\//.test(credit.source||'')){a.href=credit.source;a.target='_blank';a.rel='noopener';}
    $('obs-credit').append(a,document.createTextNode(' '));
  }
  $('obs-play').textContent=playing?'Ⅱ':'▶';$('obs-play').setAttribute('aria-label',t(playing?'atlasPause':'atlasPlay'));
}
function controls(){
  document.querySelector('.controls').hidden=false;
  const slider=['mosaic','space','cosmic'].includes(mode);
  $('obs-progress-label').hidden=!slider;$('obs-month-label').hidden=mode!=='planner';
  $('obs-target-label').hidden=!calendarPage;$('obs-today').hidden=!calendarPage;
  if(calendarPage){const select=$('obs-plan-target');select.replaceChildren(new Option(t('calendarAllCaptures'),''),...captures.filter(c=>c.features.planner).map(c=>new Option(local(c.name),c.id)));select.value=calendarTarget;}
  for(const id of ['obs-source-label','obs-grid-label','obs-rotate','obs-angle-label','obs-clear-point'])$(id).hidden=mode!=='solar';
  $('obs-clear-point').disabled=!solarLandmark;
  for(const id of ['obs-minus','obs-plus'])$(id).hidden=['planner','cosmic'].includes(mode);
  $('obs-refresh').hidden=mode!=='solar'||!data.unavailable_channels?.length;
  const details=$('obs-cosmology');details.hidden=mode!=='cosmic'||data.method!=='redshift';details.replaceChildren();
  if(!details.hidden){
    for(const [key,value,unit] of [['obs_redshift_value',data.redshift,''],['obs_angular_distance',data.angular_diameter_distance_ly,t('lightYears')],['obs_luminosity_distance',data.luminosity_distance_ly,t('lightYears')],['obs_comoving_distance',data.comoving_distance_ly,t('lightYears')]]){
      const cell=document.createElement('div');cell.append(textNode('dt',t(key)),textNode('dd',(key==='obs_redshift_value'?number(value,5):count(value))+' '+unit));details.append(cell);
    }
  }
  if(mode==='solar'){
    const list=$('obs-solar-source');list.replaceChildren(...(data.references||[]).map((r,i)=>new Option(r.name,String(i))));
    list.disabled=!data.references?.length;list.value=String(referenceIndex);
  }
}
async function open(value,keepPlaying=false){
  if(!capture&&!calendarPage)return;
  if(!calendarPage&&!capture.features[value]){if(embedded){mode=value;$('obs-hub').hidden=true;$('obs-scene').hidden=false;message(t('obs_unavailable_'+value),true,'obs_unavailable_'+value);}else $('obs-hub-status').textContent=t('obs_unavailable_'+value);return;}
  generation++;const version=generation;aborter?.abort();aborter=new AbortController();clearTimeout(pollTimer);
  mode=value;data=null;images={};playing=keepPlaying;clock=0;selectedStar=null;zoom=targetZoom=1;pan=targetPan=[.5,.5];progress=targetProgress=0;orbit=0;
  route(mode);
  solarMarker=null;solarProjection=null;solarMenu=-1;solarPicking=false;$('obs-solar-options').hidden=true;$('obs-solar-status').textContent='';
  document.body.dataset.mode=mode;$('obs-hub').hidden=true;$('obs-scene').hidden=false;glCanvas.hidden=true;
  delete document.body.dataset.ready;
  $('obs-calendar').hidden=true;$('obs-readouts').replaceChildren();
  document.querySelector('.controls').hidden=true;$('obs-cosmology').hidden=true;
  $('obs-progress').value=0;sceneText();message(t('obs_preparing_'+mode),false,'obs_preparing_'+mode);schedule();
  const params=new URLSearchParams({month:$('obs-month').value});
  if(calendarPage&&calendarTarget)params.set('capture',calendarTarget);else if(!calendarPage)params.set('capture',capture.id);
  if(forceRetry){params.set('retry','1');forceRetry=false;}
  async function poll(){
    try{
      const endpoint=calendarPage&&!calendarTarget?'/api/calendar':'/api/observatory/'+value;
      const result=await json(endpoint+'?'+params,aborter.signal);
      params.delete('retry');if(version!==generation)return;
      if(result.status==='error')throw Error(result.error);
      if(result.status!=='ready'){const key=result.status==='busy'?'obs_busy':'obs_preparing_'+value;message(t(key),false,key);pollTimer=setTimeout(poll,1200);return;}
      const next=result.data,urls=calendarPage?{}:{photo:capture.poster};
      if(value==='mosaic')urls.mosaic=next.image;
      if(value==='space'){urls.plane=next.plane;urls.stars=next.atlas;}
      if(value==='solar'){urls.own=next.own.image;next.references.forEach((r,i)=>urls['reference'+i]=r.image);}
      const loaded=Object.fromEntries(await Promise.all(Object.entries(urls).map(async([k,url])=>[k,await image(url)])));
      if(version!==generation)return;
      data=next;images=loaded;frameIndex=Math.max(0,next.captures?.findIndex(c=>c.id===capture?.id)||0);referenceIndex=0;
      if(value==='space'){
        if(!gpuAttempted){gpuAttempted=true;try{gpu=new SpaceStars(glCanvas);}catch{gpu=null;}}
        const blend=next.blend==='screen'?'screen':'plus-lighter';
        const available=gpu&&CSS.supports('mix-blend-mode',blend)&&gpu.set(next,images.stars);
        glCanvas.style.mixBlendMode=blend;glCanvas.hidden=!available;
      }
      if(value==='planner'){
        if(calendarInitial){const restored=query.get('day')||calendarRestore?.day,recent=(next.events||[]).map(e=>e.day).sort().at(-1),restoredIndex=next.days.findIndex(d=>d.date===restored);selectedDay=restoredIndex>=0?restoredIndex:Math.max(0,next.days.findIndex(d=>d.date===(recent||next.best[0])));dayView=calendarPage&&restoredIndex>=0&&!!(query.get('day')||calendarRestore?.dayView);photoIndex=Math.max(0,Number(calendarRestore?.photoIndex)||0);calendarRestore=null;calendarInitial=false;}
        if(requestedDay?.startsWith(next.month)){selectedDay=Math.max(0,next.days.findIndex(d=>d.date===requestedDay));requestedDay=null;dayView=false;}
        selectedDay=clamp(selectedDay,0,next.days.length-1);renderCalendar();
      }
      controls();sceneText();message('');schedule();
      if(value==='space'&&reduced.matches){progress=targetProgress=1;}
      if(['space','cosmic'].includes(value)&&!reduced.matches){playing=true;sceneText();schedule();}
      if(value==='solar'&&solarLandmark)refreshMarker();
      document.body.dataset.ready=value;
      if(!tv)surface.focus({preventScroll:true});
    }catch(error){if(error.name!=='AbortError'&&version===generation){playing=false;message(t(error.message),true,error.message);sceneText();if(error.message==='gaia_depth_unavailable')pollTimer=setTimeout(()=>{if(version===generation&&active&&!document.hidden)open(value);},65000);}}
  }
  poll();
}

function dimensions(){
  const w=surface.clientWidth,h=surface.clientHeight;
  const r=Math.min(devicePixelRatio||1,tv?1.5:2,2560/Math.max(w,h));
  for(const c of [canvas,glCanvas])if(c.width!==Math.round(w*r)||c.height!==Math.round(h*r)){c.width=Math.round(w*r);c.height=Math.round(h*r);}
  ctx.setTransform(r,0,0,r,0,0);return [w,h];
}
function fit(image,w,h,scale=1){const f=Math.min(w/image.width,h/image.height)*scale;return [image.width*f,image.height*f];}
function picture(image,w,h,scale=1,alpha=1){const [iw,ih]=fit(image,w,h,scale);ctx.globalAlpha=alpha;ctx.drawImage(image,(w-iw)/2,(h-ih)/2,iw,ih);ctx.globalAlpha=1;}
function readouts(items){
  const host=$('obs-readouts'),signature=JSON.stringify(items);
  if(host.dataset.signature===signature&&host.childElementCount===items.length)return;
  host.dataset.signature=signature;
  host.replaceChildren(...items.map(([large,small])=>{const e=document.createElement('div');e.className='readout';e.append(textNode('strong',large),textNode('small',small));return e;}));
}
function mosaicDates(){return [...new Set((data?.captures||[]).map(c=>c.date?.slice(0,10)).filter(Boolean))].sort().map(dateLabel).join(' · ');}
function mosaicCamera(){
  const current=data.captures[frameIndex],corners=current.corners;
  const x=corners.map(p=>p[0]),y=corners.map(p=>p[1]);
  targetPan=[.5+(Math.min(...x)+Math.max(...x)-1)/2*targetProgress,.5+(Math.min(...y)+Math.max(...y)-1)/2*targetProgress];
  targetZoom=1+(Math.max(1,Math.min(8,.9/Math.max(Math.max(...x)-Math.min(...x),Math.max(...y)-Math.min(...y))))-1)*targetProgress;
}
function drawMosaic(w,h){
  ctx.save();if(tv&&images.mosaic.height>images.mosaic.width){ctx.translate(w/2,h/2);ctx.rotate(-Math.PI/2);[w,h]=[h,w];ctx.translate(-w/2,-h/2);}
  const image=images.mosaic,[iw,ih]=fit(image,w,h,zoom),left=w/2-pan[0]*iw,top=h/2-pan[1]*ih;
  ctx.drawImage(image,left,top,iw,ih);
  if(targetProgress>.02){
    const frame=data.captures[frameIndex];ctx.beginPath();frame.corners.forEach(([x,y],i)=>i?ctx.lineTo(left+x*iw,top+y*ih):ctx.moveTo(left+x*iw,top+y*ih));ctx.closePath();
    ctx.strokeStyle='#ed998a99';ctx.lineWidth=1;ctx.stroke();
  }
  ctx.restore();
}
let spaceView=null;
function drawSpace(w,h){
  const turn=tv&&data.height>data.width?-Math.PI/2:0;
  spaceView=spaceLayout(data,w,h,zoom,orbit,progress,turn);
  ctx.save();
  const fade=spaceView.unfold;
  if(fade<1){
    ctx.globalAlpha=1-fade;
    if(turn){ctx.translate(w/2,h/2);ctx.rotate(turn);ctx.translate(-h/2,-w/2);picture(images.photo,h,w,zoom,1-fade);}
    else picture(images.photo,w,h,zoom,1-fade);
    ctx.restore();ctx.save();
  }
  distanceScaffold(ctx,data,spaceView,images.plane,t,number);
  const alpha=ease((fade-.08)/.7);
  if(!glCanvas.hidden&&gpu?.ready){glCanvas.style.opacity=String(alpha);gpu.draw(data,spaceView);}
  else {
    ctx.save();ctx.globalCompositeOperation=data.blend==='screen'?'screen':'lighter';ctx.globalAlpha=alpha;
    for(const star of data.stars){
      const p=starPoint(spaceView,star);if(!p)continue;
      const sw=Math.max(3,Math.min(30,star.width*spaceView.fit[0])),sh=Math.max(3,Math.min(30,star.height*spaceView.fit[1]));
      ctx.drawImage(images.stars,...star.atlas,p[0]-sw/2,p[1]-sh/2,sw,sh);
    }ctx.restore();
  }
  if(selectedStar){const p=starPoint(spaceView,selectedStar);if(p){ctx.strokeStyle='#ed998a';ctx.beginPath();ctx.arc(...p,10,0,Math.PI*2);ctx.stroke();}}
  ctx.restore();
}
function drawCosmic(w,h){
  lightJourney(ctx,data,images.photo,progress,w,h,t,count,dateLabel(data.capture?.date));
}
function solarPanel(image,calibration,bounds,turn=0){
  const [x,y,w,h]=bounds;ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();
  let cx=x+w/2,cy=y+h/2,iw,ih;
  if(calibration?.radius){
    const radius=Math.min(w,h)*.41*zoom;const rx=calibration.radius[0],ry=calibration.radius[1];iw=radius/rx;ih=radius/ry;
  }else [iw,ih]=fit(image,w,h,zoom*.9);
  cx-=(pan[0]-.5)*Math.min(w,h)*zoom;cy-=(pan[1]-.5)*Math.min(w,h)*zoom;
  const center=calibration?.center||[.5,.5];
  ctx.translate(cx,cy);ctx.rotate(turn);ctx.drawImage(image,-center[0]*iw,-center[1]*ih,iw,ih);ctx.restore();
  return {cx,cy,iw,ih,center};
}
function drawSolar(w,h){
  const top=55,bottom=h-65,bounds=[[0,top,w/2,bottom-top],[w/2,top,w/2,bottom-top]];
  solarPanel(images.own,data.own,bounds[0],rotation*Math.PI/180);
  const reference=data.references[referenceIndex];
  if(reference){
    const pos=solarPanel(images['reference'+referenceIndex],reference.grid,bounds[1]);
    solarProjection={...pos,bounds:bounds[1]};
    if($('obs-grid').checked){
      ctx.save();ctx.beginPath();ctx.rect(...bounds[1]);ctx.clip();ctx.lineWidth=.75;ctx.strokeStyle='#ed998a88';
      for(const line of reference.grid.lines){let pen=false;ctx.beginPath();for(const p of line){if(!p){pen=false;continue;}const x=pos.cx+(p[0]-pos.center[0])*pos.iw,y=pos.cy+(p[1]-pos.center[1])*pos.ih;if(pen)ctx.lineTo(x,y);else ctx.moveTo(x,y);pen=true;}ctx.stroke();}ctx.restore();
    }
    ctx.save();ctx.beginPath();ctx.rect(...bounds[1]);ctx.clip();
    if(solarMarker?.visible){const x=pos.cx+(solarMarker.x-pos.center[0])*pos.iw,y=pos.cy+(solarMarker.y-pos.center[1])*pos.ih;ctx.strokeStyle='#ffddbc';ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(x,y,9,0,Math.PI*2);ctx.moveTo(x-14,y);ctx.lineTo(x+14,y);ctx.moveTo(x,y-14);ctx.lineTo(x,y+14);ctx.stroke();}
    if(solarPicking){const x=w*.75,y=(top+bottom)/2;ctx.strokeStyle='#ffefe6';ctx.lineWidth=1;ctx.beginPath();ctx.arc(x,y,12,0,Math.PI*2);ctx.moveTo(x-22,y);ctx.lineTo(x+22,y);ctx.moveTo(x,y-22);ctx.lineTo(x,y+22);ctx.stroke();}
    ctx.restore();
  }else{
    ctx.fillStyle='#dcc0b8';ctx.textAlign='center';ctx.font='14px Segoe UI,Arial';ctx.fillText(t('obs_no_reference'),w*.75,h*.5);
  }
  ctx.strokeStyle='#ed998a33';ctx.beginPath();ctx.moveTo(w/2,top);ctx.lineTo(w/2,bottom);ctx.stroke();
}
function updateReadouts(){
  if(!data)return;
  if(mode==='mosaic'){
    const selected=data.captures[frameIndex];readouts([[data.captures.length+' '+t('obs_panels'),mosaicDates()],[local(selected.name),t('obs_selected_panel')+' · '+dateLabel(selected.date)]]);
    $('obs-open').href='/viewer/'+encodeURIComponent(selected.id);
  }else if(mode==='space'){
    const star=selectedStar;
    readouts([[number((star?.distance_pc||data.reference_pc)*3.2615638)+' '+t('lightYears'),star?'Gaia DR3 '+star.id+' · ± '+number(star.error_pc*3.2615638)+' '+t('lightYears'):t('obs_median_distance')],
      [data.measured_count+' '+t('gaiaStars'),t('obs_distance_layers')+' · '+number(zoom)+'×']]);
  }else if(mode==='cosmic'){
    const remaining=data.lookback_years*(1-progress);
    const items=[[count(data.lookback_years)+' '+t('obs_years'),t('obs_total_lighttime')],[progress>.999?t('obs_light_arrived'):count(remaining)+' '+t('obs_years'),t(progress>.999?'obs_recorded_on':'obs_light_remaining')]];
    if(data.age_at_emission_years)items.push([count(data.age_at_emission_years)+' '+t('obs_years'),t('obs_universe_age')]);
    readouts(items);
  }else if(mode==='solar'){
    const ref=data.references[referenceIndex];
    const items=[[t('obs_own_sun'),t(data.own.radius?'obs_unknown_north':'obs_solar_detail')+' · '+number(rotation,0)+'°'],
      [ref?.name||t('obs_reference'),ref?new Date(ref.time).toISOString().replace('T',' ').slice(0,19)+' UTC · Δ '+number(ref.delta_seconds,0)+' s':t('obs_no_reference')]];
    if(solarMarker)items.push([number(solarMarker.lat)+'° / '+number(solarMarker.lon)+'°',t(solarMarker.visible?'obs_tracked_surface':'obs_backside')]);
    readouts(items);
    if(tv)$('obs-remote-help').textContent=t(solarPicking?'obs_tv_solar_pick':'obs_tv_solar')+'\n'+(ref?.credit||data.source);
  }
}
function dayEvents(){
  const day=data?.days[selectedDay]?.date;return (data?.events||[]).filter(e=>e.day===day).sort((a,b)=>a.time&&b.time?new Date(a.time)-new Date(b.time):a.time?-1:b.time?1:a.id.localeCompare(b.id));
}
function photoHref(event){
  const params=new URLSearchParams({from:'calendar',month:data.month,day:data.days[selectedDay].date});if(calendarTarget)params.set('target',calendarTarget);return '/viewer/'+encodeURIComponent(event.id)+'?'+params+'#original';
}
function eventImage(event){
  const img=document.createElement('img');img.src=event.poster;img.alt=local(event.name);img.loading='lazy';return img;
}
function eventName(event){const id=(event.catalog_id||'').replace(/[^a-z0-9]/gi,'').toLowerCase(),name=local(event.name);return name.split('·').map(v=>v.trim()).filter(v=>v.replace(/[^a-z0-9]/gi,'').toLowerCase()!==id).join(' · ')||name;}
function nightText(day){
  const fmt=stamp=>new Intl.DateTimeFormat(language,{hour:'2-digit',minute:'2-digit',timeZone:data.timezone}).format(new Date(stamp*1000));
  const windows=day.windows.map(([a,b])=>fmt(a)+'–'+fmt(b)).join(' · ');
  return (windows||t(day.dark_hours===0?'obs_no_darkness':'obs_no_window'))+' · '+data.timezone+' · '+t('obs_moon_light')+' '+Math.round(day.moon_illumination*100)+'%'+(day.peak_altitude!==null?' · '+t('altitude')+' '+number(day.peak_altitude)+'°':'');
}
function selectCalendarDay(index,openDay=false){
  selectedDay=clamp(index,0,data.days.length-1);photoIndex=0;dayView=openDay;
  renderCalendar();route(mode);
}
function renderCalendar(){
  if(!data||mode!=='planner')return;
  $('obs-calendar').hidden=false;
  document.body.classList.toggle('calendar-day-view',dayView);
  const [year,month]=data.month.split('-').map(Number);
  $('obs-calendar-title').textContent=new Intl.DateTimeFormat(language,{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(Date.UTC(year,month-1,15)));
  $('obs-calendar-legend').hidden=dayView;$('obs-calendar-legend').textContent=t(data.kind==='collection'?'calendarLegend':'calendarTargetLegend')+(data.kind==='collection'?'':' · '+(local(data.capture?.name)||''));
  $('obs-calendar-month').hidden=dayView;$('obs-calendar-day').hidden=!dayView;
  const day=data.days[selectedDay],events=dayEvents();
  if(dayView){
    const refresh=calendarDayData!==data||calendarDayIndex!==selectedDay||calendarDayLanguage!==language;
    if(refresh){
      $('obs-day-title').textContent=dateLabel(day.date);
      const host=$('obs-day-photos');host.replaceChildren();
      photoIndex=clamp(photoIndex,0,Math.max(0,events.length-1));
      events.forEach((event,i)=>{
        const a=document.createElement('a');a.href=photoHref(event);a.className='day-photo';a.classList.toggle('selected',i===photoIndex);
        a.append(eventImage(event),textNode('strong',eventName(event)));if(eventName(event).replace(/[^a-z0-9]/gi,'').toLowerCase()!==event.catalog_id.replace(/[^a-z0-9]/gi,'').toLowerCase())a.append(textNode('span',event.catalog_id.replace('_',' ')));
        const actual=event.time?new Date(event.time):null;
        if(actual&&Number.isFinite(actual.getTime()))a.append(textNode('small','DATE-OBS · '+new Intl.DateTimeFormat(language,{dateStyle:'short',timeStyle:'short',timeZone:data.timezone}).format(actual)));
        host.append(a);
      });
      $('obs-day-empty').hidden=events.length>0;$('obs-day-night').textContent=nightText(day);
      const timeline=$('obs-day-timeline');timeline.replaceChildren();
      for(let hour=0;hour<=24;hour+=4){const tick=textNode('span',String(hour).padStart(2,'0')+':00');tick.style.left=hour/24*100+'%';timeline.append(tick);}
      for(const event of events){
        if(!event.time)continue;const time=new Date(event.time);if(!Number.isFinite(time.getTime()))continue;
        if(new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:data.timezone}).format(time)!==day.date)continue;
        const parts=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:data.timezone}).formatToParts(time);
        const hour=+parts.find(p=>p.type==='hour').value,minute=+parts.find(p=>p.type==='minute').value;
        const pin=document.createElement('a');pin.href=photoHref(event);pin.title=local(event.name)+' · DATE-OBS';pin.className='timeline-photo';pin.style.left=(hour+minute/60)/24*100+'%';pin.append(eventImage(event));timeline.append(pin);
      }
      calendarDayData=data;calendarDayIndex=selectedDay;calendarDayLanguage=language;
    }
    photoIndex=clamp(photoIndex,0,Math.max(0,events.length-1));
    $('obs-day-photos').querySelectorAll('.day-photo').forEach((a,i)=>a.classList.toggle('selected',i===photoIndex));
    if(tv)$('obs-day-photos').querySelector('.selected')?.scrollIntoView({block:'nearest',inline:'center'});
  }else{
    if(calendarMonthData!==data||calendarMonthLanguage!==language){
      const seasons=$('obs-season');seasons.replaceChildren();
      data.seasons.forEach((night,i)=>{
        const button=document.createElement('button');button.classList.toggle('current',i===month-1);
        const bar=document.createElement('i');bar.style.height=clamp(night.hours/10*35,2,35)+'px';
        const title=new Intl.DateTimeFormat(language,{month:'short',timeZone:'UTC'}).format(new Date(Date.UTC(year,i,15)));
        button.append(bar,textNode('span',title));button.title=t('obs_midmonth')+' · '+number(night.hours)+' h';
        button.addEventListener('click',()=>setMonth(year+'-'+String(i+1).padStart(2,'0')));seasons.append(button);
      });
      $('obs-weekdays').replaceChildren(...Array.from({length:7},(_,i)=>textNode('span',new Intl.DateTimeFormat(language,{weekday:'short',timeZone:'UTC'}).format(new Date(Date.UTC(2026,10,16+i))))));
      const days=$('obs-days');days.replaceChildren();const offset=(new Date(Date.UTC(year,month-1,1)).getUTCDay()+6)%7;
      for(let i=0;i<offset;i++)days.append(document.createElement('span'));
      data.days.forEach((night,i)=>{
        const cell=document.createElement('div');cell.className='calendar-day';cell.classList.toggle('selected',i===selectedDay);
        const button=document.createElement('button');button.className='day-select';button.dataset.index=i;
        button.classList.toggle('good',night.hours>0);button.classList.toggle('best',data.best.includes(night.date));button.classList.toggle('selected',i===selectedDay);
        button.append(textNode('span',String(i+1)),textNode('small',number(night.hours)+' h'));
        button.addEventListener('click',()=>selectCalendarDay(i,true));
        button.addEventListener('keydown',e=>{const d={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7}[e.key];if(d){e.preventDefault();selectCalendarDay(clamp(i+d,0,data.days.length-1));days.querySelector('[data-index="'+selectedDay+'"]').focus();}});
        cell.append(button);
        const shots=(data.events||[]).filter(e=>e.day===night.date);
        if(shots.length){
          const strip=document.createElement('div');strip.className='day-thumbs';
          shots.slice(0,2).forEach(event=>{const a=document.createElement('a');a.href='/viewer/'+encodeURIComponent(event.id)+'?'+new URLSearchParams({from:'calendar',month:data.month,day:night.date})+'#original';a.title=local(event.name);a.append(eventImage(event));strip.append(a);});
          if(shots.length>2)strip.append(textNode('span','+'+(shots.length-2)));cell.append(strip);
        }
        days.append(cell);
      });
      calendarMonthData=data;calendarMonthLanguage=language;
    }
    $('obs-days').querySelectorAll('.calendar-day').forEach((cell,i)=>{cell.classList.toggle('selected',i===selectedDay);cell.querySelector('button').classList.toggle('selected',i===selectedDay);});
    $('obs-night').textContent=dateLabel(day.date)+' · '+nightText(day);
    const preview=$('obs-day-preview');preview.replaceChildren();
    if(!events.length)preview.append(textNode('span',t('calendarNoCaptures')));
    for(const event of events){const a=document.createElement('a');a.href=photoHref(event);a.append(eventImage(event),textNode('span',local(event.name)));preview.append(a);}
  }
  if(tv)$('obs-remote-help').textContent=t(dayView?'calendarTvDay':'calendarTvMonth')+'\n'+data.source;
  route(mode);
}
function solarStatus(text){$('obs-solar-status').textContent=text;clearTimeout(solarStatusTimer);solarStatusTimer=setTimeout(()=>{$('obs-solar-status').textContent='';},4500);}
async function refreshMarker(point=null){
  if(point&&(!Number.isFinite(point.x)||!Number.isFinite(point.y)||point.x<0||point.y<0||point.x>1||point.y>1)){solarStatus(t('obs_off_sun'));return;}
  const ref=data?.references?.[referenceIndex],token=ref?.image.match(/\/observatory\/([0-9a-f]{32})\//)?.[1];
  if(!token){if(point)solarStatus(t('obs_no_reference'));return;}
  const values=point||solarLandmark;if(!values)return;
  const request=++pointRequest,version=generation;solarMarker=null;
  try{
    const result=await json('/api/observatory/solar-point/'+token+'/'+ref.channel+'?'+new URLSearchParams(values),aborter.signal);
    if(request!==pointRequest||version!==generation)return;
    solarMarker=result;solarLandmark=result.landmark;localStorage.setItem('astroweb-solar-landmark',JSON.stringify(solarLandmark));
    $('obs-clear-point').disabled=false;schedule();
  }catch(error){if(error.name!=='AbortError'&&request===pointRequest&&version===generation)solarStatus(t(error.message));}
}
function clearMarker(){solarLandmark=solarMarker=null;pointRequest++;localStorage.removeItem('astroweb-solar-landmark');$('obs-clear-point').disabled=true;schedule();}
function rotateOwn(){rotation=(rotation+90)%360;$('obs-angle').value=rotation>180?rotation-360:rotation;schedule();}
function solarOptions(){
  const host=$('obs-solar-options');host.hidden=solarMenu<0;host.replaceChildren();
  if(solarMenu<0)return;
  ['obs_rotate','obs_solar_grid','obs_pick_point','obs_clear_point','obs_compare_play','obs_reset'].forEach((key,i)=>{
    const button=textNode('button',t(key));button.classList.toggle('selected',solarMenu===i);button.addEventListener('click',()=>solarAction(i));host.append(button);
  });
}
function solarAction(index){
  solarMenu=-1;solarOptions();playing=false;
  if(index===0)rotateOwn();if(index===1)$('obs-grid').checked=!$('obs-grid').checked;
  if(index===2){if(!data.references.length)solarStatus(t('obs_no_reference'));else solarPicking=true;}
  if(index===3)clearMarker();if(index===4)play();if(index===5)reset();
  sceneText();schedule();
}
function selectSolarPoint(){
  if(!solarProjection)return;
  const p=solarProjection,[x,y,w,h]=p.bounds;
  const px=(x+w/2-p.cx)/p.iw+p.center[0],py=(y+h/2-p.cy)/p.ih+p.center[1];
  solarPicking=false;sceneText();refreshMarker({x:px,y:py});schedule();
}
function schedule(){if(!frame&&active&&!document.hidden)frame=requestAnimationFrame(tick);}
function tick(now){
  frame=0;if(!active||document.hidden||!mode)return;
  const dt=Math.min(.05,(now-(lastTime||now))/1000);lastTime=now;
  const wasMoving=Math.abs(zoom-targetZoom)+Math.abs(progress-targetProgress)+Math.hypot(pan[0]-targetPan[0],pan[1]-targetPan[1])>.0001;
  if(playing&&data){
    clock+=dt;
    if(mode==='space'){if(progress>.8)orbit+=dt*.12;targetProgress=Math.min(1,targetProgress+dt/4);}
    if(mode==='cosmic'){targetProgress=Math.min(1,targetProgress+dt/14);if(targetProgress===1){playing=false;sceneText();}}
    if(mode==='mosaic'){
      targetProgress=ease(Math.min(1,clock/2));mosaicCamera();
      if(clock>7){clock=0;frameIndex=(frameIndex+1)%data.captures.length;}
    }
    if(mode==='solar'){targetZoom=1+.35*(1-Math.cos(clock*.22));if(clock>12){clock=0;referenceIndex=(referenceIndex+1)%Math.max(1,data.references.length);$('obs-solar-source').value=String(referenceIndex);refreshMarker();}}
    if(mode==='planner'&&clock>4){clock=0;const best=data.best.map(d=>data.days.findIndex(v=>v.date===d));selectedDay=best[(best.indexOf(selectedDay)+1)%best.length]||0;renderCalendar();}
  }
  const blend=reduced.matches?1:Math.min(1,dt*10||.15);zoom+=(targetZoom-zoom)*blend;progress+=(targetProgress-progress)*blend;pan=pan.map((v,i)=>v+(targetPan[i]-v)*blend);
  const [w,h]=dimensions();ctx.fillStyle='#09060a';ctx.fillRect(0,0,w,h);
  if(data&&mode==='mosaic')drawMosaic(w,h);
  if(data&&mode==='space')drawSpace(w,h);
  if(data&&mode==='cosmic')drawCosmic(w,h);
  if(data&&mode==='solar')drawSolar(w,h);
  if(now-lastReadout>150||!playing){lastReadout=now;updateReadouts();}
  $('obs-progress').value=Math.round(targetProgress*1000);
  if(playing||wasMoving)schedule();
}

function setMonth(value){if(!/^20\d\d-(0[1-9]|1[0-2])$|^2100-(0[1-9]|1[0-2])$/.test(value))return;dayView=false;$('obs-month').value=value;open('planner',playing);}
function shiftMonth(delta){const date=new Date($('obs-month').value+'-15T12:00:00Z');date.setUTCMonth(date.getUTCMonth()+delta);setMonth(date.toISOString().slice(0,7));}
function zoomBy(factor){playing=false;if(mode==='space')targetProgress=1;targetZoom=clamp(targetZoom*factor,1,10);sceneText();schedule();}
function navigate(delta){
  if(!data)return;playing=false;
  if(mode==='mosaic'){frameIndex=(frameIndex+delta+data.captures.length)%data.captures.length;targetProgress=1;mosaicCamera();}
  if(mode==='space'){orbit+=delta*.25;targetProgress=1;}
  if(mode==='cosmic')targetProgress=clamp(targetProgress+delta*.08,0,1);
  if(mode==='solar'){referenceIndex=(referenceIndex+delta+Math.max(1,data.references.length))%Math.max(1,data.references.length);$('obs-solar-source').value=String(referenceIndex);refreshMarker();}
  if(mode==='planner'){if(dayView&&dayEvents().length){photoIndex=(photoIndex+delta+dayEvents().length)%dayEvents().length;}else selectedDay=(selectedDay+delta+data.days.length)%data.days.length;renderCalendar();}
  sceneText();schedule();
}
function reset(){playing=false;clock=0;targetProgress=0;targetZoom=1;targetPan=[.5,.5];orbit=0;rotation=0;selectedStar=null;$('obs-angle').value=0;sceneText();schedule();}
function play(){if(!data)return;playing=!playing;if(mode==='cosmic'&&targetProgress>.99)progress=targetProgress=0;sceneText();schedule();}
function full(){
  if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});
  else if(surface.requestFullscreen)surface.requestFullscreen().catch(()=>document.body.classList.toggle('obs-full'));
  else document.body.classList.toggle('obs-full');schedule();
}
function remote(command){
  if(!$('obs-startup').hidden){if(!$('obs-startup-retry').hidden&&['select','reset','toggle'].includes(command))boot();return;}
  if(!mode){
    if(command==='previous'||command==='next')selectCard(modeIndex+(command==='next'?1:-1));
    if(command==='in'||command==='out'){const i=captures.indexOf(capture);selectCapture(captures[(i+(command==='in'?-1:1)+captures.length)%captures.length]?.id);}
    if(['select','reset','toggle'].includes(command))open(modes[modeIndex]);
    return;
  }
  if(mode==='planner'){
    if(command==='previous'||command==='next'){navigate(command==='next'?1:-1);return;}
    if(command==='in'||command==='out'){if(dayView){selectedDay=clamp(selectedDay+(command==='out'?1:-1),0,data.days.length-1);photoIndex=0;renderCalendar();}else shiftMonth(command==='in'?-1:1);return;}
    if(['select','reset','toggle'].includes(command)){if(dayView){const event=dayEvents()[photoIndex];if(event)location.assign(photoHref(event));}else{dayView=true;photoIndex=0;renderCalendar();}return;}
    if(command==='home'){dayView=false;renderCalendar();return;}
  }
  if(mode==='solar'&&solarMenu>=0){
    if(['previous','next','in','out'].includes(command)){solarMenu=(solarMenu+(['next','out'].includes(command)?1:5))%6;solarOptions();}
    if(['select','reset','toggle'].includes(command))solarAction(solarMenu);
    if(command==='home'){solarMenu=-1;solarOptions();}return;
  }
  if(mode==='solar'&&solarPicking){
    if(command==='previous'||command==='next')targetPan[0]+=(command==='next'?1:-1)*.04/targetZoom;
    if(command==='in'||command==='out')targetPan[1]+=(command==='out'?1:-1)*.04/targetZoom;
    if(['select','reset','toggle'].includes(command))selectSolarPoint();
    if(command==='home'){solarPicking=false;sceneText();}schedule();return;
  }
  if(command==='home'){if(mode==='solar'&&tv){solarMenu=0;solarOptions();}else if(mode==='solar')rotateOwn();else reset();return;}
  if(['select','reset','toggle'].includes(command)){play();return;}
  if(command==='play'){if(!playing)play();return;}if(command==='pause'){playing=false;sceneText();return;}
  if(command==='previous'||command==='next')navigate(command==='next'?1:-1);
  if(command==='in'||command==='out'){if(mode==='planner')shiftMonth(command==='in'?-1:1);else if(mode==='cosmic')navigate(command==='in'?2:-2);else zoomBy(command==='in'?1.2:1/1.2);}
}
window.mapKey=remote;
window.collectionBack=()=>{if(mode==='solar'&&(solarMenu>=0||solarPicking)){solarMenu=-1;solarPicking=false;solarOptions();sceneText();schedule();return true;}if(mode==='planner'&&dayView){dayView=false;renderCalendar();return true;}if(embedded||calendarPage)return false;if(mode){hub();return true;}return false;};
window.viewActive=value=>{active=value;if(!active){cancelAnimationFrame(frame);frame=0;}else schedule();};
cards.forEach((card,i)=>{card.addEventListener('click',()=>{selectCard(i);open(card.dataset.mode);});card.addEventListener('focus',()=>selectCard(i));});
$('obs-home').addEventListener('click',hub);$('obs-capture').addEventListener('change',e=>selectCapture(e.target.value));
$('obs-prev').addEventListener('click',()=>{if(mode==='planner')selectCalendarDay((selectedDay-1+data.days.length)%data.days.length,dayView);else navigate(-1);});$('obs-next').addEventListener('click',()=>{if(mode==='planner')selectCalendarDay((selectedDay+1)%data.days.length,dayView);else navigate(1);});
$('obs-play').addEventListener('click',play);$('obs-plus').addEventListener('click',()=>zoomBy(1.2));$('obs-minus').addEventListener('click',()=>zoomBy(1/1.2));
$('obs-reset').addEventListener('click',reset);$('obs-full').addEventListener('click',full);
$('obs-month').addEventListener('change',e=>setMonth(e.target.value));
$('obs-plan-target').addEventListener('change',e=>{calendarTarget=e.target.value;open('planner');});
$('obs-day-back').addEventListener('click',()=>{dayView=false;renderCalendar();});
$('obs-today').addEventListener('click',()=>{requestedDay=new Date().toLocaleDateString('sv-SE');setMonth(requestedDay.slice(0,7));});
$('obs-progress').addEventListener('input',e=>{playing=false;targetProgress=+e.target.value/1000;if(mode==='mosaic')mosaicCamera();sceneText();schedule();});
$('obs-solar-source').addEventListener('change',e=>{playing=false;referenceIndex=+e.target.value;refreshMarker();sceneText();schedule();});
$('obs-grid').addEventListener('change',schedule);$('obs-rotate').addEventListener('click',rotateOwn);$('obs-clear-point').addEventListener('click',clearMarker);
$('obs-angle').addEventListener('input',e=>{rotation=+e.target.value;schedule();});
$('obs-retry').addEventListener('click',()=>{forceRetry=true;open(mode);});
$('obs-refresh').addEventListener('click',()=>{forceRetry=true;open(mode);});
surface.addEventListener('wheel',e=>{if(!data||mode==='planner')return;e.preventDefault();zoomBy(Math.exp(-e.deltaY*.0015));},{passive:false});
surface.addEventListener('pointerdown',e=>{if(!data||mode==='planner')return;drag={x:e.clientX,y:e.clientY,pan:[...targetPan],orbit};dragMoved=false;surface.setPointerCapture(e.pointerId);playing=false;});
surface.addEventListener('pointermove',e=>{
  if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)>4)dragMoved=true;
  if(mode==='space'){orbit=drag.orbit+dx*.005;targetProgress=1;}
  else if(mode==='mosaic'||mode==='solar'){const size=mode==='mosaic'?fit(images.mosaic,surface.clientWidth,surface.clientHeight,targetZoom):[surface.clientHeight*targetZoom,surface.clientHeight*targetZoom];targetPan=[drag.pan[0]-dx/size[0],drag.pan[1]-dy/size[1]];}
  schedule();
});
surface.addEventListener('pointerup',()=>{drag=null;});surface.addEventListener('pointercancel',()=>{drag=null;});
surface.addEventListener('click',e=>{
  if(dragMoved||!data)return;
  if(mode==='solar'&&solarProjection){
    const rect=surface.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top,p=solarProjection;
    if(x>rect.width/2)refreshMarker({x:(x-p.cx)/p.iw+p.center[0],y:(y-p.cy)/p.ih+p.center[1]});return;
  }
  if(mode==='space'&&!tv){
    const box=surface.getBoundingClientRect();
    let closest=20;
    for(const star of data.stars){const point=spaceView&&starPoint(spaceView,star);if(!point)continue;const [x,y]=point;
      const distance=Math.hypot(x-(e.clientX-box.left),y-(e.clientY-box.top));if(distance<closest){selectedStar=star;closest=distance;}}
    schedule();return;
  }
  if(mode!=='mosaic')return;
  const box=surface.getBoundingClientRect(),[w,h]=fit(images.mosaic,box.width,box.height,zoom);
  const point=[(e.clientX-box.left-box.width/2)/w+pan[0],(e.clientY-box.top-box.height/2)/h+pan[1]];
  const inside=polygon=>{let yes=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){const [xi,yi]=polygon[i],[xj,yj]=polygon[j];if((yi>point[1])!==(yj>point[1])&&point[0]<(xj-xi)*(point[1]-yi)/(yj-yi)+xi)yes=!yes;}return yes;};
  const hits=data.captures.map((f,i)=>inside(f.corners)?i:-1).filter(i=>i>=0);
  if(hits.length){frameIndex=hits[(hits.indexOf(frameIndex)+1)%hits.length];targetProgress=1;mosaicCamera();schedule();}
});
surface.addEventListener('dblclick',()=>{if(!dragMoved)full();});
enablePinch(surface,{getZoom:()=>targetZoom,begin:()=>{drag=null;playing=false;},transform:(newZoom,previous,next)=>{targetZoom=clamp(newZoom,1,10);if(mode==='mosaic'||mode==='solar')targetPan=targetPan.map((p,i)=>p-(i?next.y-previous.y:next.x-previous.x)/(surface.clientHeight*targetZoom));schedule();}});
document.addEventListener('keydown',e=>{
  if(e.target.matches('input,select'))return;
  const command={ArrowLeft:'previous',ArrowRight:'next',ArrowUp:'in',ArrowDown:'out',Enter:'select',' ':'toggle'}[e.key];
  if(command&&(tv||e.target===surface||(!mode&&e.target===document.body))){e.preventDefault();remote(command);}
  if(e.key==='Escape'&&mode&&!document.fullscreenElement){e.preventDefault();if(calendarPage&&dayView){dayView=false;renderCalendar();}else if(embedded&&parent!==window)parent.postMessage({type:'astroweb-close-exploration'},location.origin);else if(!calendarPage)hub();}
});
document.querySelectorAll('[data-lang]').forEach(b=>b.addEventListener('click',()=>{setLanguage(b.dataset.lang);translated();}));
function translated(){
  document.title='AstroWeb · '+t(calendarPage?'captureCalendar':'observatory');
  $('obs-capture').replaceChildren(...captures.map(c=>new Option(captureLabel(c),c.id)));
  if(capture){selectCaptureLanguage();route(mode);}if(data)controls();sceneText();if(mode==='planner')renderCalendar();if(statusKey)message(t(statusKey),statusError,statusKey);schedule();
}
function selectCaptureLanguage(){
  $('obs-capture').value=capture.id;
  cards.forEach(card=>card.querySelector('.card-state').textContent=t(capture.features[card.dataset.mode]?'obs_available':'obs_not_available'));
  if(tv)$('obs-hub-help').textContent=t('obs_tv_hub');
}
addEventListener('resize',schedule);new ResizeObserver(schedule).observe(surface);
document.addEventListener('visibilitychange',()=>{lastTime=0;if(document.hidden){cancelAnimationFrame(frame);frame=0;}else schedule();});
reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;sceneText();}});
document.addEventListener('fullscreenchange',schedule);
window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==parent)return;if(event.data?.type==='astroweb-active')window.viewActive(event.data.active===true);if(event.data?.type==='astroweb-language'&&['nl','en'].includes(event.data.language)){setLanguage(event.data.language);translated();}});
async function boot(){
  function startup(key){$('obs-startup-status').dataset.i18n=key;$('obs-startup-status').textContent=t(key);$('obs-startup').querySelector('.spinner').hidden=key!=='loading';}
  $('obs-startup').hidden=false;startup('loading');$('obs-startup-retry').hidden=true;$('obs-hub').hidden=true;
  try{
    const result=await json('/api/observatory');captures=result.captures;
    const wanted=query.get('month')||calendarRestore?.month;$('obs-month').value=/^(20\d\d|2100)-(0[1-9]|1[0-2])$/.test(wanted||'')?wanted:result.month;
    if(calendarPage){calendarTarget=query.get('target')||calendarRestore?.target||'';if(!captures.some(c=>c.id===calendarTarget&&c.features.planner))calendarTarget='';}
    translated();if(!captures.length&&!calendarPage){startup('emptyGallery');return;}
    selectCapture(query.get('capture'));if(capture)selectCard(Math.max(0,modes.findIndex(m=>capture.features[m])));
    if(calendarPage){document.querySelector('.obs-header>span').dataset.i18n='captureCalendar';document.querySelector('.obs-header>span').textContent=t('captureCalendar');open('planner');}
    else if(modes.includes(query.get('mode')))open(query.get('mode'));
    else $('obs-hub').hidden=false;
    $('obs-startup').hidden=true;document.body.dataset.loaded='true';
  }catch{startup('network_error');$('obs-startup-retry').hidden=false;}
}
$('obs-startup-retry').addEventListener('click',boot);
// TV instructions need their own space; canvas captions must remain visible
// above them, including when a source URL wraps onto an additional line.
if(tv&&!calendarPage)surface.after($('obs-remote-help'));
if(embedded||calendarPage)document.querySelector('.control-buttons').append($('obs-full'));
if(embedded){document.querySelector('.control-buttons').append($('obs-open'));$('obs-open').target='_top';}
setLanguage(language);
if(calendarPage){const heading=document.querySelector('.obs-header>span');heading.dataset.i18n='captureCalendar';heading.textContent=t('captureCalendar');document.title='AstroWeb · '+t('captureCalendar');}
boot();
