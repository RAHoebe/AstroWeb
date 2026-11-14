// Source corners follow the original raster: top left, top right, bottom right, bottom left.
const posters=new Map();
export function posterURL(id){return '/media/'+encodeURIComponent(id)+'/poster';}

export function loadPoster(id){
  let image=posters.get(id);
  if(!image){
    image=new Image();posters.set(id,image);
    image.src=posterURL(id);
  }
  return image;
}

export function drawFootprintImage(ctx,id,quad,redraw){
  const xs=quad.map(p=>p[0]),ys=quad.map(p=>p[1]);
  if(Math.max(...xs)<0||Math.max(...ys)<0||Math.min(...xs)>ctx.canvas.clientWidth||Math.min(...ys)>ctx.canvas.clientHeight)return;
  const img=loadPoster(id);
  if(!img.complete){img.addEventListener('load',redraw,{once:true});return;}
  if(!img.naturalWidth)return;
  const [a,b,c,d]=quad,w=img.naturalWidth,h=img.naturalHeight;
  function half(vertices,origin,horizontal,vertical){
    ctx.save();
    ctx.beginPath();ctx.moveTo(...vertices[0]);ctx.lineTo(...vertices[1]);ctx.lineTo(...vertices[2]);ctx.closePath();ctx.clip();
    ctx.transform(horizontal[0]/w,horizontal[1]/w,vertical[0]/h,vertical[1]/h,...origin);
    ctx.drawImage(img,0,0);ctx.restore();
  }
  const sub=(p,q)=>[p[0]-q[0],p[1]-q[1]];
  half([a,b,c],a,sub(b,a),sub(c,b));
  half([a,c,d],a,sub(c,d),sub(d,a));
}
