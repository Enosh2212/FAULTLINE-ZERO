/** Readable graphs over the existing FalkorDB snapshot contract. No edges are synthesized. */
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const kindName = kind => ({Change:'Code change',Symbol:'Modified function',Service:'Service',Invariant:'Business rule',BusinessInvariant:'Business rule',VerifiedFinding:'Verified finding',TestCase:'Existing test',Scenario:'Generated counterexample',ScenarioSpec:'Generated counterexample',Investigation:'Investigation',Finding:'Finding',Commit:'Git revision'}[kind] || kind);
export const relationship = name => ({TOUCHES:'modifies',MODIFIES:'modifies',PART_OF:'belongs to',CALLS:'calls',DEPENDS_ON:'depends on',ENFORCES:'enforces rule',VALIDATES:'validates',INVESTIGATES:'investigates',DISCOVERED:'discovered',EXECUTED:'executed',REFUTES:'refutes',VIOLATES:'violates',CONTAINS:'contains',COMPARES:'compares',DEFINES:'defines'}[name] || name.toLowerCase().replaceAll('_',' '));
const motion = () => !matchMedia('(prefers-reduced-motion: reduce)').matches;
const palette = {Change:['#102b2b','#66b6b0'], Symbol:['#142333','#8aafd5'], Service:['#102d20','#79c69e'], Invariant:['#25213b','#b5a3d4'],BusinessInvariant:['#25213b','#b5a3d4'],VerifiedFinding:['#34221e','#d3a18f'], TestCase:['#2a2922','#c4baa0'], Scenario:['#322817','#d3ad72'], ScenarioSpec:['#322817','#d3ad72']};
export class EvidenceGraph {
  constructor(root, {explorer=false,onEvidence=()=>{}}={}) {
    this.root=root; this.explorer=explorer; this.onEvidence=onEvidence; this.snapshot={nodes:[],edges:[]}; this.visible=new Set(); this.base=new Set(); this.history=[];this.sequence=0;
    root.innerHTML=`<div class="graph-toolbar"><div><span class="graph-live-label">${explorer?'KNOWLEDGE EXPLORER':'FOCUSED EVIDENCE'}</span><p class="graph-count">Waiting for graph data</p></div><div class="graph-camera" role="group" aria-label="Graph camera controls"><button data-camera="in" title="Zoom in" aria-label="Zoom in">+</button><button data-camera="out" title="Zoom out" aria-label="Zoom out">−</button><button data-camera="fit">Fit</button><button data-camera="reset">Reset layout</button><button data-camera="path">Focus path</button><button data-camera="selected">Focus selected</button></div></div><div class="graph-scroll"><div class="graph-canvas" role="img" aria-label="Interactive directed evidence graph. A textual alternative follows."></div></div><p class="graph-hint">Select a node or relationship to inspect it. Drag to pan; use + / − to zoom. On small screens, swipe across the graph.</p><div class="graph-inspector" aria-live="polite"><p>Select an entity to understand its role in this evidence.</p></div><div class="graph-accessible"><label>Inspect an entity <select class="graph-node-select"><option value="">Choose a node</option></select></label><div class="graph-expansion"><label>Expand selected <select class="graph-expand-kind"><option value="all">All connected types</option><option value="Symbol">Functions</option><option value="Service">Services</option><option value="Invariant">Business rules</option><option value="TestCase">Tests</option><option value="Investigation">Historical investigations</option><option value="Finding">Historical findings</option><option value="Scenario">Counterexamples</option></select></label><button class="graph-expand">Expand neighbors</button><button class="graph-collapse">Collapse last expansion</button></div></div><details class="text-path"><summary>Textual evidence &amp; relationships</summary><ul class="graph-text"></ul></details><p class="graph-layout-status" role="status"></p>`;
    this.canvas=root.querySelector('.graph-canvas');
    if(typeof window.cytoscape!=='function') {root.querySelector('.graph-layout-status').textContent='Graph renderer unavailable. The textual evidence remains available.';root.querySelector('.graph-node-select').addEventListener('change',e=>{if(e.target.value)this.inspectNode(e.target.value);});return;}
    this.elk=typeof window.ELK==='function' ? new window.ELK() : null;
    this.cy=window.cytoscape({container:this.canvas,layout:{name:'preset'},minZoom:.55,maxZoom:2.2,wheelSensitivity:.15,style:[
      {selector:'node',style:{label:'data(displayLabel)',width:166,height:92,shape:'round-rectangle','background-color':'#19241e','border-color':'#6d8b7a','border-width':1.2,color:'#e4eee7','font-family':'Segoe UI, sans-serif','font-size':14,'font-weight':500,'text-valign':'center','text-halign':'center','text-wrap':'wrap','text-max-width':142,'line-height':1.5,'overlay-opacity':0,'transition-property':'border-width, border-color, background-color','transition-duration':motion()?'160ms':'0ms'}},
      ...Object.entries(palette).map(([kind,[bg,border]])=>({selector:`node[kind = "${kind}"]`,style:{'background-color':bg,'border-color':border}})),
      {selector:'node:selected',style:{'border-color':'#ecfff1','border-width':3}},
      {selector:'edge',style:{label:'data(friendlyRelation)','curve-style':'bezier','line-color':'#527462','target-arrow-color':'#6b997f','target-arrow-shape':'triangle','arrow-scale':1.1,width:1.6,'font-size':11,'font-family':'Segoe UI, sans-serif',color:'#a2b7a9','text-background-color':'#0c1310','text-background-opacity':1,'text-background-padding':4,'text-margin-y':-12,'text-rotation':'none','overlay-opacity':0}},
      {selector:'.active-path',style:{'border-width':2,'line-color':'#84c9a3','target-arrow-color':'#84c9a3'}},
      {selector:'.dimmed',style:{opacity:.23}},
      {selector:'edge:selected, edge.hovered',style:{width:3,'line-color':'#c6e8d1','target-arrow-color':'#c6e8d1',color:'#effff4'}}
    ]});
    this.cy.on('tap','node',evt=>this.inspectNode(evt.target.id()));
    this.cy.on('tap','edge',evt=>this.inspectEdge(evt.target));
    this.cy.on('mouseover','edge',evt=>evt.target.addClass('hovered'));
    this.cy.on('mouseout','edge',evt=>evt.target.removeClass('hovered'));
    this.cy.on('tap',evt=>{if(evt.target===this.cy){this.cy.elements().removeClass('dimmed');this.cy.elements().unselect();}});
    root.querySelector('.graph-node-select').addEventListener('change',e=>{if(e.target.value)this.inspectNode(e.target.value);});
    root.querySelectorAll('[data-camera]').forEach(btn=>btn.addEventListener('click',()=>this.camera(btn.dataset.camera)));
    root.querySelector('.graph-expand').addEventListener('click',()=>this.expand(root.querySelector('.graph-expand-kind').value));
    root.querySelector('.graph-collapse').addEventListener('click',()=>{if(this.history.length){this.visible=this.history.pop();this.selected=null;this.render();}});
    let width=0;new ResizeObserver(entries=>{const next=entries[0].contentRect.width;if(next>0&&Math.abs(next-width)>2){width=next;clearTimeout(this.resizeTimer);this.resizeTimer=setTimeout(()=>{this.cy.resize();this.fit();},100);}}).observe(this.canvas);
  }
  setData(snapshot, {ids=null,path=[]}={}) {
    this.snapshot=snapshot; this.path=new Set(path);this.selected=null;this.history=[];
    this.base=new Set(ids || snapshot.nodes.map(n=>n.id));this.visible=new Set(this.base);this.render();
  }
  async render() {
    const nodes=this.snapshot.nodes.filter(n=>this.visible.has(n.id));
    const edges=this.snapshot.edges.filter(e=>this.visible.has(e.source)&&this.visible.has(e.target));
    const unique=new Map();edges.forEach(e=>unique.set(`${e.source}|${e.relation}|${e.target}`,e));
    this.shownEdges=[...unique.values()];
    this.root.querySelector('.graph-count').textContent=`${nodes.length} entities · ${this.shownEdges.length} verified relationships`;
    const select=this.root.querySelector('.graph-node-select');select.innerHTML='<option value="">Choose a node</option>'+nodes.map(n=>`<option value="${esc(n.id)}">${esc(n.label)} — ${esc(kindName(n.kind))}</option>`).join('');
    this.root.querySelector('.graph-text').innerHTML=this.shownEdges.length?this.shownEdges.map((e,i)=>`<li><button data-edge="${i}">${esc(this.name(e.source))} <span>${esc(relationship(e.relation))} →</span> ${esc(this.name(e.target))}</button></li>`).join(''):nodes.map(n=>`<li>${esc(n.label)} · ${esc(kindName(n.kind))}</li>`).join('');
    this.root.querySelectorAll('[data-edge]').forEach(btn=>btn.addEventListener('click',()=>{if(this.cy)this.inspectEdge(this.cy.getElementById(`edge-${btn.dataset.edge}`));else{const edge=this.shownEdges[Number(btn.dataset.edge)];this.root.querySelector('.graph-inspector').textContent=`${this.name(edge.source)} ${relationship(edge.relation)} → ${this.name(edge.target)}. Persisted FalkorDB relationship: ${edge.relation}`;}}));
    this.root.querySelector('.graph-collapse').disabled=!this.history.length;
    if(!this.cy)return;
    this.cy.elements().remove();
    this.cy.add([...nodes.map(n=>({group:'nodes',data:{...n,displayLabel:`${this.shortLabel(n)}\n${kindName(n.kind)}`},classes:this.path.has(n.id)?'active-path':''})),...this.shownEdges.map((e,i)=>({group:'edges',data:{id:`edge-${i}`,...e,friendlyRelation:relationship(e.relation)},classes:this.path.has(e.source)&&this.path.has(e.target)?'active-path':''}))]);
    this.root.querySelector('.graph-inspector').innerHTML='<p>Select an entity or relationship to inspect its meaning and provenance.</p>';
    await this.layout();
  }
  shortLabel(n){if(n.kind!=='Symbol'&&n.label.length>54)return n.label.slice(0,51).replace(/\s+\S*$/,'')+'…';if(n.kind==='Symbol')return n.label.replaceAll('_','_\u200b');if(n.kind==='Scenario'||n.kind==='ScenarioSpec')return 'Generated verification';return n.label;}
  name(id){return this.snapshot.nodes.find(n=>n.id===id)?.label||id;}
  async layout() {
    if(!this.cy?.nodes().length)return;
    const token=++this.sequence;
    const children=this.cy.nodes().map(n=>({id:n.id(),width:166,height:92}));
    // Layout-only reversal puts validators to the right of rules. Rendered edges keep database direction.
    const edges=this.shownEdges.map((e,i)=>({id:`layout-${i}`,sources:[e.relation==='VALIDATES'?e.target:e.source],targets:[e.relation==='VALIDATES'?e.source:e.target]}));
    try {
      if(!this.elk)throw Error('ELK unavailable');
      const result=await this.elk.layout({id:'root',layoutOptions:{'elk.algorithm':'layered','elk.direction':'RIGHT','elk.edgeRouting':'ORTHOGONAL','elk.spacing.nodeNode':'46','elk.layered.spacing.nodeNodeBetweenLayers':'90','elk.layered.considerModelOrder.strategy':'NODES_AND_EDGES'},children,edges});
      if(token!==this.sequence)return;
      const positions=Object.fromEntries(result.children.map(n=>[n.id,{x:n.x+n.width/2,y:n.y+n.height/2}]));
      this.cy.layout({name:'preset',positions,fit:false,animate:false}).run();
      this.root.querySelector('.graph-layout-status').textContent='ELK layered layout · original FalkorDB edge directions preserved';
    } catch {
      if(token!==this.sequence)return;
      const order={Change:0,Symbol:1,Service:2,Invariant:3,BusinessInvariant:3,TestCase:4,Scenario:4,ScenarioSpec:4,VerifiedFinding:5};const rows={};
      this.cy.nodes().positions(n=>{const rank=order[n.data('kind')]??2;const row=rows[rank]||0;rows[rank]=row+1;return{x:rank*230,y:row*150};});
      this.root.querySelector('.graph-layout-status').textContent='Built-in horizontal layout · ELK unavailable. Investigation results remain valid.';
    }
    this.cy.resize();this.fit();
  }
  fit(collection){if(!this.cy||this.canvas.getBoundingClientRect().width===0)return;const els=collection?.length?collection:this.cy.elements();if(!els.length)return;this.cy.fit(els,34);if(this.cy.zoom()>1.12)this.cy.zoom(1.12);this.cy.center(els);this.root.dataset.zoom=this.cy.zoom().toFixed(3);}
  camera(action){if(!this.cy)return;if(action==='in'||action==='out'){this.cy.zoom(this.cy.zoom()*(action==='in'?1.2:1/1.2));return;}if(action==='reset'){this.layout();return;}if(action==='selected'){if(!this.selected){this.status('Select an entity first.');return;}const node=this.cy.getElementById(this.selected);if(motion())this.cy.animate({center:{eles:node},zoom:1.1},{duration:220});else{this.cy.zoom(1.1);this.cy.center(node);}return;}if(action==='path'){const nodes=this.cy.nodes().filter(n=>this.path.has(n.id()));this.cy.elements().removeClass('dimmed');if(nodes.length){this.cy.nodes().difference(nodes).addClass('dimmed');this.fit(nodes.union(nodes.edgesWith(nodes)));}else this.fit();return;}this.fit();}
  status(text){this.root.querySelector('.graph-layout-status').textContent=text;}
  inspectNode(id) {
    const n=this.snapshot.nodes.find(n=>n.id===id);if(!n)return;this.selected=id;
    this.cy?.elements().unselect();this.cy?.getElementById(id).select();this.root.querySelector('.graph-node-select').value=id;
    const connected=this.snapshot.edges.filter(e=>e.source===id||e.target===id);
    const meanings={Change:'A Git change indexed from the trusted repository.',Symbol:'A function or symbol indexed from source code.',Service:'A software service recorded in the knowledge graph.',Invariant:'A business rule recorded independently of the candidate code.',BusinessInvariant:'A scoped rule with explicit evidence category, source provenance and approval state.',TestCase:'An existing approved verification test.',Scenario:'A constrained verification scenario persisted by an investigation.',Investigation:'A saved investigation record.'};
    const relevance=this.path.has(id)?'This entity is referenced in the selected verification evidence.':this.base.has(id)?'This entity belongs to the current graph context.':'This entity was revealed through a persisted relationship.';
    const list=connected.slice(0,12).map(e=>`<li>${esc(this.name(e.source))} <span>${esc(relationship(e.relation))} →</span> ${esc(this.name(e.target))} <code>${esc(e.relation)}</code></li>`).join('');
    this.root.querySelector('.graph-inspector').innerHTML=`<div class="inspector-title"><div><span class="section-kicker">${esc(kindName(n.kind))}</span><h3>${esc(n.label)}</h3></div><button class="inspect-evidence">View supporting evidence →</button></div><div class="inspector-explanation"><p><strong>What is this?</strong>${esc(meanings[n.kind]||'A persisted knowledge graph entity.')}</p><p><strong>Why is it relevant?</strong>${esc(relevance)}</p></div><details><summary>Connected relationships (${connected.length})</summary><ul>${list||'<li>No connected relationships in the loaded snapshot.</li>'}</ul>${connected.length>12?'<p>First 12 relationships shown. Expand this entity to explore more.</p>':''}</details><details><summary>Technical details &amp; provenance</summary><p>Source: authenticated FalkorDB graph snapshot. Connections are recorded relationships, not a claim of causation.</p><code>${esc(n.id)}</code>${n.source?`<p>Source: ${esc(n.source.path||n.source.origin||'persisted record')}${n.source.line?':'+n.source.line:''} · revision ${esc(n.revision||n.source.revision||'unavailable')}</p>`:''}</details>`;
    this.root.querySelector('.inspect-evidence').onclick=()=>this.onEvidence(n);
  }
  inspectEdge(edge) {
    if(!edge?.length)return;const e=edge.data();this.cy.elements().unselect();edge.select();
    this.root.querySelector('.graph-inspector').innerHTML=`<span class="section-kicker">PERSISTED RELATIONSHIP</span><h3>${esc(this.name(e.source))} <span>${esc(relationship(e.relation))} →</span> ${esc(this.name(e.target))}</h3><p>This directed <code>${esc(e.relation)}</code> relationship was returned by FalkorDB. It provides connected context; execution observations establish the behavioral finding.</p><details><summary>Technical provenance</summary><code>${esc(e.source)} → [${esc(e.relation)}] → ${esc(e.target)}</code></details>`;
  }
  expand(kind='all') {
    if(!this.selected){this.status('Select an entity before expanding its neighborhood.');return;}
    const ids=new Set(this.snapshot.edges.filter(e=>e.source===this.selected||e.target===this.selected).flatMap(e=>[e.source,e.target]));
    const added=this.snapshot.nodes.filter(n=>ids.has(n.id)&&!this.visible.has(n.id)&&(kind==='all'||n.kind===kind)).sort((a,b)=>a.id.localeCompare(b.id));
    if(!added.length){this.status('No additional connected entities of this type in the loaded snapshot.');return;}
    this.history.push(new Set(this.visible));added.slice(0,12).forEach(n=>this.visible.add(n.id));this.render();this.status(`Expanded ${Math.min(12,added.length)} neighbors.${added.length>12?' First 12 shown; expand again for more.':''}`);
  }
}
