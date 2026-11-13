import {openPolar,closePolar,drawPolar} from './polar.js';
import {layoutComparison,setComparisonObject,openEnvironment,comparisonText} from './compare.js';
import {configureGalaxy,openGalaxy,stopGalaxy,setJourneyLabels,atlasLanguage} from './atlas.js';
import {t,local,language,setLanguage,formatDate,duration} from './i18n.js';
import {SkyPlayer} from './sky.js';
const $=id=>document.getElementById(id);
const state={objects:[],adminObjects:[],jobs:[],session:null,selected:null,current:null,files:[],busy:false,preview:null};
const studioRoute = location.pathname === '/admin';
document.body.classList.toggle('studio-route', studioRoute);
$('studio').hidden = !studioRoute;
const viewerRoute=location.pathname.startsWith('/viewer/');
document.body.classList.toggle('viewer-route',viewerRoute);
$('viewer').hidden=!viewerRoute;
let journeyInfo=null;
let featuredId = null;
let uploadPosterUrl = null;
const sky=new SkyPlayer();
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function errorText(error){return t(error.message||'internal_error');}
async function api(url,options={}){
  const headers=new Headers(options.headers||{});
  if(options.body&&!(options.body instanceof FormData)){headers.set('Content-Type','application/json');options.body=JSON.stringify(options.body);}
  if(options.method&&options.method!=='GET')headers.set('X-CSRF-Token',state.session?.csrf||'');
  let response;try{response=await fetch(url,{...options,headers});}catch{throw Error('network_error');}
  if(!response.ok){let value;try{value=await response.json();}catch{}throw Error(value?.error||'internal_error');}
  return options.raw?response:response.json();
}
function message(id,text,error=false){const target=$(id);target.textContent=text;target.classList.toggle('error',error);}
let toastTimer;function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4500);}
function setBusy(value){state.busy=value;for(const id of ['render-button','preview-button','fetch-nasa'])$(id).disabled=value;}
function applyLanguage(value){setLanguage(value);drawPicker();buildGallery();if(state.current){renderViewerText();journeyCaption();layoutOriginal();atlasLanguage();drawPolar();renderDiscovery();comparisonText();}renderLogin();renderAdminList();renderJobs();renderFileList();document.querySelectorAll('[data-edit-key]').forEach(el=>el.textContent=t(el.dataset.editKey)+' · '+el.dataset.editLanguage.toUpperCase());if(state.selected){renderChoice();showVersions();showAutoRoute();}if(studioRoute)document.title='AstroWeb · Studio';sky.draw();}
document.querySelectorAll('[data-lang]').forEach(button=>button.addEventListener('click',()=>applyLanguage(button.dataset.lang)));

async function loadGallery(){try{state.objects=(await api('/api/objects')).objects;buildGallery();}catch(e){$('gallery-grid').replaceChildren(node('div','empty-state',errorText(e)));}}
function buildGallery(){
  const grid=$('gallery-grid');grid.querySelectorAll('video').forEach(video=>video.pause());grid.replaceChildren();
  const count=state.objects.length;$('gallery-count').textContent=String(count).padStart(2,'0')+' '+t(count===1?'filmSingular':'films');
  $('hero-play').disabled=!count;
  if(!count){grid.append(node('div','empty-state',t('emptyGallery')));return;}
  let hero=state.objects.find(o=>o.id===featuredId);
  if(!hero){hero=state.objects[Math.floor(Math.random()*count)];featuredId=hero.id;}$('hero-image').src=hero.poster;$('hero-name').textContent=local(hero.metadata.name);$('hero-id').textContent=hero.id.replace('_',' ');
  state.objects.forEach((object,index)=>{
    const card=node('article','gallery-card');card.tabIndex=0;card.setAttribute('role','button');card.setAttribute('aria-label',t('openFilm')+' · '+local(object.metadata.name));
    const media=node('div','card-media');const image=node('img');image.width=object.width;image.height=object.height;image.src=object.poster;image.alt=local(object.metadata.name);image.loading='lazy';const video=node('video');video.muted=true;video.loop=true;video.playsInline=true;video.preload='none';video.setAttribute('aria-hidden','true');
    const top=node('div','card-topline');top.append(node('span','media-badge',t('cinematic')+' · '+object.params.duration+'s'),node('span','card-number',String(index+1).padStart(2,'0')));
    const bottom=node('div','card-bottomline');bottom.append(node('span','',t('hoverPreview')),node('span','card-open','↗'));media.append(image,video,top,node('span','card-play','▶'),bottom);
    const info=node('div','card-info');const category=node('div','card-type');category.append(node('span','',object.id.replace('_',' ')),node('span','',local(object.metadata.type)));info.append(category,node('h3','',local(object.metadata.name)),node('p','',local(object.metadata.summary)));
    const tags=node('div','card-tags');const details=[local(object.metadata.constellation),object.observation?.telescope,duration(object.observation?.integration)].filter(Boolean);details.forEach(text=>{const tag=node('span');tag.append(node('i'),document.createTextNode(text));tags.append(tag);});info.append(tags);card.append(media,info);
    async function play(){if(reducedMotion.matches||document.hidden)return;if(!video.src)video.src=object.preview||object.video;try{await video.play();if(card.matches(':hover')||document.activeElement===card)card.classList.add('playing');else video.pause();}catch{card.classList.remove('playing');}}
    function pause(){video.pause();card.classList.remove('playing');}
    card.addEventListener('pointerenter',event=>{if(event.pointerType!=='touch')play();});card.addEventListener('pointerleave',pause);card.addEventListener('focus',play);card.addEventListener('blur',pause);card.addEventListener('click',()=>{pause();openViewer(object);});card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();pause();openViewer(object);}});grid.append(card);
  });
}
$('hero-play').addEventListener('click',()=>{const object=state.objects.find(o=>o.id===featuredId);if(object)openViewer(object);});
const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(!entry.isIntersecting){entry.target.querySelector('video')?.pause();entry.target.classList.remove('playing');}}));
new MutationObserver(()=>document.querySelectorAll('.gallery-card').forEach(card=>observer.observe(card))).observe($('gallery-grid'),{childList:true});
document.addEventListener('visibilitychange',()=>{if(document.hidden){document.querySelectorAll('video').forEach(video=>video.pause());sky.pause();}});

