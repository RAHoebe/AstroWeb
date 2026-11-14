import {local,t} from './i18n.js';

const $=id=>document.getElementById(id);
let selected,targets=[],pins=[],save;

export function editPanorama(record,objects,api){
  selected=record;
  const box=$('pano-editor');
  box.hidden=!record.capture_kind;
  box.open=false;
  if(box.hidden)return;
  save=api;
  targets=objects.filter(o=>o.id!==record.id);
  pins=(record.panorama?.pins||[]).map(({target,x,y})=>({target,x,y}));
  $('pano-wrap').checked=!!record.panorama?.wrap;
  $('pano-status').textContent='';
  $('pano-map-img').removeAttribute('src');
  $('pano-save').disabled=false;
  $('pano-preview').href='/panorama?capture='+encodeURIComponent(record.id);
  editorLanguage();
}

$('pano-editor').addEventListener('toggle',()=>{
  if($('pano-editor').open&&selected?.capture_kind)$('pano-map-img').src=selected.source_poster;
});

export function editorLanguage(){
  if(!selected?.capture_kind)return;
  const select=$('pano-target'),previous=select.value;
  select.replaceChildren(...targets.map(o=>new Option(
    [local(o.metadata.name),o.capture_date?.slice(0,10),o.session_name].filter(Boolean).join(' · '),o.id)));
  if(targets.some(o=>o.id===previous))select.value=previous;
  draw();
}

function draw(){
  const target=$('pano-target').value;
  $('pano-remove').disabled=!pins.some(pin=>pin.target===target);
  $('pano-editor-pins').replaceChildren(...pins.map(pin=>{
    const button=document.createElement('button');
    button.type='button';button.className='pano-pin';button.classList.toggle('selected',pin.target===target);
    const object=targets.find(o=>o.id===pin.target);
    button.classList.toggle('pano-pin-left',pin.x>.65);
    button.textContent=object?local(object.metadata.name):pin.target;
    button.style.left=(100*pin.x)+'%';button.style.top=(100*pin.y)+'%';
    button.addEventListener('click',e=>{e.stopPropagation();$('pano-target').value=pin.target;draw();});
    return button;
  }));
}

$('pano-target').addEventListener('change',draw);
$('pano-map').addEventListener('click',event=>{
  const target=$('pano-target').value, img=$('pano-map-img');
  if(!target||!img.naturalWidth)return;
  const r=img.getBoundingClientRect();
  const x=(event.clientX-r.left)/r.width,y=(event.clientY-r.top)/r.height;
  if(x<0||x>1||y<0||y>1)return;
  pins=pins.filter(pin=>pin.target!==target);
  pins.push({target,x,y});$('pano-status').textContent='';draw();
});
$('pano-remove').addEventListener('click',()=>{pins=pins.filter(p=>p.target!==$('pano-target').value);draw();});
$('pano-save').addEventListener('click',async()=>{
  const id=selected.id, button=$('pano-save');
  const body={wrap:$('pano-wrap').checked,pins:pins.map(p=>({...p}))};
  button.disabled=true;
  try{
    await save('/api/admin/objects/'+encodeURIComponent(id)+'/panorama',{method:'PUT',body});
    if(selected.id===id){selected.panorama=body;$('pano-status').textContent=t('saved');}
  }catch(e){if(selected.id===id)$('pano-status').textContent=t(e.message);}
  finally{if(selected.id===id)button.disabled=false;}
});
