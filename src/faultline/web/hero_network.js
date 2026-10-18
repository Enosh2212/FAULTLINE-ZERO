export class HeroNetworkCanvas {
  constructor(id) {
    this.canvas = document.getElementById(id);
    this.ctx = this.canvas?.getContext('2d');
    this.running = false;
    this.reduced = matchMedia('(prefers-reduced-motion: reduce)');
    this.resize = () => {
      const rect = this.canvas.getBoundingClientRect();
      const dpr = devicePixelRatio || 1;
      this.width = rect.width; this.height = rect.height;
      this.canvas.width = rect.width * dpr; this.canvas.height = rect.height * dpr;
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0); this.draw(0);
    };
    new ResizeObserver(this.resize).observe(this.canvas);
    new IntersectionObserver(es => es[0].isIntersecting ? this.start() : this.stop()).observe(this.canvas);
    this.canvas.setAttribute('aria-label', 'Illustration: Git change to code symbol, service, business invariant and verification');
    this.canvas.setAttribute('role', 'img');
    this.resize();
  }
  draw(time) {
    const ctx = this.ctx, w = this.width, h = this.height;
    ctx.clearRect(0, 0, w, h);
    const labels = ['Git change', 'Code symbol', 'Service', 'Invariant', 'Verification'];
    const descriptions = ['Webhook retry', 'handle_webhook()', 'Payments', 'One event. One capture.', 'Compare revisions'];
    const points = labels.map((_, i) => ({ x: w * (.15 + (i % 2) * .65), y: h * (.12 + i * .17) }));
    ctx.lineWidth = 1;
    for(let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i];
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.strokeStyle = '#2a5140'; ctx.stroke();
      const t = this.reduced.matches ? .5 : (time / 2600 + i * .2) % 1;
      ctx.beginPath(); ctx.arc(a.x + (b.x-a.x)*t, a.y + (b.y-a.y)*t, 2, 0, Math.PI*2); ctx.fillStyle = '#77dfac'; ctx.fill();
    }
    points.forEach((p,i) => {
      ctx.beginPath(); ctx.arc(p.x,p.y,7,0,Math.PI*2);ctx.fillStyle='#0c2116';ctx.fill();ctx.strokeStyle='#77dfac';ctx.stroke();
      const right=i%2===0, x=p.x+(right?18:-18);
      ctx.textAlign=right?'left':'right';ctx.fillStyle='#dfebe2';ctx.font='500 13px Segoe UI';ctx.fillText(labels[i],x,p.y-4);
      ctx.font='10px Segoe UI';ctx.fillStyle='#859b8d';ctx.fillText(descriptions[i],x,p.y+14);
    });
  }
  start() {
    if(this.running) return;
    this.running=true;
    const loop=t=>{if(!this.running)return;this.draw(t);if(!this.reduced.matches)this.frame=requestAnimationFrame(loop);};
    this.frame=requestAnimationFrame(loop);
  }
  stop() {this.running=false;cancelAnimationFrame(this.frame);}
}
