// Distance diagrams use measured/catalogued values; the display geometry is schematic.
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const mix=(a,b,t)=>a+(b-a)*t;
const smooth=v=>{v=clamp(v,0,1);return v*v*(3-2*v);};
function multiply(a,b){const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];return out;}
const unit=a=>{const n=Math.hypot(...a);return a.map(v=>v/n);};
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const dot=(a,b)=>a.reduce((n,v,i)=>n+v*b[i],0);
export function spaceLayout(data,w,h,zoom,orbit,unfold,turn=0){
  const aspect=data.height/data.width,yaw=1.12*smooth(unfold)+orbit,pitch=.22,r=Math.max(4.4,(turn?2:2*aspect)*1.4)/Math.sqrt(zoom);
  const eye=[Math.sin(yaw)*Math.cos(pitch)*r,Math.sin(pitch)*r,Math.cos(yaw)*Math.cos(pitch)*r];
  const z=unit(eye),x=unit(cross([0,1,0],z)),y=cross(z,x);
  const view=new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);
  const f=1/Math.tan(44*Math.PI/360),near=.05,far=100;
  const projection=new Float32Array([f/(w/h),0,0,0,0,f,0,0,0,0,(far+near)/(near-far),-1,0,0,2*far*near/(near-far),0]);
  const c=Math.cos(-turn),s=Math.sin(-turn),rotation=new Float32Array([c,s,0,0,-s,c,0,0,0,0,1,0,0,0,0,1]);
  const mvp=multiply(multiply(projection,view),rotation);
  const maxPc=Math.max(...data.stars.map(s=>s.distance_pc)),minPc=Math.min(...data.stars.map(s=>s.distance_pc)),floor=Math.max(.00001,minPc*.7),fitScale=Math.min((turn?h:w)/data.width,(turn?w:h)/data.height);
  return {mvp,w,h,aspect,maxPc,minPc,floor,unfold:smooth(unfold),turn,fit:[data.width*fitScale,data.height*fitScale]};
}
export function projectPoint(view,p){
  const a=view.mvp,x=p[0],y=p[1],z=p[2];
  const q=[a[0]*x+a[4]*y+a[8]*z+a[12],a[1]*x+a[5]*y+a[9]*z+a[13],a[3]*x+a[7]*y+a[11]*z+a[15]];
  if(q[2]<=0)return null;
  return [(q[0]/q[2]+1)*view.w/2,(1-q[1]/q[2])*view.h/2];
}
export function starPoint(view,star){
  const z=1.8-3.3*Math.log(star.distance_pc/view.floor)/Math.log(view.maxPc/view.floor);
  const spatial=projectPoint(view,[(star.x-.5)*2,(.5-star.y)*2*view.aspect,z]);
  if(!spatial)return null;
  let x=(star.x-.5)*view.fit[0],y=(star.y-.5)*view.fit[1];
  const c=Math.cos(view.turn),s=Math.sin(view.turn);[x,y]=[c*x-s*y,s*x+c*y];
  return [mix(view.w/2+x,spatial[0],view.unfold),mix(view.h/2+y,spatial[1],view.unfold)];
}
function quad(ctx,image,p){
  if(p.some(v=>!v))return;
  const [a,b,c,d]=p,sub=(p,q)=>[p[0]-q[0],p[1]-q[1]];
  function half(v,o,h,k){ctx.save();ctx.beginPath();ctx.moveTo(...v[0]);ctx.lineTo(...v[1]);ctx.lineTo(...v[2]);ctx.closePath();ctx.clip();ctx.transform(h[0]/image.width,h[1]/image.width,k[0]/image.height,k[1]/image.height,...o);ctx.drawImage(image,0,0);ctx.restore();}
  half([a,b,c],a,sub(b,a),sub(c,b));half([a,c,d],a,sub(c,d),sub(d,a));
}
export function distanceScaffold(ctx,data,view,plane,t,number){
  const alpha=view.unfold;if(alpha<=0)return;
  ctx.save();ctx.globalAlpha=alpha;
  const a=view.aspect;
  const board=[[-1,a,-1.7],[1,a,-1.7],[1,-a,-1.7],[-1,-a,-1.7]].map(p=>projectPoint(view,p));
  ctx.globalAlpha=alpha*.32;quad(ctx,plane,board);ctx.globalAlpha=alpha;
  ctx.font='11px Segoe UI,Arial';ctx.lineWidth=1;
  const occupied=[];
  function caption(text,x,y,align='right'){
    if(x<0||x>view.w||y<0||y>view.h)return;
    const width=ctx.measureText(text).width;
    const left=clamp(x-(align==='right'?width:width/2),8,Math.max(8,view.w-width-8)),baseline=clamp(y,14,view.h-8);
    if(occupied.some(([a,b,c,d])=>left<c&&left+width>a&&baseline-12<d&&baseline>b))return;
    occupied.push([left,baseline-12,left+width,baseline+3]);ctx.textAlign='left';ctx.fillText(text,left,baseline);
  }
  function line(points,color){const p=points.map(v=>projectPoint(view,v));if(p.some(v=>!v))return;ctx.strokeStyle=color;ctx.beginPath();p.forEach((v,i)=>i?ctx.lineTo(...v):ctx.moveTo(...v));ctx.stroke();}
  const ticks=[view.minPc*3.2615638,...[10,100,1000,10000].filter(v=>v>view.minPc*3.2615638*1.2&&v<view.maxPc*3.2615638*.8),view.maxPc*3.2615638];
  for(const distance of ticks){
    const pc=distance/3.2615638,z=1.8-3.3*Math.log(pc/view.floor)/Math.log(view.maxPc/view.floor);
    line([[-1.1,-a,z],[1.1,-a,z],[1.1,a,z],[-1.1,a,z],[-1.1,-a,z]],'#ed998a55');
    const p=projectPoint(view,[-1.25,-a,z]);if(p){ctx.fillStyle='#dcc0b8';caption(number(distance)+' '+t('lightYears'),p[0]-6,p[1]);}
  }
  line([[-1.1,-a,1.8],[-1.1,-a,-1.5]],'#ed998a99');
  const earth=projectPoint(view,[0,0,1.8]);
  if(earth){ctx.fillStyle='#ed998a';ctx.beginPath();ctx.arc(...earth,4,0,Math.PI*2);ctx.fill();ctx.fillStyle='#ffefe6';caption(t('obs_earth'),earth[0],earth[1]+19,'center');}
  if(board[1]){ctx.fillStyle='#dcc0b8';caption(t('obs_reference_photo'),board[1][0],board[1][1]-9);}
  ctx.restore();
}