function fact(list,label,value){if(value===undefined||value===null||value==='')return;const item=node('div');item.append(node('dt','',label),node('dd','',String(value)));list.append(item);}
function renderViewerText(){
  const object=state.current,m=object.metadata,obs=object.observation||{};document.title=local(m.name)+' · AstroWeb';$('viewer-id').textContent=object.id.replace('_',' ')+' · '+local(m.type);$('viewer-title').textContent=local(m.name);$('viewer-description').textContent=local(m.description);$('viewer-original').alt=local(m.name);$('viewer-facts').replaceChildren();
  fact($('viewer-facts'),t('constellation'),local(m.constellation));fact($('viewer-facts'),t('catalogTarget'),m.target);fact($('viewer-facts'),t('integration'),duration(obs.integration));fact($('viewer-facts'),t('telescope'),obs.telescope);fact($('viewer-facts'),t('frames'),obs.frames);fact($('viewer-facts'),t('singleExposure'),obs.exposure?obs.exposure+' s':'');fact($('viewer-facts'),t('filter'),obs.filter);
  if(obs.date_obs){const stamp=new Intl.DateTimeFormat(language==='nl'?'nl-NL':'en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:obs.timezone||'UTC'}).format(new Date(obs.date_obs));fact($('viewer-facts'),t('observedAt'),stamp+' · '+(obs.timezone||'UTC'));}
  $('viewer-sources').replaceChildren();const links=[...(m.sources||[])];if(m.external)links.push({label:m.external.provider,url:m.external.url});for(const link of links){if(!/^https:\/\//.test(link.url))continue;const a=node('a','',link.label+' ↗');a.href=link.url;a.target='_blank';a.rel='noopener noreferrer';$('viewer-sources').append(a);}
  $('external-description').replaceChildren();if(m.external){const ext=m.external;const details=node('details','external-block');details.append(node('summary','',t('nasaMore')));const text=local(ext.text);details.append(node('p','',text||t('untranslated')));if(language==='nl'&&ext.translation==='machine')details.append(node('p','small',t('machineTranslation')));details.append(node('p','small',ext.credit+' · '+t('fetchedAt')+' '+formatDate(ext.fetched_at)));$('external-description').append(details);}
}
function openViewer(object){location.assign('/viewer/'+encodeURIComponent(object.id));}
async function loadViewer(){
  let object;
  try{object=await api('/api/objects/'+location.pathname.split('/').pop());}
  catch(e){$('viewer-title').textContent=errorText(e);return;}
  setComparisonObject(object.id);$('environment-tab').hidden=!object.environment_available;configureGalaxy(object.galaxy,object.metadata.name);state.current=object;$('viewer').classList.toggle('portrait',object.height>object.width);$('viewer').style.setProperty('--film-ratio',String(object.width/object.height));$('viewer-video').src=object.video;$('viewer-video').poster=object.poster;$('viewer-original').src=object.original_view||object.final;$('download-movie').href=object.video+(object.video.includes('?')?'&':'?')+'download=1';$('download-original').href=object.final+'?download=1';renderViewerText();const tab=location.hash.slice(1);
  selectTab(['original','sky','journey','polar'].includes(tab)||(tab==='galaxy'&&object.galaxy)||(tab==='environment'&&object.environment_available)?tab:'film');
  if(!$('film-panel').hidden&&!reducedMotion.matches)$('viewer-video').play().catch(()=>{});}
function selectTab(name){document.querySelectorAll('[data-view]').forEach(tab=>{const selected=tab.dataset.view===name;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;});for(const panel of ['film','original','journey','galaxy','environment','sky','polar'])$(panel+'-panel').hidden=panel!==name;history.replaceState(null,'',location.pathname+location.search+(name==='film'?'':'#'+name));
  if(name==='original'&&new URLSearchParams(location.search).has('discover')){
    $('discover-toggle').checked=true;
    loadDiscovery();
  }
  if(name==='polar')openPolar(state.current.id);else closePolar();
  if(name==='environment')openEnvironment(state.current.id);
  if(name==='galaxy')openGalaxy();else stopGalaxy();
  if(name==='journey')loadJourney();else $('journey-video').pause();
  if(name!=='film')$('viewer-video').pause();if(name!=='sky')sky.pause();else sky.load(state.current,api);}
window.addEventListener('hashchange',()=>{
  if(!viewerRoute||!state.current)return;
  const tab=[...document.querySelectorAll('[data-view]:not([hidden])')].find(el=>el.dataset.view===location.hash.slice(1));
  selectTab(tab?.dataset.view||'film');
});
document.querySelectorAll('[data-view]').forEach(tab=>{tab.addEventListener('click',()=>selectTab(tab.dataset.view));tab.addEventListener('keydown',event=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('[data-view]:not([hidden])')],index=tabs.indexOf(tab);const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].focus();selectTab(tabs[next].dataset.view);});});
const originalStage=$('original-stage'),originalImage=$('viewer-original');
let photoZoom=1, photoX=0, photoY=0, photoDrag=null;
function layoutOriginal(){
  const w=originalStage.clientWidth, h=originalStage.clientHeight;
  if(!w||!h||!originalImage.naturalWidth)return;
  const fit=Math.min(w/originalImage.naturalWidth,h/originalImage.naturalHeight);
  const width=originalImage.naturalWidth*fit*photoZoom,height=originalImage.naturalHeight*fit*photoZoom;
  const limitX=Math.max(0,(width-w)/2),limitY=Math.max(0,(height-h)/2);
  photoX=clamp(photoX,-limitX,limitX);photoY=clamp(photoY,-limitY,limitY);
  originalImage.style.width=width+'px';originalImage.style.height=height+'px';
  originalImage.style.transform='translate('+(-width/2+photoX)+'px,'+(-height/2+photoY)+'px)';
  const pins=$('discovery-pins');
  pins.style.width=width+'px';pins.style.height=height+'px';pins.style.transform=originalImage.style.transform;
  layoutComparison();
  originalStage.classList.toggle('zoomed',photoZoom>1);
  $('original-fit').disabled=photoZoom===1;
  $('original-level').textContent=photoZoom.toLocaleString(language,{maximumFractionDigits:2})+'×';
}
function zoomOriginal(value,x=0,y=0){
  const control=$('original-scale');
  control.value=String(value);
  const next=Number(control.value),ratio=next/photoZoom;
  photoX=x+(photoX-x)*ratio;photoY=y+(photoY-y)*ratio;
  photoZoom=next;layoutOriginal();
}
function photoAnchor(e){
  const box=originalStage.getBoundingClientRect();
  return [e.clientX-box.left-box.width/2,e.clientY-box.top-box.height/2];
}
$('original-scale').addEventListener('input',e=>zoomOriginal(e.target.value));
$('original-fit').addEventListener('click',()=>zoomOriginal(1));
originalStage.addEventListener('wheel',e=>{
  if(!e.deltaY||e.ctrlKey)return;
  const next=clamp(photoZoom*(e.deltaY<0?1.15:1/1.15),1,+$('original-scale').max);
  if(next===photoZoom)return;
  e.preventDefault();zoomOriginal(next,...photoAnchor(e));
},{passive:false});
originalStage.addEventListener('dblclick',e=>zoomOriginal(photoZoom===1?+$('original-scale').max:1,...photoAnchor(e)));
originalStage.addEventListener('pointerdown',e=>{
  if(e.target.closest('.discovery-pin')||photoZoom===1||!e.isPrimary||e.button!==0)return;
  photoDrag={id:e.pointerId,x:e.clientX-photoX,y:e.clientY-photoY};
  originalStage.setPointerCapture(e.pointerId);originalStage.classList.add('dragging');
});
originalStage.addEventListener('pointermove',e=>{
  if(photoDrag?.id!==e.pointerId)return;
  photoX=e.clientX-photoDrag.x;photoY=e.clientY-photoDrag.y;layoutOriginal();
});
originalStage.addEventListener('lostpointercapture',()=>{photoDrag=null;originalStage.classList.remove('dragging');});
originalImage.addEventListener('load',()=>zoomOriginal(1));
new ResizeObserver(layoutOriginal).observe(originalStage);

let discoveries=null,discoveryId=null;
async function loadDiscovery(){
  const enabled=$('discover-toggle').checked;
  $('discovery-card').hidden=$('discovery-pins').hidden=!enabled;
  if(!enabled||!state.current)return;
  if(!discoveries){
    $('discovery-status').textContent=t('discoverLoading');
    try{discoveries=await api('/api/objects/'+encodeURIComponent(state.current.id)+'/discover');}
    catch(e){$('discovery-status').textContent=errorText(e);return;}
  }
  renderDiscovery();
}
function renderDiscovery(){
  if(!discoveries||!$('discover-toggle').checked)return;
  const objects=discoveries.objects;
  const current=objects.find(o=>o.id===discoveryId)||objects[0];
  const pins=$('discovery-pins'),list=$('discovery-list');
  pins.replaceChildren();list.replaceChildren();
  $('discovery-selection').hidden=!current;
  $('discovery-status').textContent=current?'':t(discoveries.kind==='missing'?'discoverMissing':'discoverEmpty');
  if(!current)return;
  discoveryId=current.id;
  for(const o of objects){
    const label=local(o.name);
    const button=node('button','discovery-pin');
    button.type='button';button.title=label;button.dataset.label=o.id;
    button.setAttribute('aria-label',label);button.setAttribute('aria-pressed',String(o.id===discoveryId));
    button.style.left=o.x*100+'%';button.style.top=o.y*100+'%';
    button.addEventListener('click',()=>{discoveryId=o.id;renderDiscovery();$('discovery-list').focus({preventScroll:true});});
    pins.append(button);
    list.add(new Option(label===o.id?label:label+' · '+o.id,o.id));
  }
  list.value=discoveryId;
  $('discovery-description').textContent=[local(current.type),local(current.summary)].filter(Boolean).join(' · ');
  const details=['RA '+current.ra.toFixed(4)+'°','Dec '+current.dec.toFixed(4)+'°',...current.aliases];
  if(current.ly)details.push('≈ '+current.ly.toLocaleString(language)+' '+t('lightYears'));
  $('discovery-data').textContent=details.join(' · ');
  $('discovery-source').href=current.source;
  $('discovery-studio').href='/admin?'+new URLSearchParams({capture:state.current.id,landmark:current.id});
  layoutOriginal();
}
$('discover-toggle').addEventListener('change',loadDiscovery);
$('discovery-list').addEventListener('change',e=>{discoveryId=e.target.value;renderDiscovery();});

function journeyCaption(){
  if(!journeyInfo)return;
  $('journey-note').textContent=t('journey_'+journeyInfo.kind);
  const survey=$('journey-survey');
  survey.hidden=!journeyInfo.survey;
  if(journeyInfo.survey==='PanSTARRS'){
    survey.textContent='Pan-STARRS1 · CDS ↗';
    survey.href='https://stpubdata.s3.us-east-1.amazonaws.com/mast/skybackgrounds/PanSTARRS/properties';
  }
}
async function loadJourney(){
  const video=$('journey-video'), status=$('journey-status');
  try{
    if(!journeyInfo)journeyInfo=await api('/api/objects/'+state.current.id+'/journey');
    journeyCaption();setJourneyLabels(journeyInfo.labels);
    if(!journeyInfo.url){video.hidden=true;status.textContent='';return;}
    if($('journey-panel').hidden)return;
    if(!video.hasAttribute('src')){
      status.textContent=t('journeyLoading');video.src=journeyInfo.url;video.load();
    }
    if(!reducedMotion.matches)video.play().catch(()=>{});
  }catch(e){status.textContent=errorText(e);}
}
$('journey-video').addEventListener('loadeddata',()=>{$('journey-status').textContent='';});
$('journey-video').addEventListener('error',()=>{$('journey-status').textContent=t('journey_failed');});
async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else if($('movie-stage').requestFullscreen)await $('movie-stage').requestFullscreen();else if($('viewer-video').webkitEnterFullscreen)$('viewer-video').webkitEnterFullscreen();else throw Error();}catch{toast(t('fullscreen_error'));}}
$('movie-stage').addEventListener('dblclick',event=>{event.preventDefault();fullscreen();});$('fullscreen-button').addEventListener('click',fullscreen);
function renderLogin(){if(!state.session)return;const setup=!state.session.initialized;$('login-title').textContent=t(setup?'setupTitle':'loginTitle');$('login-note').textContent=t(setup?'setupNote':'loginNote');$('login-submit').textContent=t(setup?'setupButton':'login');$('password').minLength=setup?11:1;$('password').autocomplete=setup?'new-password':'current-password';$('login-submit').disabled=setup&&!state.session.can_setup;if(setup&&!state.session.can_setup)$('login-note').textContent=t('local_setup_required');}
async function openStudio(){
  try{
    state.session=await api('/api/session');
    $('studio-workspace').hidden=true;
    $('login-form').hidden=state.session.authenticated;
    $('logout').hidden=!state.session.authenticated;
    renderLogin();
    if(state.session.authenticated){
      await refreshAdmin();
      if(!state.selected)newObject();
      $('studio-workspace').hidden=false;
      await receiveDiscovery();
    }
  }catch(e){toast(errorText(e));}
}
$('login-form').addEventListener('submit',async event=>{event.preventDefault();$('login-submit').disabled=true;try{const setup=!state.session.initialized;const result=await api(setup?'/api/setup':'/api/login',{method:'POST',body:{password:$('password').value}});state.session={...state.session,csrf:result.csrf,authenticated:true,initialized:true};$('password').value='';message('login-error','');await openStudio();}catch(e){message('login-error',errorText(e),true);}finally{$('login-submit').disabled=false;}});
$('logout').addEventListener('click',async()=>{try{const result=await api('/api/logout',{method:'POST'});state.session={...state.session,csrf:result.csrf,authenticated:false};newObject();await openStudio();}catch(e){toast(errorText(e));}});
async function refreshAdmin(){const response=await api('/api/admin/objects');state.adminObjects=response.objects;state.jobs=response.jobs;renderAdminList();renderJobs();
  if(state.selected){
    const updated=state.adminObjects.find(o=>o.id===state.selected.id);
    if(updated){state.selected=updated;showVersions();renderChoice();}
  }
}
function renderAdminList(){const list=$('admin-object-list');list.replaceChildren();for(const object of state.adminObjects){const button=node('button','admin-object'+(state.selected?.id===object.id?' selected':''),object.id.replace('_',' '));const name=local(object.metadata.name);if(name&&name!==object.id.replace('_',' '))button.append(node('span','admin-name',name));button.addEventListener('click',()=>selectObject(object.id));list.append(button);}}
function renderJobs(){const list=$('job-list');list.replaceChildren();if(!state.jobs.length){list.append(node('p','small muted',t('noJobs')));return;}const active=j=>['running','queued','cancelling'].includes(j.status);for(const job of [...state.jobs.filter(active),...state.jobs.filter(j=>!active(j)).slice(0,8)]){const row=node('div','job-item');row.append(node('strong','',job.object_id.replace('_',' ')),node('span','',t(job.status)+(job.status==='running'?' · '+Math.round(job.progress)+'%':'')));if(['running','queued'].includes(job.status)){const p=node('progress');p.max=100;p.value=job.progress;row.append(p);
    const cancel=node('button','button secondary cancel-render',t('cancelRender'));
    cancel.addEventListener('click',async()=>{cancel.disabled=true;try{await api('/api/admin/jobs/'+job.id+'/cancel',{method:'POST'});await refreshAdmin();}catch(e){toast(errorText(e));cancel.disabled=false;}});
    row.append(cancel);
  }if(job.status==='failed'){row.append(node('p','small muted',t(job.error)));const retry=node('button','retry-button',t('retry'));retry.addEventListener('click',async()=>{try{await api(`/api/admin/objects/${job.object_id}/render`,{method:'POST',body:job.params});await refreshAdmin();}catch(e){toast(errorText(e));}});row.append(retry);}list.append(row);}}
