// Two-finger gestures take over from the surface's existing single-pointer controls.
export function enablePinch(surface, {getZoom, begin, transform}){
  const touches=new Map();
  let active=false, baseline=null, suppressClick=false;

  function measure(){
    const [a,b]=touches.values();
    const rect=surface.getBoundingClientRect();
    return {
      x:(b?(a.x+b.x)/2:a.x)-rect.left-rect.width/2,
      y:(b?(a.y+b.y)/2:a.y)-rect.top-rect.height/2,
      distance:b?Math.hypot(a.x-b.x,a.y-b.y):0
    };
  }
  function rebase(){
    baseline=touches.size===2?{distance:measure().distance,zoom:getZoom()}:null;
  }
  function consume(event){
    event.stopImmediatePropagation();
    if(event.cancelable)event.preventDefault();
  }

  surface.addEventListener('pointerdown',event=>{
    if(event.pointerType!=='touch')return;
    if(!touches.size)suppressClick=false;
    touches.set(event.pointerId,{x:event.clientX,y:event.clientY});
    if(!active && touches.size===2){
      active=true;suppressClick=true;
      begin();
      for(const id of touches.keys())if(id!==event.pointerId)surface.setPointerCapture(id);
    }
    if(active){
      surface.setPointerCapture(event.pointerId);
      rebase();consume(event);
    }
  },true);

  surface.addEventListener('pointermove',event=>{
    if(!touches.has(event.pointerId))return;
    const previous=active?measure():null;
    touches.set(event.pointerId,{x:event.clientX,y:event.clientY});
    if(!active)return;
    consume(event);
    if(touches.size>2)return;
    const next=measure();
    let zoom=getZoom();
    if(baseline && baseline.distance>0)zoom=baseline.zoom*next.distance/baseline.distance;
    else if(touches.size===2)rebase();
    transform(zoom,previous,next);
  },true);

  function finish(event){
    if(!touches.delete(event.pointerId))return;
    if(!active)return;
    consume(event);
    if(touches.size)rebase();
    else {active=false;baseline=null;}
  }
  surface.addEventListener('pointerup',finish,true);
  surface.addEventListener('pointercancel',finish,true);
  surface.addEventListener('lostpointercapture',event=>{
    // A marker or comparison divider can transfer its capture to the surface.
    if(event.target===surface)finish(event);
  },true);
  surface.addEventListener('click',event=>{
    if(suppressClick && event.detail && event.pointerType!=='mouse')consume(event);
  },true);
}
