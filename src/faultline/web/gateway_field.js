// Lightweight particle gateway inspired by the supplied motion reference.
export function mountGatewayField(canvas, section, {root, isActive=()=>true}={}) {
  const context=canvas.getContext('2d',{alpha:true});
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let width=0,height=0,visible=false,frame=0,last=0,time=0,previous=0;
  function draw(t) {
    context.clearRect(0,0,width,height);
    const rows=width<700?24:34, columns=width<700?52:78;
    const centerX=width*.69,centerY=height*.48;
    for(let row=0;row<rows;row++) {
      const lane=(row/(rows-1)-.5)*2;
      for(let col=0;col<columns;col++) {
        const progress=(col/columns+t*.025)%1;
        const x=(progress-.5)*2;
        const spread=.025+.48*Math.pow(Math.abs(x),1.55);
        const px=centerX+x*width*.8;
        const py=centerY+lane*height*spread+Math.sin(x*3+t*.32+lane)*height*.006;
        if(px<0||px>width||py<0||py>height)continue;
        const glint=Math.pow(Math.max(0,Math.sin(col*.83+row*1.37-t*1.4)),18);
        const alpha=.16+(1-Math.abs(lane))*.14+glint*.5;
        context.fillStyle=`rgba(218,188,101,${alpha})`;
        const size=glint>.7?1.9:1.15;
        context.fillRect(px,py,size,size);
      }
    }
  }
  function tick(now){
    frame=0;
    if(now-last>=42){time+=previous?Math.min(now-previous,85)/1000:0;previous=now;last=now;draw(time);}
    frame=requestAnimationFrame(tick);
  }
  function sync(){
    const running=visible&&isActive()&&!document.hidden&&!reduced.matches;
    if(running&&!frame){previous=0;frame=requestAnimationFrame(tick);}
    if(!running){cancelAnimationFrame(frame);frame=0;previous=0;}
    if(reduced.matches)draw(0);
  }
  function resize(){
    const rect=section.getBoundingClientRect();width=rect.width;height=rect.height;
    const dpr=Math.min(devicePixelRatio||1,1.5);
    canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
    context.setTransform(dpr,0,0,dpr,0,0);draw(reduced.matches?0:time);sync();
  }
  new ResizeObserver(resize).observe(section);
  new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();}).observe(section);
  if(root)new MutationObserver(sync).observe(root,{attributes:true,attributeFilter:['class']});
  document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);resize();
}
