/* Project source editor. Models outlive their mounted pane; no file is saved implicitly. */
let monacoPromise;
let nextEditorId = 0;
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const basename = path => path.split('/').pop();
const same = (a, b) => a === b;
const recordedTime = value => {
  if(!value)return '';
  const date=new Date(typeof value==='number'&&value<1e12?value*1000:value);
  return Number.isFinite(date.getTime())?date.toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'';
};

export function createCodeEditor(options) {
  const instance = ++nextEditorId, projects = new Map();
  let root, context, state, monaco, editor, editorFile, diffEditor, diffModels = [], observer, poll, epoch = 0, navigation = 0;
  let view = 'file', sidebar = 'files', selected = '', message = '', refreshError = false, searching = 0, busy = false;
  const readonly = () => Boolean(options.readOnly?.());
  const active = () => state?.files.get(selected);
  const dirty = file => Boolean(file?.model && file.model.getValue() !== file.base);
  const hasUnsaved = () => [...projects.values()].some(project => [...project.files.values()].some(dirty));
  const query = (path, extra = {}, projectId = context.projectId) => path + '?' + new URLSearchParams({project_id:projectId, ...extra});
  const button = (action, label, title = label, disabled = false) => `<button type="button" data-code="${action}" title="${escapeHTML(title)}"${disabled?' disabled':''}>${escapeHTML(label)}</button>`;
  const call = (op, params, projectId = context.projectId) => options.action(op, {project_id:projectId, ...params});
  const tell = error => {refreshError=false;message = error?.message || String(error); renderStatus();};
  const current = token => root && token === epoch;
  const fileURI = (projectId,path,suffix='') => monaco.Uri.parse(`supersurfer://${instance}/${encodeURIComponent(projectId)}/${path.split('/').map(encodeURIComponent).join('/')}${suffix}`);

  function theme() {
    if (!monaco || !root) return;
    const css = getComputedStyle(root), color = (name,fallback) => {
      const raw = css.getPropertyValue(name).trim();
      if (!raw) return fallback;
      const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d');
      ctx.fillStyle = fallback; ctx.fillStyle = raw; return ctx.fillStyle;
    };
    const background = color('--bg','#ffffff'), foreground = color('--text','#202124');
    const dark = String(options.theme?.() || document.documentElement.dataset.theme || '').includes('dark') ||
      /^#[0-9a-f]{6}$/i.test(background) && (parseInt(background.slice(1,3),16)*.2126+parseInt(background.slice(3,5),16)*.7152+parseInt(background.slice(5,7),16)*.0722 < 128);
    monaco.editor.defineTheme('supersurfer-code-'+instance,{base:dark?'vs-dark':'vs',inherit:true,rules:[],colors:{
      'editor.background':background,'editor.foreground':foreground,'editorLineNumber.foreground':color('--muted','#858585'),
      'editorGutter.background':background,'editorWidget.background':background,
      'editor.selectionBackground':dark?'#42678e88':'#9bc8ff88','editor.inactiveSelectionBackground':dark?'#42678e44':'#9bc8ff44',
    }});
    monaco.editor.setTheme('supersurfer-code-'+instance);
  }

  function rememberView() {
    if (editor && editorFile) editorFile.viewState = editor.saveViewState();
  }
  function disposeView() {
    rememberView(); editor?.dispose(); editor = null; editorFile = null; diffEditor?.dispose(); diffEditor = null;
    for (const model of diffModels) model.dispose(); diffModels = [];
  }
  function renderStatus() {
    if (!root) return;
    const file = active(), status = root.querySelector('.code-status');
    const details = [file?.path || 'Choose a file', dirty(file)?'Unsaved changes':'', readonly()?'Read-only workspace':''].filter(Boolean).join(' · ');
    status.textContent = message || details;
    status.classList.toggle('error', Boolean(message));
    root.querySelector('[data-code="save"]').disabled = readonly() || !file?.model || file.readOnly || !dirty(file) || Boolean(file.remote) || file.saving;
    root.querySelector('[data-code="ask"]').disabled = !file || !options.onAskAgent;
    for (const action of ['new-file','new-folder']) root.querySelector(`[data-code="${action}"]`).disabled = readonly();
    for(const control of root.querySelectorAll('[data-code-review]'))control.disabled=readonly();
    for (const tab of root.querySelectorAll('[data-code-tab]')) {
      const item = state.files.get(tab.dataset.codeTab);
      tab.querySelector('.code-dirty').textContent = dirty(item)?'●':'';
      tab.classList.toggle('dirty', dirty(item));
    }
    const conflict = root.querySelector('.code-conflict');
    conflict.hidden = !file?.remote;
    if (file?.remote) conflict.querySelector('span').textContent = file.remote.exists === false ? 'This file was removed on disk. Your edits are preserved.' : 'This file changed on disk. Your edits are preserved.';
  }
  function renderTabs() {
    if (!root) return;
    root.querySelector('.code-tabs').innerHTML = [...state.files.values()].map(file =>
      `<div class="code-tab${selected===file.path?' selected':''}" data-code-tab="${escapeHTML(file.path)}"><button type="button" data-code-open="${escapeHTML(file.path)}" title="${escapeHTML(file.path)}" aria-pressed="${selected===file.path}"><span>${escapeHTML(basename(file.path))}</span><span class="code-dirty" aria-label="Unsaved changes"></span></button><button type="button" class="code-close" data-code-close="${escapeHTML(file.path)}" aria-label="Close ${escapeHTML(file.path)}">×</button></div>`).join('');
    renderStatus();
    root.querySelector('.code-tab.selected')?.scrollIntoView({block:'nearest',inline:'nearest'});
  }
  function entryHTML(entry, depth = 0) {
    const directory = entry.kind === 'directory', expanded = state.expanded.has(entry.path);
    return `<button type="button" class="code-tree-entry${entry.path===selected?' selected':''}" style="--depth:${depth}" data-code-${directory?'dir':'open'}="${escapeHTML(entry.path)}" title="${escapeHTML(entry.path)}"${directory?` aria-expanded="${expanded}"`:''}><span class="code-entry-icon" aria-hidden="true">${directory?(expanded?'⌄':'›'):'·'}</span><span>${escapeHTML(entry.name || entry.path)}</span></button>` +
      (directory && expanded ? (state.tree.get(entry.path)?.entries || []).map(child=>entryHTML(child,depth+1)).join('') : '');
  }
  function renderTree() {
    if (!root) return;
    const list = root.querySelector('.code-file-list'), filtered = state.search.trim();
    if (sidebar === 'changes') {
      const data = state.changes;
      list.innerHTML = data ? `<p class="code-list-note">${escapeHTML(data.branch || 'Git changes')} · ${data.files.length}</p>` + data.files.map(file=>
        `<div class="code-change-row"><button type="button" data-code-diff="${escapeHTML(file.path)}" title="Compare HEAD to working file"><span>${escapeHTML(file.path)}</span><small>${escapeHTML(file.status)}</small></button>${file.staged?`<button type="button" data-code-staged="${escapeHTML(file.path)}" title="Compare HEAD to staged file">Index</button>`:''}</div>`).join('') + (!data.files.length?'<p class="code-list-note">No Git changes.</p>':'') + (data.truncated?'<p class="code-list-note">Change list is truncated.</p>':'') : '<p class="code-list-note">Loading changes…</p>';
    } else if (sidebar === 'agents') {
      const data=state.agentChanges, agents=data?.agents || [];
      if(!agents.some(agent=>agent.scope===state.agentScope))state.agentScope=agents[0]?.scope || '';
      const agent=agents.find(row=>row.scope===state.agentScope);
      list.innerHTML=data?`<label class="code-agent-label">Recorded changes by agent<select class="code-agent-select" aria-label="Agent changes">${agents.map(row=>`<option value="${escapeHTML(row.scope)}"${row.scope===state.agentScope?' selected':''}>${escapeHTML(row.name)}</option>`).join('')}</select></label><p class="code-list-note">${escapeHTML(typeof data.coverage==='string'?data.coverage:'Recorded file edits only. Shell changes may be unattributed.')}</p>`+
        (agent?.changes || []).map(change=>`<div class="code-change-row"><button type="button" data-code-agent-diff="${escapeHTML(change.id)}" title="${escapeHTML([change.path,recordedTime(change.created),change.turn_id?'Turn '+change.turn_id:''].filter(Boolean).join(' · '))}"><span>${escapeHTML(change.path)}</span><small>${escapeHTML(change.kind || 'recorded edit')}${change.truncated?' · partial':''}${change.created?' · '+escapeHTML(recordedTime(change.created)):''}</small></button><button type="button" data-code-review="${escapeHTML(change.id)}" aria-pressed="${Boolean(change.reviewed)}" title="${change.reviewed?'Mark unreviewed':'Mark reviewed (does not modify code)'}"${readonly()?' disabled':''}>${change.reviewed?'✓':'Review'}</button></div>`).join('')+
        (!agent?.changes?.length?'<p class="code-list-note">No recorded file edits for this agent.</p>':''):'<p class="code-list-note">Loading agent changes…</p>';
    } else {
      const data = filtered ? state.searchResults : state.tree.get('');
      list.innerHTML = data ? data.entries.map(entry=>entryHTML(entry)).join('') + (!data.entries.length?'<p class="code-list-note">No files found.</p>':'') + (data.truncated?'<p class="code-list-note">More matches exist. Refine the file name.</p>':'') : '<p class="code-list-note">Loading files…</p>';
    }
    root.querySelector('[data-code="files"]').setAttribute('aria-pressed',sidebar==='files');
    root.querySelector('[data-code="changes"]').setAttribute('aria-pressed',sidebar==='changes');
    root.querySelector('[data-code="agents"]').setAttribute('aria-pressed',sidebar==='agents');
    root.querySelector('.code-find').hidden = sidebar !== 'files';
  }

  function modelFor(file, projectId) {
    file.model = monaco.editor.createModel(file.content ?? '', file.language || undefined, fileURI(projectId,file.path));
    file.listener = file.model.onDidChangeContent(() => {if (state?.projectId === projectId) renderStatus();});
    file.base = file.content ?? '';
    return file;
  }
  async function loadFile(path) {
    const projectId = context.projectId, project = state;
    if (project.files.get(path)?.model) return project.files.get(path);
    const record = await options.api(query('code/file',{path},projectId));
    if (project.files.get(path)?.model) return project.files.get(path);
    const file = {path, ...record, readOnly:Boolean(record.read_only), base:record.content ?? '', saving:false};
    if (record.content !== null && !record.binary && !record.too_large) modelFor(file, projectId);
    project.files.set(path,file);
    return file;
  }
  async function openFile(path) {
    const token = epoch, nav=++navigation;
    try {
      const file = await loadFile(path);
      if (!current(token) || nav!==navigation) return;
      rememberView(); selected = file.path; state.selected = selected; view = 'file'; message = '';
      renderTabs(); showEditor();
    } catch(error) {if(current(token)) tell(error);}
  }
  function editorOptions() {
    return {automaticLayout:true,fontSize:13,lineHeight:21,minimap:{enabled:false},scrollBeyondLastLine:false,
      padding:{top:10,bottom:10},smoothScrolling:true,renderLineHighlight:'gutter',wordWrap:'off',
      folding:true,stickyScroll:{enabled:true},tabSize:2,readOnly:readonly(),ariaLabel:'Source code editor',
      fixedOverflowWidgets:true,contextmenu:true};
  }
  function showEditor() {
    if (!root || !monaco) return;
    disposeView();
    const host = root.querySelector('.code-monaco'), file = active(); host.replaceChildren();
    root.querySelector('.code-diff-heading').hidden = true;
    if (!file?.model) {
      host.innerHTML = `<div class="code-empty">${escapeHTML(file?.binary?'This binary file cannot be edited as text.':file?.too_large?'This file is too large for the source editor.':'Open a file to start editing.')}</div>`;
      renderStatus(); return;
    }
    editor = monaco.editor.create(host,{...editorOptions(),model:file.model,readOnly:readonly()||file.readOnly});
    editorFile=file;
    if (file.viewState) editor.restoreViewState(file.viewState);
    editor.addAction({id:'supersurfer-save',label:'Save file',keybindings:[monaco.KeyMod.CtrlCmd|monaco.KeyCode.KeyS],run:()=>save()});
    editor.addAction({id:'supersurfer-ask',label:'Ask SuperSurfer agent about selection',contextMenuGroupId:'navigation',run:()=>askAgent()});
    renderStatus(); theme();
  }
  async function showDiff(path, staged = false, conflict = false) {
    const token = epoch, projectId = context.projectId, project=state, nav=++navigation;
    try {
      let data;
      if (conflict) {
        const file = active();
        if (!file?.remote || !file.model) return;
        data = {original:file.remote.content || '',modified:file.model.getValue(),language:file.language};
      } else data = await options.api(query('code/diff',{path,staged:staged?'1':'0'},projectId));
      if (!current(token) || nav!==navigation) return;
      if (!state.files.has(path)) {
        try {await loadFile(path);} catch(error) {
          if (data.status !== 'deleted') throw error;
          project.files.set(path,{path,content:null,base:'',readOnly:true,deleted:true});
        }
      }
      if (!current(token) || nav!==navigation) return;
      rememberView(); selected = path; state.selected = path; view = conflict?'conflict':staged?'staged':'diff';
      disposeView(); renderTabs();
      const host = root.querySelector('.code-monaco'); host.replaceChildren();
      const heading = root.querySelector('.code-diff-heading'); heading.hidden = false;
      heading.querySelector('span').textContent = conflict?'Disk ↔ Your unsaved changes':staged?'HEAD ↔ Index (staged)':'HEAD ↔ Working file (including staged changes)';
      if(data.binary || data.too_large) {host.innerHTML='<div class="code-empty">This diff cannot be displayed as text.</div>';return;}
      diffModels = [monaco.editor.createModel(data.original ?? '',data.language),monaco.editor.createModel(data.modified ?? '',data.language)];
      diffEditor = monaco.editor.createDiffEditor(host,{...editorOptions(),readOnly:true,originalEditable:false,
        renderGutterMenu:false,renderMarginRevertIcon:false,
        renderSideBySide:state.sideBySide,renderSideBySideInlineBreakpoint:600,enableSplitViewResizing:true});
      diffEditor.setModel({original:diffModels[0],modified:diffModels[1]}); theme(); renderStatus();
    } catch(error) {if(current(token)) tell(error);}
  }

  async function showAgentDiff(changeId) {
    const token=epoch,nav=++navigation,scope=state.agentScope,project=state;
    try {
      const data=await options.api(query('code/agent-diff',{scope,change_id:changeId}));
      if(!current(token)||nav!==navigation)return;
      if(!project.files.has(data.path)) {
        try {await loadFile(data.path);} catch(error) {
          if(error.status!==404)throw error;
          project.files.set(data.path,{path:data.path,content:null,readOnly:true,deleted:true});
        }
      }
      if(!current(token)||nav!==navigation)return;
      rememberView();selected=data.path;project.selected=selected;view='agent';disposeView();renderTabs();
      const heading=root.querySelector('.code-diff-heading'),host=root.querySelector('.code-monaco');
      heading.hidden=false;heading.querySelector('span').textContent=`Recorded agent edit · ${data.partial||data.truncated?'partial patch':typeof data.original==='string'?'before ↔ after':'patch'} · ${project.agentChanges.agents.find(row=>row.scope===scope)?.name || scope}`;
      host.replaceChildren();
      if(typeof data.original==='string'&&typeof data.modified==='string') {
        diffModels=[monaco.editor.createModel(data.original,data.language),monaco.editor.createModel(data.modified,data.language)];
        diffEditor=monaco.editor.createDiffEditor(host,{...editorOptions(),readOnly:true,originalEditable:false,renderGutterMenu:false,renderMarginRevertIcon:false,renderSideBySide:project.sideBySide,renderSideBySideInlineBreakpoint:600});
        diffEditor.setModel({original:diffModels[0],modified:diffModels[1]});
      } else if(data.diff) {
        diffModels=[monaco.editor.createModel(data.diff,'diff')];
        editor=monaco.editor.create(host,{...editorOptions(),readOnly:true,model:diffModels[0],ariaLabel:'Recorded agent patch'});
        heading.querySelector('span').textContent+=' · recorded patch only';
      } else host.innerHTML='<div class="code-empty">This agent edit has no available patch. Current Git changes are listed separately.</div>';
      theme();renderStatus();
    }catch(error){if(current(token))tell(error);}
  }

  async function checkDisk(file, project = state) {
    if (!file.model || file.saving) return;
    const read= file.diskRead = (file.diskRead || 0) + 1;
    let remote;
    try {remote = await options.api(query('code/file',{path:file.path},project.projectId));}
    catch(error) {
      if (error.status !== 404 && !/not found|does not exist|no such file/i.test(error.message || '')) throw error;
      remote = {exists:false,content:'',revision:null};
    }
    if(file.model.isDisposed() || project.files.get(file.path)!==file || file.saving || file.diskRead!==read)return;
    if (same(remote.revision,file.revision)) {file.remote = null; return;}
    if (dirty(file)) file.remote = remote;
    else if(remote.content !== null && !remote.binary && !remote.too_large) {
      file.model.setValue(remote.content ?? ''); file.base = remote.content ?? ''; file.revision=remote.revision; file.exists=remote.exists; file.remote=null;
    } else file.remote = remote;
  }
  async function save() {
    const file = active(), project = state;
    if (!file?.model || readonly() || file.readOnly || file.remote || file.saving || !dirty(file)) return;
    const content = file.model.getValue(); file.saving = true;file.diskRead=(file.diskRead||0)+1; message=''; renderStatus();
    try {
      const saved = await call('code.save',{path:file.path,content,revision:file.revision},project.projectId);
      file.base = content; file.revision = saved.revision; file.exists = true; file.remote=null;
      if (state===project) {message=''; await refreshTree();}
    } catch(error) {
      if (error.status === 409 || /changed|revision|conflict|already exists/i.test(error.message || '')) {
        file.saving = false;
        // Even a newly created buffer must compare against a file created concurrently.
        const wasNew = file.exists===false; file.exists=true;
        try {await checkDisk(file,project);} catch(_) {file.exists=!wasNew;}
      }
      if(state===project) tell(error);
    } finally {file.saving=false; if(state===project) renderStatus();}
  }
  async function resolveConflict(keepMine) {
    const file = active(); if(!file?.remote || !file.model) return;
    if(file.remote.binary || file.remote.too_large) {tell('The disk file is no longer editable text. Preserve your edits elsewhere before closing this tab.');return;}
    const prompt = keepMine?'Keep your version as the next edit? Saving afterward will replace the disk version you just reviewed.':'Discard your unsaved edits and reload the disk version?';
    if(!window.confirm(prompt)) return;
    if(!keepMine) file.model.setValue(file.remote.content ?? '');
    file.base=file.remote.content ?? '';file.revision=file.remote.revision;file.exists=file.remote.exists;file.remote=null;message='';view='file';showEditor();renderTabs();
  }
  function askAgent() {
    const file = active(); if(!file || !options.onAskAgent) return;
    const selection = editorFile===file ? editor?.getSelection() : null;
    let text = `Please help with ${file.path}`;
    if(selection && !selection.isEmpty()) {
      const content = file.model.getValueInRange(selection), bounded = content.slice(0,16000);
      text += `, lines ${selection.startLineNumber}–${selection.endLineNumber}.\n\n${bounded}${content.length>bounded.length?'\n[Selection truncated]':''}`;
    } else text += '.';
    if(dirty(file)) text += '\n\nThis file has unsaved editor changes. The disk version may differ; do not assume these edits have been saved.';
    options.onAskAgent(text);
  }
  function closeFile(path) {
    const file = state.files.get(path);
    if(file?.saving) {tell('Wait for this save to finish before closing the file.');return;}
    if(dirty(file) && !window.confirm(`Discard unsaved changes to ${path}?`)) return;
    ++navigation;
    if(path===selected) disposeView();
    file.listener?.dispose();file.model?.dispose();state.files.delete(path);
    if(path===selected) {selected=[...state.files.keys()].at(-1)||'';state.selected=selected;view='file';showEditor();}
    renderTabs();
  }
  async function refreshTree() {
    const project = state, token = epoch;
    const paths = ['',...project.expanded];
    const rows = await Promise.allSettled(paths.map(path=>options.api(query('code/tree',{path},project.projectId))));
    const errors=[];
    for(let index=0;index<paths.length;index++) {
      const path=paths[index],row=rows[index];
      if(row.status==='fulfilled')project.tree.set(path,row.value);
      else if(path && row.reason?.status===404) {
        for(const expanded of project.expanded)if(expanded===path || expanded.startsWith(path+'/'))project.expanded.delete(expanded);
        for(const cached of project.tree.keys())if(cached===path || cached.startsWith(path+'/'))project.tree.delete(cached);
      } else errors.push(`${path || 'Repository'}: ${row.reason?.message || String(row.reason)}`);
    }
    if(current(token)) renderTree();
    if(errors.length)throw new Error(errors.join('; '));
  }
  async function changes() {
    const token=epoch,project=state;
    try {project.changes=await options.api(query('code/changes',{},project.projectId));if(current(token)) renderTree();}
    catch(error) {if(current(token)) tell(error);}
  }
  async function agentChanges() {
    const token=epoch,project=state,params=context.experimentId?{experiment_id:context.experimentId}:{};
    try{project.agentChanges=await options.api(query('code/agents',params,project.projectId));if(current(token))renderTree();}
    catch(error){if(current(token))tell(error);}
  }
  async function findFiles() {
    const token=++searching, mounted=epoch,project=state;
    const value=root.querySelector('.code-find input').value;project.search=value;
    if(!value.trim()){renderTree();return;}
    try {const data=await options.api(query('code/tree',{query:value.trim()},project.projectId));
      if(token===searching && current(mounted)){project.searchResults=data;renderTree();}}
    catch(error){if(token===searching && current(mounted))tell(error);}
  }
  async function refresh() {
    if(!root || busy)return;busy=true;const token=epoch,project=state;
    try {const results=await Promise.allSettled([refreshTree(),...[...project.files.values()].map(file=>checkDisk(file,project))]);
      if(current(token)){if(sidebar==='changes')await changes();if(sidebar==='agents')await agentChanges();if(state.search)await findFiles();
        if(!current(token))return;
        const failure=results.find(result=>result.status==='rejected');
        if(failure){message=failure.reason?.message || String(failure.reason);refreshError=true;}
        else if(refreshError){message='';refreshError=false;}
        theme();editor?.updateOptions({readOnly:view!=='file'||readonly()||active()?.readOnly});renderStatus();}}
    catch(error){if(current(token))tell(error);}finally{busy=false;}
  }
  function showCreate(kind) {
    if(readonly())return;
    const form=root.querySelector('.code-create');form.hidden=false;form.dataset.kind=kind;
    form.querySelector('label').textContent=kind==='directory'?'New folder path':'New file path';
    const input=form.querySelector('input');input.value='';input.placeholder=kind==='directory'?'src/components':'src/example.py';input.focus();
  }
  async function create(event) {
    event.preventDefault(); if(readonly())return;
    const form=root.querySelector('.code-create'),path=form.querySelector('input').value.trim(),kind=form.dataset.kind;
    const project=state,projectId=context.projectId,token=epoch;
    if(!path || path.startsWith('/') || path.split('/').some(part=>!part || part==='.' || part==='..') || /[\0\r\n\\]/.test(path)){tell('Use a relative project path without . or .. segments.');return;}
    try {
      if(kind==='directory'){await call('code.mkdir',{path},projectId);if(current(token))await refreshTree();}
      else {
        if(project.files.has(path)){if(current(token))await openFile(path);form.hidden=true;return;}
        try {await options.api(query('code/file',{path},projectId));if(current(token))tell('A file already exists at that path. Open it from the file tree.');return;}
        catch(error){if(error.status!==404 && !/not found|does not exist|no such file/i.test(error.message||''))throw error;}
        if(project.files.has(path))return;
        const file=modelFor({path,content:'',revision:null,exists:false,readOnly:false},projectId);
        // A new empty file is a real unsaved change too.
        file.base=null;project.files.set(path,file);project.selected=path;
        if(current(token)){rememberView();selected=path;view='file';renderTabs();showEditor();}
      }
      form.hidden=true;if(current(token)){message='';renderStatus();}
    } catch(error){if(current(token))tell(error);}
  }
  async function click(event) {
    const target=event.target.closest('button');if(!target || !root.contains(target))return;
    if(target.hasAttribute('data-code-open'))return openFile(target.dataset.codeOpen);
    if(target.hasAttribute('data-code-close'))return closeFile(target.dataset.codeClose);
    if(target.hasAttribute('data-code-diff'))return showDiff(target.dataset.codeDiff);
    if(target.hasAttribute('data-code-staged'))return showDiff(target.dataset.codeStaged,true);
    if(target.hasAttribute('data-code-agent-diff'))return showAgentDiff(target.dataset.codeAgentDiff);
    if(target.hasAttribute('data-code-review')) {
      if(readonly())return;
      const scope=state.agentScope,change=state.agentChanges?.agents.find(row=>row.scope===scope)?.changes.find(row=>row.id===target.dataset.codeReview);
      if(!change)return;
      try{await call('code.review',{scope,change_id:change.id,reviewed:!change.reviewed});if(root)await agentChanges();}catch(error){tell(error);}return;
    }
    if(target.hasAttribute('data-code-dir')) {
      const path=target.dataset.codeDir;
      if(state.expanded.has(path))state.expanded.delete(path);
      else {state.expanded.add(path);try {const token=epoch,data=await options.api(query('code/tree',{path}));if(!current(token))return;state.tree.set(path,data);}catch(error){tell(error);}}
      renderTree();return;
    }
    switch(target.dataset.code) {
      case 'files':sidebar='files';renderTree();break;
      case 'changes':sidebar='changes';renderTree();await changes();break;
      case 'agents':sidebar='agents';renderTree();await agentChanges();break;
      case 'refresh':await refresh();break;
      case 'save':await save();break;
      case 'ask':askAgent();break;
      case 'new-file':showCreate('file');break;
      case 'new-folder':showCreate('directory');break;
      case 'cancel-create':root.querySelector('.code-create').hidden=true;break;
      case 'compare':await showDiff(selected,false,true);break;
      case 'reload':await resolveConflict(false);break;
      case 'keep-mine':await resolveConflict(true);break;
      case 'edit':view='file';showEditor();break;
      case 'split':state.sideBySide=!state.sideBySide;diffEditor?.updateOptions({renderSideBySide:state.sideBySide});target.textContent=state.sideBySide?'Inline':'Side by side';break;
    }
  }
  const onFocus=()=>{if(root)refresh();};
  const onChange=event=>{if(event.target.matches('.code-agent-select')){state.agentScope=event.target.value;renderTree();}};
  const beforeUnload=event=>{if(hasUnsaved()){event.preventDefault();event.returnValue='';}};
  window.addEventListener('beforeunload',beforeUnload);
  window.addEventListener('focus',onFocus);

  async function mount(element, nextContext) {
    if(root===element && root.querySelector('.code-monaco') &&
      ['projectId','experimentId','nodeId'].every(key=>context?.[key]===nextContext[key])) {
      theme();editor?.updateOptions({readOnly:view!=='file'||readonly()||active()?.readOnly});renderStatus();return;
    }
    unmount();root=element;context={...nextContext};const token=++epoch;
    if(!context.projectId)throw new Error('Source editor needs a project.');
    if(!projects.has(context.projectId))projects.set(context.projectId,{projectId:context.projectId,files:new Map(),tree:new Map(),expanded:new Set(),selected:'',search:'',searchResults:null,changes:null,sideBySide:true});
    state=projects.get(context.projectId);selected=state.selected;sidebar='files';view='file';message='';
    root.classList.add('code-editor');
    root.innerHTML=`<div class="code-toolbar"><div>${button('files','Files')}${button('changes','Git','Repository Git changes')}${button('agents','Agents','Recorded edits by agent')}</div><div>${button('new-file','+ File','Create a file',readonly())}${button('new-folder','+ Folder','Create a folder',readonly())}${button('refresh','↻','Refresh source and Git changes')}</div><div class="code-toolbar-end">${button('ask','Ask agent','Add selected code or file reference to the agent composer')}${button('save','Save','Save file (⌘/Ctrl S)',true)}</div></div>
      <form class="code-create" hidden><label for="code-new-${instance}">New file path</label><input id="code-new-${instance}" required autocomplete="off"><button type="submit">Create</button>${button('cancel-create','Cancel')}</form>
      <div class="code-body"><aside class="code-sidebar"><div class="code-find"><input type="search" placeholder="Find file by name…" aria-label="Find file by name" value="${escapeHTML(state.search)}"></div><div class="code-file-list"></div></aside><section class="code-workbench"><div class="code-tabs" aria-label="Open files"></div><div class="code-conflict" hidden><span></span><div>${button('compare','Compare')}${button('reload','Reload disk')}${button('keep-mine','Keep mine…')}</div></div><div class="code-diff-heading" hidden><span></span>${button('split',state.sideBySide?'Inline':'Side by side')}${button('edit','Edit file')}</div><div class="code-monaco"><div class="code-empty">Loading editor…</div></div></section></div><div class="code-status" role="status" aria-live="polite"></div>`;
    root.addEventListener('click',click);root.querySelector('.code-create').addEventListener('submit',create);root.querySelector('.code-find input').addEventListener('input',findFiles);
    root.addEventListener('change',onChange);
    renderTabs();renderTree();
    try {
      monacoPromise ||= import('/vendor/monaco/editor.js').catch(error=>{monacoPromise=null;throw error;});
      const module=await monacoPromise;if(!current(token))return;monaco=module.monaco||module;
      theme();showEditor();await refresh();if(!current(token))return;if(state.search)await findFiles();if(!current(token))return;
      observer=new MutationObserver(()=>{theme();editor?.updateOptions({readOnly:view!=='file'||readonly()||active()?.readOnly});renderStatus();});
      observer.observe(document.documentElement,{attributes:true,attributeFilter:['class','style','data-theme','data-vscode-theme']});
      poll=setInterval(()=>{if(!document.hidden)refresh();},15000);
    } catch(error){if(current(token)){root.querySelector('.code-monaco').innerHTML='<div class="code-empty">The editor could not load. Reopen Code to retry.</div>';tell(error);}}
  }
  function unmount() {
    ++epoch;++searching;clearInterval(poll);observer?.disconnect();observer=null;disposeView();
    if(root){root.removeEventListener('click',click);root.removeEventListener('change',onChange);root.replaceChildren();root.classList.remove('code-editor');}
    root=null;state=null;context=null;selected='';busy=false;
  }
  function dispose() {
    unmount();for(const project of projects.values())for(const file of project.files.values()){file.listener?.dispose();file.model?.dispose();}
    projects.clear();window.removeEventListener('beforeunload',beforeUnload);window.removeEventListener('focus',onFocus);
  }
  return {mount,unmount,hasUnsaved,refresh,dispose};
}
