// One GPU batch of original stellar image crops; no generated or invented stars.
export class SpaceStars {
  constructor(canvas){
    this.canvas=canvas;this.gl=canvas.getContext('webgl',{alpha:false,antialias:false,preserveDrawingBuffer:false});
    this.ready=false;
    canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();this.ready=false;});
    if(!this.gl)return;
    const gl=this.gl;
    const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error('shader');return s;};
    const vertex=shader(gl.VERTEX_SHADER,`attribute vec2 center;attribute float distance;attribute vec2 corner;attribute vec2 tex;attribute vec2 size;
      uniform mat4 mvp;uniform float maxDistance;uniform float logFloor;uniform float aspect;uniform float unfold;
      uniform vec2 viewport;uniform vec2 fit;uniform vec2 turn;varying vec2 uv;
      void main(){float z=1.8-3.3*log(distance/logFloor)/log(maxDistance/logFloor);
        vec4 position=mvp*vec4((center.x-.5)*2.,(.5-center.y)*2.*aspect,z,1.);
        vec2 pixel=(center-.5+corner*size)*fit;pixel=vec2(turn.x*pixel.x-turn.y*pixel.y,turn.y*pixel.x+turn.x*pixel.y);
        vec4 initial=vec4(pixel.x*2./viewport.x,-pixel.y*2./viewport.y,0.,1.);
        vec2 stamp=clamp(size*fit,vec2(3.),vec2(30.));
        vec4 spatial=vec4(position.xyz/max(position.w,.001),1.);
        spatial.xy+=vec2(corner.x*stamp.x,-corner.y*stamp.y)*2./viewport;
        if(position.w<=0.)spatial=vec4(2.,2.,2.,1.);
        gl_Position=mix(initial,spatial,unfold);uv=tex;}`);
    const fragment=shader(gl.FRAGMENT_SHADER,`precision mediump float;uniform sampler2D atlas;varying vec2 uv;
      void main(){gl_FragColor=vec4(texture2D(atlas,uv).rgb,1.);}`);
    this.program=gl.createProgram();gl.attachShader(this.program,vertex);gl.attachShader(this.program,fragment);gl.linkProgram(this.program);
    if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error('shader');
    gl.useProgram(this.program);this.locations={};
    for(const name of ['mvp','maxDistance','logFloor','aspect','unfold','viewport','fit','turn'])this.locations[name]=gl.getUniformLocation(this.program,name);
    this.buffer=gl.createBuffer();this.texture=gl.createTexture();
  }
  set(data,image){
    if(!this.gl)return false;
    const gl=this.gl,vertices=[],corners=[[-.5,-.5],[.5,-.5],[-.5,.5],[-.5,.5],[.5,-.5],[.5,.5]];
    for(const star of data.stars){
      const [x,y,w,h]=star.atlas;
      for(const [u,v] of corners)vertices.push(star.x,star.y,star.distance_pc,u,v,(x+(u+.5)*w)/image.width,(y+(v+.5)*h)/image.height,star.width,star.height);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);
    let offset=0;
    for(const [name,n] of [['center',2],['distance',1],['corner',2],['tex',2],['size',2]]){
      const loc=gl.getAttribLocation(this.program,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,n,gl.FLOAT,false,36,offset*4);offset+=n;
    }
    gl.bindTexture(gl.TEXTURE_2D,this.texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,image);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,data.blend==='screen'?gl.ONE_MINUS_SRC_COLOR:gl.ONE);
    this.count=vertices.length/9;this.ready=true;return true;
  }
  draw(data,view){
    if(!this.ready||!this.gl)return;
    const gl=this.gl;gl.viewport(0,0,this.canvas.width,this.canvas.height);gl.clearColor(0,0,0,1);gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(this.program);gl.uniformMatrix4fv(this.locations.mvp,false,view.mvp);
    gl.uniform1f(this.locations.logFloor,view.floor);
    gl.uniform1f(this.locations.maxDistance,view.maxPc);gl.uniform1f(this.locations.aspect,view.aspect);gl.uniform1f(this.locations.unfold,view.unfold);
    gl.uniform2fv(this.locations.viewport,[view.w,view.h]);gl.uniform2fv(this.locations.fit,view.fit);
    gl.uniform2f(this.locations.turn,Math.cos(view.turn),Math.sin(view.turn));
    gl.drawArrays(gl.TRIANGLES,0,this.count);
  }
}