let points=[{zoom:1.08,focus_x:.5,focus_y:.5}],pointIndex=0;
function savePoint(){
  const {zoom,focus_x,focus_y}=activeParams();
  points[pointIndex]={zoom,focus_x,focus_y};
  const name=$('point-name').value.trim();if(name)points[pointIndex].name=name;
}
function params(){
  savePoint();
  const first=points[0];
  return {...activeParams(),zoom:first.zoom,focus_x:first.focus_x,focus_y:first.focus_y,zoom_points:points.length>1||first.name?points:[]};
}
function drawPicker(){
  const picker=$('point-picker');picker.replaceChildren();picker.hidden=points.length===1;
  points.forEach((point,i)=>{
    const button=node('button','subtle-button',(i+1)+(point.name?' · '+point.name:''));
    button.type='button';button.setAttribute('aria-label',t('focusPoint')+' '+(i+1));
    button.setAttribute('aria-pressed',String(i===pointIndex));
    button.addEventListener('click',()=>{savePoint();choosePoint(i);});
    picker.append(button);
  });
}
function choosePoint(index){
  pointIndex=index;
  const fields=$('parameters-form').elements,p=points[index];
  $('point-name').value=p.name||'';
  fields.zoom.value=p.zoom;fields.focus_x.value=+(p.focus_x*100).toFixed(1);fields.focus_y.value=+(p.focus_y*100).toFixed(1);
  drawPicker();updateOutputs();
}
$('point-count').addEventListener('change',e=>{
  savePoint();
  const count=Number(e.target.value),previous=points.length;
  while(points.length<count){const {zoom,focus_x,focus_y}=points[pointIndex];points.push({zoom,focus_x,focus_y});}
  points.length=count;
  choosePoint(count>previous?count-1:Math.min(pointIndex,count-1));
});
function activeParams(){const raw=Object.fromEntries(new FormData($('parameters-form')));for(const key of ['zoom','depth','pan_x','pan_y','duration','resolution','fps'])raw[key]=+raw[key];raw.focus_x=Number(raw.focus_x)/100;raw.focus_y=Number(raw.focus_y)/100;return raw;}
function fillParams(value={}){
  points=value.zoom_points?.length?value.zoom_points.map(p=>({...p})):[{zoom:value.zoom??1.08,focus_x:value.focus_x??.5,focus_y:value.focus_y??.5}];
  pointIndex=0;$('point-name').value=points[0].name||'';$('point-count').value=points.length;drawPicker();const defaults={orientation:'portrait',method:'layered',motion:'orbit',zoom:1.08,focus_x:.5,focus_y:.5,pan_x:.018,pan_y:.010,depth:.65,duration:10,resolution:1280,fps:24,star_source:'auto',blend:'auto'};for(const [key,item] of Object.entries({...defaults,...value,...points[0]})){const input=$('parameters-form').elements.namedItem(key);if(input?.tagName==='SELECT'&&key==='duration'&&![...input.options].some(o=>o.value===String(item)))input.add(new Option(item+' s',String(item)));if(input)input.value=key.startsWith('focus_')?+(item*100).toFixed(1):item;}updateOutputs();}
