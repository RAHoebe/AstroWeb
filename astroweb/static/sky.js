import {t,language,formatDate} from './i18n.js';
const $=id=>document.getElementById(id);
const lerp=(a,b,f)=>a+(b-a)*f;
const angle=(a,b,f)=>(a+(((b-a+540)%360)-180)*f+360)%360;
export class SkyPlayer{
  constructor(){this.canvas=$('sky-canvas');this.ctx=this.canvas.getContext('2d');this.cache=new Map();this.playing=false;this.frame=0;this.raf=null;this.last=0;this.loadGeneration=0;this.loadError=null;$('sky-play').addEventListener('click',()=>this.playing?this.pause():this.play());$('sky-time').addEventListener('input',()=>{this.pause();this.frame=+$('sky-time').value/1000*(this.data.samples.length-1);this.draw();});}
  async load(object,api){this.pause();this.loadError=null;const generation=++this.loadGeneration;$('sky-status').textContent=t('skyLoading');this.data=null;
    $('sky-play').disabled=true;
    $('sky-time').disabled=true;
    $('sky-time').value='0';
    for(const id of ['sky-date','sky-caption','sky-clock'])$(id).textContent='';
    this.ctx.clearRect(0,0,1400,650);try{const data=this.cache.get(object.id)||await api(`/api/objects/${object.id}/sky`);if(generation!==this.loadGeneration)return;this.cache.set(object.id,data);this.data=data;$('sky-play').disabled=false;$('sky-time').disabled=false;this.index=new Map(data.stars.map((s,i)=>[s.hip,i]));this.frame=Math.max(0,data.samples.findIndex(r=>r.time>=data.observed_at));$('sky-status').textContent='';this.updateLanguage();}catch(e){if(generation===this.loadGeneration){this.loadError=e.message;this.updateLanguage();}}}
  updateLanguage(){
    if(this.loadError){$('sky-status').textContent=t(this.loadError);return;}
    if(!this.data)return;
    $('sky-date').textContent=formatDate(this.data.evening+'T12:00:00');
    const d=this.data;
    $('sky-caption').textContent=[t(d.body?'solarSkyCaption':'skyCaption'),d.default_site?t('centralNL'):'',d.day_only?t('solarNoon'):'',d.timezone].filter(Boolean).join(' ');
    this.draw();
  }
  play(){if(!this.data)return;this.playing=true;$('sky-play').textContent='Ⅱ';this.last=performance.now();const tick=now=>{if(!this.playing)return;this.frame=(this.frame+(now-this.last)/45000*(this.data.samples.length-1))%(this.data.samples.length-1);this.last=now;this.draw();this.raf=requestAnimationFrame(tick);};this.raf=requestAnimationFrame(tick);}
  pause(){this.playing=false;cancelAnimationFrame(this.raf);$('sky-play').textContent='▶';}
  draw(){if(!this.data)return;const c=this.ctx,d=this.data;const i=Math.min(d.samples.length-2,Math.floor(this.frame)),f=this.frame-i;const a=d.samples[i],b=d.samples[i+1];const alt=lerp(a.altitude,b.altitude,f),az=angle(a.azimuth,b.azimuth,f),stamp=lerp(a.time,b.time,f),sun=lerp(a.sun,b.sun,f);const darkness=Math.max(.08,Math.min(1,(-sun+2)/20));
    c.clearRect(0,0,1400,650);const gradient=c.createLinearGradient(0,0,0,530);gradient.addColorStop(0,darkness>.6?'#050a18':'#102b45');gradient.addColorStop(.8,darkness>.6?'#111f35':'#34516b');gradient.addColorStop(1,darkness>.6?'#253044':'#876e70');c.fillStyle=gradient;c.fillRect(0,0,1400,650);
    const point=(altitude,azimuth)=>[azimuth/360*1400,490-altitude/90*440];
    c.strokeStyle='#b5cbe014';c.lineWidth=1;c.setLineDash([3,7]);for(const height of [30,60]){const y=point(height,0)[1];c.beginPath();c.moveTo(0,y);c.lineTo(1400,y);c.stroke();c.fillStyle='#9bb4cf80';c.font='10px Segoe UI';c.fillText(height+'°',12,y-7);}c.setLineDash([]);
    const positions=d.positions[i].map((p,j)=>[lerp(p[0],d.positions[i+1][j][0],f),angle(p[1],d.positions[i+1][j][1],f)]);
    c.strokeStyle=`rgba(133,170,208,${darkness*.18})`;c.lineWidth=.8;for(const line of d.lines){for(let k=1;k<line.length;k++){const p=positions[this.index.get(line[k-1])],q=positions[this.index.get(line[k])];if(!p||!q||p[0]<0||q[0]<0||Math.abs(p[1]-q[1])>180)continue;const [x,y]=point(...p),[xx,yy]=point(...q);c.beginPath();c.moveTo(x,y);c.lineTo(xx,yy);c.stroke();}}
    d.stars.forEach((star,j)=>{const [height,bearing]=positions[j];if(height<0)return;const [x,y]=point(height,bearing);const radius=Math.max(.45,(6.8-star.magnitude)*.38);c.fillStyle=`rgba(209,225,247,${darkness*Math.min(1,(7-star.magnitude)/4)})`;c.beginPath();c.arc(x,y,radius,0,Math.PI*2);c.fill();if(star.magnitude<1.7&&star.name){c.font='10px Segoe UI';c.fillStyle=`rgba(177,201,224,${darkness*.7})`;c.fillText(star.name,x+7,y-7);}});
    c.strokeStyle='#e9c58b8a';c.lineWidth=1.2;c.setLineDash([4,7]);c.beginPath();let previous=null;for(const r of d.samples){if(r.altitude<0){previous=null;continue;}const p=point(r.altitude,r.azimuth);if(!previous||Math.abs(previous[0]-p[0])>700)c.moveTo(...p);else c.lineTo(...p);previous=p;}c.stroke();c.setLineDash([]);
    const [tx,ty]=point(alt,az);if(alt>=0){const glow=c.createRadialGradient(tx,ty,0,tx,ty,28);glow.addColorStop(0,'#ebca9360');glow.addColorStop(1,'#ebca9300');c.fillStyle=glow;c.fillRect(tx-30,ty-30,60,60);c.strokeStyle='#edc98b';c.lineWidth=1;c.beginPath();c.arc(tx,ty,9,0,Math.PI*2);c.stroke();c.fillStyle='#ffe0ab';c.beginPath();c.arc(tx,ty,2.5,0,Math.PI*2);c.fill();c.font='12px Segoe UI';c.fillText((d.body?t('body_'+d.body):d.id.replace('_',' ')),Math.min(1250,tx+17),ty-12);}
    c.fillStyle='#060c15';c.beginPath();c.moveTo(0,510);for(let x=0;x<=1400;x+=4){const y=500+Math.sin(x*.019)*3+Math.sin(x*.037)*4+Math.sin(x*.009)*7;c.lineTo(x,y);}c.lineTo(1400,650);c.lineTo(0,650);c.closePath();c.fill();
    const dirs=language==='nl'?['N','O','Z','W','N']:['N','E','S','W','N'];c.fillStyle='#8b9cb4';c.font='11px Segoe UI';dirs.forEach((name,k)=>c.fillText(name,Math.min(1380,k*350+10),530));
    c.fillStyle='#9bdfec';c.font='10px Segoe UI';c.fillText(t(d.body?'solarSkyDay':'night')+' / '+(d.body?t('body_'+d.body):d.id.replace('_',' ')),30,32);c.fillStyle='#b9cadc';c.font='12px Segoe UI';c.fillText(`${t('altitude')} ${alt.toFixed(1)}°   ·   ${t('azimuth')} ${az.toFixed(1)}°   ·   ${t('sun')} ${sun.toFixed(1)}°`,920,32);if(alt<0){c.fillStyle='#d4b58b';c.font='16px Segoe UI';c.fillText(t('belowHorizon'),35,70);}
    const left=40,right=1360,top=560,bottom=622;const px=index=>left+index/(d.samples.length-1)*(right-left),py=value=>bottom-Math.max(0,value)/90*(bottom-top);c.strokeStyle='#2a384d';c.beginPath();c.moveTo(left,bottom);c.lineTo(right,bottom);c.stroke();c.strokeStyle='#d4b58b';c.lineWidth=1.5;c.beginPath();d.samples.forEach((row,k)=>k?c.lineTo(px(k),py(row.altitude)):c.moveTo(px(k),py(row.altitude)));c.stroke();const marker=px(this.frame);c.strokeStyle='#9bdfec70';c.beginPath();c.moveTo(marker,top-5);c.lineTo(marker,bottom+4);c.stroke();c.fillStyle='#9bdfec';c.beginPath();c.arc(marker,py(alt),3,0,Math.PI*2);c.fill();const observed=(d.observed_at-d.samples[0].time)/(d.samples.at(-1).time-d.samples[0].time);if(observed>=0&&observed<=1){c.fillStyle='#c796d8';c.beginPath();c.arc(left+observed*(right-left),bottom+8,3,0,Math.PI*2);c.fill();}
    if(this.clockLanguage!==language||this.clockZone!==d.timezone){
      this.clockLanguage=language;this.clockZone=d.timezone;
      this.clockFormat=new Intl.DateTimeFormat(language==='nl'?'nl-NL':'en-GB',{hour:'2-digit',minute:'2-digit',timeZone:d.timezone,timeZoneName:'short'});
    }
    $('sky-time').value=String(this.frame/(d.samples.length-1)*1000);$('sky-clock').textContent=this.clockFormat.format(new Date(stamp*1000));
  }
}
