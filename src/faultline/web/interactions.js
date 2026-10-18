// Shared navigation surfaces move beneath the existing native buttons.
const nav = document.getElementById('view-nav');
const items = [...nav.querySelectorAll('.nav-item')];
const active = document.createElement('span');
const hover = document.createElement('span');
active.className = 'nav-selection-surface';
hover.className = 'nav-hover-surface';
for (const surface of [active, hover]) {
  surface.setAttribute('aria-hidden', 'true');
  nav.prepend(surface);
}
nav.classList.add('enhanced-nav');
let hovered = null;
let frame = 0;
function position(surface, item) {
  if (!item) { surface.style.opacity = '0'; return; }
  // Layout offsets ignore the button's cosmetic hover/press transforms.
  surface.style.transform = `translate3d(${item.offsetLeft}px,${item.offsetTop}px,0)`;
  surface.style.width = `${item.offsetWidth}px`;
  surface.style.height = `${item.offsetHeight}px`;
  surface.style.opacity = '1';
}
function update() {
  frame = 0;
  const selected = items.find(item => item.classList.contains('active'));
  items.forEach(item => {
    if (item === selected) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  });
  position(active, selected);
  position(hover, hovered);
}
function schedule() { if (!frame) frame = requestAnimationFrame(update); }
for (const item of items) {
  item.addEventListener('pointerenter', event => {
    if (event.pointerType === 'touch') return;
    hovered = item;
    schedule();
  });
  item.addEventListener('focus', () => { hovered = item; schedule(); });
  item.addEventListener('blur', () => { hovered = null; schedule(); });
}
nav.addEventListener('pointerleave', () => {
  hovered = nav.contains(document.activeElement) ? document.activeElement.closest('.nav-item') : null;
  schedule();
});
new MutationObserver(schedule).observe(nav, {subtree: true, attributes: true, attributeFilter: ['class']});
new ResizeObserver(schedule).observe(nav);
document.fonts.ready.then(schedule);
update();

// A small pointer-following highlight adds depth without moving the click target.
const buttons = document.querySelectorAll('#btn-header-cta, #landing-create-account, #view-landing .hero-primary-btn, #view-landing .hero-secondary-btn');
for (const button of buttons) {
  button.classList.add('polished-button');
  button.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch') return;
    const rect = button.getBoundingClientRect();
    button.style.setProperty('--pointer-x', `${event.clientX - rect.left}px`);
    button.style.setProperty('--pointer-y', `${event.clientY - rect.top}px`);
  });
}
