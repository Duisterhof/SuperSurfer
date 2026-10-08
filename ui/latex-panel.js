import {createLatexAutoCompile} from './latex-auto.js';
import {createPdfPreview} from './pdf-preview.js';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const terminal=new Set(['succeeded','failed','cancelled','timed_out','interrupted']);
const label=value=>({starting:'Preparing source',running:'Compiling',cancelling:'Stopping',succeeded:'Compiled',failed:'Compile failed',timed_out:'Time limit reached',cancelled:'Stopped',interrupted:'Interrupted'}[value]||'Ready to compile');
const time=value=>value?new Date(value*1000).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'}):'';

// Owns compiler controls; the PDF renderer owns its document, page and selection.
// Auto compiles saved changes; it never writes unsaved editor buffers.
export function createLatexPanel(options){
 function readAuto(key){try{return (localStorage.getItem('supersurfer-latex-auto:'+key)??String(options.editorSettings?.get().latex_auto_compile??true))==='true';}catch{return true;}}
 const background=createLatexAutoCompile(options);
 const records=new Map(),pdf=createPdfPreview({onSelection:options.onSelection,onSource:options.onSource,showStaleStatus:false});
 let root=null,context=null,state=null,epoch=0,timer=null,debounce=null,loading=false;
 const readonly=()=>Boolean(options.readOnly?.());
 const unsaved=()=>Boolean(options.hasUnsaved?.(context?.projectId));
 const busy=()=>[state?.data?.build,...(state?.data?.builds||[])].find(row=>row&&!terminal.has(row.status));
 const fields=()=>({project_id:context.projectId,...(context.experimentId?{experiment_id:context.experimentId}:{}),main_file:state.main.trim()||'main.tex'});
 const valid=token=>root&&epoch===token;
 const paperKey=()=>JSON.stringify({...fields(),node_id:state.nodeId||'',source_dir:state.sourceDir||''});
 function cancelAuto(){clearTimeout(debounce);debounce=null;if(state){state.autoAttempt=null;state.pendingSave=false;}}
 function schedule(){clearTimeout(timer);if(root)timer=setTimeout(()=>refresh(),busy()?750:5000);}
 function form(){
  root.innerHTML=`<div class="latex-controls"><form class="latex-build-form"><input data-latex-main aria-label="Main TeX file" placeholder="main.tex" spellcheck="false"><button class="button small-button primary" data-latex="compile" type="submit">Compile</button><button class="button small-button" type="button" data-latex="stop" hidden>Stop</button></form><div class="latex-options"><select data-latex-block aria-label="LaTeX block" hidden></select><label title="Compile saved LaTeX changes, including when this PDF view is on another page. Unsaved buffers are never saved automatically."><input type="checkbox" data-latex-auto>Auto</label><select data-latex-history aria-label="PDF build history"><option value="">Latest build</option></select><details class="latex-settings"><summary title="Compiler settings">Options</summary><div><label>Source folder<input data-latex-source placeholder="Repository root" spellcheck="false"></label><p>For a paper in a large repository, choose its folder. The main TeX path stays relative to the repository.</p></div></details><button class="icon-button" data-latex="refresh" title="Refresh compile status" aria-label="Refresh compile status">↻</button></div></div><div class="latex-status" role="status"></div><div class="latex-setup" hidden><button class="button small-button" data-latex="setup" type="button">Ask agent to set up compiler</button></div><details class="latex-log"><summary>Compiler details</summary><div class="latex-diagnostics"></div><pre></pre></details><div class="latex-pdf"></div>`;
  root.classList.add('latex-panel');root.querySelector('[data-latex-main]').value=state.main;
  root.querySelector('[data-latex-source]').value=state.sourceDir;root.querySelector('[data-latex-auto]').checked=state.auto;
  root.querySelector('form').onsubmit=event=>{event.preventDefault();compile();};
  root.onclick=event=>{const action=event.target.closest('[data-latex]')?.dataset.latex;if(action==='stop')stop();if(action==='setup')options.onSetup?.();if(action==='refresh')refresh(true);const source=event.target.closest('[data-latex-path]');if(source)options.onSource?.({path:source.dataset.latexPath,line:Number(source.dataset.latexLine)||1});};
  root.onchange=event=>{
   if(event.target.matches('[data-latex-main]')){cancelAuto();state.main=event.target.value.trim()||'main.tex';state.sourceDir='';root.querySelector('[data-latex-source]').value='';state.selection='';state.data=null;state.error='';state.lastActionError=null;refresh(true);}
   if(event.target.matches('[data-latex-source]')){cancelAuto();state.sourceDir=event.target.value.trim();state.lastActionError=null;render();}
   if(event.target.matches('[data-latex-block]')){cancelAuto();state.nodeId=event.target.value;const block=state.data?.blocks?.find(row=>row.node_id===state.nodeId);if(block){state.main=block.main_file||'main.tex';root.querySelector('[data-latex-main]').value=state.main;}state.sourceDir='';root.querySelector('[data-latex-source]').value='';state.selection='';state.data=null;state.error='';state.lastActionError=null;refresh(true);}
   if(event.target.matches('[data-latex-auto]')){cancelAuto();state.auto=event.target.checked;try{localStorage.setItem('supersurfer-latex-auto:'+context.key,String(state.auto));}catch{}if(!state.auto)state.pendingSave=false;if(state.auto)refresh(true);}
   if(event.target.matches('[data-latex-history]')){cancelAuto();state.selection=event.target.value;refresh(true);}
  };
  pdf.mount(root.querySelector('.latex-pdf'),{});render();
 }
 function render(){
  if(!root)return;const data=state.data,build=data?.build,good=build?.pdf_url?build:data?.last_successful,active=busy();
  const blocks=data?.blocks||[],blockSelect=root.querySelector('[data-latex-block]');if(blocks.length&&!blocks.some(row=>row.node_id===state.nodeId))state.nodeId=blocks[0].node_id;
  const blockOptions=blocks.map(row=>`<option value="${esc(row.node_id)}">${esc(row.label||row.node_id)}</option>`).join('');if(blockSelect.innerHTML!==blockOptions)blockSelect.innerHTML=blockOptions;blockSelect.value=state.nodeId||'';blockSelect.hidden=blocks.length<2;blockSelect.disabled=Boolean(active)||state.submitting;
  const compileButton=root.querySelector('[data-latex="compile"]');compileButton.disabled=readonly()||Boolean(active)||state.submitting||data?.capabilities?.available===false||!data?.blocks?.length;
  compileButton.textContent=state.submitting?'Starting…':active?'Compiling…':'Compile';
  compileButton.title=unsaved()?'Compile files saved on disk. Your unsaved edits are preserved.':'Compile saved source on the connected workspace';
  const stopButton=root.querySelector('[data-latex="stop"]');stopButton.hidden=!active;stopButton.disabled=readonly()||build?.status==='cancelling';
  root.querySelector('[data-latex-auto]').disabled=readonly()||data?.capabilities?.available===false||!data?.blocks?.length;
  const history=root.querySelector('[data-latex-history]'),markup='<option value="">Latest build</option>'+(data?.builds||[]).map(row=>`<option value="${esc(row.build_id)}">${esc(time(row.started||row.created))} · ${esc(label(row.status))}</option>`).join('');
  if(history.innerHTML!==markup)history.innerHTML=markup;
  history.value=state.selection;
  root.querySelector('.latex-setup').hidden=!(data?.capabilities?.available===false&&options.onSetup&&!readonly());
  history.disabled=!(data?.builds?.length);root.querySelector('[data-latex-main]').disabled=Boolean(active)||state.submitting;
  const status=root.querySelector('.latex-status');
  const stale=good&&(good.stale||good.build_id!==build?.build_id),staleText=good?.source_state==='unknown'?'Showing last good PDF · source freshness unavailable':good?.source_state==='changed'?'Showing last good PDF · saved source differs':'Showing last good PDF',parts=[state.lastActionError?.message||state.error||build?.error||data?.capabilities?.error||(!data?'Loading compiler…':label(build?.status)),good?`PDF ${time(good.finished||good.started)}`:'',stale?staleText:'',unsaved()?'Unsaved editor changes':''].filter(Boolean);
  status.textContent=parts.join(' · ');status.classList.toggle('error',Boolean(state.lastActionError||state.error||build?.error||data?.capabilities?.error));status.classList.toggle('stale',Boolean(stale));
  const diagnostics=build?.diagnostics||[],log=root.querySelector('.latex-log');log.hidden=!build?.logs&&!diagnostics.length;
  root.querySelector('.latex-diagnostics').innerHTML=diagnostics.map(row=>row.path?`<button type="button" data-latex-path="${esc(row.path)}" data-latex-line="${row.line||1}"><strong>${esc(row.path)}${row.line?':'+row.line:''}</strong> ${esc(row.message)}</button>`:`<p>${esc(row.message)}</p>`).join('');
  root.querySelector('.latex-log pre').textContent=(build?.logs_truncated?'Earlier compiler output was truncated.\n':'')+(build?.logs||'');
  if(build?.status==='failed'&&!good)log.open=true;
  pdf.setDocument(good?{...good,url:good.pdf_url,title:good.main_file,stale:Boolean(stale)}:{});
 }
 async function refresh(force=false){
  if(!root)return;if(loading){if(force)state.refreshAgain=true;return;}loading=true;
  const token=epoch,currentState=state,target=paperKey(),query=new URLSearchParams(fields());if(state.selection)query.set('build_id',state.selection);
  const matches=()=>{const currentQuery=new URLSearchParams(fields());if(state.selection)currentQuery.set('build_id',state.selection);return target===paperKey()&&String(query)===String(currentQuery);};
  try{const data=await options.api('latex?'+query);if(!valid(token))return;if(!matches()){state.refreshAgain=true;return;}state.data=data;state.error='';
   // A successful status read is a receipt too: the start response may have
   // been lost after the server committed the build. Keep an unseen ID for a
   // safe retry, but let the next deliberate Compile create a fresh build.
   if(state.pending&&[data.build,...(data.builds||[])].some(row=>row?.request_id===state.pending.params.request_id)){state.pending=null;if(state.lastActionError?.operation==='start')state.lastActionError=null;}
   if(!state.initialized){state.initialized=true;const main=data.build?.main_file||data.blocks?.[0]?.main_file;if(main&&state.main==='main.tex'&&main!=='main.tex'){state.main=main;root.querySelector('[data-latex-main]').value=main;state.refreshAgain=true;}}
   render();
   const build=data.build;
   if(state.auto&&state.pendingSave&&!state.selection&&!readonly()&&data.capabilities?.available&&!busy())debouncedCompile();
   if(state.auto&&!state.selection&&!unsaved()&&!readonly()&&data.capabilities?.available&&!busy()&&build?.stale&&(build.source_dir||'')===state.sourceDir&&(!build.node_id||build.node_id===state.nodeId)&&build.source_fingerprint&&state.autoAttempt!==build.source_fingerprint){state.autoAttempt=build.source_fingerprint;debouncedCompile();}
  }catch(error){if(valid(token)){if(!matches())state.refreshAgain=true;else{state.error=error.message;render();}}}
  finally{if(valid(token)){loading=false;if(currentState.refreshAgain){currentState.refreshAgain=false;queueMicrotask(()=>refresh());}else schedule();}}
 }
 function debouncedCompile(){
  clearTimeout(debounce);if(!root||!state.auto||state.selection)return;
  const token=epoch,target=paperKey();
  debounce=setTimeout(()=>{
   if(!valid(token)||!state.auto||state.selection||target!==paperKey()||unsaved()||readonly()||busy()||state.submitting)return;
   // A user may be typing a new path without having blurred its input yet.
   // Never let a save for one paper launch the newly typed paper instead.
   if((root.querySelector('[data-latex-main]').value.trim()||'main.tex')!==state.main||root.querySelector('[data-latex-source]').value.trim()!==state.sourceDir)return;
   if(state.data?.capabilities?.available&&state.data.blocks?.some(row=>row.node_id===state.nodeId))compile();
  },900);
 }
 async function compile(){
  if(!root||readonly()||busy()||state.submitting)return;const token=epoch,currentState=state;
  state.main=root.querySelector('[data-latex-main]').value.trim()||'main.tex';state.sourceDir=root.querySelector('[data-latex-source]').value.trim();
  const intent={...fields(),operation:'start',source_dir:state.sourceDir,...(state.nodeId?{node_id:state.nodeId}:{})},signature=JSON.stringify(intent);
  if(!state.pending||state.pending.signature!==signature)state.pending={signature,params:{...intent,request_id:'latex_'+crypto.randomUUID().replaceAll('-','')}};
  state.submitting=true;state.pendingSave=false;state.error='';state.lastActionError=null;state.selection='';render();
  try{const build=await options.action('latex.action',state.pending.params);currentState.pending=null;if(!valid(token))return;state.data={...state.data,build};state.autoAttempt=build.source_fingerprint;render();await refresh(true);}
  catch(error){if(error.status>=400&&error.status<500)currentState.pending=null;currentState.lastActionError={operation:'start',message:error.message};if(valid(token))render();}
  finally{currentState.submitting=false;if(valid(token)){render();schedule();}}
 }
 async function stop(){
  if(!root||readonly()||!busy())return;cancelAuto();state.pendingSave=false;state.auto=false;try{localStorage.setItem('supersurfer-latex-auto:'+context.key,'false');}catch{}root.querySelector('[data-latex-auto]').checked=false;const token=epoch,target=paperKey();
  try{await options.action('latex.action',{...fields(),operation:'stop',build_id:busy().build_id});if(!valid(token)||target!==paperKey())return;state.lastActionError=null;await refresh(true);}
  catch(error){if(valid(token)&&target===paperKey()){state.lastActionError={operation:'stop',message:error.message};render();}}
 }
 function unmount(){const saved=state?.pendingSave&&state.auto&&!state.selection?state.savedRecord:null,choice=state?{nodeId:state.nodeId,main:state.main,sourceDir:state.sourceDir}:{};if(state)state.pendingSave=false;epoch++;clearTimeout(timer);clearTimeout(debounce);if(saved)Promise.resolve(background.saved(saved,choice)).catch(error=>options.onError?.(error));pdf.unmount();if(root){root.onclick=root.onchange=null;const form=root.querySelector('form');if(form)form.onsubmit=null;}root=null;context=null;state=null;loading=false;}
 return {mount(element,ctx){const key=ctx.projectId+':'+(ctx.experimentId||'');if(root===element&&context?.key===key){render();return;}unmount();root=element;context={...ctx,key};state=records.get(key);if(!state){state={main:'main.tex',sourceDir:'',auto:readAuto(key),pendingSave:false,selection:'',data:null,error:'',initialized:false,pending:null};records.set(key,state);}form();refresh(true);},sourceSaved(record){const {projectId,experimentId}=record,key=projectId+':'+(experimentId||'');if(!root||context.key!==key)return background.saved(record,records.get(key)||{});if(record.path?.startsWith('artifact:')||!/\.(tex|latex|bib|sty|cls)$/i.test(record.path||''))return;state.savedRecord={...record};state.refreshAgain=true;if(state.auto&&!state.selection){state.pendingSave=true;debouncedCompile();}refresh(true);},refresh,unmount,dispose(){unmount();records.clear();pdf.dispose?.();}};
}
