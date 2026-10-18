// Cursor-reactive dot typography; semantic headline text remains in the DOM.
const heading=document.querySelector('.hero-headline');
const root=document.getElementById('view-landing');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const precise=matchMedia('(hover:hover) and (pointer:fine)');
const source=document.createElement('span');source.className='particle-text-source';source.innerHTML=heading.innerHTML;
const canvas=document.createElement('canvas');canvas.className='particle-headline-canvas';canvas.setAttribute('aria-hidden','true');
heading.replaceChildren(source,canvas);
const ctx=canvas.getContext('2d'),sample=document.createElement('canvas'),mask=sample.getContext('2d',{willReadFrequently:true});
let dots=[],width=0,height=0,frame=0,visible=false,last=0,pointer={x:-1000,y:-1000};
function enabled(){return !reduced.matches&&root.classList.contains('active')&&!document.hidden&&visible;}
function paint(){ctx.clearRect(0,0,width,height);for(const p of dots){ctx.fillStyle=p.color;ctx.fillRect(p.x,p.y,p.size,p.size);}}
function step(now){frame=0;if(!enabled())return;const dt=Math.min(2,(now-last)/16.67||1);last=now;let energy=0;for(const p of dots){const dx=p.x-pointer.x,dy=p.y-pointer.y,d=Math.hypot(dx,dy),r=Math.min(85,width*.16);if(precise.matches&&d<r){const force=(1-d/r)*2.4*dt;p.vx+=dx/Math.max(d,1)*force;p.vy+=dy/Math.max(d,1)*force;}p.vx+=(p.tx-p.x)*.055*dt;p.vy+=(p.ty-p.y)*.055*dt;p.vx*=Math.pow(.82,dt);p.vy*=Math.pow(.82,dt);p.x+=p.vx*dt;p.y+=p.vy*dt;energy+=Math.abs(p.vx)+Math.abs(p.vy);}paint();if(energy>.18||pointer.x>-900)frame=requestAnimationFrame(step);}
function schedule(){if(enabled()&&!frame){last=performance.now();frame=requestAnimationFrame(step);}}
function resize(){const box=heading.getBoundingClientRect(),style=getComputedStyle(heading);width=box.width;height=box.height;if(!width||!height)return;const dpr=Math.min(devicePixelRatio||1,1.5);canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);sample.width=Math.ceil(width);sample.height=Math.ceil(height);mask.clearRect(0,0,width,height);const size=parseFloat(style.fontSize),line=parseFloat(style.lineHeight);mask.font=`${style.fontWeight} ${size}px ${style.fontFamily}`;mask.letterSpacing=style.letterSpacing;mask.textBaseline='alphabetic';mask.fillStyle='#fff';const lines=source.innerText.trim().split(/\n+/);lines.forEach((text,i)=>mask.fillText(text.trim(),0,size*.82+i*line));const pixels=mask.getImageData(0,0,sample.width,sample.height).data;const gap=width<420?2:2.8;dots=[];for(let y=1;y<height;y+=gap)for(let x=1;x<width;x+=gap){const alpha=pixels[(Math.floor(y)*sample.width+Math.floor(x))*4+3];if(alpha>100)dots.push({x,y,tx:x,ty:y,vx:0,vy:0,size:width<420?1.15:1.55,color:y<line?'#eff5ed':'#a1dfb3'});}paint();sync();}
function sync(){heading.classList.toggle('particle-ready',!reduced.matches&&dots.length>0);if(!enabled()){cancelAnimationFrame(frame);frame=0;pointer={x:-1000,y:-1000};if(reduced.matches){for(const p of dots){p.x=p.tx;p.y=p.ty;p.vx=p.vy=0;}paint();}}else schedule();}
heading.addEventListener('pointermove',event=>{if(!precise.matches)return;const box=heading.getBoundingClientRect();pointer={x:event.clientX-box.left,y:event.clientY-box.top};schedule();});
heading.addEventListener('pointerleave',()=>{pointer={x:-1000,y:-1000};schedule();});
new ResizeObserver(resize).observe(heading);new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();}).observe(heading);
new MutationObserver(sync).observe(root,{attributes:true,attributeFilter:['class']});document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);document.fonts.ready.then(resize);
