import {agentReviewControls,decideAgentEdit} from './agent-review.js';
import {workspacePath} from './workspace-files.js';
/* Independent repository tiles. File/patch navigation is delegated to one shared editor. */
const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const localTime=value=>{const date=new Date(typeof value==='number'&&value<1e12?value*1000:value);return value&&Number.isFinite(date.getTime())?date.toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'';};

function createTile(options,kind) {
  const states=new Map();let root,context,state,epoch=0,request=0,timer,searchTimer;
  const key=value=>JSON.stringify([value.projectId,kind==='agents'?value.experimentId||'':'']);
  const readonly=()=>Boolean(options.readOnly?.());
  const current=token=>root&&token===epoch;
  const query=(endpoint,params={},ctx=context)=>endpoint+'?'+new URLSearchParams({project_id:ctx.projectId,...params});
  const report=message=>{if(root){const status=root.querySelector('.code-tile-status');status.textContent=message||'';status.hidden=!message;}};
  function treeRow(entry,depth=0) {
    const directory=entry.kind==='directory',expanded=state.expanded.has(entry.path);
    return `<button type="button" class="code-tree-entry" style="--depth:${depth}" data-tile-${directory?'directory':'file'}="${escapeHTML(entry.path)}" title="${escapeHTML(workspacePath(context.repo,context.projectId,entry.path))}"${directory?` aria-expanded="${expanded}"`:''}><span class="code-entry-icon" aria-hidden="true">${directory?(expanded?'⌄':'›'):'·'}</span><span>${escapeHTML(state.search?entry.path:entry.name)}</span></button>`+
      (directory&&expanded?(state.tree.has(entry.path)?state.tree.get(entry.path).entries.map(child=>treeRow(child,depth+1)).join(''):'<p class="code-list-note">Loading…</p>'):'');
  }
  function render() {
    if(!root)return;
    const list=root.querySelector('.code-tile-list');
    if(kind==='files') {
      const data=state.search?state.searchResults:state.tree.get('');
      list.innerHTML=data?data.entries.map(entry=>treeRow(entry)).join('')+(!data.entries.length?'<p class="code-list-note">No files found.</p>':'')+(data.truncated?'<p class="code-list-note">More files exist. Refine the name search.</p>':''):'<p class="code-list-note">Loading files…</p>';
    }else {
      const data=state.data,agents=data?.agents||[];
      if(!agents.some(row=>row.scope===state.scope))state.scope=agents[0]?.scope||'';
      const agent=agents.find(row=>row.scope===state.scope);
      list.innerHTML=data?`<label class="code-agent-label">Agent<select class="code-agent-select" aria-label="Agent changes">${agents.map(row=>`<option value="${escapeHTML(row.scope)}"${row.scope===state.scope?' selected':''}>${escapeHTML(row.name)}</option>`).join('')}</select></label><details class="code-coverage"><summary>About recorded edits</summary><p>${escapeHTML(typeof data.coverage==='string'?data.coverage:'Recorded patches only; shell edits may be unattributed.')}</p></details>`+
        (agent?.changes||[]).map(change=>`<div class="code-change-row"><button type="button" data-tile-change="${escapeHTML(change.id)}" title="${escapeHTML([change.path,localTime(change.created),change.turn_id?'Turn '+change.turn_id:''].filter(Boolean).join(' · '))}"><span>${escapeHTML(change.path)}</span><small>${escapeHTML(change.kind||'recorded edit')}${change.partial||change.truncated?' · partial':''}${change.created?' · '+escapeHTML(localTime(change.created)):''}</small></button><button type="button" data-tile-review="${escapeHTML(change.id)}" aria-pressed="${Boolean(change.reviewed)}" title="${change.reviewed?'Mark unreviewed':'Mark reviewed (does not change code)'}"${readonly()||state.saving.has(change.id)?' disabled':''}>${change.reviewed?'✓':'Review'}</button>${agentReviewControls(change,state.scope,{readOnly:readonly(),busy:state.saving.has(change.id)})}</div>`).join('')+(!agent?.changes?.length?'<p class="code-list-note">No recorded changes for this agent.</p>':''):'<p class="code-list-note">Loading recorded changes…</p>';
    }
  }
  async function folder(path, saved=state, ctx=context, force=false) {
    if(saved.pending.has(path))return saved.pending.get(path);
    if(!force&&saved.tree.has(path)&&Date.now()-(saved.loaded.get(path)||0)<15000)return saved.tree.get(path);
    const job=options.api(query('code/tree',{path},ctx)).then(data=>{saved.tree.set(path,data);saved.loaded.set(path,Date.now());return data;}).finally(()=>saved.pending.delete(path));
    saved.pending.set(path,job);return job;
  }
  async function refresh() {
    if(!root)return false;
    const token=epoch,sequence=++request,saved=state,ctx=context;
    try {
      if(kind==='agents') {
        const data=await options.api(query('code/agents',ctx.experimentId?{experiment_id:ctx.experimentId}:{},ctx));
        if(!current(token)||sequence!==request)return false;
        saved.data=data;render();report('');return true;
      }
      if(saved.search) {
        const data=await options.api(query('code/tree',{query:saved.search},ctx));
        if(!current(token)||sequence!==request)return false;
        saved.searchResults=data;render();report('');return true;
      }
      const paths=['',...saved.expanded],rows=await Promise.allSettled(paths.map(path=>folder(path,saved,ctx,true)));
      if(!current(token)||sequence!==request)return false;
      const errors=[];
      paths.forEach((path,index)=>{
        const row=rows[index];
        if(row.status==='fulfilled')saved.tree.set(path,row.value);
        else if(path&&row.reason?.status===404) {
          for(const expanded of saved.expanded)if(expanded===path||expanded.startsWith(path+'/'))saved.expanded.delete(expanded);
          for(const cached of saved.tree.keys())if(cached===path||cached.startsWith(path+'/'))saved.tree.delete(cached);
        }else errors.push(`${path||'Repository'}: ${row.reason?.message||String(row.reason)}`);
      });
      render();report(errors.join('; '));return !errors.length;
    }catch(error){if(current(token)&&sequence===request)report(error.message||String(error));return false;}
  }
  async function click(event) {
    const button=event.target.closest('button');if(!button||!root?.contains(button))return;
    const token=epoch,ctx=context,saved=state;
    try {
      if(button.hasAttribute('data-tile-refresh'))return refresh();
      if(button.hasAttribute('data-tile-directory')) {
        const path=button.dataset.tileDirectory;
        if(saved.expanded.has(path)){saved.expanded.delete(path);render();return;}
        saved.expanded.add(path);render();
        try{await folder(path,saved,ctx);if(current(token)){render();report('');}}
        catch(error){if(current(token)){saved.expanded.delete(path);render();report(error.message||String(error));}}return;
      }
      if(button.hasAttribute('data-tile-file')) {
        if(!options.onOpenFile){report('Add or open a Code editor to view this file.');return;}
        await options.onOpenFile(button.dataset.tileFile);return;
      }
      if(button.hasAttribute('data-tile-change')) {
        if(!options.onOpenChange){report('Add or open a Code editor to inspect this recorded patch.');return;}
        await options.onOpenChange(saved.scope,button.dataset.tileChange);return;
      }
      if(button.dataset.agentDecision){
        if(readonly())return;const id=button.dataset.agentChange;if(saved.saving.has(id))return;saved.saving.add(id);render();
        try{await decideAgentEdit({api:options.api,action:options.action,projectId:ctx.projectId,scope:button.dataset.agentScope,changeId:id,decision:button.dataset.agentDecision,hasUnsaved:()=>options.hasUnsaved?.(ctx.projectId),isCurrent:()=>current(token)});await options.onDecision?.();if(current(token))await refresh();}
        finally{saved.saving.delete(id);if(current(token))render();}return;
      }
      if(button.hasAttribute('data-tile-review')) {
        if(readonly())return;
        const scope=saved.scope,change=saved.data?.agents.find(row=>row.scope===scope)?.changes.find(row=>row.id===button.dataset.tileReview);
        if(!change||saved.saving.has(change.id))return;
        saved.saving.add(change.id);render();
        try{await options.action('code.review',{project_id:ctx.projectId,scope,change_id:change.id,reviewed:!change.reviewed});if(current(token))await refresh();}
        finally{saved.saving.delete(change.id);if(current(token))render();}
      }
    }catch(error){if(current(token))report(error.message||String(error));}
  }
  const onInput=event=>{if(event.target.matches('.code-tile-search')){state.search=event.target.value.trim();++request;clearTimeout(searchTimer);searchTimer=setTimeout(()=>refresh(),180);}};
  const onChange=event=>{if(event.target.matches('.code-agent-select')){state.scope=event.target.value;render();}};
  async function mount(element,nextContext) {
    if(!nextContext.projectId)throw new Error('Repository tiles need a project.');
    if(root===element&&key(context)===key(nextContext)&&root.querySelector('.code-tile-list')){
      for(const button of root.querySelectorAll('[data-tile-review]'))button.disabled=readonly()||state.saving.has(button.dataset.tileReview);
      return true;
    }
    unmount();root=element;context={...nextContext};const token=++epoch;
    if(!states.has(key(context)))states.set(key(context),{tree:new Map(),loaded:new Map(),pending:new Map(),expanded:new Set(),search:'',searchResults:null,data:null,scope:'',saving:new Set()});
    state=states.get(key(context));root.classList.add('code-repository-tile');root.dataset.codeTile=kind;
    root.innerHTML=`<header class="code-tile-heading"><span>${kind==='files'?'Files':'Agent changes'}</span><button type="button" data-panel-fullscreen aria-label="Full screen" title="Full screen">⤢</button><button type="button" data-tile-refresh title="Refresh ${kind==='files'?'files':'agent changes'}" aria-label="Refresh ${kind==='files'?'files':'agent changes'}">↻</button></header>${kind==='files'?`<div class="code-find"><input class="code-tile-search" type="search" placeholder="Find file by name…" aria-label="Find file by name" value="${escapeHTML(state.search)}"></div>`:''}<div class="code-tile-list"></div><div class="code-tile-status" role="status" hidden></div>`;
    root.addEventListener('click',click);root.addEventListener('input',onInput);root.addEventListener('change',onChange);render();
    const result=await refresh();if(!current(token))return false;
    timer=setInterval(()=>{if(!document.hidden)refresh();},15000);return result;
  }
  function unmount() {
    ++epoch;++request;clearInterval(timer);clearTimeout(searchTimer);
    if(root){root.removeEventListener('click',click);root.removeEventListener('input',onInput);root.removeEventListener('change',onChange);root.replaceChildren();root.classList.remove('code-repository-tile');delete root.dataset.codeTile;}
    root=null;context=null;state=null;
  }
  return {mount,unmount,refresh,dispose(){unmount();states.clear();}};
}

export const createRepositoryExplorer=options=>createTile(options,'files');
export const createAgentChanges=options=>createTile(options,'agents');