function updateOutputs(){updateFocusMarker();for(const output of document.querySelectorAll('[data-output]')){const key=output.dataset.output,value=+$('parameters-form').elements.namedItem(key).value;output.textContent=key.startsWith('pan')?(value*100).toFixed(1)+'%':key==='zoom'?value.toFixed(2)+'×':value.toFixed(2);}}
$('parameters-form').addEventListener('input',updateOutputs);$('parameters-form').addEventListener('submit',event=>event.preventDefault());
function newObject(){clearImportControls();state.selected=null;setFocusImage(null);showVersions();state.files=[];$('upload-form').reset();$('upload-section').hidden=false;$('edit-section').hidden=true;$('metadata-section').hidden=true;$('preview-button').hidden=true;$('preview-image').hidden=true;$('render-button').querySelector('[data-i18n]').dataset.i18n='createFilm';$('render-button').querySelector('[data-i18n]').textContent=t('createFilm');fillParams();renderFileList();renderAdminList();message('studio-message','');}
$('new-object').addEventListener('click',newObject);
function renderChoice(){
  const g=state.selected?.gaia||{};
  $('gaia-status').textContent=g.status?t('gaia_'+g.status)+(g.matches?' · '+g.matches+' '+t('gaiaStars')+' · '+g.median_arcsec+'″':''):'';
  $('gaia-retry').hidden=['pending','running','solved'].includes(g.status);
  const choice=state.selected?.render?.choice;$('render-choice').textContent=choice?`${t('starLayer')}: ${choice.source} · ${t('blending')}: ${choice.blend} · MAE ${(choice.mae*100).toFixed(2)}%`:'';}
