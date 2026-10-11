import {pageLayoutPages} from './surfboard.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={feeds:'data',requires:'requires',owns:'owns',handoff:'handoff',triggers:'wakes',recovers:'repairs'};
export function createWorkflow(options){
 let root,scope,data,timer,signature='',pending=false,receipt=null,chosen='',revision='',message='',expanded=false,rolloutVersion=0;
 const fields=()=>({project_id:scope.projectId,...(scope.experimentId?{experiment_id:scope.experimentId}:{})});
 const versions=()=>({expected_version:data.source.version,expected_draft_version:data.source.draft?.draft_version||0});
 const board=()=>data.source.draft?.board||data.source.board;
 const selected=()=>data.library.entries.find(e=>e.id===chosen);
 async function load(force=false){
  const target=root,key=scope;try{const next=await options.api('workflow?'+new URLSearchParams(fields()));if(root!==target||scope!==key)return;const sig=JSON.stringify(next);if(next.source.draft?.draft_version&&next.source.draft?.draft_version!==data?.source.draft?.draft_version)expanded=true;data=next;if(!chosen&&data.source.draft?.library_source){chosen=data.source.draft.library_source.id;revision=data.source.draft.library_source.version;}if(sig!==signature||force){signature=sig;render();}}
  catch(e){if(root===target&&scope===key){message=e.message;expanded=true;notice();}}
 }
 function notice(){const el=root?.querySelector('.wf-notice');if(el){el.textContent=message;el.hidden=!message;}}
 function render(){
  if(!root||!data)return;
  // Replace only the proposal area. The real chat and its drafts never remount.
  const panel=root.querySelector('.wf-proposal');
  const draftName=panel.querySelector('[aria-label="Surfboard name"]')?.value||'';
  const oldScope=panel.querySelector('[aria-label="Workflow change scope"]')?.value;
  const checked=[...panel.querySelectorAll('.wf-targets input:checked')].map(x=>x.value);
  const rollout=data.source.draft?.rollout,newRollout=(data.source.draft?.draft_version||0)!==rolloutVersion;rolloutVersion=data.source.draft?.draft_version||0;
  panel.hidden=!expanded;
  root.querySelector('.wf-start').innerHTML=`<button class="button small-button" data-wf="toggle">${expanded?'Hide':'View'} workflow</button><select aria-label="Choose a saved workflow"><option value="">Choose a saved Surfboard…</option>${data.library.entries.map(e=>`<option value="${esc(e.id)}">${esc(e.name)}</option>`).join('')}</select><button class="button small-button" data-wf="advanced">Advanced</button>`;
  root.querySelector('[aria-label="Choose a saved workflow"]').onchange=e=>{chosen=e.target.value;revision=selected()?.version||'';receipt=null;expanded=true;render();};
  const entry=selected(),b=data.source.draft?board():entry?.revisions.find(r=>r.version==revision)?.board||board(),link=data.link,rows=pageLayoutPages(b,scope.experimentId?'item':'project');
  panel.innerHTML=`<div class="wf-toolbar"><strong>${data.source.draft?'Proposed workflow':esc(b.name)}</strong><button class="button small-button" data-wf="advanced">Advanced ↗</button></div>
  <div class="wf-notice notice" role="status" hidden></div>
  <div class="wf-library"><label>Saved Surfboard <select aria-label="Saved Surfboard"><option value="">Current workflow${link?' · linked':''}</option>${data.library.entries.map(e=>`<option value="${esc(e.id)}" ${chosen===e.id?'selected':''}>${esc(e.name)} · v${e.version}</option>`).join('')}</select></label>${entry?`<select aria-label="Surfboard version">${[...entry.revisions].reverse().map(r=>`<option value="${r.version}" ${String(r.version)===String(revision)?'selected':''}>Version ${r.version}</option>`).join('')}</select><button class="button small-button" data-wf="choose">Preview saved</button>`:''}</div>
  <details class="wf-outline" open><summary>Views & workflow</summary>
  <div class="wf-view-preview" aria-label="View preview">${rows.map(p=>`<section><strong>${esc(p.title)}</strong><div>${p.tiles.map(t=>`<span style="flex:${t.span||12}">${esc(t.title||t.kind.replaceAll('_',' '))}</span>`).join('')}</div></section>`).join('')}</div>
  <div class="wf-diagram" aria-label="Workflow schematic">${b.edges.map(edge=>{const a=b.nodes.find(n=>n.id===edge.source),z=b.nodes.find(n=>n.id===edge.target);return `<div><span>${esc(a?.label)}</span><small>${esc(labels[edge.relation]||'clarify')} →</small><span>${esc(z?.label)}</span></div>`;}).join('')}</div></details>
  <details><summary>Agents, requirements & when you’re away</summary><ul>${b.nodes.filter(n=>['agent','approval','timer'].includes(n.kind)).map(n=>`<li><strong>${esc(n.label)}</strong> · ${esc(n.kind==='agent'?n.config?.role:n.kind==='approval'?(n.config?.requirements||[]).join(', '):JSON.stringify(n.config))}</li>`).join('')}</ul><p>Applying sets up the workspace. It starts no jobs or recurring work. Agents follow your requests; monitoring needs an explicit scope and stopping condition.</p></details>
  <div class="wf-save"><input aria-label="Surfboard name" placeholder="Name this Surfboard…" maxlength="160"><button class="button small-button" data-wf="save">Save as new</button>${link?'<button class="button small-button" data-wf="revise">Save new version</button>':''}</div>
  <label class="wf-scope">Apply changes to <select aria-label="Workflow change scope"><option value="current">${scope.experimentId?'This task':'Future tasks in this project'}</option>${scope.experimentId?'<option value="future">Future tasks in this project</option>':''}<option value="existing">Selected existing tasks using this Surfboard</option></select></label>
  <div class="wf-targets" hidden>${data.tasks.filter(t=>!t.archived&&t.library_id&&(t.library_id===(chosen||link?.id))).map(t=>`<label><input type="checkbox" value="${esc(t.id)}">${esc(t.name)}${t.project_id!==scope.projectId?' · another project':''}</label>`).join('')||'<p>No linked tasks yet. Preview a saved Surfboard and apply it to a task to link it.</p>'}</div>
  <div class="wf-actions"><button class="button primary" data-wf="preview">Review & use workflow</button>${scope.experimentId?'<button class="button" data-wf="open">Open task</button>':'<button class="button" data-wf="new-task">Create first task</button>'}</div>
  <div class="wf-review"></div>
  ${data.changes.length?`<details><summary>Change history</summary>${[...data.changes].reverse().slice(0,10).map(c=>`<div class="wf-history">${new Date(c.at*1000).toLocaleString()} · ${c.count} target${c.count===1?'':'s'} <button class="button small-button" data-rollback="${esc(c.id)}">Undo batch</button></div>`).join('')}</details>`:''}`;
  panel.querySelector('[aria-label="Surfboard name"]').value=draftName;
  const mode=panel.querySelector('[aria-label="Workflow change scope"]');mode.value=(newRollout&&rollout?.scope)||oldScope||'current';
  panel.querySelector('.wf-targets').hidden=mode.value!=='existing';
  for(const input of panel.querySelectorAll('.wf-targets input'))input.checked=newRollout&&rollout?!!rollout.task_ids?.includes(input.value):checked.includes(input.value);
  panel.querySelector('[aria-label="Workflow change scope"]').onchange=e=>panel.querySelector('.wf-targets').hidden=e.target.value!=='existing';
  panel.querySelector('[aria-label="Saved Surfboard"]').onchange=e=>{chosen=e.target.value;revision=selected()?.version||'';receipt=null;render();};
  panel.querySelector('[aria-label="Surfboard version"]')?.addEventListener('change',e=>{revision=e.target.value;receipt=null;});
  panel.querySelectorAll('button').forEach(b=>b.disabled=pending||options.readOnly());notice();if(receipt)renderReview();
 }
 function renderReview(){
  const el=root?.querySelector('.wf-review');if(!el||!receipt)return;
  el.innerHTML=`<section aria-label="Review workflow update"><h3>${receipt.applied?'Workflow applied':'Review exact changes'}</h3>${receipt.targets.map(t=>`<article><strong>${esc(t.name)}</strong><ul>${t.summary.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>${t.conflicts.map(c=>`<p class="error">${esc(c)}</p>`).join('')}</article>`).join('')}<p>Existing executions keep their recorded contracts. No jobs or monitoring are launched.</p>${!receipt.applied?`<button class="button primary" data-wf="apply" ${!receipt.can_apply||pending?'disabled':''}>Apply these changes</button>`:''}</section>`;
 }
 async function perform(button){
  if(pending||options.readOnly())return;
  const kind=button.dataset.wf;if(kind==='toggle'){expanded=!expanded;render();return;}if(kind==='advanced')return options.advanced();if(kind==='open')return options.open();if(kind==='new-task')return options.newTask();
  const target=root,key=scope,isCurrent=()=>root===target&&scope===key;pending=true;message='';
  try{
   if(button.dataset.rollback){await options.action('workflow.rollback',{preview_id:button.dataset.rollback});if(!isCurrent())return;receipt=null;message='Previous configuration restored. No jobs were changed.';}
   else if(kind==='save'||kind==='revise'){
    const name=root.querySelector('[aria-label="Surfboard name"]').value.trim()||board().name;
    const result=await options.action('workflow.save',{...fields(),...versions(),name,library_revision:data.library.version,...(kind==='revise'?{library_id:data.link.id}:{})});if(!isCurrent())return;chosen=result.entry.id;revision=result.entry.version;receipt=null;message='Saved. Preview and use it to link this task, or select other linked tasks. '+(result.warnings||[]).join(' ');
   }else if(kind==='preview'||kind==='choose'){
    if(kind==='choose'&&chosen){
     const snapshot=selected().revisions.find(r=>r.version==revision)||selected().revisions.at(-1);
     await options.action('workflow.stage',{...fields(),...versions(),library_id:chosen,library_version:snapshot.version});if(!isCurrent())return;await load();if(!isCurrent())return;
    }
    const mode=root.querySelector('[aria-label="Workflow change scope"]').value;
    const targets=mode==='existing'?[...root.querySelectorAll('.wf-targets input:checked')].map(x=>x.value):mode==='current'&&scope.experimentId?[scope.experimentId]:[];
    const reviewed=await options.action('workflow.preview',{...fields(),...versions(),targets,future_default:mode==='future'||!scope.experimentId&&mode==='current',...(chosen?{use_saved:!data.source.draft,library_id:chosen,library_version:Number(revision)||selected().version}:{})});if(!isCurrent())return;receipt=reviewed;
   }else if(kind==='apply'){
    const applied=await options.action('workflow.apply',{preview_id:receipt.id});if(!isCurrent())return;receipt=applied;message='Workflow applied. You can start work in the task chat when ready.';await options.applied();
   }
   if(isCurrent())await load(true);
  }catch(e){if(isCurrent()){message=e.message;notice();}}finally{if(isCurrent()){pending=false;root.querySelectorAll('button').forEach(b=>b.disabled=options.readOnly());renderReview();}}
 }
 return {
  mount(element,context){if(root===element&&scope?.projectId===context.projectId&&scope?.experimentId===context.experimentId)return;this.unmount();root=element;scope=context;signature='';data=null;pending=false;rolloutVersion=0;receipt=null;chosen='';revision='';message='';expanded=false;root.innerHTML='<section class="wf-column"><div class="wf-start"></div><div class="wf-chat"></div></section><aside class="wf-proposal" aria-label="Workflow proposal"><p>Loading your workflow…</p></aside>';root.onclick=e=>{const b=e.target.closest('[data-wf],[data-rollback]');if(b){e.preventDefault();void perform(b);}};void load();timer=setInterval(()=>{if(!pending)void load();},3000);},
  unmount(){clearInterval(timer);if(root)root.onclick=null;root=null;scope=null;},refresh:()=>load(true),
 };
}
