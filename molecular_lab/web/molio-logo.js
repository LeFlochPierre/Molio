'use strict';
// The brand sculpture has its own viewer and never loads a target or starts a job.
const logoMotionPreference=matchMedia('(prefers-reduced-motion: reduce)');
let molioLogo=null, molioMeshPromise=null, molioLogoRevision=0;
let molioLogoSpinning=!logoMotionPreference.matches;
// A small dedicated WebGL renderer gives the logo soft studio lighting without
// changing the scientific viewers' materials or lighting.
function createMolioLogoRenderer(host,core){
  const mesh=core;
  const canvas=document.createElement('canvas');host.append(canvas);
  const gl=canvas.getContext('webgl',{alpha:true,antialias:true,preserveDrawingBuffer:true});
  if(!gl){canvas.remove();throw Error('WebGL unavailable');}
  const compile=(type,source)=>{const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(shader));return shader;};
  const vertex=compile(gl.VERTEX_SHADER,`attribute vec3 position,normal,color;uniform vec3 mintOffset,cyanOffset,centreOffset;uniform vec2 angle;uniform float aspect,zoom;varying vec3 vNormal,vColor;
    vec3 turn(vec3 p){float cy=cos(angle.x),sy=sin(angle.x),cx=cos(angle.y),sx=sin(angle.y);vec3 q=vec3(cy*p.x+sy*p.z,p.y,-sy*p.x+cy*p.z);return vec3(q.x,cx*q.y-sx*q.z,sx*q.y+cx*q.z);}
    vec3 flex(vec3 p){
      float end=(1.-smoothstep(-3.,6.,p.y))*smoothstep(5.,9.,abs(p.x));
      float centre=(1.-smoothstep(3.6,8.5,abs(p.x)))*(1.-smoothstep(2.8,7.5,p.y));
      float right=smoothstep(-3.,3.,p.x);
      return p+end*mix(cyanOffset,mintOffset,right)+centre*centreOffset;
    }
    void main(){
      vec3 tangent=normalize(cross(normal,abs(normal.y)<.9?vec3(0.,1.,0.):vec3(1.,0.,0.)));
      vec3 bitangent=cross(normal,tangent);
      vec3 p0=flex(position);
      vec3 bentNormal=normalize(cross(flex(position+tangent*.01)-p0,flex(position+bitangent*.01)-p0));
      vec3 p=turn(p0);vNormal=turn(bentNormal);vColor=color;
      gl_Position=vec4(p.x*.041*zoom/aspect,p.y*.041*zoom,-p.z*.018,1.);
    }`);
  const fragment=compile(gl.FRAGMENT_SHADER,`precision mediump float;varying vec3 vNormal,vColor;
    void main(){vec3 n=normalize(vNormal);vec3 light=normalize(vec3(.45,.7,1.));float diffuse=max(dot(n,light),0.);float shine=pow(max(dot(n,normalize(light+vec3(0.,0.,1.))),0.),18.);float rim=pow(1.-abs(n.z),3.);vec3 color=vColor*(.66+.34*diffuse)+vec3(.13)*shine+vec3(.045)*rim;gl_FragColor=vec4(color,1.);}`);
  const program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Logo shader unavailable');gl.useProgram(program);
  const buffers=[];
  for(const [name,values] of [['position',mesh.vertices],['normal',mesh.normals],['color',mesh.colours]]){
    const buffer=gl.createBuffer();buffers.push(buffer);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values.flat()),gl.STATIC_DRAW);
    const location=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,3,gl.FLOAT,false,0,0);
  }
  const indices=gl.createBuffer();buffers.push(indices);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,indices);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(mesh.faces),gl.STATIC_DRAW);
  const uniforms=Object.fromEntries(['angle','aspect','zoom','mintOffset','cyanOffset','centreOffset'].map(name=>[name,gl.getUniformLocation(program,name)]));
  gl.enable(gl.DEPTH_TEST);gl.clearColor(0,0,0,0);let yaw=0,pitch=-.10,zoom=1,flexTime=0;
  const render=()=>{gl.viewport(0,0,canvas.width,canvas.height);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniform2f(uniforms.angle,yaw,pitch);gl.uniform1f(uniforms.aspect,canvas.width/canvas.height);gl.uniform1f(uniforms.zoom,zoom);
    // Give the three nodes a restrained shared sway; large offsets make the necks
    // look elastic instead of like one coherent soft object.
    const angle=flexTime*.55;
    const wave=phase=>Math.sin(angle+phase)-Math.sin(phase), drift=Math.sin(angle*.72);
    const lead=wave(.15),follow=wave(-.35),middle=wave(-.10);
    gl.uniform3f(uniforms.mintOffset, .85*lead,.35*drift,1.2*lead);
    gl.uniform3f(uniforms.cyanOffset,-.8*follow,.35*drift,-1.15*follow);
    gl.uniform3f(uniforms.centreOffset,.35*middle,.45*drift,.8*middle);
    gl.drawElements(gl.TRIANGLES,mesh.faces.length,gl.UNSIGNED_SHORT,0);};
  const resize=()=>{const ratio=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(host.clientWidth*ratio);canvas.height=Math.round(host.clientHeight*ratio);canvas.style.width='100%';canvas.style.height='100%';render();};
  const events=new AbortController();let drag=null;
  canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);},{signal:events.signal});
  canvas.addEventListener('pointermove',e=>{if(drag){yaw+=(e.clientX-drag.x)*.012;pitch+=(e.clientY-drag.y)*.012;drag={x:e.clientX,y:e.clientY};render();}},{signal:events.signal});
  for(const event of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(event,()=>{drag=null;},{signal:events.signal});
  resize();
  return {render,resize,setFlexTime:time=>{flexTime=time;},getView:()=>[yaw,pitch,zoom],setView:view=>{[yaw,pitch,zoom]=view;render();},rotate:(degrees,axis)=>{if(axis==='x')pitch+=degrees*Math.PI/180;else yaw+=degrees*Math.PI/180;render();},clear:()=>{events.abort();buffers.forEach(buffer=>gl.deleteBuffer(buffer));gl.deleteProgram(program);gl.deleteShader(vertex);gl.deleteShader(fragment);}};
}
// One unhurried turn every 20 seconds about Y; flexible nodes move separately.
// Differences preserve the user's orientation when pausing, dragging or resuming.
function resetMolioMomentum(){
  if(!molioLogo)return;
  molioLogo.pointer=null;molioLogo.impulse=[0,0];molioLogo.velocity=[0,0];
}
function animateMolioLogo(){
  if(!molioLogo)return;cancelAnimationFrame(molioLogo.frame);molioLogo.frame=0;
  if(!molioLogoSpinning||document.hidden||currentPage!=='welcome')return;
  const item=molioLogo;let last=0;
  const tick=time=>{
    if(molioLogo!==item||!molioLogoSpinning||document.hidden)return;
    if(!last)last=time;
    if(time-last>=16){
      const dt=Math.min(time-last,64)/1000,view=item.viewer.getView();
      item.motionTime+=dt;
      // Smooth both the hand-off from idle rotation and the mouse's impulse.
      item.idle+=(Number(!item.pointer)-item.idle)*(1-Math.exp(-dt*4));
      for(let axis=0;axis<2;axis++){
        item.velocity[axis]+=(item.impulse[axis]-item.velocity[axis])*(1-Math.exp(-dt*10));
        item.impulse[axis]*=Math.exp(-dt*2.4);
      }
      item.viewer.setFlexTime(item.motionTime);
      item.viewer.setView([view[0]+(item.idle*Math.PI/10+item.velocity[0])*dt,view[1]+item.velocity[1]*dt,view[2]]);
      last=time;
    }
    item.frame=requestAnimationFrame(tick);
  };
  item.frame=requestAnimationFrame(tick);
}
function disposeMolioLogo(){
  ++molioLogoRevision;const item=molioLogo;if(!item)return;molioLogo=null;
  cancelAnimationFrame(item.frame);item.observer.disconnect();item.viewer.clear();
  const canvas=item.host.querySelector('canvas');const gl=canvas&&(canvas.getContext('webgl')||canvas.getContext('experimental-webgl'));
  gl?.getExtension('WEBGL_lose_context')?.loseContext();canvas?.remove();delete item.host.dataset.ready;
}
async function openMolioLogo(){
  if(molioLogo){animateMolioLogo();return;}
  const revision=++molioLogoRevision,host=document.getElementById('molio-logo-view');
  try{
    if(!molioMeshPromise)molioMeshPromise=fetch('/molio-logo.json').then(r=>{if(!r.ok)throw Error('Logo unavailable');return r.json();}).catch(error=>{molioMeshPromise=null;throw error;});
    const mesh=await molioMeshPromise;if(revision!==molioLogoRevision||currentPage!=='welcome')return;
    const viewer=createMolioLogoRenderer(host,mesh);
    const item={viewer,host,frame:0,motionTime:0,pointer:null,impulse:[0,0],velocity:[0,0],idle:1,observer:new ResizeObserver(()=>{viewer.resize();})};molioLogo=item;
    item.initialView=viewer.getView();item.observer.observe(host);
    host.dataset.ready='true';
    animateMolioLogo();
  }catch(_){
    disposeMolioLogo();document.getElementById('logo-help').textContent='Molio · your molecular workspace';
  }
}
window.addEventListener('studio-page',event=>{if(event.detail.route==='welcome')openMolioLogo();else disposeMolioLogo();});
logoMotionPreference.addEventListener('change',event=>{molioLogoSpinning=!event.matches;resetMolioMomentum();animateMolioLogo();});
document.addEventListener('visibilitychange',()=>{resetMolioMomentum();animateMolioLogo();});
document.addEventListener('DOMContentLoaded',()=>{
  const host=document.getElementById('molio-logo-view');
  const pause=()=>{molioLogoSpinning=false;resetMolioMomentum();animateMolioLogo();};
  host.addEventListener('pointerenter',event=>{
    if(molioLogo&&event.pointerType==='mouse')molioLogo.pointer={x:event.clientX,y:event.clientY};
  });
  host.addEventListener('pointermove',event=>{
    const item=molioLogo;
    if(!item||event.pointerType!=='mouse'||event.buttons||!molioLogoSpinning||logoMotionPreference.matches)return;
    if(item.pointer){
      const deltas=[event.clientX-item.pointer.x,event.clientY-item.pointer.y];
      for(let axis=0;axis<2;axis++)item.impulse[axis]=Math.max(-2.8,Math.min(2.8,item.impulse[axis]+deltas[axis]*.024));
    }
    item.pointer={x:event.clientX,y:event.clientY};
  });
  // Keep velocity on exit: the sculpture coasts before returning to its idle turn.
  host.addEventListener('pointerleave',()=>{if(molioLogo)molioLogo.pointer=null;});
  host.addEventListener('pointerdown',pause);host.addEventListener('wheel',pause,{passive:true});
  host.addEventListener('keydown',event=>{
    if(event.code==='Space'){event.preventDefault();molioLogoSpinning=!molioLogoSpinning;resetMolioMomentum();animateMolioLogo();return;}
    if(event.key==='Home'&&molioLogo){event.preventDefault();resetMolioMomentum();molioLogo.motionTime=0;molioLogo.viewer.setFlexTime(0);molioLogo.viewer.setView(molioLogo.initialView);return;}
    const rotations={ArrowLeft:[-12,'y'],ArrowRight:[12,'y'],ArrowUp:[-12,'x'],ArrowDown:[12,'x']};
    if(rotations[event.key]&&molioLogo){event.preventDefault();pause();molioLogo.viewer.rotate(...rotations[event.key]);}
  });

});