$('gaia-retry').addEventListener('click',async()=>{
  try{await api('/api/admin/objects/'+state.selected.id+'/align',{method:'POST'});await refreshAdmin();}
  catch(e){toast(errorText(e));}
});
function selectObject(id){const object=state.adminObjects.find(item=>item.id===id);if(!object)return;clearImportControls();state.selected=object;$('auto-tools').hidden=false;$('find-more').hidden=false;$('find-more').href='/viewer/'+encodeURIComponent(id)+'?discover=1#original';$('upload-section').hidden=true;$('edit-section').hidden=false;$('metadata-section').hidden=false;$('preview-button').hidden=false;$('preview-image').hidden=true;$('edit-object-title').textContent=object.id.replace('_',' ')+' · '+local(object.metadata.name);setFocusImage(object.source_poster||object.poster);showVersions();renderChoice();fillParams(object.params);const text=$('render-button').querySelector('[data-i18n]');text.dataset.i18n='rerender';text.textContent=t('rerender');renderAdminList();fillMetadata(object);fillObservation(object);message('studio-message','');}
let pendingLandmark=null;
const draftKey=id=>'astroweb-discovery-draft-'+id;
function clearImportControls(){
  resetAutoRoute();$('auto-tools').hidden=true;
  pendingLandmark=null;$('point-replace').hidden=true;$('find-more').hidden=true;
}
$('point-name').addEventListener('input',()=>{savePoint();drawPicker();});
$('find-more').addEventListener('click',()=>{
  sessionStorage.setItem(draftKey(state.selected.id),JSON.stringify(params()));
});
function applyLandmark(i){
  const o=pendingLandmark,object=state.selected;
  const rotate=$('parameters-form').elements.orientation.value==='portrait'&&object.source_width>object.source_height;
  const zoom=Math.max(2,points[i]?.zoom||2);
  points[i]={name:local(o.name).slice(0,100),zoom,focus_x:rotate?1-o.y:o.x,focus_y:rotate?o.x:o.y};
  $('point-count').value=points.length;choosePoint(i);
  $('point-replace').hidden=true;pendingLandmark=null;
  $('point-name').scrollIntoView({block:'center'});
}
async function receiveDiscovery(){
  const query=new URLSearchParams(location.search),id=query.get('capture'),landmark=query.get('landmark');
  if(!id||!landmark)return;
  const data=await api('/api/objects/'+encodeURIComponent(id)+'/discover');
  const found=data.objects.find(o=>o.id===landmark);
  if(!found||!state.adminObjects.some(o=>o.id===id)){toast(t('discoverEmpty'));return;}
  selectObject(id);
  const draft=sessionStorage.getItem(draftKey(id));
  if(draft){try{fillParams(JSON.parse(draft));}finally{sessionStorage.removeItem(draftKey(id));}}
  pendingLandmark=found;
  history.replaceState(null,'',location.pathname);
  if(points.length===$('point-count').options.length){
    const select=$('replace-index');select.replaceChildren();
    points.forEach((p,i)=>select.add(new Option((i+1)+(p.name?' · '+p.name:''),i)));
    $('point-replace').hidden=false;select.scrollIntoView({block:'center'});return;
  }
  // The initial, unnamed centre stop is a placeholder for the first discovery.
  const first=points[0],empty=points.length===1&&!first.name&&first.zoom===1.08&&first.focus_x===.5&&first.focus_y===.5;
  applyLandmark(empty?0:points.length);
}
$('replace-point').addEventListener('click',()=>{if(pendingLandmark)applyLandmark(Number($('replace-index').value));});

function fillMetadata(object){$('rename-form').elements.identifier.value=object.id.replace('_',' ');$('metadata-form').elements.galactic_distance_ly.value=object.metadata.galactic_distance_ly??'';const fields=$('metadata-fields');fields.replaceChildren();$('metadata-form').elements.namedItem('target').value=object.metadata.target;for(const key of ['name','type','constellation','summary','description'])for(const lang of ['nl','en']){const label=node('label');const title=node('span','',t(key)+' · '+lang.toUpperCase());title.dataset.editKey=key;title.dataset.editLanguage=lang;const input=node(['summary','description'].includes(key)?'textarea':'input');input.name=key+'_'+lang;input.maxLength=key==='description'?5000:350;input.value=object.metadata[key]?.[lang]||'';label.append(title,input);fields.append(label);}}
function fillObservation(object){const observation=object.observation||{};for(const key of ['date_obs','latitude','longitude','ra','dec','timezone'])$('observation-form').elements.namedItem(key).value=observation[key]??(key==='timezone'?'Europe/Amsterdam':'');$('observation-form').elements.namedItem('publish_location').checked=!!observation.publish_location;const details=$('fits-details');details.replaceChildren();fact(details,t('integration'),duration(observation.integration));fact(details,t('frames'),observation.frames);fact(details,t('telescope'),observation.telescope);fact(details,'FITS',observation.filename);fact(details,'DATE-OBS',observation.time_comment);fact(details,'UTC',observation.time_scale_assumed?(language==='nl'?'Aangenomen volgens FITS-conventie':'Assumed by FITS convention'):observation.time_scale);}
function assignFiles(files){state.files=[...files];
  const final=state.files.find(file=>/_final\.(png|jpe?g|tiff?)$/i.test(file.name));
  setFocusImage(final);const first=state.files.find(file=>/_(?:final|stars|starless|stars_laid)\./i.test(file.name));if(first){const match=first.name.match(/^([A-Za-z][A-Za-z0-9]*[_ -]\d+[A-Za-z]?)(?:_)/);if(match)$('identifier').value=match[1].toUpperCase().replace(/[ -]/g,'_');}renderFileList();}
