// Moving maps share the NAS renderer's world coordinates and easing. Only the
// camera uniforms change per frame. At rest the detailed NAS canvas takes over.
function motionLayer(canvas,target,maxZoom,isPolar) {
  const gl=canvas.getContext('webgl',{alpha:false,antialias:true,depth:false,stencil:false});
  if(!gl)throw Error('No WebGL');
  const program=gl.createProgram();
  function shader(type,source) {
    const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));
    gl.attachShader(program,s);gl.deleteShader(s);
  }
  shader(gl.VERTEX_SHADER,`attribute vec2 pos;attribute vec2 uv;uniform vec4 camera;uniform float diameter;
    varying vec2 texCoord;void main(){texCoord=uv;gl_Position=vec4(pos*camera.xy+camera.zw,0.,1.);gl_PointSize=diameter;}`);
  shader(gl.FRAGMENT_SHADER,`precision mediump float;varying vec2 texCoord;uniform sampler2D photo;uniform int type;uniform vec4 tint;
    void main(){if(type==1){gl_FragColor=texture2D(photo,texCoord);}
    else if(type==2){float r=length(texCoord*2.-1.);if(r>1.)discard;gl_FragColor=mix(vec4(.14,.17,.29,1.),vec4(.05,.08,.16,1.),r);}
    else{if(type==3 && distance(gl_PointCoord,vec2(.5))>.5)discard;gl_FragColor=tint;}} `);
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  const pos=gl.getAttribLocation(program,'pos'),uv=gl.getAttribLocation(program,'uv');
  const uniform=n=>gl.getUniformLocation(program,n);
  const camera=uniform('camera'),diameter=uniform('diameter'),type=uniform('type'),tint=uniform('tint');
  const batches=[];gl.enableVertexAttribArray(pos);gl.enableVertexAttribArray(uv);
  function batch(primitive,vertices,color,kind=0,size=1,texture=null) {
    if(!vertices.length)return;
    const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);
    batches.push({primitive,b,count:vertices.length/4,color,kind,size,texture});
  }
  function quad(p,image,disc=false){
    let tex=null;
    if(image){
      tex=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,tex);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      for(const axis of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T])gl.texParameteri(gl.TEXTURE_2D,axis,gl.CLAMP_TO_EDGE);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);
    }
    const coords=[[0,0],[1,0],[1,1],[0,1]],v=[];
    for(const i of [0,1,2,0,2,3])v.push(...p[i],...coords[i]);
    batch(gl.TRIANGLES,v,[1,1,1,1],disc?2:1,1,tex);
  }
  const marker=document.getElementById('motion-target');
  function hide(){canvas.hidden=marker.hidden=true;}
  function draw(step){
    if(gl.isContextLost()){hide();return false;}
    const w=innerWidth,h=innerHeight,ratio=Math.min(devicePixelRatio,1.5);
    const ww=Math.round(w*ratio),hh=Math.round(h*ratio);
    if(canvas.width!==ww||canvas.height!==hh){canvas.width=ww;canvas.height=hh;}
    canvas.style.width=w+'px';canvas.style.height=h+'px';canvas.hidden=marker.hidden=false;
    gl.viewport(0,0,ww,hh);gl.clearColor(.027,.04,.075,1);gl.clear(gl.COLOR_BUFFER_BIT);
    const t=step/8,e=t*t*(3-2*t),base=isPolar?Math.max(1,Math.min(w,h)/2-26):Math.min(w,h);
    const scale=base*Math.pow(maxZoom,e);
    const dx=target[0]*base*(1-e),dy=target[1]*base*(1-e);
    gl.uniform4f(camera,2*scale/w,-2*scale/h,2*(dx-target[0]*scale)/w,-2*(dy-target[1]*scale)/h);
    for(const b of batches){
      gl.bindBuffer(gl.ARRAY_BUFFER,b.b);gl.vertexAttribPointer(pos,2,gl.FLOAT,false,16,0);gl.vertexAttribPointer(uv,2,gl.FLOAT,false,16,8);
      gl.uniform4fv(tint,b.color);gl.uniform1i(type,b.kind);gl.uniform1f(diameter,b.size*ratio);
      if(b.texture)gl.bindTexture(gl.TEXTURE_2D,b.texture);
      gl.drawArrays(b.primitive,0,b.count);
    }
    marker.style.transform='translate('+ (w/2+dx)+'px,'+(h/2+dy)+'px)';return true;
  }
  return {gl,batch,quad,draw,hide};
}

function galaxyMotion(canvas,g,image,name){
  const layer=motionLayer(canvas,[g.xy[0]-.5,g.xy[1]-.5],13,false);
  layer.quad([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]],image);
  document.getElementById('motion-label').textContent=name;return layer;
}

async function polarMotion(canvas,data,en){
  if(!data.target)return null;
  const side=data.target.dec<0?-1:1,rad=Math.PI/180;
  function point(ra,dec){const r=(90-side*dec)/90;return [-r*Math.sin(ra*rad)*side,-r*Math.cos(ra*rad)];}
  const target=point(data.target.ra,data.target.dec),corners=data.corners.map(c=>point(...c));
  const extent=corners.length?Math.max(...corners.map(p=>Math.hypot(p[0]-target[0],p[1]-target[1]))):.05;
  const layer=motionLayer(canvas,target,Math.min(45,Math.max(3,.62/Math.max(extent,.01))),true),gl=layer.gl;
  layer.quad([[-1,-1],[1,-1],[1,1],[-1,1]],null,true);
  if(corners.length===4){
    const image=new Image();image.src='/media/'+encodeURIComponent(data.capture)+'/poster';
    try{await image.decode();layer.quad(corners,image);}catch{/* The measured footprint remains visible. */}
  }
  const edges=[],grid=[],positions=new Map(),stars=[[],[],[]];
  function edge(list,a,b){list.push(...a,0,0,...b,0,0);}
  for(let d=15;d<=90;d+=15){
    for(let ra=0;ra<360;ra+=3)edge(grid,point(ra,side*(90-d)),point(ra+3,side*(90-d)));
  }
  for(let ra=0;ra<360;ra+=30)edge(grid,[0,0],point(ra,0));
  for(const [id,ra0,dec0,mag] of data.stars){
    let ra=ra0,dec=dec0;const v=data.motion[id];
    if(v){const years=data.epoch-2000,x=v[0]+years*v[3],y=v[1]+years*v[4],z=v[2]+years*v[5];
      ra=Math.atan2(y,x)/rad;dec=Math.atan2(z,Math.hypot(x,y))/rad;}
    if(dec*side<0)continue;
    const p=point(ra,dec);positions.set(id,p);stars[mag<2?2:mag<4?1:0].push(...p,0,0);
  }
  for(const group of data.groups)for(const line of group.lines)for(let i=1;i<line.length;i++){
    const a=positions.get(line[i-1]),b=positions.get(line[i]);if(a&&b)edge(edges,a,b);
  }
  layer.batch(gl.LINES,grid,[.23,.27,.39,1]);layer.batch(gl.LINES,edges,[.38,.47,.57,1]);
  stars.forEach((v,i)=>layer.batch(gl.POINTS,v,i===2?[1,.94,.81,1]:[.77,.84,.94,1],3,1.2+i));
  if(corners.length===4){const outline=[];corners.forEach((p,i)=>edge(outline,p,corners[(i+1)%4]));layer.batch(gl.LINES,outline,[1,.81,.50,1]);}
  document.getElementById('motion-label').textContent=data.target.name[en?'en':'nl'];return layer;
}
