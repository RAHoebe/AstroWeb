'use strict';
const root=document.documentElement, en=root.lang==='en', tr=(nl,english)=>en?english:nl;
const $=id=>document.getElementById(id), stage=$('stage'), menu=$('menu'), hud=$('hud');
const enc=encodeURIComponent, primary=decodeURIComponent(root.dataset.capture);
const api=async path=>{
  const response=await fetch(path);
  if(!response.ok)throw Error(String(response.status));
  return response.json();
};
const endpoint=(id,part='')=>'/api/objects/'+enc(id)+part;
const text=v=>typeof v==='string'?v:v?.[root.lang]||v?.nl||v?.en||'';
const name=p=>text(p.metadata?.name||p.name)||p.catalog_id||p.id;
const date=p=>(p.capture_date||p.date||'').slice(0,10);
const title=p=>[name(p),date(p)].filter(Boolean).join(' · ');
const mod=(n,length)=>(n%length+length)%length;
const localMedia=path=>{if(typeof path!=='string'||!path.startsWith('/media/'))throw Error('media');return path;};
const photoSrc=p=>localMedia(p.original_view||p.final);
let generation=0, back=null, key=()=>{}, tick=null, active=true, wasPlaying=false;
const poster=p=>'/media/'+enc(p.id)+'/poster';
let collection=[],current,selectedMenu=0;
const details=new Map(), tracks=new Map();
function cached(cache,id,fetcher){
  if(!cache.has(id))cache.set(id,fetcher().catch(error=>{cache.delete(id);throw error;}));
  return cache.get(id);
}
const detail=p=>p.final?Promise.resolve(p):cached(details,p.id,()=>api(endpoint(p.id)));
const nightData=p=>cached(tracks,p.id,()=>api(endpoint(p.id,'/night-tracks')));
let visibleScene=null,fadeTimer;
function releaseVideo(v){
  v.onended=v.onerror=v.onplaying=v.onloadedmetadata=null;v.pause();v.remove();v.removeAttribute('src');v.load();
}
function freezeVideo(layer){
  const v=layer.querySelector('video');
  if(!v||v.readyState<2||!v.videoWidth)return;
  // Capture once before releasing the decoder, retaining the displayed rotation and letterbox.
  const c=document.createElement('canvas'),scale=Math.min(1,1920/Math.max(v.videoWidth,v.videoHeight));
  c.width=Math.round(v.videoWidth*scale);c.height=Math.round(v.videoHeight*scale);
  c.className='movie';c.style.cssText=v.style.cssText;c.getContext('2d').drawImage(v,0,0,c.width,c.height);
  v.before(c);releaseVideo(v);
}
function clear(backTo,hold=false){
  ++generation;back=backTo;key=()=>{};tick=null;wasPlaying=false;
  clearTimeout(fadeTimer);
  if(hold&&!visibleScene&&stage.childElementCount){
    const contents=[...stage.children];
    visibleScene=elm('div','scene visible');visibleScene.append(...contents);
  }
  if(hold&&visibleScene)freezeVideo(visibleScene);
  for(const child of [...stage.children]){
    if(hold&&child===visibleScene)continue;
    child.querySelectorAll('video').forEach(releaseVideo);
    if(child.tagName==='VIDEO')releaseVideo(child);else child.remove();
  }
  if(!hold){visibleScene=null;$('credit').textContent='';}
  stage.classList.remove('menu-backdrop');menu.hidden=true;hud.hidden=true;
  return generation;
}
function reveal(layer,credit=''){
  if(!layer.isConnected||visibleScene===layer)return;
  clearTimeout(fadeTimer);
  for(const child of [...stage.children])if(child!==layer&&child!==visibleScene)child.remove();
  const previous=visibleScene;
  visibleScene=layer;
  // Establish the transparent start state even for an already decoded photo.
  layer.getBoundingClientRect();
  layer.classList.add('visible');$('credit').textContent=credit;
  if(previous)fadeTimer=setTimeout(()=>previous.remove(),450);
}
function status(line,help=''){
  hud.hidden=false;hud.querySelector('strong').textContent=line;$('hint').textContent=help;
}
function elm(tag,cls,parent=stage){const e=document.createElement(tag);e.className=cls||'';parent.append(e);return e;}
function fallback(bg){if(bg){const i=elm('img','backdrop');i.src=localMedia(bg);i.alt='';}}
function choices(heading,sub,options,backTo=null,idx=0,bg=current&&poster(current),onHighlight=null){
  clear(backTo);stage.classList.add('menu-backdrop');fallback(bg);menu.hidden=false;menu.querySelector('h1').textContent=heading;$('sub').textContent=sub;
  const list=$('choices');list.replaceChildren();
  const buttons=options.map(([label,run],i)=>{
    const b=elm('button','',list);b.textContent=label;b.onclick=()=>{idx=i;run();};return b;
  });
  function highlight(){buttons.forEach((b,i)=>b.classList.toggle('active',i===idx));buttons[idx]?.scrollIntoView({block:'nearest'});
    $('menu-help').textContent=(onHighlight?.(idx)||'')+'\n'+tr('↑ ↓  Kiezen     OK  Openen     Terug','↑ ↓  Choose     OK  Open     Back');}
  highlight();
  key=k=>{
    if(['previous','in','next','out'].includes(k)){
      idx=mod(idx+(['previous','in'].includes(k)?-1:1),buttons.length);highlight();
    }else if(k==='reset')buttons[idx]?.click();
  };
}
function problem(line,backTo,retry){
  choices(line,'',[[tr('Opnieuw proberen','Try again'),retry],[tr('Terug','Back'),backTo]],backTo);
}
async function loadView(backTo,load,show,retry){
  const g=clear(backTo);status(tr('Even laden…','Loading…'));
  try{const result=await load();if(g===generation)show(result);}
  catch{if(g===generation)problem(tr('Deze weergave is niet beschikbaar','This view is unavailable'),backTo,retry);}
}
function stillPhoto(layer){
  const plane=elm('div','photo-plane',layer),img=elm('img','backdrop',plane);
  img.addEventListener('load',()=>plane.classList.toggle('tall',img.naturalHeight>img.naturalWidth));
  return img;
}
function image(path){const img=new Image();img.src=localMedia(path);return img.decode().then(()=>img);}
function movie(layer,url,onReady,onEnd,onError){
  const video=elm('video','movie',layer);
  video.controls=false;video.playsInline=true;video.muted=true;
  video.onloadedmetadata=()=>{if(video.videoHeight>video.videoWidth){
    Object.assign(video.style,{width:'100vh',height:'100vw',left:'50%',top:'50%',transform:'translate(-50%,-50%) rotate(-90deg)'});
  }};
  let presented=false;
  function firstFrame(){
    if(presented||!video.isConnected||video.readyState<2)return;
    presented=true;onReady();
  }
  if(video.requestVideoFrameCallback)video.requestVideoFrameCallback(firstFrame);
  else video.addEventListener('loadeddata',()=>requestAnimationFrame(firstFrame),{once:true});
  video.onended=onEnd;video.onerror=onError;video.src=localMedia(url);
  if(active)video.play().catch(e=>{if(video.isConnected&&e.name!=='AbortError')onError();});else wasPlaying=true;
  return video;
}
window.mapKey=k=>key(k);
window.collectionBack=()=>{if(!back)return false;back();return true;};
window.viewActive=value=>{
  if(value===active)return;active=value;
  const v=stage.querySelector('.scene:last-child video'), glide=visibleScene?.querySelector('.glide');
  if(glide)glide.style.animationPlayState=active&&!glide.dataset.paused?'running':'paused';
  if(!active){wasPlaying=!!v&&!v.paused;v?.pause();}
  else if(v&&wasPlaying)v.play().catch(()=>{});
};
let last=performance.now();
setInterval(()=>{const now=performance.now(),dt=Math.min(1,(now-last)/1000);last=now;if(active&&tick)tick(dt);},150);
const exploring=root.dataset.mode==='explore';
const modes=exploring?[
  [tr('Opnamenacht en vanavond','Capture night and tonight'),tr('Bekijk de hemelbaan van dit object op de opnamenacht en vanavond.','See this object on its capture night and tonight.'),()=>nightView(current,main)],
  [tr('Wat zie ik?','What am I seeing?'),tr('Ontdek de benoemde onderdelen in deze opname.','Explore the named features in this capture.'),discover]
]:[
  [tr('Avondvoorstelling','Evening programme'),tr('Vijf minuten films, foto’s en kaarten. Begint bij een willekeurige opname.','Five minutes of films, photos and charts, starting with a random capture.'),()=>evening(5)],
  [tr('Fotolijst','Photo frame'),tr('Een uur lang alle opnamen. Begint bij een willekeurige foto.','One hour of photographs, starting with a random capture.'),()=>frame(false)]
];
function runMode(index){
  selectedMenu=index;
  if(!exploring)current=collection[Math.floor(Math.random()*collection.length)];
  modes[index][2]();
}
function main(){
  choices(tr(exploring?'Verken':'Kijkmodi',exploring?'Explore':'Viewing modes'),
    exploring?title(current):tr('Start direct met een willekeurige opname.','Start immediately with a random capture.'),
    modes.map(([label],i)=>[label,()=>runMode(i)]),null,selectedMenu,poster(current),i=>modes[i][1]);
}
function start(){
  const g=clear(null);status(exploring?tr('Opname laden…','Loading capture…'):tr('Galerij laden…','Loading gallery…'));
  const load=exploring?api(endpoint(primary)).then(p=>[p]):Promise.all([api('/api/objects'),api('/api/atlas')]).then(([gallery,atlas])=>{
    const latest=new Map(gallery.objects.map(p=>[p.id,p]));
    const rank=new Map(gallery.objects.map((p,i)=>[p.catalog_id,i]));
    return atlas.captures.map(p=>({...p,...latest.get(p.id)})).sort((a,b)=>
      (rank.get(a.catalog_id)??Infinity)-(rank.get(b.catalog_id)??Infinity)||date(b).localeCompare(date(a)));
  });
  load.then(rows=>{
    if(g!==generation)return;
    if(!rows.length)throw Error('empty');
    collection=rows;current=collection.find(p=>p.id===primary)||collection[0];main();
  }).catch(()=>{if(g===generation)choices(exploring?tr('Opname niet beschikbaar','Capture unavailable'):tr('Galerij niet beschikbaar','Gallery unavailable'),'',[[tr('Opnieuw proberen','Try again'),start]],null,0,null);});
}
function nightView(p,backTo){
  loadView(backTo,()=>nightData(p),data=>{
    clear(backTo);const canvas=elm('canvas');
    let mode='capture',index,playing=false;
    function draw(){
      const label=mode==='tonight'?tr('Vanavond','Tonight'):tr('Opnamenacht','Capture night');
      drawNight(canvas,data,mode,index,tr,name(p)+' · '+label);
      status(label,'↑ ↓  '+tr('Datum','Date')+'     ← →  '+tr('Tijd','Time')+'     OK  '+(playing?tr('Pauze','Pause'):tr('Afspelen','Play')));
    }
    function choose(value){
      mode=value;const seq=data[mode], ref=mode==='tonight'?data.now:data.observed;
      index=Math.max(0,Math.min(seq.target.length-1,Math.round((ref-seq.start)/seq.step)));draw();
    }
    choose(mode);let elapsed=0;
    tick=dt=>{if(playing&&(elapsed+=dt)>.4){elapsed=0;index=mod(index+1,data[mode].target.length);draw();}};
    key=k=>{
      if(k==='previous'||k==='next'){playing=false;index=mod(index+(k==='next'?1:-1),data[mode].target.length);draw();}
      if(k==='in'||k==='out')choose(mode==='capture'?'tonight':'capture');
      if(k==='reset'||k==='toggle'){playing=!playing;draw();}
      if(k==='play'||k==='pause'){playing=k==='play';draw();}
    };
  },()=>nightView(p,backTo));
}
function evening(minutes){
  const first=collection.findIndex(p=>p.id===current.id);
  const photos=[...collection.slice(first),...collection.slice(0,first)];
  let object=0,scene=0,remaining=minutes*60,paused=false,elapsed=0;
  const lists=new Map();
  function chapters(p){
    if(lists.has(p.id))return lists.get(p.id);
    const list=[{kind:'photo'}];
    lists.set(p.id,list);
    const addCapture=capture=>{
      if(capture.video)list.push({kind:'film',url:capture.video});
      if(capture.sky_available)list.push({kind:'chart'});
    };
    if(p.final)addCapture(p);
    const ready=p.final?Promise.resolve():detail(p).then(addCapture).catch(()=>{});
    ready.then(()=>api(endpoint(p.id,'/tv-program'))).then(program=>{
      if(program.journey)list.push({kind:'sky',url:program.journey});
      if(program.trips?.length)list.push({kind:'hubble',...program.trips[0]});
    }).catch(()=>{});
    return list;
  }
  const labels={photo:tr('Opname','Capture'),film:'Film',sky:tr('Hemelreis','Sky journey'),chart:tr('Skykaart','Sky chart'),hubble:tr('Archiefreis','Archive journey')};
  async function next(step){
    const g=clear(main,true),layer=elm('div','scene');
    let p=photos[object],list=chapters(p);
    scene+=step;
    if(scene>=list.length||scene<0){
      const backwards=scene<0;object=mod(object+(backwards?-1:1),photos.length);p=photos[object];list=chapters(p);
      scene=backwards?list.length-1:0;
    }
    const chapter=list[scene];let duration=9,video=null,failed=false,ready=false;
    function present(){if(g===generation){ready=true;reveal(layer,chapter.credit);hint();}}
    elapsed=0;paused=false;
    if(!visibleScene)status(title(p),labels[chapter.kind]);
    key=k=>{if(k==='next'||k==='previous')next(k==='next'?1:-1);};
    if(chapter.kind==='chart'){
      try{
        const data=await nightData(p);if(g!==generation)return;
        const c=elm('canvas','',layer),seq=data.capture;let prev=-1;
        const paint=()=>{const i=Math.min(seq.target.length-1,Math.floor(elapsed/duration*seq.target.length));
          if(i!==prev){drawNight(c,data,'capture',i,tr,name(p));prev=i;}};
        paint();c.update=paint;present();
      }catch{if(g!==generation)return;failed=true;}
    }else if(chapter.url){
      duration=90;video=movie(layer,chapter.url,present,()=>{if(g===generation)next(1);},()=>{failed=true;});
    }else{
      const img=stillPhoto(layer);img.src=poster(p);img.decode().then(present).catch(()=>{failed=true;});
    }
    function hint(){status(title(p)+' · '+labels[chapter.kind],(paused?tr('Gepauzeerd','Paused')+'   ':'')+'← →  '+tr('Hoofdstuk','Chapter')+'     OK  Ⅱ / ▶');}
    key=k=>{
      if(k==='next'||k==='previous')return next(k==='next'?1:-1);
      if(['reset','toggle','play','pause'].includes(k)){
        paused=k==='pause'||(k!=='play'&&!paused);if(video){if(paused)video.pause();else video.play().catch(()=>{failed=true;});}hint();
      }
    };
    tick=dt=>{if(failed){next(1);return;}if(paused||!ready)return;elapsed+=dt;remaining-=dt;
      if(remaining<=0){choices(tr('Einde voorstelling','End of programme'),'',[[tr('Opnieuw afspelen','Play again'),()=>runMode(0)],[tr('Kijkmodi','Viewing modes'),main]],main);return;}
      if(elapsed>4)hud.hidden=true;layer.querySelector('canvas')?.update?.();
      if(elapsed>=duration)next(1);
    };
  }
  next(0);
}
function frame(motion){
  const rows=collection, cache=new Map();
  let index=rows.findIndex(p=>p.id===current.id),remaining=3600,age=0,paused=false;
  function slide(){
    const session=clear(main,true);
    let plane=null;
    let request=0,ready=false;
    function getSlide(i){
      return cached(cache,rows[i].id,()=>image(poster(rows[i])));
    }
    function caption(){
      const p=rows[index];
      status(title(p)+' · '+(index+1)+'/'+rows.length,
        tr('← →  Foto     OK  Origineel openen     ↓  ','← →  Photo     OK  Open original     ↓  ')+
        (paused?tr('Hervatten','Resume'):tr('Pauze','Pause')));
    }
    async function show(i){
      const ticket=++request;index=mod(i,rows.length);age=0;ready=false;
      const next=mod(index+1,rows.length);
      try{
        const img=await getSlide(index);
        if(session!==generation||ticket!==request)return;
        if(visibleScene?.contains(img)){ready=true;caption();return;}
        const layer=elm('div','scene');plane=elm('div','photo-plane',layer);
        plane.classList.toggle('tall',img.naturalHeight>img.naturalWidth);
        img.className=motion?'backdrop glide':'backdrop';
        img.dataset.paused=paused?'yes':'';img.style.animationPlayState=paused||!active?'paused':'running';
        plane.append(img);ready=true;reveal(layer);caption();
        for(const id of cache.keys())if(id!==rows[index].id&&id!==rows[next].id)cache.delete(id);
        getSlide(next).catch(()=>{});
      }catch{
        if(session!==generation||ticket!==request)return;
        status(title(rows[index]),tr('Foto niet beschikbaar · ← → andere opname','Photo unavailable · ← → another capture'));
        ready=true;
      }
    }
    function original(){
      const p=rows[index];
      loadView(slide,()=>getSlide(index),preview=>{
        const g=clear(slide),camera=new PhotoCamera(),canvas=elm('canvas'),ctx=canvas.getContext('2d');
        canvas.width=innerWidth*devicePixelRatio;canvas.height=innerHeight*devicePixelRatio;
        let img=preview;
        const draw=()=>{ctx.clearRect(0,0,canvas.width,canvas.height);camera.draw(ctx,img,canvas.width,canvas.height);
          status(title(p),camera.scaleLabel(en)+'    '+camera.help(en)+'    '+tr('Terug  Fotolijst','Back  Photo frame'));};
        draw();key=k=>{camera.key(k);draw();};
        detail(p).then(d=>image(photoSrc(d))).then(full=>{if(g===generation){img=full;draw();}}).catch(()=>{});
      },original);
    }
    status(title(rows[index]),tr('Foto laden…','Loading photo…'));show(index);
    key=k=>{
      if(k==='reset')return original();
      if(k==='previous'||k==='next')return show(index+(k==='next'?1:-1));
      if(['out','toggle','play','pause'].includes(k)){
        paused=k==='pause'||(k!=='play'&&!paused);
        const img=plane?.firstElementChild;
        if(img){img.dataset.paused=paused?'yes':'';img.style.animationPlayState=paused?'paused':'running';}caption();
      }
    };
    tick=dt=>{
      if(paused||!ready)return;age+=dt;remaining-=dt;
      if(remaining<=0)return main();
      if(age>5)hud.hidden=true;
      if(age>=25)show(index+1);
    };
  }
  slide();
}
function destinationFor(obj,options,capture,solar){
  if(solar)return options.find(option=>option.id===obj.journey);
  const norm=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
  const ids=[obj.id,...(obj.aliases||[])].map(norm).filter(Boolean);
  const isMain=ids.includes(norm(capture.catalog_id));
  return options.find(o=>isMain&&o.id.startsWith('skymap-'))||
    options.find(o=>ids.includes(norm(o.id))||ids.includes(norm(o.target))||(o.id==='nucleus'&&ids.includes('M31')));
}
function discover(){
  const catalogs=new Map(),archive=new Map();
  function openPhoto(){
    const p=current,g=clear(main,true);
    status(title(p),tr('Onderdelen opzoeken…','Finding features…'));
    Promise.all([cached(catalogs,p.id,()=>api(endpoint(p.id,'/discover')).catch(error=>{if(['400','404'].includes(error.message))return {objects:[]};throw error;})),image(poster(p))]).then(([data,img])=>{
      if(g!==generation)return;
      const objects=data.objects;
      const solar=data.kind==='surface'||!!p.body;
      let index=0,zoomed=false;
      function guide(){
        const session=clear(main,true),layer=elm('div','scene');
        const field=elm('div','guide-camera',layer);
        const photo=img.isConnected?img.cloneNode():img;field.append(photo);
        const ring=elm('div','guide-ring',layer);ring.hidden=!objects.length;
        const iw=img.naturalWidth,ih=img.naturalHeight,turn=ih>iw;
        const w=innerWidth,h=innerHeight,fit=Math.min(w/(turn?ih:iw),h/(turn?iw:ih));
        const dw=(turn?ih:iw)*fit,dh=(turn?iw:ih)*fit;
        Object.assign(field.style,{width:dw+'px',height:dh+'px'});
        Object.assign(photo.style,{width:iw*fit+'px',height:ih*fit+'px',transform:turn?'translateY('+dh+'px) rotate(-90deg)':''});
        let options=[];
        function paint(){
          const point=objects[index],z=zoomed?3:1;
          const x=point?(turn?point.y:point.x):.5,y=point?(turn?1-point.x:point.y):.5;
          const offset=(size,screen,frac)=>size<=screen?(screen-size)/2:Math.max(screen-size,Math.min(0,screen/2-frac*size));
          const left=offset(dw*z,w,x),top=offset(dh*z,h,y);
          field.style.transform='translate('+left+'px,'+top+'px) scale('+z+')';
          ring.style.transform='translate('+(left+x*dw*z)+'px,'+(top+y*dh*z)+'px) translate(-50%,-50%)';
          const controls=tr('↑  Inzoomen    ↓  Overzicht','↑  Zoom in    ↓  Overview');
          if(!point){status(title(p),tr('Geen benoemde onderdelen in deze opname.','No named features in this capture.')+'    '+tr('Terug  Verken','Back  Explore'));return;}
          const trip=destinationFor(point,options,p,solar);
          const heading=(text(point.name)||point.id)+' · '+text(point.type)+' · '+(index+1)+'/'+objects.length;
          const coordinates=Number.isFinite(point.ra)&&Number.isFinite(point.dec)
            ? ['RA '+point.ra.toFixed(3)+'°','Dec '+point.dec.toFixed(3)+'°'] : [];
          const journeyHint=solar?tr('Houd OK vast  Detailreis','Hold OK  Detail journey')
            :tr('Houd OK vast  Archiefreis','Hold OK  Archive journey');
          status(heading,[title(p),text(point.summary)||[...(point.aliases||[]),...coordinates].join(' · '),
            (objects.length>1?tr('← →  Onderdeel','← →  Feature')+'     ':'')+controls+
            '     OK  '+(zoomed?tr('Overzicht','Overview'):tr('Inzoomen','Zoom in'))+(trip?'     '+journeyHint:'')].filter(Boolean).join('\n'));
        }
        paint();reveal(layer);
        if(!matchMedia('(prefers-reduced-motion: reduce)').matches){
          field.style.transition=ring.style.transition='transform .4s ease-in-out';
        }
        if(solar?objects.some(point=>point.journey):objects.length){
          const route=solar?'/solar-system':'/hubble?view=tv';
          cached(archive,p.id,()=>api(endpoint(p.id,route))).then(result=>{
            if(session!==generation)return;
            const observations=result.observations||[];
            options=solar?observations:observations.filter(option=>option.tv_video?.startsWith('/media/'));
            paint();
          }).catch(()=>{});
        }
        key=k=>{
          if((k==='out'||k==='in')&&objects.length){zoomed=k==='in';paint();return;}
          if(k==='next'||k==='previous'){
            if(!objects.length)return;
            index=mod(index+(k==='next'?1:-1),objects.length);zoomed=true;paint();return;
          }
          if(k==='reset'&&objects.length){zoomed=!zoomed;paint();}
          if(k==='rotate'&&objects.length){
            const trip=destinationFor(objects[index],options,p,solar);
            if(!trip)return;
            const url=solar?'/media/'+enc(p.id)+'/solar-system/'+enc(trip.id):trip.tv_video;
            const token=clear(guide,true),layer=elm('div','scene');
            // Solar System films carry the mission credit in the picture.
            const v=movie(layer,url,()=>{if(token===generation)reveal(layer,solar?'':trip.tv_credit);},()=>{if(token===generation)guide();},
              ()=>{if(token===generation)problem(tr('Film niet beschikbaar','Film unavailable'),guide,guide);});
            key=k=>{if(['reset','toggle','play','pause'].includes(k)){
              if(k==='pause'||(k!=='play'&&!v.paused))v.pause();else v.play().catch(()=>{});
            }};
          }
        };
      }
      guide();
    }).catch(()=>{if(g===generation)problem(tr('Opname niet beschikbaar','Capture unavailable'),main,openPhoto);});
  }
  openPhoto();
}
start();
