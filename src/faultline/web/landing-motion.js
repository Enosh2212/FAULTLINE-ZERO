// Native scrolling drives reversible motion. No wheel interception or animation library.
const root = document.getElementById('view-landing');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const compact = matchMedia('(max-width: 700px), (max-height: 650px)');
const stages = [...root.querySelectorAll('.stage-card')];
const fan = [...root.querySelectorAll('.problem-card')];
const foundation = root.querySelector('#section-problem');
const headings = [...root.querySelectorAll('.section-header')];
const deck = root.querySelector('.evidence-interactive-deck');
const cta = root.querySelector('.cta-inner');
const tracked = [...stages, ...fan, ...headings, deck, cta];
const clamp = value => Math.max(0, Math.min(1, value));
const smooth = value => value * value * (3 - 2 * value);
let frame = 0;
let geometry = [];

// Decorative diagrams illustrate the four stages, without inventing investigation results.
const illustrations = [
  '<path d="M42 26h215v94H42z"/><path d="M42 48h215"/><circle cx="55" cy="37" r="2"/><circle cx="64" cy="37" r="2"/><path d="M62 68h49m-49 14h114m-114 14h83"/><path class="diagram-accent" d="M156 66h66m-55 16h55m-40 16h40"/>',
  '<path d="M52 76h55m20-9 43-28m-43 46 43 27m21-73h48m-48 73h48"/><g class="diagram-nodes"><rect x="20" y="58" width="34" height="34" rx="10"/><rect x="104" y="58" width="34" height="34" rx="10"/><rect x="164" y="22" width="34" height="34" rx="10"/><rect x="164" y="95" width="34" height="34" rx="10"/><circle cx="250" cy="39" r="13"/><circle cx="250" cy="112" r="13"/></g><path class="diagram-accent" d="m30 75 6 6 11-13m78-2v17m-8-8h16"/>',
  '<rect x="38" y="20" width="224" height="110" rx="13"/><path d="M38 47h224m-185 17h102m-102 22h136m-136 22h86"/><g class="diagram-accent"><circle cx="58" cy="64" r="4"/><circle cx="58" cy="86" r="4"/><circle cx="58" cy="108" r="4"/><path d="m220 69 12 8-12 8z"/></g>',
  '<rect x="20" y="35" width="104" height="80" rx="12"/><rect x="176" y="35" width="104" height="80" rx="12"/><path d="M134 75h31m-9-8 9 8-9 8M40 55h45m-45 16h65m-65 16h52M196 55h45m-45 16h65m-65 16h52"/><path class="diagram-accent" d="M40 103h63m94 0h63"/>'
];
stages.forEach((card, index) => {
  const graphic = document.createElement('div');
  graphic.className = 'stage-illustration';
  graphic.setAttribute('aria-hidden', 'true');
  graphic.innerHTML = `<svg viewBox="0 0 300 150" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${illustrations[index]}</svg>`;
  card.querySelector('h3').before(graphic);
});

function measure() {
  if (!root.classList.contains('active')) return;
  // Measure untransformed layout anchors once per resize/view change, never per card animation.
  geometry = [...stages, ...headings, deck, cta].map(element => {
    let top = 0;
    for (let parent = element; parent; parent = parent.offsetParent) top += parent.offsetTop;
    return {element, top, height: element.offsetHeight};
  });
  schedule();
}
function set(element, property, value) { element.style.setProperty(property, value); }
function update() {
  frame = 0;
  if (!root.classList.contains('active') || reduced.matches || root.classList.contains('motion-paused')) return;
  const height = innerHeight;
  const y = scrollY;
  for (const {element, top, height: elementHeight} of geometry) {
    if (top + elementHeight < y - 200 || top > y + height + 250) continue;
    const entrance = smooth(clamp((y + height * .96 - top) / Math.min(height * .55, 400)));
    const isCard = element.classList.contains('stage-card');
    const index = isCard ? stages.indexOf(element) : 0;
    set(element, '--enter', entrance.toFixed(4));
    set(element, '--rise', `${((1 - entrance) * (isCard ? 100 : 48)).toFixed(2)}px`);
    if (isCard) {
      const side = index % 2 ? 1 : -1;
      set(element, '--slide', `${(side * (1 - entrance) * (compact.matches ? 28 : 85)).toFixed(2)}px`);
      set(element, '--rotate', `${(side * (1 - entrance) * 7).toFixed(3)}deg`);
      set(element, '--scale', (.92 + entrance * .08).toFixed(4));
    }
  }
  const rect = foundation.getBoundingClientRect();
  if (!compact.matches) {
    const travel = Math.max(1, foundation.offsetHeight - height);
    const progress = smooth(clamp((100 - rect.top) / (travel + 100)));
    fan.forEach((card, index) => {
      const side = index - 1;
      set(card, '--fan-x', `${(side * (-190 + progress * 224)).toFixed(2)}px`);
      set(card, '--fan-y', `${(side === 0 ? -12 + progress * 16 : 58 - progress * 58).toFixed(2)}px`);
      set(card, '--fan-rotate', `${(side * (18 - progress * 18)).toFixed(2)}deg`);
      set(card, '--fan-scale', (.88 + progress * .12).toFixed(4));
    });
    set(foundation, '--spread', progress.toFixed(4));
  } else {
    fan.forEach(card => {
      const r = card.getBoundingClientRect();
      const progress = smooth(clamp((height * .95 - r.top) / (height * .45)));
      set(card, '--enter', progress.toFixed(4));
    });
  }
}
function schedule() { if (!frame) frame = requestAnimationFrame(update); }
function configure() {
  root.classList.toggle('motion-enabled', !reduced.matches && !root.classList.contains('motion-paused'));
  tracked.forEach(element => {
    element.classList.remove('scroll-reveal', 'is-visible');
    if (reduced.matches) element.removeAttribute('style');
  });
  measure();
}
addEventListener('scroll', schedule, {passive: true});
addEventListener('resize', measure, {passive: true});
addEventListener('hashchange', () => requestAnimationFrame(measure));
new MutationObserver(() => requestAnimationFrame(measure)).observe(root, {attributes: true, attributeFilter: ['class']});
// Saved evidence arrives asynchronously and can move all subsequent sections.
new ResizeObserver(measure).observe(root);
reduced.addEventListener('change', configure);
root.addEventListener('landing-motion-change', configure);
compact.addEventListener('change', configure);
root.addEventListener('focusin', event => {
  const target = event.target.closest('.evidence-interactive-deck, .cta-inner');
  if (target) { set(target, '--enter', '1'); set(target, '--rise', '0px'); }
});
configure();
document.fonts.ready.then(measure);
