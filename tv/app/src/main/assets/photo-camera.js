// D-pad: zoom with Up/Down, then press OK to pan with all four arrows.
class PhotoCamera {
  reset(){this.zoom=1;this.turns=0;this.x=this.y=this.dx=this.dy=0;this.pan=false;}
  constructor(){this.reset();}
  help(en){
    if(this.pan)return en?'Arrows  Pan     OK  Zoom':'Pijlen  Schuiven     OK  Zoomen';
    return en?'↑ ↓  Zoom     OK  Pan':'↑ ↓  Zoom     OK  Schuiven';
  }
  scaleLabel(en){return this.zoom.toLocaleString(en?'en':'nl',{maximumFractionDigits:1})+'×';}
  key(k){
    if(k==='rotate'){this.turns=(this.turns+1)%4;this.x=this.y=0;return;}
    if(k==='reset'){this.pan=!this.pan;if(this.pan && this.zoom===1)this.zoom=1.2;return;}
    if(!this.pan){if(k==='in'||k==='out')this.zoom=Math.max(5,Math.min(50,Math.round(5*this.zoom)+(k==='in'?1:-1)))/5;
      if(this.zoom===1)this.x=this.y=0;return;}
    if(k==='previous')this.x-=this.dx;
    if(k==='next')this.x+=this.dx;
    if(k==='in')this.y-=this.dy;
    if(k==='out')this.y+=this.dy;
  }
  draw(ctx,img,w,h){
    if(!img?.naturalWidth)return;
    const turns=this.turns-(img.naturalHeight>img.naturalWidth?1:0),turn=turns%2!==0;
    const iw=turn?img.naturalHeight:img.naturalWidth, ih=turn?img.naturalWidth:img.naturalHeight;
    const scale=Math.min(w/iw,h/ih)*this.zoom, dw=iw*scale,dh=ih*scale;
    const limit=(value,extent)=>Math.max(-extent,Math.min(extent,value));
    this.x=limit(this.x,Math.max(0,(dw-w)/(2*dw)));this.y=limit(this.y,Math.max(0,(dh-h)/(2*dh)));
    this.dx=.11*w/dw;this.dy=.11*h/dh;
    ctx.save();ctx.translate(w/2-this.x*dw,h/2-this.y*dh);ctx.rotate(turns*Math.PI/2);
    ctx.scale(scale,scale);ctx.drawImage(img,-img.naturalWidth/2,-img.naturalHeight/2);ctx.restore();
  }
}
