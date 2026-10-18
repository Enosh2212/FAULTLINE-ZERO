// A slowly turning tubular sculpture, drawn locally without a video or 3D library.
const canvas=document.getElementById('auth-sculpture'),context=canvas.getContext('2d',{alpha:true});
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let width=0,height=0,frame=0,last=0,time=0,visible=true;
function point(u,v,t){
 const wave=u*7.4+t*.22;
 const cx=width*(.38+u*.88),cy=height*(.49+.13*Math.sin(wave));
 const dx=width*.88,dy=height*.13*7.4*Math.cos(wave),length=Math.hypot(dx,dy);
 const cap=u<.12?Math.sqrt(Math.max(0,1-Math.pow((u-.12)/.12,2))):1;
 const radius=Math.min(width,height)*(.14+.035*Math.sin(u*6-t*.16))*cap;
 const angle=v*Math.PI/2,side=Math.sin(angle),depth=Math.cos(angle);
 return{x:cx-dy/length*radius*side,y:cy+dx/length*radius*side,light:Math.max(.19,Math.min(.95,.2+depth*.6-side*.23+Math.sin(wave)*.05))};
}
function draw(t){context.clearRect(0,0,width,height);const rows=120,cols=48;for(let i=rows-1;i>=0;i--)for(let j=0;j<cols;j++){const a=point(i/rows,j/cols*2-1,t),b=point((i+1)/rows,j/cols*2-1,t),c=point((i+1)/rows,(j+1)/cols*2-1,t),d=point(i/rows,(j+1)/cols*2-1,t);const shade=(a.light+b.light+c.light+d.light)/4;const r=Math.round(177*shade),g=Math.round(187*shade),blue=Math.round(179*shade);context.fillStyle=context.strokeStyle=`rgb(${r},${g},${blue})`;context.lineWidth=.55;context.beginPath();context.moveTo(a.x,a.y);context.lineTo(b.x,b.y);context.lineTo(c.x,c.y);context.lineTo(d.x,d.y);context.closePath();context.fill();context.stroke();}}
function tick(now){frame=0;if(now-last>50){time+=.05;last=now;draw(time);}frame=requestAnimationFrame(tick);}
function sync(){const run=visible&&!document.hidden&&!reduced.matches;if(run&&!frame)frame=requestAnimationFrame(tick);if(!run){cancelAnimationFrame(frame);frame=0;}if(reduced.matches)draw(0);}
function resize(){width=innerWidth;height=innerHeight;const dpr=Math.min(devicePixelRatio||1,1.25);canvas.width=width*dpr;canvas.height=height*dpr;context.setTransform(dpr,0,0,dpr,0,0);draw(time);sync();}
addEventListener('resize',resize,{passive:true});document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();}).observe(canvas);resize();
