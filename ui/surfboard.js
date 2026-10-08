const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const copy = value => JSON.parse(JSON.stringify(value));
const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
const symbols = {brief:'◇',agent:'✦',code:'⌘',check:'✓',experiment:'◈',compute:'▦',wandb:'▥',results:'▤',visualizer:'◒',preview:'▣',approval:'◉',document:'▧',timer:'◷'};
const names = {feeds:'Data flows to',requires:'Requires',owns:'Works on',handoff:'Hands off to',triggers:'Triggers',recovers:'Recovers'};
const scopeNames = {project:'All project experiments',item:'Current experiment',selected:'Selected experiments'};
const uid = prefix => prefix+'_'+Array.from(crypto.getRandomValues(new Uint8Array(6)),n=>n.toString(16).padStart(2,'0')).join('');
const field = (label,html) => `<label class="sb-field"><span>${esc(label)}</span>${html}</label>`;
const option = (value,label,current) => `<option value="${esc(value)}" ${value===current?'selected':''}>${esc(label)}</option>`;
const input = (name,value,attributes='') => `<input data-field="${esc(name)}" value="${esc(value)}" ${attributes}>`;
const select = (name,choices,current) => `<select data-field="${esc(name)}">${choices.map(v=>option(Array.isArray(v)?v[0]:v,Array.isArray(v)?v[1]:v,current)).join('')}</select>`;

