// Both tracks use the same horizontal coordinates. North is up, east is left, as on a sky chart.
function drawNight(canvas, data, selection, index, tr, title) {
  const ratio=Math.min(1.5,devicePixelRatio), w=Math.round(innerWidth*ratio),h=Math.round(innerHeight*ratio);
  if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
  const ctx=canvas.getContext('2d'), scale=h/720;
  ctx.setTransform(scale,0,0,scale,0,0);
  const width=w/scale, cx=width*.37, cy=336, radius=Math.min(222,width*.23);
  ctx.fillStyle='#0e0c15';ctx.fillRect(0,0,width,720);
  const point=([az,alt])=>{
    const r=radius*(90-alt)/90, a=az*Math.PI/180;
    return [cx-r*Math.sin(a),cy-r*Math.cos(a)];
  };
  const label=(text,x,y,color='#e6cabe',size=17)=>{
    ctx.font=size+'px Roboto,sans-serif';ctx.fillStyle=color;ctx.fillText(text,x,y);
  };
  for(const alt of [0,30,60]){
    ctx.strokeStyle='#50424b';ctx.beginPath();ctx.arc(cx,cy,radius*(90-alt)/90,0,2*Math.PI);ctx.stroke();
  }
  for(const [a,name] of [[0,'N'],[90,tr('O','E')],[180,tr('Z','S')],[270,'W']]){
    const [x,y]=point([a,-8]);label(name,x-5,y+5);
  }
  const active=data[selection], other=selection==='capture'?data.tonight:data.capture;
  function path(track,color,dashed){
    ctx.strokeStyle=color;ctx.lineWidth=dashed?2:3;ctx.setLineDash(dashed?[5,7]:[]);
    ctx.beginPath();let visible=false;
    const hours=new Set(track.hours);
    for(const [i,row] of track.target.entries()){if(!hours.has(i)||row[1]<0){visible=false;continue;}const [x,y]=point(row);if(visible)ctx.lineTo(x,y);else ctx.moveTo(x,y);visible=true;}
    ctx.stroke();ctx.setLineDash([]);
  }
  path(other,'#958897',true);path(active,'#f09c80',false);
  const bodyNames={moon:tr('Maan','Moon'),sun:tr('Zon','Sun'),mars:'Mars',jupiter:'Jupiter',saturn:tr('Saturnus','Saturn'),venus:'Venus',mercury:tr('Mercurius','Mercury'),uranus:'Uranus',neptune:tr('Neptunus','Neptune')};
  for(const [body,rows] of Object.entries(active.bodies)){
    if(rows[index][1]<0)continue;
    const [x,y]=point(rows[index]);ctx.fillStyle='#e4ccaa';ctx.beginPath();ctx.arc(x,y,2.5,0,2*Math.PI);ctx.fill();label(bodyNames[body],x+5,y-5,'#e4ccaa',13);
  }
  const pos=active.target[index];
  if(pos[1]>=0){const [x,y]=point(pos);ctx.lineWidth=3;ctx.strokeStyle='#fff3bb';ctx.beginPath();ctx.arc(x,y,7,0,2*Math.PI);ctx.stroke();}
  const clock=i=>new Date((active.start+i*active.step)*1000).toLocaleTimeString(document.documentElement.lang,{timeZone:data.timezone,hour:'2-digit',minute:'2-digit',hour12:false});
  const left=width*.63;
  label(active.day,left,216,'#ffba9d',28);label(clock(index)+' · '+data.timezone,left,254);
  label(tr('Hoogte','Altitude')+'  '+pos[1].toFixed(1)+'°',left,306,'#fff2df',25);
  label(pos[1]<0?tr('Onder de horizon','Below the horizon'):tr('Boven de horizon','Above the horizon'),left,339);
  if(active.peak!==null){
    label(tr('Hoogste stand','Highest point')+'  ≈ '+clock(active.peak),left,394);
    label(active.target[active.peak][1].toFixed(1)+'°',left,425);
  }else label(tr('Geen zonsondergang','No sunset'),left,394);
  label(tr('Stippellijn · andere datum','Dashed line · other date'),left,474,'#bdadbc',16);
  if(data.default_site)label(tr('Locatie · midden van Nederland','Site · central Netherlands'),left,508,'#bdadbc',15);
  if(data.day_only && selection==='capture')label(tr('Exacte opnametijd onbekend','Exact capture time unknown'),left,535,'#bdadbc',15);
  label(title,Math.round(width*.06),64,'#ffdbc8',27);
}