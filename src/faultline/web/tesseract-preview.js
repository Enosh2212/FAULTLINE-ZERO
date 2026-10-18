// GPU-transformed samples on the 32 edges of a rotating 4D hypercube.
// Geometry uploads once; only uniforms change per frame.
export function mountTesseractPreview(canvas,section,root){
 const gl=canvas.getContext('webgl',{alpha:true,antialias:false,powerPreference:'low-power',preserveDrawingBuffer:true});
 if(!gl)return false;
 const vertex=`attribute vec4 aPosition;attribute float aSeed;uniform float uTime,uAspect,uSize,uSpeed,uBreath,uDpr;varying vec3 vColor;varying float vAlpha;
 void main(){vec4 q=aPosition;float t=uTime*uSpeed;float c=cos(t),s=sin(t);q.xw=mat2(c,-s,s,c)*q.xw;c=cos(t*.67);s=sin(t*.67);q.yz=mat2(c,-s,s,c)*q.yz;q*=1.+uBreath*sin(uTime*.65);float f=3.6/max(1.2,3.6-q.w);vec3 p=q.xyz*f;c=cos(t*.25+.3);s=sin(t*.25+.3);p.xz=mat2(c,-s,s,c)*p.xz;float depth=5.5/max(1.3,5.5-p.z);vec2 screen=p.xy*depth*uSize;gl_Position=vec4(screen.x/uAspect-.08,screen.y+.03,0.,1.);gl_PointSize=clamp((1.05+depth*.25)*uDpr,1.,3.);vColor=mix(vec3(.31,.72,.49),vec3(.42,.59,.86),aSeed);vAlpha=(.12+.12*depth)*(.8+.2*sin(aSeed*40.+uTime*.4));}`;
 const fragment=`precision mediump float;varying vec3 vColor;varying float vAlpha;void main(){float r=length(gl_PointCoord-.5);float a=(1.-smoothstep(.18,.5,r))*vAlpha;gl_FragColor=vec4(vColor,a);}`;
 function compile(type,source){const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){gl.deleteShader(shader);throw Error('Preview shader could not compile');}return shader;}
 let program;
 try{program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,vertex));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Preview shader could not link');}catch{return false;}
 gl.useProgram(program);
 const count=20000,data=new Float32Array(count*5);let edge=0,index=0;
 for(let v=0;v<16;v++)for(let axis=0;axis<4;axis++){const next=v^(1<<axis);if(next<v)continue;const samples=edge===31?count-index:625;for(let j=0;j<samples;j++){const t=j/Math.max(1,samples-1);for(let a=0;a<4;a++){const from=(v&(1<<a))?1:-1,to=(next&(1<<a))?1:-1;data[index*5+a]=from+(to-from)*t;}data[index*5+4]=edge/31;index++;}edge++;}
 const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
 const position=gl.getAttribLocation(program,'aPosition'),seed=gl.getAttribLocation(program,'aSeed');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,4,gl.FLOAT,false,20,0);gl.enableVertexAttribArray(seed);gl.vertexAttribPointer(seed,1,gl.FLOAT,false,20,16);
 const uniform={time:gl.getUniformLocation(program,'uTime'),aspect:gl.getUniformLocation(program,'uAspect'),size:gl.getUniformLocation(program,'uSize'),speed:gl.getUniformLocation(program,'uSpeed'),breath:gl.getUniformLocation(program,'uBreath'),dpr:gl.getUniformLocation(program,'uDpr')};
 gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);gl.clearColor(0,0,0,0);
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');let visible=false,frame=0,previous=0,time=0,last=0,lost=false;
 const settings={speed:.26,size:.85,breath:.11};
 const panel=document.createElement('details');panel.className='tesseract-preview-controls';panel.innerHTML='<summary>Background preview</summary><p>4D tesseract · 20,000 GPU particles</p><label>Rotation speed<input data-control="speed" type="range" min="0" max="0.8" step="0.01" value="0.26"></label><label>Size<input data-control="size" type="range" min="0.35" max="1.5" step="0.01" value="0.85"></label><label>Breathing<input data-control="breath" type="range" min="0" max="0.3" step="0.01" value="0.11"></label><button type="button" aria-pressed="false">Pause background</button><a href="/#landing">Exit preview</a>';
 section.append(panel);canvas.dataset.preview='tesseract';root.classList.add('tesseract-preview');
 let paused=false;const pause=panel.querySelector('button');pause.onclick=()=>{paused=!paused;pause.textContent=paused?'Resume background':'Pause background';pause.setAttribute('aria-pressed',String(paused));sync();};
 panel.querySelectorAll('input').forEach(input=>input.addEventListener('input',()=>{settings[input.dataset.control]=Number(input.value);draw();}));
 function draw(){if(lost)return;gl.clear(gl.COLOR_BUFFER_BIT);gl.uniform1f(uniform.time,reduced.matches?0:time);gl.uniform1f(uniform.speed,settings.speed);gl.uniform1f(uniform.size,settings.size);gl.uniform1f(uniform.breath,settings.breath);gl.drawArrays(gl.POINTS,0,count);}
 function tick(now){frame=0;if(now-last>=33){time+=previous?Math.min(now-previous,80)/1000:0;previous=now;last=now;draw();}frame=requestAnimationFrame(tick);}
 function sync(){const run=visible&&root.classList.contains('active')&&!document.hidden&&!reduced.matches&&!paused&&!lost;if(run&&!frame){previous=0;frame=requestAnimationFrame(tick);}if(!run){cancelAnimationFrame(frame);frame=0;previous=0;}if(reduced.matches)draw();}
 function resize(){const rect=section.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,1.5);canvas.width=Math.round(rect.width*dpr);canvas.height=Math.round(rect.height*dpr);gl.viewport(0,0,canvas.width,canvas.height);gl.uniform1f(uniform.aspect,Math.max(.1,rect.width/Math.max(1,rect.height)));gl.uniform1f(uniform.dpr,dpr);draw();}
 canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();lost=true;sync();panel.querySelector('p').textContent='Background paused: graphics context unavailable.';});
 canvas.addEventListener('webglcontextrestored',()=>location.reload());
 new ResizeObserver(resize).observe(section);new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();}).observe(section);new MutationObserver(sync).observe(root,{attributes:true,attributeFilter:['class']});document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);resize();sync();return true;
}