function renderFileList(){const list=$('file-checklist');list.replaceChildren();for(const role of ['final','starless','stars','stars_laid','FITS']){const matches=state.files.filter(file=>role==='FITS'?/\.(fits|fit|fts)$/i.test(file.name):new RegExp('_'+role+'\\.(png|jpe?g|tiff?)$','i').test(file.name));const chip=node('span','file-chip'+(matches.length===1?' ready':matches.length>1?' invalid':''),(matches.length===1?'✓ ':'')+role+(role==='FITS'?' · '+(language==='nl'?'optioneel':'optional'):''));chip.title=matches.map(file=>file.name).join('\n');list.append(chip);}}
$('image-files').addEventListener('change',event=>assignFiles(event.target.files));const drop=document.querySelector('.dropzone');drop.addEventListener('dragover',event=>{event.preventDefault();drop.classList.add('dragging');});drop.addEventListener('dragleave',()=>drop.classList.remove('dragging'));drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('dragging');assignFiles(event.dataTransfer.files);});
$('render-button').addEventListener('click',async()=>{if(state.busy||!$('parameters-form').reportValidity())return;setBusy(true);try{if(state.selected){await api(`/api/admin/objects/${state.selected.id}/render`,{method:'POST',body:params()});}else{if(!$('upload-form').reportValidity())return;const images=state.files.filter(file=>/\.(png|jpe?g|tiff?)$/i.test(file.name)),fits=state.files.filter(file=>/\.(fits|fit|fts)$/i.test(file.name));if(images.length!==4||fits.length>1||images.length+fits.length!==state.files.length)throw Error('four_images_required');const form=new FormData();form.set('identifier',$('identifier').value);form.set('params',JSON.stringify(params()));images.forEach(file=>form.append('images',file));if(fits[0])form.set('fits',fits[0]);message('studio-message',t('uploading'));const result=await api('/api/admin/objects',{method:'POST',body:form});await refreshAdmin();selectObject(result.object.id);}message('studio-message',t('queuedMessage'));await refreshAdmin();}catch(e){message('studio-message',errorText(e),true);}finally{setBusy(false);}});
$('preview-button').addEventListener('click',async()=>{if(!state.selected||state.busy||!$('parameters-form').reportValidity())return;setBusy(true);message('studio-message',t('working'));try{const response=await api(`/api/admin/objects/${state.selected.id}/preview?point=${pointIndex+1}`,{method:'POST',body:params(),raw:true});if(state.preview)URL.revokeObjectURL(state.preview);state.preview=URL.createObjectURL(await response.blob());$('preview-image').src=state.preview;$('preview-image').hidden=false;message('studio-message','');}catch(e){message('studio-message',errorText(e),true);}finally{setBusy(false);}});
$('rename-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const object=state.selected,button=event.target.querySelector('button');
  if(!object||button.disabled)return;
  button.disabled=true;
  try{
    const result=await api('/api/admin/objects/'+object.id+'/identifier',{method:'PUT',body:{identifier:event.target.elements.identifier.value}});
    state.selected=null;
    await refreshAdmin();selectObject(result.object.id);toast(t('saved'));
  }catch(e){toast(errorText(e));}finally{button.disabled=false;}
});
$('metadata-form').addEventListener('submit',async event=>{event.preventDefault();if(!state.selected)return;const form=new FormData(event.target),body={target:form.get('target'),galactic_distance_ly:form.get('galactic_distance_ly')?Number(form.get('galactic_distance_ly')):null};for(const key of ['name','type','constellation','summary','description'])body[key]={nl:form.get(key+'_nl'),en:form.get(key+'_en')};try{await api(`/api/admin/objects/${state.selected.id}/metadata`,{method:'PUT',body});toast(t('saved'));await refreshAdmin();state.selected=state.adminObjects.find(o=>o.id===state.selected.id);await loadGallery();}catch(e){toast(errorText(e));}});
$('fetch-nasa').addEventListener('click',async()=>{if(!state.selected||state.busy)return;setBusy(true);message('studio-message',t('working'));try{await api(`/api/admin/objects/${state.selected.id}/metadata/refresh`,{method:'POST',body:{}});message('studio-message',t('saved'));await refreshAdmin();await loadGallery();}catch(e){message('studio-message',errorText(e),true);}finally{setBusy(false);}});
$('observation-form').addEventListener('submit',async event=>{event.preventDefault();if(!state.selected)return;const form=new FormData(event.target),body=Object.fromEntries(form);body.publish_location=form.has('publish_location');for(const key of ['latitude','longitude','ra','dec'])body[key]=+body[key];try{await api(`/api/admin/objects/${state.selected.id}/observation`,{method:'PUT',body});sky.invalidate(state.selected.id);toast(t('saved'));await refreshAdmin();state.selected=state.adminObjects.find(o=>o.id===state.selected.id);await loadGallery();}catch(e){toast(errorText(e));}});
let focusGeneration=0;
async function setFocusImage(source){
  const generation=++focusGeneration;
  if(uploadPosterUrl){URL.revokeObjectURL(uploadPosterUrl);uploadPosterUrl=null;}
  const img=$('edit-poster');
  $('focus-image').hidden=true;
  img.removeAttribute('src');
  if(source instanceof File){
    if(/\.tiff?$/i.test(source.name)){
      const body=new FormData();body.append('image',source);
      try{
        const response=await api('/api/admin/upload-poster',{method:'POST',body,raw:true});
        source=await response.blob();
      }catch(e){if(generation===focusGeneration)message('studio-message',errorText(e),true);return;}
      if(generation!==focusGeneration)return;
    }
    uploadPosterUrl=URL.createObjectURL(source);source=uploadPosterUrl;
  }
  if(source)img.src=source;
}
function drawFocusImage(){
  const img=$('edit-poster'), canvas=$('rotated-focus');
  if(!img.complete||!img.naturalWidth)return;
  const rotate=img.naturalWidth>img.naturalHeight && $('parameters-form').elements.orientation.value==='portrait';
  img.hidden=rotate;canvas.hidden=!rotate;
  if(rotate){
    const ratio=Math.min(1,1400/img.naturalWidth);
    canvas.width=Math.round(img.naturalHeight*ratio);canvas.height=Math.round(img.naturalWidth*ratio);
    const ctx=canvas.getContext('2d');
    ctx.translate(canvas.width,0);ctx.rotate(Math.PI/2);
    ctx.drawImage(img,0,0,canvas.height,canvas.width);
  }
  $('focus-image').hidden=false;
}
$('edit-poster').addEventListener('load',drawFocusImage);
$('parameters-form').elements.orientation.addEventListener('change',()=>{
  const img=$('edit-poster'), fields=$('parameters-form').elements;
  if(img.naturalWidth>img.naturalHeight){
    for(let i=0;i<points.length;i++){
      if(i===pointIndex)continue;
      const q=points[i],x=q.focus_x,y=q.focus_y,rotate=fields.orientation.value==='portrait';
      q.focus_x=rotate?1-y:y;q.focus_y=rotate?x:1-x;
    }
    const x=+fields.focus_x.value,y=+fields.focus_y.value;
    const rotate=fields.orientation.value==='portrait';
    fields.focus_x.value=+(rotate?100-y:y).toFixed(1);
    fields.focus_y.value=+(rotate?x:100-x).toFixed(1);
  }
  drawFocusImage();updateFocusMarker();
});
$('edit-poster').addEventListener('error',()=>{$('focus-image').hidden=true;});
function clamp(value,low,high){return Math.max(low,Math.min(high,value));}

