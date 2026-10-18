import {AgentHeadRig} from './agent_head_rig.js';
// Original vector interpretation of a floating agent and its connected context.
// Decorative only: the scene does not represent live execution or completed checks.
export class HeroAgentScene {
  constructor(id) {
    const previous = document.getElementById(id);
    previous.hidden = true;
    this.root = document.createElement('div');
    this.root.className = 'hero-agent-scene is-paused';
    this.root.innerHTML = `<svg viewBox="0 0 600 520" role="img" aria-labelledby="agent-scene-title agent-scene-desc">
      <title id="agent-scene-title">FAULTLINE agent connected to code and verification</title>
      <desc id="agent-scene-desc">Illustrative floating agent surrounded by Git changes, services, business rules, test scenarios, and execution evidence. This is not a live investigation.</desc>
      <defs>
        <radialGradient id="agent-halo"><stop stop-color="#72ecaa" stop-opacity=".22"/><stop offset="1" stop-color="#72ecaa" stop-opacity="0"/></radialGradient>
        <linearGradient id="agent-shell" x1="253" y1="144" x2="347" y2="224" gradientUnits="userSpaceOnUse"><stop stop-color="#d8f7e4"/><stop offset=".3" stop-color="#a7ceba"/><stop offset=".7" stop-color="#3f7c5d"/><stop offset="1" stop-color="#244b37"/></linearGradient>
        <linearGradient id="agent-body" x1="266" y1="223" x2="332" y2="297" gradientUnits="userSpaceOnUse"><stop stop-color="#a1ddba"/><stop offset=".5" stop-color="#4a8c67"/><stop offset="1" stop-color="#173c28"/></linearGradient>
        <linearGradient id="agent-tile" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#244d37"/><stop offset="1" stop-color="#112a1c"/></linearGradient>
        <radialGradient id="agent-platform"><stop stop-color="#e4fff0"/><stop offset=".6" stop-color="#99e8b9"/><stop offset="1" stop-color="#437e5a"/></radialGradient>
        <linearGradient id="agent-beam" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#8ef4b5" stop-opacity="0"/><stop offset="1" stop-color="#8ef4b5" stop-opacity=".14"/></linearGradient>
        <filter id="agent-soft-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3"/></filter>
      </defs>
      <ellipse cx="300" cy="320" rx="270" ry="170" fill="url(#agent-halo)"/>
      <path d="M230 95h140l-9 236H239Z" fill="url(#agent-beam)"/>
      <g class="agent-connections" fill="none" stroke="#70c99a" stroke-width="1.2">
        <path d="M300 272V118M175 299l-69-57M425 299l69-57M203 369l-62 53M397 369l62 53" opacity=".3"/>
        <path class="agent-data-flow" d="M300 272V118M175 299l-69-57M425 299l69-57M203 369l-62 53M397 369l62 53" stroke="#b3ffd0" stroke-dasharray="2 14" stroke-width="3"/>
      </g>
      <g fill="none" stroke="#73b68d">
        <ellipse cx="300" cy="334" rx="188" ry="83" opacity=".18"/>
        <ellipse class="agent-orbit" cx="300" cy="334" rx="166" ry="72" stroke-dasharray="2 13" stroke-width="2" opacity=".7"/>
        <ellipse cx="300" cy="334" rx="146" ry="62" opacity=".45"/>
        <ellipse class="agent-orbit agent-orbit-inner" cx="300" cy="334" rx="126" ry="52" stroke-dasharray="45 20 15 40" stroke-width="2" stroke="#b0f7cd"/>
      </g>
      <ellipse cx="300" cy="351" rx="112" ry="43" fill="#06130c"/>
      <path d="M188 334v14c0 25 50 45 112 45s112-20 112-45v-14" fill="#153322" stroke="#427153"/>
      <ellipse cx="300" cy="334" rx="112" ry="45" fill="#224b33" stroke="#95dab0" stroke-width="1.4"/>
      <ellipse cx="300" cy="332" rx="98" ry="36" fill="#73b98e" opacity=".3" filter="url(#agent-soft-glow)"/>
      <ellipse cx="300" cy="330" rx="88" ry="31" fill="url(#agent-platform)"/>
      <ellipse class="agent-shadow" cx="300" cy="325" rx="37" ry="10" fill="#173622" opacity=".35"/>
      <g class="hero-floating-agent">
        <ellipse cx="300" cy="260" rx="34" ry="44" fill="url(#agent-body)" stroke="#b1ebc333"/>
        <ellipse cx="260" cy="262" rx="13" ry="22" transform="rotate(20 260 262)" fill="url(#agent-body)"/>
        <ellipse cx="340" cy="262" rx="13" ry="22" transform="rotate(-20 340 262)" fill="url(#agent-body)"/>
        <foreignObject x="230" y="108" width="140" height="150"><canvas class="agent-head-canvas" width="420" height="450" aria-hidden="true"></canvas></foreignObject>
      </g>
      ${this.tile(239,66,122,'Git changes','DIFF',-5)}
      ${this.tile(26,195,134,'Services','CONTEXT',-9)}
      ${this.tile(440,195,134,'Business rules','INVARIANTS',9)}
      ${this.tile(52,413,153,'Test scenarios','VERIFICATION',-7)}
      ${this.tile(395,413,153,'Execution evidence','OBSERVED OUTPUT',7)}
      <text x="300" y="475" text-anchor="middle" fill="#8eb39b" font-size="9" letter-spacing="2">FAULTLINE ZERO / CONNECTED INTELLIGENCE</text>
    </svg>`;
    previous.after(this.root);
    previous.parentElement.classList.add('hero-agent-container');
    previous.parentElement.querySelector('.canvas-caption-bar').innerHTML='<span>Illustrative agent · code → context → verification</span>';
    const landing = document.getElementById('view-landing');
    new MutationObserver(() => {
      if (this.visible && landing.classList.contains('active')) this.start(); else this.stop();
    }).observe(landing, {attributes:true, attributeFilter:['class']});
    this.headRig = new AgentHeadRig(this.root, previous.closest('.landing-hero-section'));
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) this.stop();
      else if (this.visible && document.getElementById('view-landing').classList.contains('active')) this.start();
    });
    new IntersectionObserver(entries => {
      this.visible = entries[0].isIntersecting;
      if (this.visible && document.getElementById('view-landing').classList.contains('active')) this.start();
      else this.stop();
    }).observe(this.root);
  }
  tile(x,y,width,label,kicker,angle) {
    return `<g transform="translate(${x} ${y}) rotate(${angle} ${width/2} 26)"><rect y="7" width="${width}" height="57" rx="13" fill="#07180f" stroke="#193f28"/><rect width="${width}" height="57" rx="13" fill="url(#agent-tile)" stroke="#6ba88066"/><path d="M13 1h${width-26}" stroke="#b9f3ce" stroke-opacity=".22"/><text x="${width/2}" y="20" text-anchor="middle" fill="#82b798" font-size="8" letter-spacing="1.1">${kicker}</text><text x="${width/2}" y="39" text-anchor="middle" fill="#d9eee0" font-size="13" font-weight="500">${label}</text></g>`;
  }
  start() { if (document.getElementById('view-landing').classList.contains('motion-paused')) { this.stop(); return; } this.running=true; this.root.classList.remove('is-paused'); this.headRig.start(); }
  stop() { this.running=false; this.root.classList.add('is-paused'); this.headRig.stop(); }
}