export function lightJourney(ctx,data,photo,progress,w,h,t,number,date){
  const p=clamp(progress,0,1),left=w*.21,right=w*.82,y=h*.51,total=data.lookback_years;
  ctx.save();ctx.globalAlpha=.12;
  const bg=Math.max(w/photo.width,h/photo.height);ctx.drawImage(photo,(w-photo.width*bg)/2,(h-photo.height*bg)/2,photo.width*bg,photo.height*bg);ctx.globalAlpha=1;
  const shade=ctx.createRadialGradient(w*.5,h*.5,0,w*.5,h*.5,w*.7);shade.addColorStop(0,'#180f1433');shade.addColorStop(1,'#09060aee');ctx.fillStyle=shade;ctx.fillRect(0,0,w,h);
  const imageWidth=w*.31,imageHeight=Math.min(h*.48,imageWidth*photo.height/photo.width),iw=imageHeight*photo.width/photo.height;
  ctx.drawImage(photo,left-iw/2,y-imageHeight/2,iw,imageHeight);ctx.strokeStyle='#ed998a66';ctx.strokeRect(left-iw/2,y-imageHeight/2,iw,imageHeight);
  const start=left+iw/2+18,end=right-33,rayY=y;
  ctx.strokeStyle='#ed998a44';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(start,rayY);ctx.lineTo(end,rayY);ctx.stroke();
  const x=start+(end-start)*p;
  const trail=ctx.createLinearGradient(Math.max(start,x-w*.13),0,x,0);trail.addColorStop(0,'#ed998a00');trail.addColorStop(1,'#ffddbaff');ctx.strokeStyle=trail;ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(Math.max(start,x-w*.13),rayY);ctx.lineTo(x,rayY);ctx.stroke();
  ctx.fillStyle='#ffe3bf';ctx.shadowColor='#ed998a';ctx.shadowBlur=18;ctx.beginPath();ctx.arc(x,rayY,5,0,2*Math.PI);ctx.fill();ctx.shadowBlur=0;
  ctx.strokeStyle='#dcc0b8';ctx.lineWidth=1.3;ctx.beginPath();ctx.arc(right,y,27,0,2*Math.PI);ctx.ellipse(right,y,12,27,0,0,Math.PI*2);ctx.ellipse(right,y,27,9,0,0,Math.PI*2);ctx.stroke();
  const size=clamp(w*.017,12,21);ctx.font=size+'px Segoe UI,Arial';ctx.fillStyle='#ffefe6';ctx.textAlign='center';
  ctx.fillText(t('obs_light_departure'),left,y+imageHeight/2+28);ctx.fillText(t('obs_earth'),right,y+58);
  ctx.font=clamp(size*.8,10,16)+'px Segoe UI,Arial';ctx.fillStyle='#dcc0b8';ctx.fillText(number(total)+' '+t('obs_years_ago'),left,y+imageHeight/2+51);
  ctx.fillText(date||t('unknownDate'),right,y+81);
  ctx.fillStyle='#ed998a';ctx.fillText(t('obs_photon'),x,rayY-21);
  ctx.fillStyle='#dcc0b8';ctx.textAlign='center';ctx.fillText(t('obs_light_schematic'),w/2,h*.91);
  const arrival=smooth((p-.86)/.14);
  if(arrival>0){
    ctx.fillStyle=`rgba(9,6,10,${arrival})`;ctx.fillRect(0,0,w,h);
    const f=Math.min(w/photo.width,h/photo.height);ctx.globalAlpha=arrival;ctx.drawImage(photo,(w-photo.width*f)/2,(h-photo.height*f)/2,photo.width*f,photo.height*f);ctx.globalAlpha=1;
    ctx.fillStyle='#180f14df';ctx.fillRect(w*.1,h*.78,w*.8,Math.min(80,h*.16));ctx.fillStyle='#ffefe6';ctx.font=clamp(w*.025,16,30)+'px Segoe UI,Arial';ctx.fillText(t('obs_light_arrived'),w/2,h*.84);
    ctx.font=clamp(w*.014,11,17)+'px Segoe UI,Arial';ctx.fillStyle='#dcc0b8';ctx.fillText(number(total)+' '+t('obs_years_travelled'),w/2,h*.89);
  }
  ctx.restore();
}