// Background-plane geometry at peak zoom (Scene.camera/warp at phase 0.5).
let suggestions=[],autoGeneration=0;
function resetAutoRoute(){
  autoGeneration++;suggestions=[];$('auto-review').hidden=true;$('auto-frames').replaceChildren();$('auto-zoom').disabled=false;
}
function suggestedPoints(){
  const object=state.selected;
  const rotate=$('parameters-form').elements.orientation.value==='portrait'&&object.source_width>object.source_height;
  return suggestions.map((p,i)=>({name:p.name||t('autoStructure')+' '+(i+1),zoom:p.zoom,
    focus_x:rotate?1-p.y:p.x,focus_y:rotate?p.x:p.y}));
}
function showAutoRoute(){
  if(!suggestions.length)return;
  const proposals=suggestedPoints(),frames=$('auto-frames');
  frames.replaceChildren();$('auto-list').replaceChildren();
  proposals.forEach((pt,i)=>{
    const c=cropGeometry({...activeParams(),...pt},i,proposals.length);
    const box=node('span','auto-frame',String(i+1));
    Object.assign(box.style,{left:c.left*100+'%',top:c.top*100+'%',width:c.size*100+'%',height:c.size*100+'%'});
    frames.append(box);$('auto-list').append(node('li','',pt.name+' · '+pt.zoom+'×'));
  });
}
$('auto-zoom').addEventListener('click',async()=>{
  resetAutoRoute();const generation=autoGeneration;
  $('auto-zoom').disabled=true;$('auto-review').hidden=false;$('auto-note').textContent=t('working');$('auto-list').replaceChildren();$('auto-apply').hidden=true;
  try{
    const reply=await api('/api/admin/objects/'+state.selected.id+'/autozoom',{method:'POST',body:{count:Number($('auto-count').value)}});
    if(generation!==autoGeneration)return;
    suggestions=reply.points;$('auto-note').textContent=t(suggestions.length?'autoReview':'autoEmpty');$('auto-apply').hidden=!suggestions.length;showAutoRoute();
  }catch(e){if(generation===autoGeneration)$('auto-note').textContent=errorText(e);}
  finally{if(generation===autoGeneration)$('auto-zoom').disabled=false;}
});
$('auto-cancel').addEventListener('click',resetAutoRoute);
$('auto-count').addEventListener('change',resetAutoRoute);
$('auto-apply').addEventListener('click',()=>{
  if(!suggestions.length)return;
  points=suggestedPoints();resetAutoRoute();$('point-count').value=points.length;choosePoint(0);
});
function cropGeometry(p,index=pointIndex,count=points.length){
  const factor=p.method==='kenburns'?1:1-.35*p.depth;
  const margin=1.025+2*Math.max(Math.abs(p.pan_x),Math.abs(p.pan_y))*(1+1.2*p.depth);
  const size=1/(margin*(p.zoom+Math.min(p.zoom-1,.35)*(factor-1)));
  const phase=2*Math.PI*(index+1)/(count+1);
  const motion=p.motion==='push'?.2:1;
  const shiftX=-Math.sin(phase)*motion*p.pan_x*factor*size;
  const orbitShift=-(p.motion==='orbit'?Math.cos(phase):Math.sin(phase)*motion)*p.pan_y*factor*size;
  const left=clamp(p.focus_x+shiftX-size/2,0,1-size);
  const top=clamp(p.focus_y+orbitShift-size/2,0,1-size);
  return {size,left,top,orbitShift,shiftX};
}
function updateFocusMarker(){
  showAutoRoute();
  const p=activeParams(),crop=cropGeometry(p);
  savePoint();
  const ghosts=$('other-frames');ghosts.replaceChildren();
  points.forEach((pt,i)=>{
    if(i===pointIndex)return;
    const c=cropGeometry({...p,...pt},i),box=node('span','ghost-crop',String(i+1));
    Object.assign(box.style,{left:c.left*100+'%',top:c.top*100+'%',width:c.size*100+'%',height:c.size*100+'%'});
    ghosts.append(box);
  });
  $('focus-marker').style.left=p.focus_x*100+'%';
  $('focus-marker').style.top=p.focus_y*100+'%';
  const frame=$('zoom-frame').style;
  frame.left=crop.left*100+'%';
  frame.top=crop.top*100+'%';
  frame.width=frame.height=crop.size*100+'%';
  $('preview-image').hidden=true;
}
function setFocusPoint(x,y){
  const fields=$('parameters-form').elements;
  fields.focus_x.value=(clamp(x,0,1)*100).toFixed(1);
  fields.focus_y.value=(clamp(y,0,1)*100).toFixed(1);
  updateOutputs();
}
for(const input of document.querySelectorAll('.focus-fields input'))input.addEventListener('input',updateFocusMarker);

