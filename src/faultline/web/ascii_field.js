// Shared field used by the landing hero and authentication pages.
export function mountAsciiField(canvas, section, {isActive = () => true, root = null} = {}) {
const ctx = canvas.getContext('2d', {alpha: true});
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const glyphs = ' .:-=+*#@';
let width = 0, height = 0, cells = [], frame = 0, lastTime = -Infinity;
let visible = false, elapsed = 0, previous = 0;

function draw(time) {
  ctx.clearRect(0, 0, width, height);
  ctx.font = `${width < 700 ? 11 : 12}px Consolas, monospace`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (const cell of cells) {
    const curl = Math.sin(cell.y * 5.8 - time * .22) * 1.35;
    const wave = Math.sin(cell.x * 7.2 + curl + time * .16);
    const crossing = Math.cos(cell.y * 6.3 + cell.x * 3.1 - time * .13);
    const density = Math.max(0, Math.min(1, (wave * .72 + crossing * .28 + 1) / 2));
    const index = Math.floor(Math.pow(density, 1.35) * (glyphs.length - 1));
    if (!index) continue;
    ctx.fillStyle = `rgba(119,223,165,${(.06 + density * .57).toFixed(3)})`;
    ctx.fillText(glyphs[index], cell.px, cell.py);
  }
}
function resize() {
  const rect = section.getBoundingClientRect();
  width = rect.width; height = rect.height;
  const dpr = Math.min(devicePixelRatio || 1, 1.5);
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  cells = [];
  const stepX = width < 700 ? 14 : 13;
  const stepY = 17;
  for (let y = stepY / 2; y < height; y += stepY) {
    for (let x = stepX / 2; x < width; x += stepX) {
      cells.push({px: x, py: y, x: x / Math.max(width, 1), y: y / Math.max(height, 1)});
    }
  }
  draw(reduced.matches ? 0 : elapsed / 1000);
}
function tick(now) {
  frame = 0;
  if (now - lastTime >= 40) {
    elapsed += previous ? Math.min(now - previous, 80) : 0;
    previous = now; lastTime = now;
    draw(elapsed / 1000);
  }
  frame = requestAnimationFrame(tick);
}
function sync() {
  const running = visible && isActive() && !document.hidden && !reduced.matches;
  if (running && !frame) { previous = 0; lastTime = -Infinity; frame = requestAnimationFrame(tick); }
  if (!running) { cancelAnimationFrame(frame); frame = 0; previous = 0; }
  if (reduced.matches) draw(0);
}
new ResizeObserver(resize).observe(section);
new IntersectionObserver(entries => { visible = entries[0].isIntersecting; sync(); }).observe(section);
if (root) new MutationObserver(sync).observe(root, {attributes: true, attributeFilter: ['class']});
document.addEventListener('visibilitychange', sync);
reduced.addEventListener('change', sync);
resize();

}