// The editor owns its DOM and each project's local draft. Background workspace
// refreshes never rebuild a focused input or replace an unsaved graph.
export function createSurfboardEditor(options) {
 const cache=new Map();let root=null,active=null,poll=null,loading=null,destroyed=false;
 function state(){return cache.get(active);}
 function isMounted(){return root?.isConnected&&!destroyed;}
 function showError(error){const s=state();if(s){s.error=error.message||String(error);renderNotice();}else if(root)root.textContent=error.message;}
 function ingest(s,data,force=false){
  const draft=data.draft, next=draft?.board||data.board;
  const changed=data.version!==s.version||(draft?.draft_version??0)!==(s.draftVersion??0);
  if(s.board&&!force&&!changed){s.catalog=data.catalog||s.catalog;s.templates=data.templates||s.templates;return;}
  if(s.board&&!force&&s.dirty&&changed){s.incoming=data;return;}
  if(s.board&&!force&&s.dirty)return;
  s.catalog=data.catalog||s.catalog||[];s.templates=data.templates||s.templates||[];
  s.live=copy(data.board);s.board=copy(next);s.version=data.version;s.draftVersion=draft?.draft_version??0;
  s.serverBoard=copy(next);s.errors=draft?.errors||[];s.compiled=data.compiled;s.summary=draft?.summary||'';
  s.dirty=false;s.incoming=null;s.error='';if(data.warning)s.warning=data.warning;
 }
 async function load({force=false}={}){
  const id=active,s=state();if(!id||loading===id&&!force)return;const request=(s.loadVersion||0)+1;s.loadVersion=request;loading=id;
  try{const data=await options.api('surfboard?project_id='+encodeURIComponent(id));if(active!==id||s.loadVersion!==request)return;const before=s.board&&JSON.stringify(s.board);ingest(s,data,force);if(isMounted()){if(!before||before!==JSON.stringify(s.board))render();else{renderNotice();updateToolbar();}}}
  catch(error){if(active===id)showError(error);}finally{if(loading===id)loading=null;}
 }
 function mark(){const s=state();s.dirty=!same(s.board,s.serverBoard);s.error='';s.errors=[];s.warning='';s.revision++;updateToolbar();renderNotice();}
 function writable(){return !options.readOnly?.()&&!state()?.busy;}
 function dirtyCount(){const s=state();if(!s?.live)return 0;return changes(s.live,s.board).length;}
 function changes(old,next){
  const out=[];if(old.name!==next.name)out.push(`Rename board to “${next.name}”`);
  if(old.workflow!==next.workflow)out.push(`Use ${next.workflow==='web'?'Web design':next.workflow} workflow`);
  for(const node of next.nodes){const prev=old.nodes.find(n=>n.id===node.id);if(!prev)out.push(`Add ${node.label}`);else if(!same({...prev,x:0,y:0},{...node,x:0,y:0}))out.push(`Update ${node.label}`);}
  for(const node of old.nodes)if(!next.nodes.some(n=>n.id===node.id))out.push(`Remove ${node.label}`);
  for(const edge of next.edges){const prev=old.edges.find(e=>e.id===edge.id);if(!prev||!same(prev,edge)){const from=next.nodes.find(n=>n.id===edge.source)?.label||edge.source,to=next.nodes.find(n=>n.id===edge.target)?.label||edge.target;out.push(`${from} → ${to}: ${names[edge.relation]||'needs clarification'}`);}}
  for(const edge of old.edges)if(!next.edges.some(e=>e.id===edge.id))out.push('Remove connection');
  if(!same(old.defaults,next.defaults))out.push('Update project defaults');
  if(!out.length&&!same(old,next))out.push('Rearrange blocks');return out;
 }
 function render(){
  if(!isMounted())return;const s=state();
  if(!s.board){root.innerHTML='<div class="loading-state"><span class="spinner"></span><p>Loading surfboard…</p></div>';return;}
  root.className='sb-editor';root.dataset.project=active;
  root.innerHTML=`<header class="sb-heading"><div><span class="sb-eyebrow">PROJECT WORKFLOW</span><h1>${esc(s.board.name)}</h1></div><button type="button" class="sb-button" data-sb="chat" title="Open the surfboard configurator">✦ Configure with AI</button></header>
   <div class="sb-toolbar"><label class="sb-starter"><span>Start from</span><select aria-label="Surfboard starter"><option value="">Choose a starter…</option>${(s.templates||[]).map(t=>option(t.workflow,t.name,'')).join('')}</select></label><div class="sb-save-state" aria-live="polite"></div><button class="sb-button" data-sb="settings" title="Board defaults">Settings</button><button class="sb-button" data-sb="undo" title="Restore the last saved draft">Undo edits</button><button class="sb-button" data-sb="save">Save draft</button><button class="sb-button sb-primary" data-sb="review">Review & apply</button><details class="sb-menu"><summary aria-label="More surfboard actions">•••</summary><div><button data-sb="export">Export board</button><button data-sb="import">Import board…</button><button data-sb="discard">Revert to active</button></div></details><input class="sb-import" type="file" accept="application/json,.json" hidden></div>
   <div class="sb-notice" role="status" hidden></div>
   <div class="sb-palette"><div class="sb-palette-heading"><strong>Blocks</strong><span>Drag or click to add</span><input type="search" placeholder="Find a block…" aria-label="Find a block"></div><div class="sb-blocks">${s.catalog.map(block=>`<button type="button" draggable="true" data-kind="${esc(block.kind)}" title="${esc(block.description)}"><span>${symbols[block.kind]||'◇'}</span>${esc(block.label)}</button>`).join('')}</div></div>
   ${s.board.workflow!=='research'&&s.board.nodes.some(n=>['check','preview'].includes(n.kind)&&!n.config?.argv?.length)?'<div class="sb-setup"><span>Connect checks and preview to this repository.</span><button type="button" class="sb-button" data-sb="setup-commands">✦ Configure commands with agent</button></div>':''}<div class="sb-workbench"><div class="sb-canvas" tabindex="0" aria-label="Surfboard graph. Drag blocks; connect their right and left handles. Drag empty space to pan."><div class="sb-world"><svg class="sb-wires" aria-label="Workflow connections"><defs><marker id="sb-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse"><path d="M0 0L8 4L0 8" fill="currentColor"/></marker></defs><g class="sb-wire-paths"></g></svg><div class="sb-nodes"></div></div><div class="sb-canvas-help">Drag blocks · Connect dots · Drag canvas to pan</div><div class="sb-zoom"><button data-sb="zoom-out" aria-label="Zoom out">−</button><span class="sb-zoom-value">100%</span><button data-sb="zoom-in" aria-label="Zoom in">+</button><button data-sb="fit">Fit</button></div></div><aside class="sb-inspector" aria-label="Block settings"></aside></div>
   <form class="sb-prompt"><span aria-hidden="true">✦</span><input aria-label="Describe a surfboard change" value="${esc(s.prompt||'')}" placeholder="Describe a change… e.g. compare every experiment in one visualizer"><button type="submit" class="sb-button" aria-label="Ask configurator">Ask ↗</button></form><div class="sb-review" hidden></div>`;
  bind();renderGraph();renderInspector();renderNotice();updateToolbar();
  if(!s.fitted){requestAnimationFrame(()=>{if(isMounted()&&state()===s){fit(true);s.fitted=true;}});}
 }
 function renderGraph(){
  const s=state(),container=root?.querySelector('.sb-nodes');if(!container)return;
  container.innerHTML=s.board.nodes.map(node=>`<article class="sb-node ${s.selected===node.id?'selected':''} ${node.kind==='wandb'?'sb-data-node':''}" data-node="${esc(node.id)}" style="left:${Number(node.x)||0}px;top:${Number(node.y)||0}px" tabindex="0" aria-label="${esc(node.label)} block"><button type="button" class="sb-port sb-input" data-port="input" aria-label="Connect to ${esc(node.label)}" title="Connect to ${esc(node.label)}"></button><div class="sb-node-body"><div class="sb-node-kind"><span>${symbols[node.kind]||'◇'}</span>${esc(s.catalog.find(c=>c.kind===node.kind)?.label||node.kind)}</div><strong>${esc(node.label)}</strong><small>${esc(nodeSubtitle(node))}</small></div><button type="button" class="sb-port sb-output ${s.connecting===node.id?'connecting':''}" data-port="output" aria-label="Connect from ${esc(node.label)}" title="Drag to another block, or click both connection dots"></button></article>`).join('');
  drawWires();transform();
 }
 function nodeSubtitle(node){const config=node.config||{};if(node.kind==='wandb')return scopeNames[config.sharing||state().board.defaults?.data_sharing||'project'];if(node.kind==='agent')return `${config.role||'worker'} · ${config.tools?.length??'Default'} tools`;if(node.kind==='approval')return `${config.requirements?.length||0} requirements`;if(['code','check','preview'].includes(node.kind))return config.argv?.join(' ')||'Agent-guided';if(node.kind==='timer')return config.event==='interval'?`Every ${config.interval_minutes||10} minutes`:config.event||'Interval';return config.description|| (node.kind==='visualizer'?'Curves, comparisons & custom views':'');}
 function point(node,end=false){return {x:(Number(node.x)||0)+(end?0:196),y:(Number(node.y)||0)+48};}
 function path(from,to){const bend=Math.max(45,Math.abs(to.x-from.x)*.42);return `M${from.x},${from.y} C${from.x+bend},${from.y} ${to.x-bend},${to.y} ${to.x},${to.y}`;}
 function drawWires(ghost=null){
  const s=state(),layer=root?.querySelector('.sb-wire-paths');if(!layer)return;
  layer.innerHTML=s.board.edges.map(edge=>{const a=s.board.nodes.find(n=>n.id===edge.source),b=s.board.nodes.find(n=>n.id===edge.target);if(!a||!b)return '';const from=point(a),to=point(b,true),d=path(from,to);return `<g class="sb-wire ${!edge.relation?'pending':''} ${s.selected===edge.id?'selected':''}" data-edge="${esc(edge.id)}"><path class="sb-wire-hit" d="${d}"/><path class="sb-wire-line" d="${d}" marker-end="url(#sb-arrow)"/><text x="${(from.x+to.x)/2}" y="${(from.y+to.y)/2-10}" text-anchor="middle">${esc(edge.relation?names[edge.relation]||edge.relation:'Clarify connection')}</text></g>`;}).join('')+(ghost?`<path class="sb-wire-line sb-ghost" d="${path(ghost.from,ghost.to)}"/>`:'');
 }
 function transform(){const s=state(),world=root?.querySelector('.sb-world');if(!world)return;world.style.transform=`translate(${s.pan.x}px,${s.pan.y}px) scale(${s.zoom})`;root.querySelector('.sb-zoom-value').textContent=Math.round(s.zoom*100)+'%';}
 function fit(initial=false){const s=state(),canvas=root?.querySelector('.sb-canvas');if(!canvas||!s.board.nodes.length)return;const xs=s.board.nodes.map(n=>n.x||0),ys=s.board.nodes.map(n=>n.y||0),left=Math.min(...xs),top=Math.min(...ys),width=Math.max(...xs)-left+196,height=Math.max(...ys)-top+98;s.zoom=Math.min(1.05,Math.max(.2,Math.min((canvas.clientWidth-72)/width,(canvas.clientHeight-90)/height)));if(initial)s.zoom=Math.max(.8,s.zoom);s.pan={x:width*s.zoom>canvas.clientWidth?24-left*s.zoom:(canvas.clientWidth-width*s.zoom)/2-left*s.zoom,y:height*s.zoom>canvas.clientHeight?24-top*s.zoom:(canvas.clientHeight-height*s.zoom)/2-top*s.zoom-8};transform();}
 function zoom(factor){const s=state(),canvas=root.querySelector('.sb-canvas'),next=Math.min(1.8,Math.max(.2,s.zoom*factor)),ratio=next/s.zoom;s.pan={x:canvas.clientWidth/2+(s.pan.x-canvas.clientWidth/2)*ratio,y:canvas.clientHeight/2+(s.pan.y-canvas.clientHeight/2)*ratio};s.zoom=next;transform();}
 function coords(event){const s=state(),rect=root.querySelector('.sb-canvas').getBoundingClientRect();return{x:(event.clientX-rect.left-s.pan.x)/s.zoom,y:(event.clientY-rect.top-s.pan.y)/s.zoom};}
 function renderInspector(){
  const s=state(),pane=root?.querySelector('.sb-inspector');if(!pane)return;const node=s.board.nodes.find(n=>n.id===s.selected),edge=s.board.edges.find(n=>n.id===s.selected);
  pane.classList.toggle('has-selection',!!(node||edge));root.querySelector('.sb-workbench').classList.toggle('sb-inspecting',!!(node||edge||s.settings));
  if(!node&&!edge){pane.innerHTML=`<div class="sb-inspector-title"><strong>Your surfboard</strong></div>${field('Board name',input('board.name',s.board.name))}<p class="sb-muted">Select a block to adjust its behavior. Connect blocks to describe how work and data flow.</p><details><summary>Project defaults</summary>${defaultsFields()}<p class="sb-muted">Individual chats can override these defaults.</p></details><div class="sb-data-legend"><span>▥</span><p><strong>Shared knowledge</strong>Research data is shared within this project by default. Select a W&B block to narrow its sources.</p></div>`;return;}
  if(edge){const a=s.board.nodes.find(n=>n.id===edge.source),b=s.board.nodes.find(n=>n.id===edge.target),source=s.catalog.find(c=>c.kind===a?.kind),relations=(source?.relations||[]).filter(r=>!r.targets||r.targets.includes(b?.kind));pane.innerHTML=`<div class="sb-inspector-title"><strong>Connection</strong><button data-sb="deselect" aria-label="Close settings">×</button></div><p class="sb-connection-name">${esc(a?.label)} <span>→</span> ${esc(b?.label)}</p>${!edge.relation?'<p class="sb-callout">The configurator will ask what this arrow should mean. It cannot run until its meaning is set.</p>':''}${field('Meaning',select('edge.relation',[['','Ask the configurator'],...relations.map(r=>[r.relation,r.label||names[r.relation]])],edge.relation||''))}${field('Details',`<textarea data-field="edge.description" rows="3" placeholder="What should happen here?">${esc(edge.description||'')}</textarea>`)}<button class="sb-button" data-sb="clarify">✦ Discuss this connection</button><button class="sb-button sb-danger" data-sb="delete">Remove connection</button>`;return;}
  const block=s.catalog.find(c=>c.kind===node.kind)||{},c=node.config||{};
  let fields=field('Label',input('node.label',node.label));
  if(node.kind==='wandb'){
   fields+=field('Experiment data',select('config.sharing',[['','Inherit project default'],...Object.entries(scopeNames)],c.sharing??''));
   if((c.sharing||s.board.defaults?.data_sharing)==='selected'){const experiments=options.experiments?.(active)||[];fields+=`<fieldset class="sb-experiment-choices"><legend>Include experiments</legend>${experiments.length?experiments.map(x=>`<label><input type="checkbox" data-experiment-choice="${esc(x.id)}" ${(c.experiment_ids||[]).includes(x.id)?'checked':''}>${esc(x.name)}</label>`).join(''):'<span class="sb-muted">Create an experiment to select it here.</span>'}</fieldset>`;}
   fields+='<p class="sb-muted">Connected visualizers receive these sources with experiment and run identities intact.</p>';
  }
  if(node.kind==='agent'){
   fields+=field('Role',select('config.role',['lead','worker'],c.role||'worker'));
   const role=c.role||'worker';fields+='<p class="sb-muted">Model and effort are shared by this project’s '+esc(role)+' agents.</p>';fields+=field('Model',input('default.model',s.board.defaults?.models?.[role]||'','placeholder="Workspace default" list="sb-model-list"'))+`<datalist id="sb-model-list">${(options.models?.()||[]).map(m=>`<option value="${esc(m.id||m.model)}">${esc(m.displayName||m.id)}</option>`).join('')}</datalist>`;
   fields+=field('Effort',select('default.reasoning',[['','Workspace default'],'low','medium','high','xhigh','max','ultra'],s.board.defaults?.reasoning?.[role]||''));
   fields+=field('Instructions',`<textarea data-field="config.instructions" rows="4" placeholder="What should this agent own?">${esc(c.instructions||'')}</textarea>`);
  }
  if(['check','preview'].includes(node.kind)&&!c.argv?.length)fields+='<button class="sb-button sb-setup-command" data-sb="setup-command">✦ Set up with agent</button>';
  if(['code','check','preview'].includes(node.kind)){fields+=`<fieldset class="sb-argv"><legend>Command <small>one argument per row</small></legend>${(c.argv||[]).map((arg,i)=>`<div><input aria-label="Command argument ${i+1}" data-arg="${i}" value="${esc(arg)}"><button data-remove-arg="${i}" aria-label="Remove argument ${i+1}">×</button></div>`).join('')}<button class="sb-button" data-sb="add-argument">+ Argument</button></fieldset>`;}
  const special=new Set(['sharing','experiment_ids','role','instructions','argv','description']);
  for(const [key,spec] of Object.entries(block.config_fields||{})){
   if(special.has(key)||['model','reasoning'].includes(key))continue;const value=c[key]??spec.default;
   if(spec.enum&&spec.type!=='array')fields+=field(spec.label||human(key),select('config.'+key,spec.enum,value??spec.enum[0]));
   else if(spec.type==='boolean')fields+=`<label class="sb-check"><input type="checkbox" data-field="config.${esc(key)}" ${value?'checked':''}>${esc(spec.label||human(key))}</label>`;
   else if(spec.type==='array'){
    const choices=spec.by_role?.[c.role||'worker']||spec.items?.enum||spec.enum||spec.choices;
    if(choices?.length)fields+=`<details><summary>${esc(spec.label||human(key))} <small>${Array.isArray(value)?value.length:'Default'}</small></summary>${key==='tools'?`<label class="sb-check"><input type="checkbox" data-inherit-tools ${c.tools===undefined?'checked':''}>Use connected capabilities</label><p class="sb-muted">Uncheck to restrict this role to selected tools.</p>`:''}<div class="sb-tool-choices">${choices.map(v=>`<label><input type="checkbox" data-array="${esc(key)}" value="${esc(v)}" ${key==='tools'&&c.tools===undefined?'disabled':''} ${(value||[]).includes(v)?'checked':''}>${esc(human(v))}</label>`).join('')}</div></details>`;
    else if(value?.length)fields+=`<details><summary>${esc(spec.label||human(key))}</summary><ul class="sb-skill-list">${value.map(v=>`<li>${esc(v)}</li>`).join('')}</ul><button class="sb-button" data-sb="edit-with-ai">Edit with configurator</button></details>`;
   }else fields+=field(spec.label||human(key),input('config.'+key,value??'',spec.type==='number'||spec.type==='integer'?`type="number" ${spec.minimum!==undefined?'min="'+spec.minimum+'"':''}`:''));
  }
  if(node.kind!=='agent')fields+=field('Guidance',`<textarea data-field="config.description" rows="2" placeholder="Optional instructions for this block">${esc(c.description||'')}</textarea>`);
  const skills=block.skills||block.default_skills||[];
  if(skills.length)fields+=`<details class="sb-skills"><summary>Included skills · ${skills.length}</summary><ul>${skills.map(skill=>`<li>${esc(typeof skill==='string'?skill:skill.name)}</li>`).join('')}</ul></details>`;
  pane.innerHTML=`<div class="sb-inspector-title"><strong>${symbols[node.kind]||'◇'} ${esc(block.label||node.kind)}</strong><button data-sb="deselect" aria-label="Close settings">×</button></div><p class="sb-muted">${esc(block.description||'')}</p>${fields}<div class="sb-inspector-actions"><button class="sb-button" data-sb="duplicate">Duplicate</button><button class="sb-button sb-danger" data-sb="delete">Remove block</button></div>`;
 }
 function human(value){return String(value).replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());}
 function defaultsFields(){const d=state().board.defaults||{};return field('Permission default',select('defaults.approval_mode',[['','Workspace default'],['ask','Ask for approval'],['auto_review','Approve for me'],['yolo','YOLO']],d.approval_mode||''))+field('Experiment data sharing',select('defaults.data_sharing',[['project','Share within project'],['item','Current experiment only']],d.data_sharing||'project'));}
 function updateToolbar(){if(!isMounted()||!state()?.board)return;const s=state(),count=dirtyCount();root.querySelector('.sb-save-state').textContent=s.busy?'Saving…':s.dirty?'Unsaved changes':s.draftVersion?'Draft saved':`Active · v${s.version}`;for(const button of root.querySelectorAll('[data-sb="save"],[data-sb="review"],[data-sb="undo"],[data-sb="discard"]'))button.disabled=!writable()||(button.dataset.sb==='undo'&&!s.dirty)||(button.dataset.sb==='review'&&!count)||(button.dataset.sb==='save'&&!s.dirty);root.classList.toggle('sb-busy',!!s.busy);root.querySelector('.sb-starter select').disabled=!writable();root.querySelector('.sb-prompt button').disabled=!writable();for(const input of root.querySelectorAll('.sb-inspector input:not([data-array]),.sb-inspector select,.sb-inspector textarea'))input.disabled=!writable();}
 function renderNotice(){const el=root?.querySelector('.sb-notice'),s=state();if(!el)return;const pending=s.board?.edges.filter(edge=>!edge.relation).length||0;el.hidden=!(s.error||s.incoming||pending||s.errors?.length||s.warning);el.classList.toggle('error',!!s.error);el.innerHTML=s.error?`${esc(s.error)}${s.incoming?' <button data-sb="use-incoming">Load newer draft</button>':''}`:s.incoming?`A newer draft is available. Your edits are preserved. <button data-sb="use-incoming">Load newer draft</button>`:pending?`${pending} connection${pending===1?' needs':'s need'} clarification. Open the configurator to answer its questions.`:(s.errors||[]).map(error=>esc(typeof error==='string'?error:error.message||JSON.stringify(error))).join('<br>')||esc(s.warning||'');}
 async function mutate(op,extra={}){
  const s=state(),id=active;if(!writable())return null;s.loadVersion=(s.loadVersion||0)+1;s.busy=true;s.error='';updateToolbar();renderNotice();
  try{const response=await options.action(op,{project_id:id,expected_version:s.version,expected_draft_version:s.draftVersion,...extra});if(active===id){if(response?.board)ingest(s,response,true);else await load({force:true});render();}return response;}
  catch(error){if(active===id){showError(new Error(error.message+(error.status===409?' Your edits are preserved. Export them or load the newer draft to resolve this conflict.':'')));if(error.status===409){try{s.incoming=await options.api('surfboard?project_id='+encodeURIComponent(id));renderNotice();}catch{}}}return null;}
  finally{s.busy=false;if(active===id)updateToolbar();}
 }
 async function save(){const s=state();if(!s.dirty)return true;return !!await mutate('surfboard.draft',{board:copy(s.board)});}
 async function ask(text,pendingEdge=null){const s=state();if(!text.trim()||!writable())return;const response=await mutate('surfboard.ask',{text:text.trim(),board:copy(s.board),...(pendingEdge?{pending_edge:pendingEdge}:{})});if(response){options.onChat?.(response.scope||'surfboard:'+active);if(response.accepted===false){showError(new Error(response.error||'Draft saved, but the configurator could not start.'));return;}if(s.prompt===text.trim()){s.prompt='';root.querySelector('.sb-prompt input').value='';}}}
 function clarify(edge){const s=state(),a=s.board.nodes.find(n=>n.id===edge.source),b=s.board.nodes.find(n=>n.id===edge.target);return ask(`I drew an arrow from “${a?.label}” (${a?.kind}) to “${b?.label}” (${b?.kind}). Ask me one short question about what this connection should do, then propose its meaning in the surfboard draft. Keep the active board unchanged.`,copy(edge));}
 function add(kind,pos=null){if(!writable())return;const s=state(),block=s.catalog.find(b=>b.kind===kind);if(!block)return;const config={};for(const [key,spec] of Object.entries(block.config_fields||{}))if(spec.default!==undefined)config[key]=copy(spec.default);if(kind==='wandb'){config.experiment_ids=[];}const canvas=root.querySelector('.sb-canvas');const preferred=pos||{x:(canvas.clientWidth/2-s.pan.x)/s.zoom-98,y:(canvas.clientHeight/2-s.pan.y)/s.zoom-48};const center=freePosition(preferred);const node={id:uid(kind),kind,label:block.label,x:Math.max(-3000,Math.min(10000,Math.round(center.x))),y:Math.max(-3000,Math.min(10000,Math.round(center.y))),config};s.board.nodes.push(node);s.selected=node.id;const r=root.querySelector('.sb-canvas');if(node.x*s.zoom+s.pan.x<15||node.x*s.zoom+s.pan.x+196*s.zoom>r.clientWidth-15)s.pan.x=r.clientWidth/2-(node.x+98)*s.zoom;if(node.y*s.zoom+s.pan.y<15||node.y*s.zoom+s.pan.y+98*s.zoom>r.clientHeight-55)s.pan.y=r.clientHeight/2-(node.y+49)*s.zoom;mark();renderGraph();renderInspector();}
 function freePosition(preferred){const s=state(),collides=p=>s.board.nodes.some(n=>p.x<n.x+218&&p.x+218>n.x&&p.y<n.y+120&&p.y+120>n.y);if(!collides(preferred))return preferred;for(let ring=1;ring<8;ring++){for(let row=-ring;row<=ring;row++)for(let col=-ring;col<=ring;col++){if(Math.abs(row)!==ring&&Math.abs(col)!==ring)continue;const p={x:preferred.x+col*232,y:preferred.y+row*132};if(p.x>=0&&p.y>=0&&!collides(p))return p;}}return{x:preferred.x,y:Math.max(0,...s.board.nodes.map(n=>n.y))+140};}
 async function connect(source,target){const s=state();s.connecting=null;if(!writable()||source===target)return renderGraph();if(s.board.edges.some(e=>e.source===source&&e.target===target)){s.error='These blocks are already connected. Select their arrow to change its meaning.';renderNotice();return renderGraph();}const edge={id:uid('edge'),source,target,relation:null,description:''};s.board.edges.push(edge);s.selected=edge.id;mark();renderGraph();renderInspector();await clarify(edge);}
 function choose(id){state().selected=id;renderGraph();renderInspector();}
 function review(){const s=state(),panel=root.querySelector('.sb-review'),diff=changes(s.live,s.board),pending=s.board.edges.some(e=>!e.relation);panel.hidden=false;panel.innerHTML=`<section role="dialog" aria-modal="true" aria-label="Review surfboard changes"><div class="sb-inspector-title"><strong>Review changes</strong><button data-sb="close-review" aria-label="Close review">×</button></div><p>Only this project changes. Existing jobs keep their recorded execution contracts.</p><ul>${diff.map(line=>`<li>${esc(line)}</li>`).join('')}</ul>${pending?'<p class="sb-callout">Clarify pending connections before applying.</p>':''}<div class="sb-review-actions"><button class="sb-button" data-sb="close-review">Keep editing</button><button class="sb-button sb-primary" data-sb="apply" ${pending?'disabled':''}>Apply to project</button></div></section>`;panel.querySelector('[data-sb="close-review"]').focus();}
 async function handle(name){const s=state();
  if(name==='chat')return options.onChat?.('surfboard:'+active);
  if(name==='setup-commands'||name==='setup-command'){const node=name==='setup-command'?s.board.nodes.find(n=>n.id===s.selected):null;return ask(`Set up ${node?'the “'+node.label+'” '+node.kind+' block':'the check and preview blocks'} for this project. Inspect the repository manifests, package scripts, and existing instructions using read-only commands. Propose the appropriate argument arrays, timeout, and preview port in this surfboard draft. Reuse the repository’s actual tooling; ask me a short question only where the choice is ambiguous. Do not install dependencies, run checks, start a server, or apply the board yet.`);}
  if(name==='fit')return fit();if(name==='zoom-in')return zoom(1.18);if(name==='zoom-out')return zoom(1/1.18);
  if(name==='review')return review();if(name==='close-review'){root.querySelector('.sb-review').hidden=true;return;}
  if(name==='export'){const blob=new Blob([JSON.stringify(s.board,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=s.board.name.replace(/[^a-z0-9-]+/gi,'-')+'.surfboard.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;}
  if(!writable())return;
  if(name==='save')return save();
  if(name==='apply'){if(await save()){const result=await mutate('surfboard.apply');if(result)options.onApplied?.();}return;}
  if(name==='undo'){s.board=copy(s.serverBoard);s.dirty=false;s.error='';render();return;}
  if(name==='discard'){if(!confirm('Revert this draft to the active surfboard?'))return;return mutate('surfboard.discard');}
  if(name==='use-incoming'){if(s.dirty&&!confirm('Replace your local edits with the newer saved draft? Export first if you want to keep both.'))return;ingest(s,s.incoming,true);render();return;}
  if(name==='import'){root.querySelector('.sb-import').click();return;}
  if(name==='settings'){s.settings=!s.settings;s.selected=null;renderInspector();return;}
  if(name==='deselect'){s.settings=false;choose(null);return;}
  const node=s.board.nodes.find(n=>n.id===s.selected),edge=s.board.edges.find(e=>e.id===s.selected);
  if(name==='clarify'&&edge)return clarify(edge);
  if(name==='edit-with-ai'&&node){root.querySelector('.sb-prompt input').value=`Change the ${node.label} block: `;root.querySelector('.sb-prompt input').focus();return;}
  if(name==='delete'){s.board.nodes=s.board.nodes.filter(n=>n.id!==s.selected);s.board.edges=s.board.edges.filter(e=>e.id!==s.selected&&e.source!==s.selected&&e.target!==s.selected);s.selected=null;mark();renderGraph();renderInspector();}
  if(name==='duplicate'&&node){const duplicate={...copy(node),id:uid(node.kind),label:node.label+' copy',x:node.x+32,y:node.y+126};s.board.nodes.push(duplicate);s.selected=duplicate.id;mark();renderGraph();renderInspector();}
  if(name==='add-argument'&&node){node.config.argv??=[];node.config.argv.push('');mark();renderInspector();const inputs=root.querySelectorAll('[data-arg]');inputs[inputs.length-1]?.focus();}
 }
 function change(event){if(!writable())return;const el=event.target,s=state(),node=s.board.nodes.find(n=>n.id===s.selected),edge=s.board.edges.find(n=>n.id===s.selected),key=el.dataset.field;let rebuild=false;
  if(key){const [group,name]=key.split('.'),value=el.type==='checkbox'?el.checked:el.type==='number'&&el.value!==''?Number(el.value):el.value;
   if(group==='board')s.board[name]=value;
   if(group==='node'&&node)node[name]=value;
   if(group==='config'&&node){if((el.type==='number'||name==='sharing')&&el.value==='')delete node.config[name];else node.config[name]=value;if(name==='sharing'&&value!=='selected')node.config.experiment_ids=[];rebuild=['sharing','role'].includes(name);}
   if(group==='edge'&&edge)edge[name]=value||null;
   if(group==='defaults'){s.board.defaults??={};if(value==='')delete s.board.defaults[name];else s.board.defaults[name]=value;}
   if(group==='default'&&node){const prop=name==='model'?'models':'reasoning';s.board.defaults??={};s.board.defaults[prop]??={};const role=node.config.role||'worker';if(value==='')delete s.board.defaults[prop][role];else s.board.defaults[prop][role]=value;}
  }else if(el.dataset.arg!==undefined&&node)node.config.argv[Number(el.dataset.arg)]=el.value;
  else if(el.dataset.experimentChoice&&node){node.config.experiment_ids=[...root.querySelectorAll('[data-experiment-choice]:checked')].map(x=>x.dataset.experimentChoice);}
  else if(el.hasAttribute('data-inherit-tools')&&node){if(el.checked)delete node.config.tools;else node.config.tools=[];rebuild=true;}
  else if(el.dataset.array&&node){node.config[el.dataset.array]=[...root.querySelectorAll('[data-array]')].filter(x=>x.dataset.array===el.dataset.array&&x.checked).map(x=>x.value);}
  else return;mark();renderGraph();if(rebuild)renderInspector();if(key==='board.name')root.querySelector('h1').textContent=s.board.name;
 }
 function bind(){
  root.onclick=async event=>{const button=event.target.closest('[data-sb]');if(button){event.preventDefault();try{await handle(button.dataset.sb);}catch(error){showError(error);}return;}const kind=event.target.closest('[data-kind]');if(kind){add(kind.dataset.kind);return;}const port=event.target.closest('[data-port]');if(port){const node=port.closest('[data-node]').dataset.node;if(port.dataset.port==='output'){state().connecting=node;renderGraph();}else if(state().connecting)await connect(state().connecting,node);return;}const edge=event.target.closest('[data-edge]');if(edge){choose(edge.dataset.edge);return;}const node=event.target.closest('[data-node]');if(node){choose(node.dataset.node);return;}const remove=event.target.closest('[data-remove-arg]');if(remove&&writable()){const n=state().board.nodes.find(n=>n.id===state().selected);n.config.argv.splice(Number(remove.dataset.removeArg),1);mark();renderInspector();}};
  root.oninput=event=>{if(event.target.matches('.sb-prompt input')){state().prompt=event.target.value;return;}if(event.target.matches('.sb-palette input')){const query=event.target.value.toLowerCase();for(const block of root.querySelectorAll('[data-kind]'))block.hidden=!block.textContent.toLowerCase().includes(query);return;}change(event);};
  root.onchange=async event=>{
   const s=state();if(event.target.matches('.sb-starter select')){const value=event.target.value,template=s.templates.find(t=>t.workflow===value);if(!template)return;if(dirtyCount()&&!confirm('Replace the current draft with this starter? The active board will stay unchanged.')){event.target.value='';return;}s.board=copy(template);s.selected=null;s.fitted=false;mark();render();}
   else if(event.target.matches('.sb-import')){try{const file=event.target.files[0];if(!file)return;if(file.size>500000)throw new Error('This board is too large (maximum 500 KB).');const board=JSON.parse(await file.text());const result=await mutate('surfboard.draft',{board});if(result){s.fitted=false;fit();}}catch(error){showError(error);}event.target.value='';}
  };
  root.querySelector('.sb-prompt').onsubmit=event=>{event.preventDefault();ask(root.querySelector('.sb-prompt input').value).catch(showError);};
  root.ondragstart=event=>{const block=event.target.closest('[data-kind]');if(block&&writable()){event.dataTransfer.setData('application/x-surfboard-block',block.dataset.kind);event.dataTransfer.effectAllowed='copy';}};
  const canvas=root.querySelector('.sb-canvas');canvas.ondragover=event=>{if(event.dataTransfer.types.includes('application/x-surfboard-block')){event.preventDefault();event.dataTransfer.dropEffect='copy';}};canvas.ondrop=event=>{event.preventDefault();add(event.dataTransfer.getData('application/x-surfboard-block'),coords(event));};
  canvas.onwheel=event=>{if(event.ctrlKey||event.metaKey){event.preventDefault();zoom(event.deltaY>0?1/1.1:1.1);}};
  canvas.onkeydown=event=>{if(event.target.matches('input,textarea,select'))return;if(event.key==='Escape'){state().connecting=null;choose(null);}if((event.key==='Delete'||event.key==='Backspace')&&state().selected){event.preventDefault();handle('delete');}if(event.target.matches('[data-node]')&&event.key==='Enter'){choose(event.target.dataset.node);root.querySelector('.sb-inspector input')?.focus();}};
  canvas.onpointerdown=event=>{
   if(event.button!==0||event.target.closest('.sb-zoom')||event.target.closest('[data-edge]'))return;const s=state(),port=event.target.closest('[data-port]'),el=event.target.closest('[data-node]'),node=el&&s.board.nodes.find(n=>n.id===el.dataset.node);
   if((node||port)&&!writable())return;if(port?.dataset.port==='input')return;
   const start=coords(event),client={x:event.clientX,y:event.clientY},origin=node?{x:node.x,y:node.y}:{...s.pan};let moved=false;
   const move=e=>{const dx=e.clientX-client.x,dy=e.clientY-client.y;if(Math.abs(dx)+Math.abs(dy)>4)moved=true;if(port){drawWires({from:point(node),to:coords(e)});return;}if(node){node.x=Math.round(origin.x+dx/s.zoom);node.y=Math.round(origin.y+dy/s.zoom);s.dirty=true;el.style.left=node.x+'px';el.style.top=node.y+'px';drawWires();}else{s.pan={x:origin.x+dx,y:origin.y+dy};transform();}};
   const end=e=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',cancel);if(!isMounted()||state()!==s)return;if(port&&moved){const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-node]');if(target)connect(node.id,target.dataset.node).catch(showError);else drawWires();}else if(node&&moved){mark();}else if(!node&&!moved){choose(null);}if(moved){const suppress=click=>{click.preventDefault();click.stopPropagation();};canvas.addEventListener('click',suppress,{capture:true,once:true});setTimeout(()=>canvas.removeEventListener('click',suppress,true),0);}};
   const cancel=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',cancel);if(node){node.x=origin.x;node.y=origin.y;renderGraph();}};
   window.addEventListener('pointermove',move);window.addEventListener('pointerup',end);window.addEventListener('pointercancel',cancel);
  };
 }
 return {
  mount(element,projectId){destroyed=false;if(root===element&&active===projectId&&root.querySelector('.sb-canvas'))return;root=element;active=projectId;if(!cache.has(projectId))cache.set(projectId,{board:null,live:null,version:0,draftVersion:0,dirty:false,revision:0,selected:null,pan:{x:40,y:40},zoom:1});render();load();clearInterval(poll);poll=setInterval(()=>{if(isMounted()&&!state()?.busy)load();},3000);},
  unmount(){clearInterval(poll);poll=null;root=null;active=null;destroyed=true;},
  refresh(){return load();},
  dirty(){return !!state()?.dirty;},
 };
}