const focusImage=$('focus-image');
let gesture=null;
focusImage.addEventListener('dragstart',event=>event.preventDefault());
focusImage.addEventListener('pointerdown',event=>{
  if(gesture||event.button!==0||!event.isPrimary)return;
  const p=activeParams();
  gesture={id:event.pointerId,x:event.clientX,y:event.clientY,rect:focusImage.getBoundingClientRect(),
    crop:cropGeometry(p),params:p,corner:event.target.dataset.corner,inside:!!event.target.closest('#zoom-frame'),moved:false};
  focusImage.setPointerCapture(event.pointerId);
});
function resizeCrop(g,dx,dy){
  const {left,top,size}=g.crop;
  const east=g.corner.endsWith('e'),south=g.corner.startsWith('s');
  const anchorX=east?left:left+size,anchorY=south?top:top+size;
  const {width,height}=g.rect;
  // Project the pointer onto the crop diagonal in screen pixels.
  const delta=((east?dx:-dx)*width+(south?dy:-dy)*height)/(width*width+height*height);
  const fields=$('parameters-form').elements;
  const maxSize=Math.min(east?1-anchorX:anchorX,south?1-anchorY:anchorY);
  const desired=clamp(size+delta,cropGeometry({...g.params,zoom:+fields.zoom.max}).size,maxSize);
  // Snap to the same valid zoom ticks as the slider, keeping the far corner fixed.
  let low=Math.round(+fields.zoom.min/+fields.zoom.step),high=Math.round(+fields.zoom.max/+fields.zoom.step);
  while(low<high){
    const mid=Math.floor((low+high)/2);
    if(cropGeometry({...g.params,zoom:mid*fields.zoom.step}).size>desired+1e-10)low=mid+1;
    else high=mid;
  }
  fields.zoom.value=(low*fields.zoom.step).toFixed(2);
  const crop=cropGeometry({...g.params,zoom:+fields.zoom.value});
  setFocusPoint(anchorX+(east?1:-1)*crop.size/2-crop.shiftX,anchorY+(south?1:-1)*crop.size/2-crop.orbitShift);
}
focusImage.addEventListener('pointermove',event=>{
  if(!gesture||gesture.id!==event.pointerId||!gesture.inside)return;
  const dx=event.clientX-gesture.x,dy=event.clientY-gesture.y;
  if(!gesture.moved&&Math.hypot(dx,dy)<3)return;
  gesture.moved=true;
  if(gesture.corner){resizeCrop(gesture,dx,dy);return;}
  focusImage.classList.add('is-dragging');
  const {left,top,size,orbitShift}=gesture.crop;
  const x=clamp(left+dx/gesture.rect.width,0,1-size);
  const y=clamp(top+dy/gesture.rect.height,0,1-size);
  setFocusPoint(x+size/2-gesture.crop.shiftX,y+size/2-orbitShift);
});
focusImage.addEventListener('pointerup',event=>{
  if(!gesture||gesture.id!==event.pointerId)return;
  if(!gesture.moved&&!gesture.corner){
    const {left,top,width,height}=gesture.rect;
    setFocusPoint((event.clientX-left)/width,(event.clientY-top)/height);
  }
  focusImage.releasePointerCapture(event.pointerId);
});
focusImage.addEventListener('lostpointercapture',()=>{
  gesture=null;
  focusImage.classList.remove('is-dragging');
});

function showVersions(){
  const versions=state.selected?.versions||[];
  const list=$('version-list');
  const previous=list.value;
  const signature=JSON.stringify([language,...versions.map(v=>[v.id,v.selected])]);
  if(list.dataset.signature===signature)return;
  list.dataset.signature=signature;
  $('versions-section').hidden=!versions.length;
  list.replaceChildren();
  versions.forEach((v,i)=>{
    const date=new Date(v.created_at).toLocaleString(language==='nl'?'nl-NL':'en-GB');
    const label=t('version')+' '+(versions.length-i)+' · '+date+(v.selected?' · '+t('inGallery'):'');
    list.add(new Option(label,v.id));
  });
  const preferred=versions.find(v=>v.id===previous)||versions.find(v=>v.selected)||versions[0];
  if(preferred)list.value=preferred.id;
  reviewVersion();
}
function reviewVersion(){
  const v=state.selected?.versions?.find(v=>v.id===$('version-list').value);
  const player=$('version-video');
  if(!v){if(player.hasAttribute('src')){player.removeAttribute('src');player.load();}return;}
  if(player.getAttribute('src')!==v.url){player.src=v.url;
    player.poster=state.selected.source_poster+(v.params.orientation==='portrait'&&state.selected.source_width>state.selected.source_height?'?rotation=90':'');}
  const p=v.params;
  const details=$('version-params');
  details.replaceChildren();
  const percent=n=>+(100*n).toFixed(1)+'%';
  const items=[
    ['orientation',t(p.orientation==='portrait'?'orientPortrait':'orientOriginal')],['method',t('method_'+p.method)],['motion',t('motion_'+p.motion)],['zoom',p.zoom+'×'],
    ['focusPoint',percent(p.focus_x)+' / '+percent(p.focus_y)],['panX',percent(p.pan_x)],['panY',percent(p.pan_y)],
    ['depth',p.depth],['duration',p.duration+' s'],['frameRate',p.fps+' fps'],['resolution',p.resolution+' px'],
    ['starLayer',p.star_source==='auto'?t('automatic'):p.star_source],['blending',p.blend==='auto'?t('automatic'):p.blend]
  ];
  for(const [key,value] of items)fact(details,t(key),value);
  if(p.zoom_points?.length)p.zoom_points.forEach((pt,i)=>fact(details,t('focusPoint')+' '+(i+1),(pt.name?pt.name+' · ':'')+pt.zoom+'× · '+percent(pt.focus_x)+' / '+percent(pt.focus_y)));
  const button=$('publish-version');
  $('delete-version').hidden=v.selected;
  button.disabled=v.selected;
  button.textContent=t(v.selected?'inGallery':'chooseGallery');
}
$('version-list').addEventListener('change',reviewVersion);
$('publish-version').addEventListener('click',async()=>{
  const object=state.selected;
  const id=$('version-list').value;
  $('publish-version').disabled=true;
  try{
    await api('/api/admin/objects/'+object.id+'/versions/'+id+'/select',{method:'PUT'});
    await refreshAdmin();toast(t('saved'));
  }catch(e){toast(errorText(e));reviewVersion();}
});
$('delete-version').addEventListener('click',async()=>{
  const list=$('version-list'),id=list.value,object=state.selected;
  if(!object||!id||!window.confirm(object.id+' · '+list.selectedOptions[0].text+'\\n\\n'+t('deletePrompt')))return;
  const player=$('version-video');
  player.pause();player.removeAttribute('src');player.load();
  $('delete-version').disabled=true;
  try{
    const result=await api('/api/admin/objects/'+object.id+'/versions/'+id,{method:'DELETE'});
    await refreshAdmin();toast(t(result.cleanup_pending?'deleteDeferred':'versionDeleted'));
  }catch(e){toast(errorText(e));await refreshAdmin();reviewVersion();}
  finally{$('delete-version').disabled=false;}
});
let polling=false;
setInterval(async()=>{
  if(!studioRoute||document.hidden||!state.session?.authenticated||polling)return;
  polling=true;
  try{await refreshAdmin();}catch{}finally{polling=false;}
},2500);
setLanguage(language);fillParams();
if(studioRoute){document.title='AstroWeb · Studio';openStudio();}else if(viewerRoute)loadViewer();else loadGallery();
