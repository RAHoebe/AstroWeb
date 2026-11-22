import {enablePinch} from './pinch.js';
import {openPolar,closePolar,drawPolar} from './polar.js';
import {layoutComparison,setComparisonObject,openEnvironment,comparisonText} from './compare.js';
import {configureGalaxy,openGalaxy,stopGalaxy,setJourneyLabels,atlasLanguage} from './atlas.js';
import {t,local,language,setLanguage,formatDate,duration} from './i18n.js';
import {editPanorama,editorLanguage} from './panorama-editor.js';
import {SkyPlayer} from './sky.js';
const $=id=>document.getElementById(id);
const state={objects:[],adminObjects:[],jobs:[],session:null,selected:null,current:null,files:[],busy:false,uploading:false,preview:null};
const studioRoute = location.pathname === '/admin';
document.body.classList.toggle('studio-route', studioRoute);
$('studio').hidden = !studioRoute;
const viewerRoute=location.pathname.startsWith('/viewer/');
document.body.classList.toggle('viewer-route',viewerRoute);
$('viewer').hidden=!viewerRoute;
let journeyInfo=null;
let featuredId = null;
let gaiaDepthRequest=0;
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
function applyLanguage(value){setLanguage(value);$('exploration-frame').contentWindow?.postMessage({type:'astroweb-language',language:value},location.origin);drawPicker();if(!viewerRoute&&!studioRoute)buildGallery();if(state.current){renderViewerText();journeyCaption();hubbleCaption();layoutOriginal();atlasLanguage();drawPolar();renderDiscovery();comparisonText();}renderLogin();renderAdminList();renderJobs();renderFileList();renderDraftIdentity();renderUploadProgress();showAutoRoute();document.querySelectorAll('[data-edit-key]').forEach(el=>el.textContent=t(el.dataset.editKey)+' · '+el.dataset.editLanguage.toUpperCase());if(state.selected){renderChoice();showVersions();editorLanguage();updateGaiaDepth();}if(studioRoute)document.title='AstroWeb · Studio';sky.updateLanguage();}
document.querySelectorAll('[data-lang]').forEach(button=>button.addEventListener('click',()=>applyLanguage(button.dataset.lang)));

async function loadGallery(){try{state.objects=(await api('/api/objects')).objects;buildGallery();}catch(e){$('gallery-grid').replaceChildren(node('div','empty-state',errorText(e)));}}
function galleryEdgeGray(image){
  const width=image.naturalWidth, height=image.naturalHeight;
  const canvas=document.createElement('canvas');
  canvas.width=width;canvas.height=2;
  const ctx=canvas.getContext('2d');
  if(!ctx)return;
  ctx.drawImage(image,0,0,width,1,0,0,width,1);
  ctx.drawImage(image,0,height-1,width,1,0,1,width,1);
  const pixels=ctx.getImageData(0,0,width,2).data, levels=[];
  for(let i=0;i<pixels.length;i+=4){
    levels.push(Math.round(.2126*pixels[i]+.7152*pixels[i+1]+.0722*pixels[i+2]));
  }
  levels.sort((a,b)=>a-b);
  const gray=Math.round((levels[width-1]+levels[width])/2);
  image.parentElement.style.backgroundColor=`rgb(${gray}, ${gray}, ${gray})`;
}

function buildGallery(){
  const grid=$('gallery-grid');observer.disconnect();grid.querySelectorAll('video').forEach(video=>video.pause());grid.replaceChildren();
  const count=state.objects.length;$('gallery-count').textContent=String(count).padStart(2,'0')+' '+t(count===1?'filmSingular':'films');
  $('hero-play').disabled=!count;
  if(!count){grid.append(node('div','empty-state',t('emptyGallery')));return;}
  let hero=state.objects.find(o=>o.id===featuredId);
  if(!hero){hero=state.objects[Math.floor(Math.random()*count)];featuredId=hero.id;}$('hero-image').src=hero.poster;$('hero-name').textContent=local(hero.metadata.name);$('hero-id').textContent=captureLabel(hero);
  state.objects.forEach(object=>{
    const card=node('a','gallery-card');card.href='/viewer/'+encodeURIComponent(object.id);card.setAttribute('aria-label',t('openFilm')+' · '+local(object.metadata.name));
    const media=node('div','card-media'), image=node('img'), video=node('video');
    image.width=object.width;image.height=object.height;image.alt=local(object.metadata.name);image.loading='lazy';
    video.muted=true;video.loop=true;video.playsInline=true;video.preload='none';video.setAttribute('aria-hidden','true');
    media.append(image,video);
    image.addEventListener('load',()=>galleryEdgeGray(image),{once:true});
    image.src=object.poster;
    const info=node('div','card-info');const category=node('div','card-type');category.append(node('span','',captureLabel(object)),node('span','',local(object.metadata.type)));info.append(category,node('h3','',local(object.metadata.name)),node('p','',local(object.metadata.summary)));
    const tags=node('div','card-tags');const details=[object.capture_date?object.capture_date.slice(0,10):'',local(object.metadata.constellation),object.observation?.telescope,duration(object.observation?.integration)].filter(Boolean);details.forEach(text=>{const tag=node('span');tag.append(node('i'),document.createTextNode(text));tags.append(tag);});info.append(tags);card.append(media,info);
    async function play(){if(reducedMotion.matches||document.hidden)return;if(!video.src)video.src=object.preview||object.video;try{await video.play();if(card.matches(':hover')||document.activeElement===card)card.classList.add('playing');else video.pause();}catch{card.classList.remove('playing');}}
    function pause(){video.pause();card.classList.remove('playing');}
    card.addEventListener('pointerenter',event=>{if(event.pointerType!=='touch')play();});card.addEventListener('pointerleave',pause);card.addEventListener('focus',play);card.addEventListener('blur',pause);card.addEventListener('click',pause);card.addEventListener('keydown',event=>{if(event.key===' '){event.preventDefault();card.click();}});grid.append(card);observer.observe(card);
  });
}
$('hero-play').addEventListener('click',()=>{const object=state.objects.find(o=>o.id===featuredId);if(object)openViewer(object);});
const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(!entry.isIntersecting){entry.target.querySelector('video')?.pause();entry.target.classList.remove('playing');}}));

document.addEventListener('visibilitychange',()=>{if(document.hidden){document.querySelectorAll('video').forEach(video=>video.pause());sky.pause();}});

