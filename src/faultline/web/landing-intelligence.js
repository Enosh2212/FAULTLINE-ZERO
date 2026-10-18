// Landing-only motion controls; no framework or external runtime required.
const root = document.getElementById('view-landing');
const toggle = document.getElementById('landing-motion-toggle');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
function sync() {
  toggle.disabled = reduced.matches;
  toggle.textContent = reduced.matches ? 'Reduced motion' : root.classList.contains('motion-paused') ? 'Resume motion' : 'Pause motion';
  toggle.setAttribute('aria-pressed', String(reduced.matches || root.classList.contains('motion-paused')));
}
toggle.addEventListener('click', () => {
  root.classList.toggle('motion-paused');
  root.dispatchEvent(new Event('landing-motion-change'));
  sync();
});
reduced.addEventListener('change', sync);
sync();

root.querySelector('.landing-skip').addEventListener('click', event => {
  event.preventDefault();
  const main = document.getElementById('landing-main');
  main.focus({preventScroll:true});
  window.scrollTo({top:0,behavior:'instant'});
});