function fact(list,label,value){if(value===undefined||value===null||value==='')return;const item=node('div');item.append(node('dt','',label),node('dd','',String(value)));list.append(item);}
function captureLabel(obj){
  if(obj.capture_kind)return [t(obj.capture_kind),obj.session_name].filter(Boolean).join(' · ');
  return [(obj.catalog_id||obj.id).replace('_',' '),obj.session_name].filter(Boolean).join(' · ');
}
function renderNeighbours(){
  const links=state.current?.neighbours||{},nav=$('viewer-neighbours');
  nav.hidden=!links.previous;
  if(nav.hidden)return;
  for(const [key,id,caption] of [['previous','viewer-prev','previousObject'],['next','viewer-next','nextObject']]){
    const obj=links[key],a=$(id);
    a.href='/viewer/'+encodeURIComponent(obj.id)+location.hash;
    const identifier=(obj.catalog_id||obj.id).split('~')[0].replace(/[\s_]+/g,'').toLowerCase();
    const name=local(obj.name).split('·').map(part=>part.trim()).filter(part=>part.replace(/[\s_]+/g,'').toLowerCase()!==identifier).join(' · ');
    a.replaceChildren(node('small','',t(caption)),node('strong','',captureLabel(obj)),node('span','',name));
  }
}
function captureOptionLabel(captures, capture, index){
  const stamp=capture.capture_date??capture.date;
  let text=t('unknownDate');
  if(stamp){
    const dayOnly=stamp.length===10, date=new Date(dayOnly?stamp+'T00:00:00Z':stamp);
    const options=dayOnly?{dateStyle:'long'}:{dateStyle:'medium',timeStyle:'short'};
    if(Number.isFinite(date.getTime()))text=formatDate(date,{...options,timeZone:'UTC'})+(dayOnly?'':' UTC');
  }
  const repeated=captures.filter(o=>(o.capture_date??o.date)===stamp&&o.session_name===capture.session_name).length>1;
  return [text,capture.session_name,repeated?t('captureNumber')+' '+(index+1):'',
    capture.published?'':t('unpublished')].filter(Boolean).join(' · ');
}
function renderCaptureDates(object){
  const select=$('capture-date-picker'),captures=object.captures||[];
  $('capture-total').textContent=' ('+captures.length+' '+t(captures.length===1?'oneCapture':'manyCaptures')+')';
  select.replaceChildren();
  for(const [i,v] of captures.entries())select.add(new Option(captureOptionLabel(captures,v,i),v.id));
  select.value=object.id;select.disabled=captures.length<2;
}
$('capture-date-picker').addEventListener('change',e=>{
  location.assign('/viewer/'+encodeURIComponent(e.target.value)+location.hash);
});
function renderViewerText(){
  renderNeighbours();renderCaptureDates(state.current);
  const object=state.current,m=object.metadata,obs=object.observation||{};document.title=local(m.name)+' · AstroWeb';$('viewer-id').textContent=captureLabel(object)+' · '+local(m.type);$('viewer-title').textContent=local(m.name);$('viewer-description').textContent=local(m.description);$('viewer-original').alt=local(m.name);$('viewer-facts').replaceChildren();
  fact($('viewer-facts'),t('constellation'),local(m.constellation));fact($('viewer-facts'),t('catalogTarget'),m.target);fact($('viewer-facts'),t('integration'),duration(obs.integration));fact($('viewer-facts'),t('telescope'),obs.telescope);fact($('viewer-facts'),t('frames'),obs.frames);fact($('viewer-facts'),t('singleExposure'),obs.exposure?obs.exposure+' s':'');fact($('viewer-facts'),t('filter'),obs.filter);
  if(obs.date_obs){const stamp=new Intl.DateTimeFormat(language==='nl'?'nl-NL':'en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:obs.timezone||'UTC'}).format(new Date(obs.date_obs));fact($('viewer-facts'),t(obs.time_source==='filename'?'observedAtFilename':'observedAt'),stamp+' · '+(obs.timezone||'UTC'));}
  $('viewer-sources').replaceChildren();const links=[...(m.sources||[])];if(m.external&&!links.some(link=>link.url===m.external.url))links.push({label:m.external.provider,url:m.external.url});for(const link of links){if(!/^https:\/\//.test(link.url))continue;const a=node('a','',link.label+' ↗');a.href=link.url;a.target='_blank';a.rel='noopener noreferrer';$('viewer-sources').append(a);}
  $('external-description').replaceChildren();if(m.external){const ext=m.external;const details=node('details','external-block');details.append(node('summary','',t('nasaMore')));const text=local(ext.text);details.append(node('p','',text||t('untranslated')));if(language==='nl'&&ext.translation==='machine')details.append(node('p','small',t('machineTranslation')));details.append(node('p','small',ext.credit+' · '+t('fetchedAt')+' '+formatDate(ext.fetched_at)));$('external-description').append(details);}
}
function openViewer(object){location.assign('/viewer/'+encodeURIComponent(object.id));}
async function loadViewer(){
  let object;
  try{object=await api('/api/objects/'+location.pathname.split('/').pop());}
  catch(e){$('viewer-title').textContent=errorText(e);return;}
  state.current=object;
  for(const name of ['mosaic','space','cosmic','solar'])$('exploration-'+name).hidden=!object.explorations?.[name];
  if(object.alignment_pending)watchViewerAlignment(object.id);
  $('hubble-tab').hidden=!object.hubble_available;
  if(object.body){
    document.querySelector('[data-view="polar"]').hidden=true;
    const setLabel=(el,key)=>{el.dataset.i18n=key;el.textContent=t(key);};
    const tab=$('hubble-tab');
    tab.hidden=false;tab.dataset.view='solar-system';setLabel(tab,'solarTour');
    setLabel($('hubble-panel').querySelector('strong'),'solarTour');
    $('hubble-video').dataset.i18nAria='solarTour';$('hubble-video').setAttribute('aria-label',t('solarTour'));
    $('skymap-link').hidden=true;
    setLabel($('sky-panel').querySelector('.eyebrow'),'solarSkyDay');
    $('ir-toggle').closest('label').hidden=true;
  }
  const query=new URLSearchParams(location.search);
  if(query.get('from')==='calendar'){
    const link=document.querySelector('.viewer-actions [data-i18n="backGallery"]');link.dataset.i18n='backCalendar';link.textContent=t('backCalendar');
    const params=new URLSearchParams({month:query.get('month')||'',day:query.get('day')||''});if(query.get('target'))params.set('target',query.get('target'));link.href='/calendar?'+params;
  }
  if(query.get('from')==='panorama'){
    const link=document.querySelector('.viewer-actions [data-i18n="backGallery"]');
    link.dataset.i18n='panoReturn';link.textContent=t('panoReturn');
    link.href='/panorama'+(query.get('scene')?'?capture='+encodeURIComponent(query.get('scene')):'');
  }
  setComparisonObject(object.id);
  $('environment-tab').hidden=!object.environment_available;
  configureGalaxy(object.galaxy,object.metadata.name);
  $('download-movie').hidden=!object.video;
  if(object.video)$('download-movie').href=object.video+(object.video.includes('?')?'&':'?')+'download=1';
  $('download-original').href=object.final+'?download=1';
  if(object.capture_kind){
    $('capture-panorama').hidden=false;
    $('capture-panorama').href='/panorama?capture='+encodeURIComponent(object.id);
    for(const tab of document.querySelectorAll('[data-view]'))tab.hidden=!['film','original'].includes(tab.dataset.view);
    $('ir-toggle').closest('label').hidden=true;
  }
  renderViewerText();
  const tab=location.hash.slice(1);
  const requested=query.has('discover')&&tab==='original'?'discover':object.body&&tab==='hubble'?'solar-system':tab;
  selectTab([...document.querySelectorAll('[data-view]:not([hidden])')].some(el=>el.dataset.view===requested)?requested:'film');
  if(object.video&&!$('film-panel').hidden&&!reducedMotion.matches)$('viewer-video').play().catch(()=>{});}
function watchViewerAlignment(id,attempt=0){
  if(attempt>=36)return;
  setTimeout(async()=>{
    if(state.current?.id!==id)return;
    if(document.hidden){watchViewerAlignment(id,attempt+1);return;}
    try{
      const updated=await api('/api/objects/'+encodeURIComponent(id));
      state.current.explorations=updated.explorations;
      for(const name of ['mosaic','space','cosmic','solar'])$('exploration-'+name).hidden=!updated.explorations?.[name];
      if(updated.alignment_pending)watchViewerAlignment(id,attempt+1);
    }catch{/* A failed optional refresh must not interrupt the current film. */}
  },5000);
}
function selectTab(name){
  const exploration=['mosaic','space','cosmic','solar'].includes(name);
  const activePanel=exploration?'exploration':({'solar-system':'hubble',discover:'original'}[name]||name);
  for(const tab of document.querySelectorAll('[data-view]')){
    const selected=tab.dataset.view===name;
    tab.setAttribute('aria-selected',String(selected));
    tab.tabIndex=selected?0:-1;
  }
  for(const panel of ['film','original','journey','galaxy','environment','hubble','sky','polar','exploration']){
    $(panel+'-panel').hidden=panel!==activePanel;
  }
  history.replaceState(null,'',location.pathname+location.search+(name==='film'?'':'#'+name));
  const frame=$('exploration-frame');
  if(exploration){
    if(frame.dataset.mode!==name){frame.dataset.mode=name;frame.title=t('obs_'+name);frame.src='/observatory?'+new URLSearchParams({embed:'1',capture:state.current.id,mode:name,lang:language});}
    else frame.contentWindow?.postMessage({type:'astroweb-active',active:true},location.origin);
  }else frame.contentWindow?.postMessage({type:'astroweb-active',active:false},location.origin);
  const object=state.current;
  const note=$('viewer-interpretation');note.dataset.i18n=exploration?'obs_note_'+name:'artisticNote';note.textContent=t(note.dataset.i18n);
  if(['original','discover'].includes(name)&&!$('viewer-original').hasAttribute('src')){
    $('viewer-original').src=object.original_view||object.final;
  }
  if(name==='film'&&object.video&&!$('viewer-video').hasAttribute('src')){
    $('viewer-video').poster=object.poster;
    $('viewer-video').src=object.video;
  }
  if(name==='discover'){
    if($('ir-toggle').checked){
      $('ir-toggle').checked=false;
      $('ir-toggle').dispatchEvent(new Event('change'));
    }
    $('discovery-card').hidden=$('discovery-pins').hidden=false;
    loadDiscovery();
  }else{
    $('discovery-card').hidden=$('discovery-pins').hidden=true;
    closeSurfaceForm();
  }
  if(name==='polar')openPolar(state.current.id);else closePolar();
  renderNeighbours();
  if(name==='hubble'||name==='solar-system')openHubble();else $('hubble-video').pause();
  if(name==='environment')openEnvironment(state.current.id);
  if(name==='galaxy')openGalaxy();else stopGalaxy();
  if(name==='journey')loadJourney();else $('journey-video').pause();
  if(name!=='film')$('viewer-video').pause();if(name!=='sky')sky.pause();else sky.load(state.current,api);}
window.addEventListener('hashchange',()=>{
  if(!viewerRoute||!state.current)return;
  const tab=[...document.querySelectorAll('[data-view]:not([hidden])')].find(el=>el.dataset.view===location.hash.slice(1));
  selectTab(tab?.dataset.view||'film');
});
window.addEventListener('message',event=>{if(event.origin===location.origin&&event.source===$('exploration-frame').contentWindow&&event.data?.type==='astroweb-close-exploration')selectTab('film');});
$('exploration-frame').addEventListener('load',()=>{const frame=$('exploration-frame');frame.contentWindow?.postMessage({type:'astroweb-active',active:!$('exploration-panel').hidden},location.origin);frame.contentWindow?.postMessage({type:'astroweb-language',language},location.origin);});
document.querySelectorAll('[data-view]').forEach(tab=>{tab.addEventListener('click',()=>selectTab(tab.dataset.view));tab.addEventListener('keydown',event=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('[data-view]:not([hidden])')],index=tabs.indexOf(tab);const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].focus();selectTab(tabs[next].dataset.view);});});
const originalStage=$('original-stage'),originalImage=$('viewer-original');
let photoZoom=1, photoX=0, photoY=0, photoDrag=null;
function showPhysicalScale(w,h,width,height){
  const measure=state.current?.physical,source=$('physical-source');
  if(!measure)return;
  const fmt=n=>n.toLocaleString(language,{maximumSignificantDigits:3})+' '+t('lightYears');
  source.hidden=!measure.source;if(measure.source)source.href=measure.source;
  $('physical-distance').textContent=measure.distance_ly?t('envDistance')+' ≈ '+fmt(measure.distance_ly)+(measure.distance_km?' ('+measure.distance_km.toLocaleString(language,{maximumSignificantDigits:4})+' km)':''):t('scaleUnknown');
  $('physical-size').textContent=measure.width_ly&&measure.height_ly?t('visibleScale')+' · '+t('fieldWidth')+' ≈ '+fmt(measure.width_ly*Math.min(1,w/width))+' · '+t('fieldHeight')+' ≈ '+fmt(measure.height_ly*Math.min(1,h/height)):measure.distance_ly?t('scaleUnmeasured'):'';
}
function layoutOriginal(){
  const w=originalStage.clientWidth, h=originalStage.clientHeight;
  if(!w||!h||!originalImage.naturalWidth)return;
  const fit=Math.min(w/originalImage.naturalWidth,h/originalImage.naturalHeight);
  const width=originalImage.naturalWidth*fit*photoZoom,height=originalImage.naturalHeight*fit*photoZoom;
  showPhysicalScale(w,h,width,height);
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
function zoomOriginal(value,x=0,y=0,nx=x,ny=y){
  const control=$('original-scale');
  control.value=String(value);
  const next=Number(control.value),ratio=next/photoZoom;
  photoX=nx+(photoX-x)*ratio;photoY=ny+(photoY-y)*ratio;
  guideZoom=false;
  $('discovery-zoom').textContent=t('zoomFeature');
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
originalStage.addEventListener('dblclick',e=>{
  if(!surfaceEdit&&!e.target.closest('.discovery-pin'))zoomOriginal(photoZoom===1?+$('original-scale').max:1,...photoAnchor(e));
});
enablePinch(originalStage,{
  getZoom:()=>photoZoom,
  begin(){photoDrag=null;originalStage.classList.remove('dragging');},
  transform(value,previous,next){zoomOriginal(value,previous.x,previous.y,next.x,next.y);}
});
originalStage.addEventListener('pointerdown',e=>{
  if(surfaceEdit||e.target.closest('.discovery-pin')||photoZoom===1||!e.isPrimary||e.button!==0)return;
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

let discoveries=null, discoveryPending=null, discoveryId=null, guideZoom=false, surfaceEdit=null, discoverySearching=false;
async function loadDiscovery(){
  if(!$('discovery-card').hidden && !discoveries){
    $('discovery-status').textContent=t('discoverLoading');
    discoveryPending??=api('/api/objects/'+encodeURIComponent(state.current.id)+'/discover');
    try{discoveries=await discoveryPending;}
    catch(e){$('discovery-status').textContent=errorText(e);return;}
    finally{discoveryPending=null;}
  }
  renderDiscovery();
  if(!state.current?.body && discoveries && discoveries.kind!=='missing' && !discoveries.catalogue && !discoverySearching){
    discoverySearching=true;
    renderDiscovery();
    try{discoveries=await api('/api/objects/'+encodeURIComponent(state.current.id)+'/discover?catalogue=1');}
    catch{discoveries.catalogue='unavailable';}
    finally{discoverySearching=false;renderDiscovery();}
  }
}

function currentFeature(){
  return discoveries?.objects.find(o=>o.id===discoveryId)||discoveries?.objects[0];
}

function zoomToFeature(){
  const feature=currentFeature();
  if(!feature||!originalImage.naturalWidth)return;
  const width=originalStage.clientWidth, height=originalStage.clientHeight;
  const fit=Math.min(width/originalImage.naturalWidth,height/originalImage.naturalHeight);
  $('original-scale').value='3';
  photoZoom=3;
  photoX=(.5-feature.x)*originalImage.naturalWidth*fit*photoZoom;
  photoY=(.5-feature.y)*originalImage.naturalHeight*fit*photoZoom;
  layoutOriginal();
}

function pickFeature(id){
  if(surfaceEdit)return;
  discoveryId=id;
  renderDiscovery();
  if(guideZoom)zoomToFeature();
}

function stepFeature(step){
  const objects=discoveries?.objects||[];
  if(objects.length<2)return;
  const index=objects.findIndex(o=>o.id===discoveryId);
  pickFeature(objects[(index+step+objects.length)%objects.length].id);
}

function positionPin(button,x,y){
  button.style.left=(x*100)+'%';
  button.style.top=(y*100)+'%';
  button.classList.toggle('label-left',x>.65);
}

function renderDiscovery(){
  if(!discoveries||$('discovery-card').hidden)return;
  const {objects,kind,presets}=discoveries;
  const current=currentFeature();
  const pins=$('discovery-pins'), list=$('discovery-list');
  pins.replaceChildren();list.replaceChildren();
  $('surface-tools').hidden=!presets||!!surfaceEdit;
  $('surface-move').hidden=!current;
  $('surface-remove').hidden=current?.placement!=='manual';
  $('discovery-selection').hidden=!current||!!surfaceEdit;
  const missing=kind==='surface'?'surfaceEmpty':kind==='missing'?'discoverMissing':'discoverEmpty';
  $('discovery-status').textContent=discoverySearching?t('discoverySearching'):
    discoveries.catalogue==='unavailable'?t('discoveryCatalogueUnavailable'):current||surfaceEdit?'':t(missing);
  if(surfaceEdit)renderSurfaceForm();
  for(const o of objects){
    const label=local(o.name)||o.id;
    if(!surfaceEdit){
      const button=node('button','discovery-pin');
      button.type='button';button.title=label;button.dataset.label=label;
      if(o.label)button.classList.add('label-star');
      button.setAttribute('aria-label',label);
      button.setAttribute('aria-pressed',String(o.id===current?.id));
      positionPin(button,o.x,o.y);
      button.addEventListener('click',()=>{pickFeature(o.id);list.focus({preventScroll:true});});
      pins.append(button);
    }
    list.add(new Option(label,o.id));
  }
  if(current&&!surfaceEdit){
    discoveryId=current.id;
    list.value=discoveryId;
    $('discovery-prev').disabled=$('discovery-next').disabled=objects.length<2;
    $('discovery-zoom').textContent=t(guideZoom?'fitPhoto':'zoomFeature');
    $('discovery-description').textContent=[local(current.type),local(current.summary)].filter(Boolean).join(' · ');
    const details=[];
    if(Number.isFinite(current.ra)&&Number.isFinite(current.dec)){
      details.push('RA '+current.ra.toFixed(4)+'°','Dec '+current.dec.toFixed(4)+'°',...(current.aliases||[]));
    }
    const placementLabel={manual:'surfaceManual',registered:'surfaceRegistered','ring-axis':'surfaceRingAxis'}[current.placement];
    if(placementLabel)details.push(t(placementLabel));
    if(current.ly)details.push('≈ '+current.ly.toLocaleString(language)+' '+t('lightYears'));
    $('discovery-data').textContent=details.join(' · ');
    $('discovery-source').hidden=!current.source;
    if(current.source)$('discovery-source').href=current.source;
    $('discovery-journey').hidden=!current.journey;
    if(current.journey){
      const query=new URLSearchParams({destination:current.journey});
      $('discovery-journey').href=location.pathname+'?'+query+(state.current.body?'#solar-system':'#hubble');
    }
    $('discovery-studio').href='/admin?'+new URLSearchParams({capture:state.current.id,landmark:current.id});
  }
  if(surfaceEdit?.point){
    const {x,y}=surfaceEdit.point;
    const marker=node('span','discovery-pin discovery-draft');
    marker.setAttribute('aria-hidden','true');
    positionPin(marker,x,y);
    pins.append(marker);
  }
  layoutOriginal();
}

function openSurfaceForm(feature){
  const preset=discoveries.presets.find(entry=>entry.id===feature?.id);
  surfaceEdit={id:feature?.placement==='manual'?feature.id:null,preset:preset?.id||'',point:null,saving:false};
  $('surface-name').value=feature&&!preset?local(feature.name):'';
  zoomOriginal(1);
  renderDiscovery();
  $('surface-preset').focus();
}
function closeSurfaceForm(){
  if(!surfaceEdit)return;
  surfaceEdit=null;
  $('surface-form').hidden=true;
  originalStage.classList.remove('placing-label');
}
function renderSurfaceForm(){
  $('surface-form').hidden=false;
  originalStage.classList.add('placing-label');
  const pick=$('surface-preset');
  pick.replaceChildren(new Option(t('surfaceCustom'),''));
  for(const preset of discoveries.presets)pick.add(new Option(local(preset.name),preset.id));
  pick.value=surfaceEdit.preset;
  $('surface-name').hidden=!!surfaceEdit.preset;
  $('surface-name').required=!surfaceEdit.preset;
  $('surface-save').disabled=!surfaceEdit.point||surfaceEdit.saving;
}
async function saveSurface(payload){
  state.session??=await api('/api/session');
  const result=await api('/api/admin/objects/'+encodeURIComponent(state.current.id)+'/surface-label',{method:'PUT',body:payload});
  discoveryId=payload.remove?null:result.id;
  closeSurfaceForm();
  discoveries=null;
  await loadDiscovery();
  toast(t('saved'));
}

$('discovery-list').addEventListener('change',e=>pickFeature(e.target.value));
$('discovery-prev').addEventListener('click',()=>stepFeature(-1));
$('discovery-next').addEventListener('click',()=>stepFeature(1));
$('discovery-zoom').addEventListener('click',()=>{
  guideZoom=!guideZoom;
  if(guideZoom)zoomToFeature();else zoomOriginal(1);
  $('discovery-zoom').textContent=t(guideZoom?'fitPhoto':'zoomFeature');
});
$('surface-add').addEventListener('click',()=>openSurfaceForm());
$('surface-move').addEventListener('click',()=>openSurfaceForm(currentFeature()));
$('surface-cancel').addEventListener('click',()=>{closeSurfaceForm();renderDiscovery();$('surface-add').focus();});
$('surface-preset').addEventListener('change',e=>{surfaceEdit.preset=e.target.value;renderSurfaceForm();});
originalStage.addEventListener('click',e=>{
  if(!surfaceEdit||surfaceEdit.saving)return;
  const rect=originalImage.getBoundingClientRect();
  if(!rect.width||!rect.height)return;
  const x=(e.clientX-rect.left)/rect.width, y=(e.clientY-rect.top)/rect.height;
  if(x<0||x>1||y<0||y>1)return;
  surfaceEdit.point={x,y};
  renderDiscovery();
});
$('surface-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const edit=surfaceEdit;
  if(!edit?.point||edit.saving)return;
  edit.saving=true;
  $('surface-save').disabled=true;
  try{
    await saveSurface({id:edit.id,preset:edit.preset,name:$('surface-name').value,...edit.point});
    $('surface-add').focus();
  }catch(error){
    edit.saving=false;
    if(surfaceEdit===edit)$('surface-save').disabled=false;
    toast(errorText(error));
  }
});
$('surface-remove').addEventListener('click',async ()=>{
  const feature=currentFeature();
  if(feature?.placement!=='manual'||!confirm(t('surfaceRemovePrompt')))return;
  $('surface-remove').disabled=true;
  try{await saveSurface({id:feature.id,remove:true});$('surface-add').focus();}
  catch(error){toast(errorText(error));}
  finally{$('surface-remove').disabled=false;}
});

let hubbleFields=null,hubblePending=null,hubbleState='',hubbleObservations=[];
function hubbleCaption(){
  const select=$('hubble-field');
  let archiveIndex=0;
  for(const opt of select.options){
    const obs=hubbleObservations.find(o=>o.id===opt.value);
    if(obs?.provider){opt.textContent=obs.title;continue;}
    if(obs?.name){opt.textContent=local(obs.name);continue;}
    const label=obs?.id.startsWith('skymap-')?'NASA Hubble Skymap · '+obs.title:obs?.filter?(['ANY','NONE','PAR','PARALLEL'].includes(obs.target?.toUpperCase())?t('archiveField'):obs.target)+' · '+obs.filter:t('hubble_'+opt.value);
    const field=obs?.full_footprint?' · '+t('archiveRegion')+' '+(++archiveIndex):'';
    opt.textContent=t('hubble_'+(obs?.relation||'field'))+' · '+label+field;
  }
  const active=hubbleObservations.find(o=>o.id===select.value);
  const source=$('hubble-source');
  source.href=active?.source||(active?.filter?'https://hla.stsci.edu/hlaview.html#Images|'+encodeURIComponent(active.id):'https://esahubble.org/images/heic2501a/');
  source.textContent=active?.credit?active.credit+' ↗':active?.filter?'NASA/ESA Hubble · '+active.id+' ↗':'NASA, ESA, B. Williams (University of Washington) ↗';
  $('hubble-description').textContent=active?.provider?t('archiveMissionNote')+(active.provider==='jwst'?' '+t('archiveInfrared'):'')+' · '+active.telescope+' · '+active.filter:active?.name?t('solarMissionNote'):active?t('hubble_'+active.relation)+' · '+t(active.id.startsWith('skymap-')?'skymapNote':active.full_footprint?'fullHstNote':active.telescope?'hstPlateNote':active.source?'groundPlateNote':active.filter?'archiveHubbleNote':'hubbleNote'):'';
  const status=state.current?.body?({hubbleLoading:active?.cached===false?'solarPreparing':'solarLoading',hubble_unavailable:'solarDetailUnavailable',hubble_no_field:'solarDetailMissing'}[hubbleState]||hubbleState):hubbleState;
  if(active?.full_footprint)$('hubble-description').textContent+=' RA '+active.ra.toFixed(4)+'° · Dec '+active.dec.toFixed(4)+'°';
  if(active?.alignment==='lunar-map')$('hubble-description').textContent=t('lunarMissionNote');
  if(active?.alignment==='merope-wfpc2')$('hubble-description').textContent=t('meropeHubbleNote');
  if(active?.alignment==='saturn-ring-axis')$('hubble-description').textContent=t('saturnMissionNote');
  if(active?.alignment==='separate-moon')$('hubble-description').textContent=t('separateMoonNote');
  $('hubble-status').textContent=status?t(status):'';
  $('hubble-retry').hidden=hubbleState!=='hubble_unavailable';
}
function loadHubbleField(){
  const field=$('hubble-field').value,video=$('hubble-video');
  video.hidden=!field;
  if(!field)return;
  hubbleState='hubbleLoading';hubbleCaption();
  video.src='/media/'+encodeURIComponent(state.current.id)+(state.current.body?'/solar-system/':'/hubble/')+encodeURIComponent(field);
  video.load();
  if(!reducedMotion.matches&&!$('hubble-panel').hidden)video.play().catch(()=>{});
}
async function openHubble(){
  try{
    if(!hubbleFields){
      hubbleState='hubbleLoading';hubbleCaption();
      hubblePending??=api('/api/objects/'+encodeURIComponent(state.current.id)+(state.current.body?'/solar-system':'/hubble'));
      const {fields,observations}=await hubblePending;
      hubbleObservations=observations||[];
      if(!hubbleFields){
        hubbleFields=fields;
        const select=$('hubble-field');
        select.replaceChildren(...fields.map(k=>new Option(k,k)));
        const destination=new URLSearchParams(location.search).get('destination');
        if(fields.includes(destination))select.value=destination;
        hubbleCaption();
      }
    }
    $('hubble-field').disabled=!hubbleFields.length;
    if(!hubbleFields.length){hubbleState='hubble_no_field';$('hubble-video').hidden=true;hubbleCaption();return;}
    if(!$('hubble-panel').hidden&&!$('hubble-video').hasAttribute('src'))loadHubbleField();
  }catch{hubblePending=null;hubbleState='hubble_unavailable';hubbleCaption();}
}
$('hubble-field').addEventListener('change',loadHubbleField);
$('hubble-retry').addEventListener('click',()=>hubbleFields?.length?loadHubbleField():openHubble());
$('hubble-video').addEventListener('error',()=>{hubbleState='hubble_unavailable';hubbleCaption();});
$('hubble-video').addEventListener('loadeddata',()=>{const active=hubbleObservations.find(o=>o.id===$('hubble-field').value);if(active&&state.current?.body)active.cached=true;hubbleState='';hubbleCaption();});
function journeyCaption(){
  if(!journeyInfo)return;
  $('journey-note').textContent=journeyInfo.solar?[t(journeyInfo.url?'solarJourneyNote':'solarDateMissing'),journeyInfo.default_site?t('centralNL'):'',journeyInfo.day_only?t('solarNoon'):''].filter(Boolean).join(' '):t('journey_'+journeyInfo.kind);
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
    if(!journeyInfo){
      status.textContent=t('journeyLoading');
      const id=state.current.id, info=await api('/api/objects/'+id+'/journey');
      if(state.current?.id!==id)return;
      journeyInfo=info;
    }
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
let adminRequest=0, lastAdminResponse=0;
async function refreshAdmin(){
  const request=++adminRequest;
  const response=await api('/api/admin/objects');
  if(request<lastAdminResponse)return;
  lastAdminResponse=request;
  state.adminObjects=response.objects;state.jobs=response.jobs;
  if(state.selected){
    const updated=state.adminObjects.find(o=>o.id===state.selected.id);
    if(updated){
      state.selected=updated;showVersions();renderChoice();
      if(autoAlignment==='pending'&&['solved','no_match','no_pointing','unavailable'].includes(updated.gaia?.status))findZoomRoute();
    }
  }
  renderAdminList();renderJobs();
}
function studioGroup(object){
  return object.catalog_id||object.id;
}
function studioLabel(object){
  const seen=new Set();
  function distinct(value){
    return (value||'').split('·').map(part=>part.trim()).filter(part=>{
      const key=part.toLowerCase().replace(/[\s_]+/g,'');
      if(!key||seen.has(key))return false;
      seen.add(key);return true;
    }).join(' · ');
  }
  const identifier=object.capture_kind?'':studioGroup(object).split('~')[0].replaceAll('_',' ');
  return [distinct(identifier),distinct(local(object.metadata.name)||(object.capture_kind?t(object.capture_kind):''))].filter(Boolean);
}
function renderAdminList(){
  const list=$('admin-object-list'),groups=new Map();
  for(const object of state.adminObjects){
    const group=studioGroup(object);
    if(!groups.has(group))groups.set(group,object);
  }
  const options=[...groups].map(([id,object])=>[id,studioLabel(object).join(' · ')]);
  const signature=JSON.stringify([language,options]);
  if(list.dataset.signature!==signature){
    list.dataset.signature=signature;
    list.replaceChildren(new Option(t('chooseStudioObject'),''));
    for(const [value,label] of options)list.add(new Option(label,value));
  }
  list.disabled=state.uploading||!options.length;
  list.value=state.selected?studioGroup(state.selected):'';
  renderStudioCaptures();
}
function renderStudioCaptures(){
  if(!state.selected)return;
  const list=$('studio-capture-picker'),group=studioGroup(state.selected);
  const captures=state.adminObjects.filter(o=>studioGroup(o)===group);
  const options=captures.map((object,i)=>[object.id,captureOptionLabel(captures,object,i)]);
  const signature=JSON.stringify(options);
  if(list.dataset.signature!==signature){
    list.dataset.signature=signature;
    list.replaceChildren(...options.map(([value,label])=>new Option(label,value)));
  }
  list.disabled=captures.length<2;
  list.value=state.selected.id;
  $('studio-capture-total').textContent='('+captures.length+' '+t(captures.length===1?'oneCapture':'manyCaptures')+')';
}
$('admin-object-list').addEventListener('change',event=>{
  const object=state.adminObjects.find(o=>studioGroup(o)===event.target.value);
  if(object)selectObject(object.id);
  else newObject();
});
$('studio-capture-picker').addEventListener('change',event=>selectObject(event.target.value));
function renderJobs(){
  const list=$('job-list'),active=job=>['running','queued','cancelling'].includes(job.status);
  const jobs=[...state.jobs.filter(job=>active(job)&&job.status!=='queued'),
    ...state.jobs.filter(job=>job.status==='queued'),...state.jobs.filter(job=>!active(job))].slice(0,5);
  const objects=new Map(state.adminObjects.map(object=>[object.id,object]));
  function jobTitle(job){
    const object=objects.get(job.object_id);
    if(object)return studioLabel(object).at(-1);
    const id=job.object_id.split('~')[0];
    return ['STARTRAILS','MILKYWAY'].includes(id)?t(id.toLowerCase()):id.replaceAll('_',' ');
  }
  const signature=JSON.stringify([language,jobs.map(job=>[job.id,jobTitle(job),job.status,job.stage,Math.round(job.progress),job.error])]);
  if(list.dataset.signature===signature)return;
  list.dataset.signature=signature;
  const focused=document.activeElement.closest?.('[data-job]')?.dataset.job;
  list.replaceChildren();
  if(!jobs.length){list.append(node('p','small muted',t('noJobs')));return;}
  for(const job of jobs){
    const row=node('div','job-item');row.dataset.job=job.id;
    const status=t(job.status==='running'&&job.stage==='journey'?'journeyPreparing':job.status);
    const title=node('strong','',jobTitle(job));title.title=title.textContent;
    row.append(title,node('span','',status+(job.status==='running'?' · '+Math.round(job.progress)+'%':'')));
    if(['running','queued'].includes(job.status)){
      const progress=node('progress');progress.max=100;progress.value=job.progress;row.append(progress);
      const cancel=node('button','button secondary cancel-render',t('cancelRender'));
      cancel.addEventListener('click',async()=>{
        cancel.disabled=true;
        try{
          const reply=await api('/api/admin/jobs/'+job.id+'/cancel',{method:'POST'});
          state.jobs=state.jobs.map(current=>current.id===job.id&&['queued','running'].includes(current.status)?reply.job:current);
          renderJobs();await refreshAdmin();
        }catch(error){toast(errorText(error));cancel.disabled=false;}
      });
      row.append(cancel);
    }
    if(job.status==='failed'){
      row.append(node('p','small muted',t(job.error)));
      const retry=node('button','retry-button',t('retry'));
      retry.addEventListener('click',async()=>{
        try{await api('/api/admin/objects/'+job.object_id+'/render',{method:'POST',body:job.params});await refreshAdmin();}
        catch(error){toast(errorText(error));}
      });
      row.append(retry);
    }
    list.append(row);
  }
  if(focused){
    const row=[...list.children].find(element=>element.dataset.job===focused);
    row?.querySelector('button:not(:disabled)')?.focus({preventScroll:true});
  }
}

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
  pointIndex=0;$('point-name').value=points[0].name||'';$('point-count').value=points.length;drawPicker();const defaults={orientation:'portrait',method:'layered',gaia_fill:'background',motion:'orbit',zoom:1.08,focus_x:.5,focus_y:.5,pan_x:.018,pan_y:.010,depth:.65,duration:10,resolution:1280,fps:24,star_source:'auto',blend:'auto'};for(const [key,item] of Object.entries({...defaults,...value,...points[0]})){const input=$('parameters-form').elements.namedItem(key);if(input?.tagName==='SELECT'&&key==='duration'&&![...input.options].some(o=>o.value===String(item)))input.add(new Option(item+' s',String(item)));if(input)input.value=key.startsWith('focus_')?+(item*100).toFixed(1):item;}updateOutputs();updateGaiaDepth();}
function updateOutputs(){updateFocusMarker();for(const output of document.querySelectorAll('[data-output]')){const key=output.dataset.output,value=+$('parameters-form').elements.namedItem(key).value;output.textContent=key.startsWith('pan')?(value*100).toFixed(1)+'%':key==='zoom'?value.toFixed(2)+'×':value.toFixed(2);}}
async function updateGaiaDepth(){
  const token=++gaiaDepthRequest, el=$('gaia-depth-status');
  el.hidden=$('parameters-form').elements.method.value!=='gaia';
  $('gaia-fill-control').hidden=el.hidden;
  if(el.hidden)return;
  if(!state.selected){el.textContent=t('gaiaDepthUpload');return;}
  el.textContent=t('gaiaDepthLoading');
  try{
    const report=await api('/api/admin/objects/'+encodeURIComponent(state.selected.id)+'/gaia-depth?fill='+$('parameters-form').elements.gaia_fill.value);
    if(token!==gaiaDepthRequest)return;
    el.textContent=report.matched+' '+t('gaiaDepthReady')+(report.estimated?' · '+report.estimated+' '+t('gaiaEstimated'):'')+' · '+Math.round(report.min_pc*3.26156)+'–'+Math.round(report.max_pc*3.26156)+' '+t('lightYears');
  }catch(e){if(token===gaiaDepthRequest)el.textContent=errorText(e);}
}
$('parameters-form').elements.method.addEventListener('change',updateGaiaDepth);
$('parameters-form').elements.gaia_fill.addEventListener('change',updateGaiaDepth);
$('parameters-form').addEventListener('input',updateOutputs);$('parameters-form').addEventListener('submit',event=>event.preventDefault());
function solarMode(){return state.selected?!!state.selected.body:$('capture-kind').value==='solar';}
function nightscapeKind(){
  if(state.selected)return state.selected.capture_kind;
  const kind=$('capture-kind').value;
  return ['startrails','milkyway'].includes(kind)?kind:null;
}
function singleImageMode(){return solarMode()||!!nightscapeKind();}
function updateCaptureKind(){
  const solar=solarMode(),landscape=nightscapeKind(),single=singleImageMode(),fields=$('parameters-form').elements;
  const body=$('solar-body'),identifier=$('identifier');
  body.hidden=document.querySelector('label[for="solar-body"]').hidden=!solar;
  identifier.hidden=document.querySelector('label[for="identifier"]').hidden=single;
  $('landscape-title').hidden=document.querySelector('label[for="landscape-title"]').hidden=!landscape;
  $('rename-form').closest('details').hidden=!!landscape;
  $('fetch-nasa').hidden=!!landscape;
  $('metadata-form').elements.target.closest('label').hidden=!!landscape;
  $('metadata-form').elements.galactic_distance_ly.closest('label').hidden=!!landscape;
  document.querySelector('[data-i18n="galacticDistanceHint"]').hidden=!!landscape;
  identifier.required=!single;
  if(solar&&!state.selected)identifier.value=body.value;
  fields.method.querySelectorAll('option').forEach(o=>o.disabled=single&&o.value!=='kenburns');
  if(single){fields.method.value='kenburns';fields.depth.value=0;}
  for(const k of ['depth','star_source','blend'])fields[k].closest('label').hidden=single;
  if(state.selected&&single)$('find-more').hidden=true;
  const texts=[['uploadIntro','solarIntro','landscapeIntro'],['chooseFiles','solarChoose'],['filenameHint','solarHint'],['dropHint','solarFiles']];
  for(const [deep,bodyKey,landscapeKey=bodyKey] of texts){
    const selectors=[deep,bodyKey,landscapeKey].map(k=>'#upload-section [data-i18n="'+k+'"]');
    const el=document.querySelector(selectors.join(','));
    el.dataset.i18n=landscape?landscapeKey:solar?bodyKey:deep;
    el.textContent=t(el.dataset.i18n);
  }
}
$('capture-kind').addEventListener('change',()=>{
  $('identifier').value='';fillParams(singleImageMode()?{method:'kenburns',orientation:'original'}:{});
  updateCaptureKind();assignFiles(state.files);
});
$('solar-body').addEventListener('change',updateCaptureKind);
function newObject(){
  if(state.uploading)return;
  clearImportControls();state.selected=null;setFocusImage(null);showVersions();state.files=[];
  $('upload-form').reset();$('upload-section').hidden=false;$('edit-section').hidden=true;
  $('studio-editor').hidden=true;$('metadata-section').hidden=true;$('preview-image').hidden=true;
  fillParams();updateCaptureKind();renderFileList();renderAdminList();message('studio-message','');
}
$('new-object').addEventListener('click',newObject);
function renderChoice(){
  $('edit-object-title').textContent=studioLabel(state.selected).join(' · ');
  const firstFilm=!state.selected.video;
  $('draft-uploaded').hidden=!firstFilm;
  const text=$('render-button').querySelector('[data-i18n]');
  text.dataset.i18n=firstFilm?'createFilm':'rerender';text.textContent=t(text.dataset.i18n);
  const g=state.selected?.gaia||{};
  $('gaia-status').textContent=g.status&&!state.selected?.capture_kind?t('gaia_'+g.status)+(g.matches?' · '+g.matches+' '+t('gaiaStars')+' · '+g.median_arcsec+'″':''):'';
  $('gaia-retry').hidden=['pending','running','solved','not_applicable'].includes(g.status);
  const choice=state.selected?.render?.choice;$('render-choice').textContent=choice?`${t('starLayer')}: ${choice.source} · ${t('blending')}: ${choice.blend} · MAE ${(choice.mae*100).toFixed(2)}%`:'';}
$('gaia-retry').addEventListener('click',async()=>{
  try{await api('/api/admin/objects/'+state.selected.id+'/align',{method:'POST'});await refreshAdmin();}
  catch(e){toast(errorText(e));}
});
function selectObject(id){
  const object=state.adminObjects.find(item=>item.id===id);
  if(!object||state.uploading)return;
  clearImportControls();state.selected=object;state.files=[];
  editPanorama(object,state.adminObjects,api);
  $('find-more').hidden=false;$('find-more').href='/viewer/'+encodeURIComponent(id)+'#discover';
  $('upload-section').hidden=true;$('edit-section').hidden=false;$('studio-editor').hidden=false;
  $('metadata-section').hidden=false;$('preview-button').hidden=false;$('preview-image').hidden=true;
  setFocusImage(object.source_poster||object.poster);showVersions();renderChoice();fillParams(object.params);
  updateCaptureKind();renderAdminList();fillMetadata(object);fillObservation(object);message('studio-message','');
}
let pendingLandmark=null;
const draftKey=id=>'astroweb-discovery-draft-'+id;
function clearImportControls(){
  resetAutoRoute();$('auto-tools').hidden=true;delete $('identifier').dataset.override;
  identityRequest++;draftIdentity=null;uploadToken=null;transfer=null;renderDraftIdentity();renderUploadProgress();message('upload-error','');
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

function fillMetadata(object){for(const key of ['distance_ly','distance_source','redshift','redshift_source'])$('metadata-form').elements[key].value=object.metadata[key]??'';$('rename-form').elements.identifier.value=(object.catalog_id||object.id).replace('_',' ');$('metadata-form').elements.galactic_distance_ly.value=object.metadata.galactic_distance_ly??'';const fields=$('metadata-fields');fields.replaceChildren();$('metadata-form').elements.namedItem('target').value=object.metadata.target;for(const key of ['name','type','constellation','summary','description'])for(const lang of ['nl','en']){const label=node('label');const title=node('span','',t(key)+' · '+lang.toUpperCase());title.dataset.editKey=key;title.dataset.editLanguage=lang;const input=node(['summary','description'].includes(key)?'textarea':'input');input.name=key+'_'+lang;input.maxLength=key==='description'?5000:350;input.value=object.metadata[key]?.[lang]||'';label.append(title,input);fields.append(label);}}
function fillObservation(object){
  const fields=$('observation-form').elements;
  for(const k of ['latitude','longitude','ra','dec'])fields[k].required=!object.body;
  for(const k of ['ra','dec']){fields[k].disabled=!!object.body;fields[k].closest('label').hidden=!!object.body;}
  const observation=object.observation||{};
  for(const key of ['date_obs','latitude','longitude','ra','dec','timezone']){
    fields.namedItem(key).value=observation[key]??(key==='timezone'?'Europe/Amsterdam':'');
  }
  fields.namedItem('publish_location').checked=!!observation.publish_location;
  const details=$('fits-details');
  details.replaceChildren();
  fact(details,t('integration'),duration(observation.integration));
  fact(details,t('frames'),observation.frames);
  fact(details,t('telescope'),observation.telescope);
  if(object.has_fits)fact(details,'FITS',observation.filename);
  if(observation.time_source==='filename'){
    fact(details,t('observedAtFilename'),observation.date_obs||t('asiTimeMissing'));
  }else{
    fact(details,'DATE-OBS',observation.time_comment);
    fact(details,'UTC',observation.time_scale_assumed?(language==='nl'?'Aangenomen volgens FITS-conventie':'Assumed by FITS convention'):observation.time_scale);
  }
}
let pendingIdentity=Promise.resolve(),identityRequest=0,draftIdentity=null,uploadToken=null,transfer=null;
async function fitsObject(file){
  if(!file)return '';
  const block=28800,names={};
  for(let offset=0;offset<Math.min(file.size,1024*1024);offset+=block){
    const text=await file.slice(offset,offset+block).text();
    if(!offset&&!text.startsWith('SIMPLE  ='))return '';
    for(let pos=0;pos+80<=text.length;pos+=80){
      const card=text.slice(pos,pos+80),key=card.slice(0,8).trim();
      if(key==='END')return names.TARGNAME||names.OBJNAME||'';
      if(['OBJECT','TARGNAME','OBJNAME'].includes(key)){
        const value=card.slice(10).trimStart().match(/^'((?:[^']|'')*)'/);
        if(value)names[key]=value[1].replaceAll("''","'").trim();
        if(names.OBJECT)return names.OBJECT;
      }
    }
  }
  return '';
}
function renderDraftIdentity(){
  const hint=$('identifier-source');
  hint.textContent='';
  const target=draftIdentity?.target;
  if(!target)return;
  const designation=target.id.replaceAll('_',' '),name=local(target.name);
  const object=[designation,name&&name.replace(/[ _]+/g,'').toLowerCase()!==designation.replaceAll(' ','').toLowerCase()?name:'']
    .filter(Boolean).join(' · ');
  const source={wiki:'FITS · Wikipedia / Wikidata',fits:'FITS · OBJECT',prefix:t('filenamePrefix'),manual:t('studioManualID')}[draftIdentity.source];
  hint.textContent=t(target.known?'studioRecognized':'studioUnrecognized')+' '+object+(source?' ('+source+')':'');
}
async function identifyDraft(files){
  const request=++identityRequest;
  const input=$('identifier');
  draftIdentity=null;renderDraftIdentity();
  if(singleImageMode()||!files.length)return;
  const manual=input.dataset.override?input.value.trim():'';
  const photos=files.filter(f=>/\.(png|jpe?g|tiff?)$/i.test(f.name));
  const fits=files.find(f=>/\.(fits|fit|fts)$/i.test(f.name));
  try{
    const object=await fitsObject(fits);
    if(request!==identityRequest||state.selected)return;
    const result=await api('/api/admin/upload-identity',{method:'POST',body:{
      names:photos.slice(0,4).map(f=>f.name),object,identifier:manual}});
    if(request!==identityRequest||state.selected)return;
    if(result.identifier&&!input.dataset.override)input.value=result.identifier;
    draftIdentity=result;
    renderDraftIdentity();
  }catch(e){if(request===identityRequest&&!state.selected)message('upload-error',errorText(e),true);}
}
$('identifier').addEventListener('input',()=>{
  $('identifier').dataset.override=$('identifier').value?'1':'';
  identityRequest++;draftIdentity=null;renderDraftIdentity();
});
$('identifier').addEventListener('change',()=>{pendingIdentity=identifyDraft(state.files);});
function assignFiles(files){
  if(state.uploading)return;
  state.files=[...files];uploadToken=null;message('upload-error','');
  if(!singleImageMode()&&!$('identifier').dataset.override)$('identifier').value='';
  pendingIdentity=identifyDraft(state.files);
  renderFileList();
}
function renderFileList(){const list=$('file-checklist');list.replaceChildren();for(const role of (singleImageMode()?['final','FITS']:['final','starless','stars','stars_laid','FITS'])){const matches=state.files.filter(file=>singleImageMode()&&role==='final'?/\.(png|jpe?g|tiff?)$/i.test(file.name):role==='FITS'?/\.(fits|fit|fts)$/i.test(file.name):new RegExp('_'+role+'\\.(png|jpe?g|tiff?)$','i').test(file.name));const chip=node('span','file-chip'+(matches.length===1?' ready':matches.length>1?' invalid':''),(matches.length===1?'✓ ':'')+role+((role==='FITS'||role==='stars_laid')?' · '+(language==='nl'?'optioneel':'optional'):''));chip.title=matches.map(file=>file.name).join('\n');list.append(chip);}}
$('image-files').addEventListener('change',event=>assignFiles(event.target.files));const drop=document.querySelector('.dropzone');drop.addEventListener('dragover',event=>{event.preventDefault();drop.classList.add('dragging');});drop.addEventListener('dragleave',()=>drop.classList.remove('dragging'));drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('dragging');assignFiles(event.dataTransfer.files);});
function renderUploadProgress(){
  $('upload-transfer').hidden=!transfer;
  if(!transfer)return;
  const bar=$('upload-progress');
  if(transfer.saving){
    bar.value=100;$('upload-status').textContent=t('uploadValidating');return;
  }
  const unit=new Intl.NumberFormat(language==='nl'?'nl-NL':'en-GB',{maximumFractionDigits:1});
  const mib=bytes=>unit.format(bytes/1048576)+' MiB';
  const status=[t('uploading')];
  if(transfer.total){
    const percent=Math.floor(100*transfer.loaded/transfer.total);
    bar.value=percent;status.push(percent+'%',mib(transfer.loaded)+' / '+mib(transfer.total));
  }else{
    bar.removeAttribute('value');status.push(mib(transfer.loaded));
  }
  $('upload-status').textContent=status.join(' · ');
}
function uploadFiles(body){
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();
    xhr.open('POST','/api/admin/objects');xhr.responseType='json';
    xhr.setRequestHeader('X-CSRF-Token',state.session?.csrf||'');
    xhr.upload.onprogress=event=>{
      transfer={loaded:event.loaded,total:event.lengthComputable?event.total:0};
      renderUploadProgress();
    };
    xhr.upload.onload=()=>{
      transfer={saving:true};renderUploadProgress();
    };
    xhr.onload=()=>{
      if(xhr.status>=200&&xhr.status<300&&xhr.response?.object)resolve(xhr.response.object);
      else reject(Error(xhr.response?.error||(xhr.status===413?'upload_too_large':'internal_error')));
    };
    xhr.onerror=xhr.onabort=()=>reject(Error('network_error'));
    xhr.send(body);
  });
}
function lockUpload(locked){
  state.uploading=locked;$('upload-fields').disabled=locked;$('new-object').disabled=locked;
  $('logout').disabled=locked;renderAdminList();
}
$('upload-form').addEventListener('input',()=>{uploadToken=null;message('upload-error','');});
$('upload-form').addEventListener('submit',async event=>{
  event.preventDefault();
  if(state.uploading)return;
  lockUpload(true);message('upload-error','');
  let object;
  try{
    await pendingIdentity;
    const images=state.files.filter(file=>/\.(png|jpe?g|tiff?)$/i.test(file.name));
    const fits=state.files.filter(file=>/\.(fits|fit|fts)$/i.test(file.name));
    if((singleImageMode()?images.length!==1:![3,4].includes(images.length))||fits.length>1||images.length+fits.length!==state.files.length)
      throw Error(singleImageMode()?'single_image_required':'four_images_required');
    const body=new FormData();
    uploadToken??=Array.from(crypto.getRandomValues(new Uint8Array(16)),byte=>byte.toString(16).padStart(2,'0')).join('');
    body.set('draft_only','1');body.set('upload_token',uploadToken);body.set('identifier',$('identifier').value);
    body.set('session_name',$('session-name').value);body.set('capture_date',$('upload-capture-date').value);
    if(nightscapeKind()){body.set('capture_kind',nightscapeKind());body.set('title',$('landscape-title').value);}
    if($('identifier').dataset.override)body.set('identifier_override','1');
    images.forEach(file=>body.append('images',file));if(fits[0])body.set('fits',fits[0]);
    transfer={loaded:0,total:0};renderUploadProgress();
    object=await uploadFiles(body);
  }catch(e){message('upload-error',errorText(e),true);}
  finally{transfer=null;renderUploadProgress();lockUpload(false);}
  if(object){
    state.adminObjects=[object,...state.adminObjects.filter(item=>item.id!==object.id)];
    selectObject(object.id);$('edit-section').scrollIntoView({block:'start'});
  }
});
$('render-button').addEventListener('click',async()=>{
  if(!state.selected||state.busy||!$('parameters-form').reportValidity())return;
  setBusy(true);
  try{
    await api('/api/admin/objects/'+encodeURIComponent(state.selected.id)+'/render',{method:'POST',body:params()});
    message('studio-message',t('queuedMessage'));await refreshAdmin();
  }catch(e){message('studio-message',errorText(e),true);}
  finally{setBusy(false);}
});
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
$('metadata-form').addEventListener('submit',async event=>{event.preventDefault();if(!state.selected)return;const form=new FormData(event.target),body={target:form.get('target'),galactic_distance_ly:form.get('galactic_distance_ly')?Number(form.get('galactic_distance_ly')):null};for(const key of ['distance_ly','redshift']){body[key]=form.get(key)?Number(form.get(key)):null;body[key==='distance_ly'?'distance_source':'redshift_source']=form.get(key==='distance_ly'?'distance_source':'redshift_source')||'';}for(const key of ['name','type','constellation','summary','description'])body[key]={nl:form.get(key+'_nl'),en:form.get(key+'_en')};try{await api(`/api/admin/objects/${state.selected.id}/metadata`,{method:'PUT',body});toast(t('saved'));await refreshAdmin();state.selected=state.adminObjects.find(o=>o.id===state.selected.id);}catch(e){toast(errorText(e));}});
$('fetch-nasa').addEventListener('click',async()=>{
  const id=state.selected?.id;
  if(!id||state.busy)return;
  setBusy(true);message('studio-message',t('working'));
  try{
    const reply=await api('/api/admin/objects/'+encodeURIComponent(id)+'/metadata/refresh',{method:'POST',body:{}});
    if(state.selected?.id===id)fillMetadata({...state.selected,metadata:reply.metadata});
    message('studio-message',t('saved'));await refreshAdmin();
  }catch(e){message('studio-message',errorText(e),true);}
  finally{setBusy(false);}
});
$('observation-form').addEventListener('submit',async event=>{event.preventDefault();if(!state.selected)return;const form=new FormData(event.target),body=Object.fromEntries(form);body.publish_location=form.has('publish_location');for(const key of ['latitude','longitude','ra','dec'])if(key in body)body[key]=body[key]===''?null:+body[key];try{await api(`/api/admin/objects/${state.selected.id}/observation`,{method:'PUT',body});toast(t('saved'));await refreshAdmin();state.selected=state.adminObjects.find(o=>o.id===state.selected.id);}catch(e){toast(errorText(e));}});
function setFocusImage(source){
  $('film-orientation').hidden=true;
  resetAutoRoute();$('auto-tools').hidden=true;
  const img=$('edit-poster');
  $('focus-image').hidden=true;
  if(source)img.src=source;else img.removeAttribute('src');
}
function drawFocusImage(){
  const img=$('edit-poster'), canvas=$('rotated-focus');
  if(!img.complete||!img.naturalWidth)return;
  const landscape=img.naturalWidth>img.naturalHeight;
  $('film-orientation').hidden=!landscape;
  const rotate=landscape && $('parameters-form').elements.orientation.value==='portrait';
  img.hidden=rotate;canvas.hidden=!rotate;
  if(rotate){
    const ratio=Math.min(1,1400/img.naturalWidth);
    canvas.width=Math.round(img.naturalHeight*ratio);canvas.height=Math.round(img.naturalWidth*ratio);
    const ctx=canvas.getContext('2d');
    ctx.translate(canvas.width,0);ctx.rotate(Math.PI/2);
    ctx.drawImage(img,0,0,canvas.height,canvas.width);
  }
  $('focus-image').hidden=false;$('auto-tools').hidden=false;
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
$('edit-poster').addEventListener('error',()=>{$('film-orientation').hidden=true;$('focus-image').hidden=true;$('auto-tools').hidden=true;resetAutoRoute();});
function clamp(value,low,high){return Math.max(low,Math.min(high,value));}

// Background-plane geometry at peak zoom (Scene.camera/warp at phase 0.5).
let suggestions=[],autoGeneration=0,autoAlignment='';
function resetAutoRoute(){
  autoGeneration++;suggestions=[];autoAlignment='';$('auto-review').hidden=true;
  $('auto-frames').replaceChildren();$('auto-alignment').textContent='';$('auto-zoom').disabled=false;
}
function suggestedPoints(){
  const img=$('edit-poster');
  const rotate=$('parameters-form').elements.orientation.value==='portrait'&&img.naturalWidth>img.naturalHeight;
  return suggestions.map((p,i)=>({name:local(p.label)||p.name||t('autoStructure')+' '+(i+1),zoom:p.zoom,
    focus_x:rotate?1-p.y:p.x,focus_y:rotate?p.x:p.y}));
}
function showAutoRoute(){
  $('auto-alignment').textContent=autoAlignment?t('routeAlignment_'+autoAlignment):'';
  if(!suggestions.length)return;
  const proposals=suggestedPoints(),frames=$('auto-frames');
  frames.replaceChildren();$('auto-list').replaceChildren();
  proposals.forEach((pt,i)=>{
    const c=cropGeometry({...activeParams(),...pt},i,proposals.length);
    const box=node('span','auto-frame',String(i+1));
    Object.assign(box.style,{left:c.left*100+'%',top:c.top*100+'%',width:c.size*100+'%',height:c.size*100+'%'});
    const item=node('li','',pt.name+' · '+pt.zoom+'×');
    if(suggestions[i].kind==='catalog'&&autoAlignment!=='surface')item.append(node('small',' muted',' · '+t('routeCataloguePoint')));
    frames.append(box);$('auto-list').append(item);
  });
}
async function findZoomRoute(){
  const id=state.selected?.id;
  if(!id)return;
  resetAutoRoute();const generation=autoGeneration;
  $('auto-zoom').disabled=true;$('auto-review').hidden=false;$('auto-note').textContent=t('routeSearching');
  $('auto-list').replaceChildren();$('auto-apply').hidden=true;
  try{
    const count=Number($('auto-count').value);
    const reply=await api('/api/admin/objects/'+encodeURIComponent(id)+'/autozoom',{method:'POST',body:{count}});
    if(generation!==autoGeneration)return;
    suggestions=reply.points;autoAlignment=reply.alignment||'';
    $('auto-note').textContent=t(suggestions.length?'autoReview':'autoEmpty');$('auto-apply').hidden=!suggestions.length;showAutoRoute();
  }catch(e){if(generation===autoGeneration)$('auto-note').textContent=errorText(e);}
  finally{if(generation===autoGeneration)$('auto-zoom').disabled=false;}
}
$('auto-zoom').addEventListener('click',findZoomRoute);
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
  const capture=state.selected?.id||'';
  const signature=JSON.stringify([capture,language,...versions.map(v=>[v.id,v.selected])]);
  if(list.dataset.signature===signature)return;
  const newest=versions[0];
  const newlyRendered=list.dataset.capture===capture && newest && !Array.from(list.options).some(option=>option.value===newest.id);
  list.dataset.signature=signature;list.dataset.capture=capture;
  $('versions-section').hidden=!versions.length;
  list.replaceChildren();
  versions.forEach((v,i)=>{
    const date=new Date(v.created_at).toLocaleString(language==='nl'?'nl-NL':'en-GB');
    const label=t('version')+' '+(versions.length-i)+' · '+t('method_'+v.params.method)+(v.params.method==='gaia'&&v.params.gaia_fill==='local'?' · '+t('gaiaFillLocal'):'')+' · '+date+(v.selected?' · '+t('inGallery'):'');
    list.add(new Option(label,v.id));
  });
  const preferred=newlyRendered?newest:versions.find(v=>v.id===previous)||versions.find(v=>v.selected)||newest;
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
  if(v.render?.gaia){
    fact(details,'Gaia DR3',v.render.gaia.matched+' · '+t('gaiaDepthReady'));
    fact(details,t('gaiaFill'),t(p.gaia_fill==='local'?'gaiaFillLocal':'gaiaFillBackground'));
    if(v.render.gaia.estimated)fact(details,t('gaiaEstimated'),v.render.gaia.estimated);
  }
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
  if(!object||!id||!window.confirm(captureLabel(object)+' · '+list.selectedOptions[0].text+'\n\n'+t('deletePrompt')))return;
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
