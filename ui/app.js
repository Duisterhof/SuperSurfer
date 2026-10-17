import {installPanelZoom} from './panel-zoom.js';
import {createWorkflow} from './workflow.js';
import {ensureDockLayout,renderDockLayout} from './dock-layout.js';
import {createPanelWindows} from './panel-windows.js';
import {createPorts} from './ports.js';
import {createTodos} from './todos.js';
import {createFileUploads} from './file-uploads.js';
import {workspacePath} from './workspace-files.js';
import {createFilePicker} from './file-picker.js';
import {createPanelFocus} from './panel-focus.js';
import {createChatContext,contextMarkup} from './chat-context.js';
import {createSurfboardEditor, createViewLayoutEditor, createPageLayoutEditor} from './surfboard.js';
import {createEditorSettings} from './editor-settings.js';
import {createWorkbenchEditor} from './workbench-editor.js';
import {createCodeEditor} from './code-editor.js';
import {createLatexPanel} from './latex-panel.js';
import {projectCapacity,capacityWaitReason} from './run-capacity.js';
import {createRepositoryExplorer, createAgentChanges} from './code-tiles.js';
import {connectLiveResults} from './results-live.js';
import {renderChatTimeline} from './chat-checks.js';
import {createTileLayout} from './tile-layout.js';
import {createPdfPreview} from './pdf-preview.js';
import {createAccountGate} from './account-gate.js';
import {createWorkspaceAccounts} from './accounts.js';
if (window.superSurferDesktop) document.body.classList.add('desktop-app');
document.querySelector('#new-workspace-window').hidden=!window.superSurferDesktop?.newWindow;
const $ = (selector, root = document) => root.querySelector(selector);
window.superSurferDesktop?.onWorkspaceCommand?.(command=>command.startsWith('zoom-')?panelZoom.zoom(command==='zoom-reset'?0:command==='zoom-in'?1:-1):$('#'+({rearrange:'arrange-page',sidebar:'sidebar-toggle',chat:'right-sidebar-toggle'}[command]))?.click());
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e = escapeHtml;
const paths = {
 stop:'<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>',
 archive:'<rect x="3" y="3" width="18" height="5" rx="1"/><path d="M5 8v13h14V8M10 12h4"/>',
 maximize:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>', restore:'<rect x="3" y="7" width="14" height="14" rx="2"/><path d="M7 7V3h14v14h-4"/>',
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>', layers:'<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>', cpu:'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/><rect x="9" y="9" width="6" height="6" rx="1"/>', settings:'<path d="M10.68 2.59L13.32 2.59L13.64 4.89L15.87 5.81L17.72 4.41L19.59 6.28L18.19 8.13L19.11 10.36L21.41 10.68L21.41 13.32L19.11 13.64L18.19 15.87L19.59 17.72L17.72 19.59L15.87 18.19L13.64 19.11L13.32 21.41L10.68 21.41L10.36 19.11L8.13 18.19L6.28 19.59L4.41 17.72L5.81 15.87L4.89 13.64L2.59 13.32L2.59 10.68L4.89 10.36L5.81 8.13L4.41 6.28L6.28 4.41L8.13 5.81L10.36 4.89Z"/><circle cx="12" cy="12" r="3"/>', plus:'<path d="M12 5v14M5 12h14"/>', folder:'<path d="M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z"/>', chevron:'<path d="m9 5 7 7-7 7"/>', chevronDown:'<path d="m6 9 6 6 6-6"/>', refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 6a8 8 0 0 1 13 3M5 15a8 8 0 0 0 13 3"/>', server:'<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M11 6.5h6M11 17.5h6"/>', panel:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>', close:'<path d="m6 6 12 12M6 18 18 6"/>', spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/>', arrowUp:'<path d="M12 19V5m-6 6 6-6 6 6"/>', arrowRight:'<path d="M5 12h14m-6-6 6 6-6 6"/>', file:'<path d="M14 3H5v18h14V8l-5-5Z"/><path d="M14 3v5h5M8 12h8M8 16h6"/>', play:'<path d="m8 4 12 8-12 8V4Z"/>', clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', link:'<path d="m10 13 4-4m-6 7-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0m0 2 1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0" transform="translate(2 1) scale(.9)"/>', external:'<path d="M14 3h7v7m0-7L10 14M10 3H4v17h17v-6"/>', edit:'<path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z"/>', history:'<path d="M3 5v5h5M3 10a9 9 0 1 1 2 8M12 7v5l4 2"/>', check:'<path d="m5 12 4 4 10-10"/>', pause:'<path d="M8 5v14M16 5v14"/>', grip:'<circle cx="9" cy="5" r=".7"/><circle cx="15" cy="5" r=".7"/><circle cx="9" cy="12" r=".7"/><circle cx="15" cy="12" r=".7"/><circle cx="9" cy="19" r=".7"/><circle cx="15" cy="19" r=".7"/>', branch:'<circle cx="6" cy="4" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="20" r="2"/><path d="M6 6v12m0-4c10 0 12-2 12-6"/>', activity:'<path d="M2 12h5l3-8 4 16 3-8h5"/>', message:'<path d="M21 4H3v14h5l4 3 4-3h5V4Z"/><path d="M7 9h10M7 13h6"/>', lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>', terminal:'<path d="m5 7 5 5-5 5m8 0h6"/>', chart:'<path d="M4 3v17h17M8 15l4-6 4 3 5-7"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.file}</svg>`;
$$('[data-icon]').forEach(el => {el.innerHTML = icon(el.dataset.icon);});
const terminal = new Set(['completed','complete','succeeded','success','failed','cancelled','canceled','error','stopped']);
const active = new Set(['running','launching','starting','stopping']);
const modelRoles = ['manager','lead','worker'];
const backendLabels={codex:'Codex',cursor:'Cursor',claude:'Claude Code'};
const currentBackend=()=>state.chat?.preferences?.backend||state.data?.settings?.backends?.[state.scope==='manager'?'manager':state.experimentId?'worker':'lead']||'codex';
const state = {data:null,view:'workspace',runFilter:'active',queuePriority:false,projectId:null,experimentId:null,tab:'overview',experiment:null,edit:false,scope:null,pinnedAgent:null,chat:null,models:[],account:null,chatVisible:true,chatWidth:390,sidebarWidth:null,sidebarCollapsed:false,projectTreeHeight:null,filesHeight:null,chatMaximized:false,loading:false,modalKind:null,stateSignature:'',sidebarSignature:'',chatSignature:'',experimentRequest:0};
const metricsCache = new Map();
let savedNavigation = null, navigationRestored = false, taskTabs={};
const taskTabKey=(projectId,experimentId)=>projectId+'/'+(experimentId||'_project');
let stateWaiters = [];
let selectedMetric = null;
let modelCatalogBackend='codex',modelCatalogRequestedBackend=null;
let modelCatalogPromise = null, modelCatalogLoadedAt = 0, chatPreferenceSaveScope = null;
const chatPreferenceRevisions = new Map();
const approvalRevisions = new Map(), approvalBusy = new Set(), approvalErrors = new Map();
const startingExperiments = new Set();
let draggedRun = null, stateBusy = false, chatBusy = false, toastTimeout, renderPending = false;
const hash = new URLSearchParams(location.hash.slice(1));
if(hash.has('token')) {sessionStorage.setItem('supersurfer-token',hash.get('token')); history.replaceState(null,'',location.pathname+location.search);}
async function readNavigation() {
  try { savedNavigation = JSON.parse(localStorage.getItem('supersurfer-workspace') || 'null'); } catch { savedNavigation = null; }
  if (window.superSurferDesktop?.getWorkspace) {
    try { const saved = await window.superSurferDesktop.getWorkspace(); if (saved && typeof saved === 'object' && !Array.isArray(saved)) savedNavigation = saved; } catch {}
  }
  if (!savedNavigation || typeof savedNavigation !== 'object' || Array.isArray(savedNavigation)) savedNavigation = {};
  if(panelWindows.detached)savedNavigation={...savedNavigation,...panelWindows.navigation};
  taskTabs=Object.fromEntries(Object.entries(savedNavigation.taskTabs||{}).filter(([key,value])=>/^[A-Za-z0-9_:-]{1,200}\/[A-Za-z0-9_:-]{1,200}$/.test(key)&&typeof value==='string'&&/^(?:page:page_[a-f0-9]+|[A-Za-z0-9_][A-Za-z0-9_-]{0,63})$/.test(value)).slice(-512));
  state.view = ['workspace', 'compute', 'settings'].includes(savedNavigation.view) ? savedNavigation.view : 'workspace';
  state.tab = ['_files', '_todos', 'overview', 'runs', 'results', 'compute', 'surfboard', 'artifacts', 'activity', 'editor', 'chat', 'documents', 'preview'].includes(savedNavigation.tab)||/^(?:page:page_[a-f0-9]+|[A-Za-z0-9][A-Za-z0-9_-]{0,63})$/.test(savedNavigation.tab||'') ? savedNavigation.tab : 'overview';
  state.chatVisible = typeof savedNavigation.chatVisible === 'boolean' ? savedNavigation.chatVisible : true;
  state.chatWidth = Number.isFinite(savedNavigation.chatWidth) ? Math.min(760,Math.max(280,savedNavigation.chatWidth)) : 390;
  state.sidebarWidth = Number.isFinite(savedNavigation.sidebarWidth) ? Math.min(600,Math.max(160,savedNavigation.sidebarWidth)) : null;
  state.sidebarCollapsed=savedNavigation.sidebarCollapsed===true;
  state.projectTreeHeight=Number.isFinite(savedNavigation.projectTreeHeight)?Math.max(60,Math.min(1200,savedNavigation.projectTreeHeight)):null;
  state.filesHeight=Number.isFinite(savedNavigation.filesHeight)?Math.max(60,Math.min(1200,savedNavigation.filesHeight)):null;
  if(!Object.hasOwn(savedNavigation,'filesHeight'))try{const old=Number(localStorage.getItem('supersurfer-files-height'));if(old>0&&Number.isFinite(old))state.filesHeight=Math.max(60,Math.min(1200,old+37));}catch{}
  state.chatMaximized = savedNavigation.chatMaximized === true;
  const pin=savedNavigation.pinnedAgent;
  if(pin&&typeof pin.scope==='string'&&/^(manager|(?:project|experiment|conversation|surfboard):[A-Za-z0-9_:-]+)$/.test(pin.scope))state.pinnedAgent=pin;
  $('#chat-panel').hidden = !state.chatVisible;
  $('#chat-toggle').setAttribute('aria-expanded', String(state.chatVisible));
  applyChatLayout();
}
function restoreNavigation(data) {
  if(panelWindows.detached){state.projectId=panelWindows.navigation.projectId;state.experimentId=panelWindows.navigation.experimentId;navigationRestored=true;return;}
  if (!navigationRestored) {
    state.projectId = data.projects.some(p => p.id === savedNavigation?.projectId) ? savedNavigation.projectId : (data.projects.find(p=>!p.archived)||data.projects[0])?.id || null;
    state.experimentId = state.view === 'workspace' && data.experiments.some(x => x.id === savedNavigation?.experimentId && x.project_id === state.projectId) ? savedNavigation.experimentId : null;
    if (data.connected || data.projects.length) navigationRestored = true;
    return;
  }
  if (!data.projects.some(p => p.id === state.projectId)) {
    state.projectId = (data.projects.find(p=>!p.archived)||data.projects[0])?.id || null;
    state.experimentId = null;
    state.experiment = null;
  }
  if (state.experimentId && !data.experiments.some(x => x.id === state.experimentId && x.project_id === state.projectId)) {
    state.experimentId = null;
    state.experiment = null;
    state.tab = 'overview';
  }
}
function persistNavigation() {
  if(panelWindows.detached)return;
  if(state.view==='workspace'&&state.projectId){const key=taskTabKey(state.projectId,state.experimentId);delete taskTabs[key];taskTabs[key]=state.tab;taskTabs=Object.fromEntries(Object.entries(taskTabs).slice(-512));}
  const value = { taskTabs, view: state.view, projectId: state.projectId, experimentId: state.experimentId, tab: state.tab, chatVisible: state.chatVisible, chatWidth: state.chatWidth, sidebarWidth: state.sidebarWidth, sidebarCollapsed:state.sidebarCollapsed, projectTreeHeight:state.projectTreeHeight, filesHeight:state.filesHeight, chatMaximized: state.chatMaximized, pinnedAgent:state.pinnedAgent };
  try { localStorage.setItem('supersurfer-workspace', JSON.stringify(value)); } catch {}
  savedNavigation = value;
  if (window.superSurferDesktop?.setWorkspace) window.superSurferDesktop.setWorkspace(value).catch(() => {});
}
function sidebarSectionBudget(){
 const sidebar=$('.sidebar'),css=getComputedStyle(sidebar),sections=new Set(['workspace-files-section','project-tree','page-left-tiles']);
 let available=sidebar.clientHeight-(parseFloat(css.paddingTop)||0)-(parseFloat(css.paddingBottom)||0);
 for(const el of sidebar.children){const style=getComputedStyle(el);if(style.display==='none')continue;available-=(parseFloat(style.marginTop)||0)+(parseFloat(style.marginBottom)||0);if(!sections.has(el.id))available-=el.getBoundingClientRect().height;}
 available=Math.max(0,available);
 return {available,projectMin:Math.min(60,available*.25),dockMin:$('.app-shell').classList.contains('has-page-left')?Math.min(140,available*.35):0};
}
function filesHeightBounds(){
 const {available,projectMin,dockMin}=sidebarSectionBudget(),max=Math.max(37,Math.floor(available-projectMin-dockMin));
 return {min:Math.min(120,max),max};
}
function applyFilesHeight(){
 const section=$('#workspace-files-section'),divider=$('#workspace-files-divider');divider.hidden=section.hidden||!section.open;
 if(section.hidden||!section.open)return;
 const bounds=filesHeightBounds(),height=Math.round(Math.max(bounds.min,Math.min(bounds.max,state.filesHeight??260)));
 section.style.setProperty('--files-section-height',height+'px');
 divider.setAttribute('aria-valuemin',bounds.min);divider.setAttribute('aria-valuemax',bounds.max);divider.setAttribute('aria-valuenow',height);
}
function projectTreeBounds(){
 const {available,projectMin,dockMin}=sidebarSectionBudget(),files=$('#workspace-files-section');
 return {min:projectMin,max:Math.max(projectMin,available-(files.hidden?0:files.getBoundingClientRect().height)-dockMin)};
}
function applyProjectTreeHeight(){
 const divider=$('#sidebar-projects-resizer'),show=$('.app-shell').classList.contains('has-page-left');divider.hidden=!show;
 applyFilesHeight();const budget=sidebarSectionBudget();$('.sidebar').style.setProperty('--project-tree-min-height',budget.projectMin+'px');$('.sidebar').style.setProperty('--sidebar-dock-min-height',budget.dockMin+'px');if(!show)return;
 const bounds=projectTreeBounds(),height=Math.round(Math.max(bounds.min,Math.min(bounds.max,state.projectTreeHeight||Math.min(230,$('.sidebar').clientHeight*.3))));
 $('.sidebar').style.setProperty('--project-tree-height',height+'px');divider.setAttribute('aria-valuenow',height);divider.setAttribute('aria-valuemin',bounds.min);divider.setAttribute('aria-valuemax',Math.floor(bounds.max));
}
function sidebarWidthBounds(){return {min:160,max:Math.max(160,Math.min(600,Math.floor(window.innerWidth*.4))) };}
function applySidebarLayout(page=activePage()){
 const shell=$('.app-shell'),bounds=sidebarWidthBounds(),fallback=window.innerWidth<=760?160:window.innerWidth<=1100?175:206;
 const width=Math.round(Math.max(bounds.min,Math.min(bounds.max,page?.left_width||state.sidebarWidth||(shell.classList.contains('has-page-left')?230:fallback))));
 shell.style.setProperty('--sidebar-width',width+'px');shell.classList.toggle('narrow-sidebar',width<200);shell.classList.toggle('sidebar-collapsed',state.sidebarCollapsed);const toggle=$('#sidebar-toggle');toggle.setAttribute('aria-expanded',String(!state.sidebarCollapsed));toggle.setAttribute('aria-label',state.sidebarCollapsed?'Show workspace sidebar':'Hide workspace sidebar');toggle.title=(state.sidebarCollapsed?'Show':'Hide')+' workspace sidebar (⌘/Ctrl B)';
 const divider=$('#sidebar-resizer');divider.hidden=state.sidebarCollapsed||state.chatVisible&&state.chatMaximized;
 divider.setAttribute('aria-valuemin',bounds.min);divider.setAttribute('aria-valuemax',bounds.max);divider.setAttribute('aria-valuenow',width);divider.setAttribute('aria-valuetext',width+' pixels wide');
 divider.setAttribute('aria-disabled',String(readOnly()&&Boolean(page?.left_width||tileLayout.editing())));const edge=$('#left-sidebar-toggle');edge.hidden=state.chatVisible&&state.chatMaximized;edge.textContent=state.sidebarCollapsed?'›':'‹';edge.title=edge.ariaLabel=state.sidebarCollapsed?'Open workspace sidebar':'Collapse workspace sidebar';applyProjectTreeHeight();
}
function resizeSidebar(width){
 const bounds=sidebarWidthBounds();width=Math.round(Math.max(bounds.min,Math.min(bounds.max,width)));
 if(activePage()?.left_width||tileLayout.editing()){if(!readOnly())tileLayout.resizeSidebar(width);}
 else {state.sidebarWidth=width;applyChatLayout();}
}
function chatWidthBounds(){
 const bodyWidth=$('.workspace-body')?.clientWidth||window.innerWidth;
 return {min:280,max:Math.max(280,Math.min(760,bodyWidth-(window.innerWidth>760?336:0)))};
}
function applyChatLayout(){
 const shell=$('.app-shell'),maximized=state.chatVisible&&state.chatMaximized&&!rightSidebarCollapsed;
 shell.classList.toggle('chat-maximized',maximized);document.body.classList.toggle('detached-chat',panelWindows.detached&&state.chatVisible);applySidebarLayout();
 $('#chat-panel').hidden=!state.chatVisible||rightSidebarCollapsed;
 const bounds=chatWidthBounds(),width=Math.round(Math.min(bounds.max,Math.max(bounds.min,activePage()?.right_width||state.chatWidth||390)));
 shell.style.setProperty('--chat-panel-width',width+'px');
 const divider=$('#chat-resizer');
 divider.hidden=!state.chatVisible||maximized;
 divider.setAttribute('aria-valuemin',String(bounds.min));divider.setAttribute('aria-valuemax',String(Math.round(bounds.max)));divider.setAttribute('aria-valuenow',String(width));divider.setAttribute('aria-valuetext',width+' pixels wide');
 const button=$('#chat-maximize'),label=maximized?'Restore agent panel':'Maximize agent chat';
 button.setAttribute('aria-label',label);button.title=label;button.setAttribute('aria-pressed',String(maximized));button.innerHTML=icon(maximized?'restore':'maximize');
 $('#chat-toggle').setAttribute('aria-expanded',String(state.chatVisible));
 if(state.data)dockChat();
}
function resizeChat(width){const bounds=chatWidthBounds();state.chatWidth=Math.round(Math.min(bounds.max,Math.max(bounds.min,width)));if(activePage()?.right_width||tileLayout.editing())tileLayout.resizeDock(state.chatWidth);else applyChatLayout();}
let globalPageZoom=1;
const panelZoom=installPanelZoom({editorFor:kind=>kind==='editor'?codeEditor:extraEditors[kind],globalZoom:delta=>{if(window.superSurferDesktop?.zoomWorkspace)window.superSurferDesktop.zoomWorkspace(delta).catch(error=>toast(error.message,true));else{globalPageZoom=delta===0?1:Math.max(.65,Math.min(2,globalPageZoom+delta*.1));document.documentElement.style.zoom=globalPageZoom;}}});
const responseCache=new Map(),pollUnchanged=Symbol('unchanged');let responseCacheToken;
async function api(path, body, requestOptions={}) {
  const headers={'Accept':'application/json'},token=sessionStorage.getItem('supersurfer-token');
  if(token)headers.Authorization=`Bearer ${token}`;
  if(token!==responseCacheToken){responseCache.clear();responseCacheToken=token;}
  const cacheable=body===undefined&&/^(state|chat|experiment|experiment-agents|project-agents|results|view-layout|worker-wakeups)(\?|$)/.test(path),cached=cacheable?responseCache.get(path):null;
  if(cached)headers['If-None-Match']=cached.etag;
  if(body!==undefined)headers['Content-Type']='application/json';
  const controller=new AbortController(),outer=requestOptions.signal,abort=()=>controller.abort();
  if(outer?.aborted)abort();else outer?.addEventListener('abort',abort,{once:true});
  const timeout=setTimeout(abort,body?.op==='run.queue'?180000:45000);
  try {
    const response=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
    if(response.status===304&&cached){const value=structuredClone(cached.data);value[pollUnchanged]=true;return value;}
    let data;
    try {data=await response.json();}catch(error){if(controller.signal.aborted)throw error;throw new Error(`Workspace service returned ${response.status}.`);}
    if(!response.ok){const error=new Error(data.error||`Request failed (${response.status})`);error.status=response.status;error.run_id=data.run_id;throw error;}
    if(cacheable&&response.headers.get('ETag')&&token===responseCacheToken){
      responseCache.delete(path);const size=JSON.stringify(data).length;
      if(size<=4_000_000)responseCache.set(path,{etag:response.headers.get('ETag'),data:structuredClone(data),size});
      while(responseCache.size>12||[...responseCache.values()].reduce((sum,row)=>sum+row.size,0)>8_000_000)responseCache.delete(responseCache.keys().next().value);
    }
    return data;
  }catch(error){
    if(error.name==='AbortError'&&!outer?.aborted)throw new Error('The workspace service did not respond in time. Check the connection and try again.');
    throw error;
  }finally{clearTimeout(timeout);outer?.removeEventListener('abort',abort);}
}
async function action(op,params={}) {return op==='code.save'?api('code/save',params):api('action',{op,params});}
function toast(message,error=false) {clearTimeout(toastTimeout);const el=$('#toast');el.textContent=message;el.classList.toggle('error',error);el.hidden=false;toastTimeout=setTimeout(()=>{el.hidden=true;},error?8000:4000);}
function safeUrl(value) {if(typeof value!=='string'||!/^https?:\/\//i.test(value.trim()))return null;try {const url = new URL(value,location.origin);return ['https:','http:'].includes(url.protocol)?url.href:null;} catch {return null;}}
function link(value,label,cls='') {const p=project();if(typeof value==='string'&&p?.repo&&value.startsWith(p.repo.replace(/\/$/,'')+'/')){const path=value.slice(p.repo.replace(/\/$/,'').length+1);if(!path.split('/').some(part=>['.','..',''].includes(part)))return `<button type="button" class="inline-file-link ${e(cls)}" data-workspace-file="${e(path)}" data-workspace-project="${e(p.id)}">${label}</button>`;}const url=safeUrl(value);return url?`<a href="${e(url)}" target="_blank" rel="noopener noreferrer" class="${e(cls)}">${label}</a>`:`<span class="${e(cls)}">${label}</span>`;}
function renderMath(source, displayMode, original) {
  // Limit expansion and dimensions; never trust TeX links, HTML or resource commands.
  if (!window.katex || source.length > 16000) return `<span class="math-fallback">${e(original)}</span>`;
  try {
    return window.katex.renderToString(source, {displayMode, throwOnError:false, trust:false,
      strict:'ignore', maxExpand:500, maxSize:20, macros:{}, output:'htmlAndMathml'});
  } catch { return `<span class="math-fallback">${e(original)}</span>`; }
}
function inline(text) {
  const tokens=[];
  const token = html => {tokens.push(html);return `\u0000${tokens.length-1}\u0000`;};
  // Protect code and links before recognizing math. Escaped dollars stay literal.
  let value=String(text).replace(/\u0000/g,'').replace(/`([^`]+)`/g,(_,code)=>token(`<code>${e(code)}</code>`));
  value=value.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g,(_,label,url)=>token(link(url,e(label))));
  value=value.replace(/\\\$/g,()=>token('$'));
  value=value.replace(/\\\(([\s\S]*?)\\\)|\$\$([^\u0000]*?)\$\$|(?<!\$)\$([^\s$\u0000](?:[^$\n\u0000]*?[^\s$\u0000])?)\$(?!\$)/g,
    (original,paren,display,dollar)=>token(renderMath(paren??display??dollar,display!==undefined,original)));
  value=e(value).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/__([^_]+)__/g,'<strong>$1</strong>').replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g,'<em>$1</em>').replace(/~~([^~]+)~~/g,'<del>$1</del>').replace(/\n/g,'<br>');
  return value.replace(/\u0000(\d+)\u0000/g,(_,index)=>tokens[Number(index)] || '');
}
function markdown(text='') {
  const lines=String(text).replace(/\r/g,'').split('\n'); let out=[],paragraph=[],list=null;
  const closeP=()=>{if(paragraph.length){out.push(`<p>${inline(paragraph.join('\n'))}</p>`);paragraph=[];}};
  const closeList=()=>{if(list){out.push(`</${list}>`);list=null;}};
  const flush=()=>{closeP();closeList();};
  for(let i=0;i<lines.length;i++) {
    const line=lines[i];
    if(/^\s*```/.test(line)){flush();const code=[];while(++i<lines.length&&!/^\s*```/.test(lines[i]))code.push(lines[i]);out.push(`<pre><code>${e(code.join('\n'))}</code></pre>`);continue;}
    // Consume standalone display blocks before Markdown treats TeX rows as lists/tables.
    const mathOpen=line.trimStart().startsWith('$$')?'$$':line.trimStart().startsWith('\\[')?'\\[':null;
    if(mathOpen){
      const close=mathOpen==='$$'?'$$':'\\]',parts=[line.trimStart().slice(mathOpen.length)];let end=i;
      while(!parts.at(-1).includes(close)&&end+1<lines.length)parts.push(lines[++end]);
      const at=parts.at(-1).indexOf(close);
      if(at>=0&&!parts.at(-1).slice(at+close.length).trim()){
        parts[parts.length-1]=parts.at(-1).slice(0,at);flush();
        out.push(`<div class="math-block">${renderMath(parts.join('\n'),true,lines.slice(i,end+1).join('\n'))}</div>`);i=end;continue;
      }
    }
    const heading=line.match(/^(#{1,4})\s+(.+)$/);if(heading){flush();out.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`);continue;}
    if(/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)){flush();out.push('<hr>');continue;}
    if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-{3,}/.test(lines[i+1])){
      flush();const cells=row=>row.replace(/^\s*\||\|\s*$/g,'').split('|').map(c=>c.trim());const head=cells(line);i++;
      let rows='';while(i+1<lines.length&&lines[i+1].includes('|')&&lines[i+1].trim()){i++;rows+=`<tr>${cells(lines[i]).map(c=>`<td>${inline(c)}</td>`).join('')}</tr>`;}
      out.push(`<div class="table-wrap"><table><thead><tr>${head.map(c=>`<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`);continue;
    }
    const item=line.match(/^\s*(?:([-*+])|\d+\.)\s+(.+)$/);if(item){closeP();const kind=item[1]?'ul':'ol';if(list!==kind){closeList();out.push(`<${kind}>`);list=kind;}out.push(`<li>${inline(item[2])}</li>`);continue;}
    if(/^>\s?/.test(line)){flush();const quotes=[line.replace(/^>\s?/,'')];while(i+1<lines.length&&/^>\s?/.test(lines[i+1]))quotes.push(lines[++i].replace(/^>\s?/,''));out.push(`<blockquote>${markdown(quotes.join('\n'))}</blockquote>`);continue;}
    if(!line.trim()){flush();continue;}
    closeList();paragraph.push(line);
  }
  flush();return out.join('');
}
const status = (value,detail='') => `<span title="${e(detail)}" class="badge ${e(String(value||'unknown').toLowerCase())}"><span class="status-dot ${e(String(value||'unknown').toLowerCase())}"></span>${e(value||'unknown')}</span>`;
function date(value,short=false) {if(!value)return 'Not recorded';const d=new Date(typeof value==='number'?value*1000:value);if(isNaN(d))return 'Not recorded';return short?d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):d.toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});}
function elapsed(value) {if(!value)return 'Not observed';const seconds=Math.max(0,(Date.now()-new Date(typeof value==='number'?value*1000:value).getTime())/1000);if(!Number.isFinite(seconds))return 'Not observed';if(seconds<60)return 'Just now';if(seconds<3600)return `${Math.floor(seconds/60)}m ago`;if(seconds<86400)return `${Math.floor(seconds/3600)}h ago`;return `${Math.floor(seconds/86400)}d ago`;}
const project = () => state.data?.projects.find(p=>p.id===state.projectId);
const experiment = () => state.data?.experiments.find(x=>x.id===state.experimentId);
const isWorkflow = () => state.view==='workspace'&&state.tab==='workflow'&&!!state.projectId;
const isSurfboard = () => state.view==='workspace'&&['surfboard','workflow'].includes(state.tab)&&!!state.projectId;
const scopeBoard = () => state.experimentId?(state.experiment?.id===state.experimentId?state.experiment:experiment())?.surfboard:project()?.surfboard;
const projectWorkflow = (p=project()) => (p?.id===state.projectId&&state.experimentId?scopeBoard()?.workflow:p?.surfboard?.workflow)||'research';
const itemLabel = (p=project()) => (p?.id===state.projectId&&state.experimentId?scopeBoard()?.item_label:null)||p?.surfboard?.item_label||({research:'experiment',software:'feature',web:'design task',writing:'writing task'}[projectWorkflow(p)])||'experiment';
const pluralItems = (p=project()) => itemLabel(p)+'s';
const leadLabel = (p=project()) => ({research:'Research lead',software:'Technical lead',web:'Design lead',writing:'Writing lead'}[projectWorkflow(p)]||'Project lead');
const workflowEditor=createWorkflow({api,action,readOnly:()=>readOnly(),advanced:()=>navigate({projectId:state.projectId,experimentId:state.experimentId,tab:'surfboard'}),open:()=>navigate({projectId:state.projectId,experimentId:state.experimentId,tab:scopeBoard()?.pages?.item?.[0]?.id||'overview'}),newTask:()=>showAddExperiment(),applied:()=>refreshState(true)});
const surfboardEditor=createSurfboardEditor({api,action,chooseBlock:chooseReusableBlock,readOnly:()=>readOnly(),experiments:id=>(state.data?.experiments||[]).filter(x=>x.project_id===id),models:()=>state.models,onChat:scope=>selectConversation(scope,{persist:false}),onApplied:()=>refreshState(true)});
const filePicker=createFilePicker({api}),panelFocus=createPanelFocus();
const panelWindows=createPanelWindows({capture:()=>({projectId:state.projectId,experimentId:state.experimentId,page:state.tab}),hasUnsaved:kind=>(extraEditors[kind]||codeEditor).hasUnsaved(state.projectId),presentation:kind=>(extraEditors[kind]||codeEditor).presentation(),prepareEditor:kind=>(extraEditors[kind]||codeEditor).prepareDetach?.(),onChange:()=>renderMain(),onError:error=>toast(error.message,true)});
function pickWorkspaceFile(onChoose,{pdfOnly=false,title='Open file',uploadTarget='editor'}={}){const p=project();if(!p)return;filePicker.open({projectId:p.id,repo:p.repo,pdfOnly,title,onChoose,onUpload:readOnly()?null:()=>fileUploads.pick(uploadTarget),onError:error=>toast(error.message,true)});}
async function loadWorkspacePdf(url,{signal}={}){const response=await fetch(url,{signal,headers:sessionStorage.getItem('supersurfer-token')?{Authorization:'Bearer '+sessionStorage.getItem('supersurfer-token')}:{}});if(!response.ok)throw new Error('PDF could not be loaded ('+response.status+').');return new Uint8Array(await response.arrayBuffer());}
const editorSettings=createEditorSettings({api,action,readOnly:()=>readOnly(),hasUnsaved:()=>codeEditor.hasUnsaved(),onConfigureExtension:configureEditorExtension});
const codeEditor=createCodeEditor({api,action,editorSettings,readOnly:()=>readOnly(),onOpenWorkspaceFile:path=>openPageCode({path}),onToggleFiles:()=>{if(panelWindows.detached){pickWorkspaceFile(path=>codeEditor.openFile(path));return;}const section=$('#workspace-files-section');if(state.sidebarCollapsed){state.sidebarCollapsed=false;section.open=true;applySidebarLayout();persistNavigation();}else section.open=!section.open;},onExtensions:()=>{if(panelWindows.detached){toast('Open workspace Settings → Editor in the main window.');return;}state.view='settings';renderMain();},onAskAgent:prepareCodeQuestion,onPickFile:pickWorkspaceFile,onUpload:()=>fileUploads.pick('editor'),onCompare:showCompareDialog,loadBytes:loadWorkspacePdf,onSave:record=>latexPanel.sourceSaved(record)});
const latexPanel=createLatexPanel({api,action,editorSettings,onError:error=>toast(error.message,true),readOnly:()=>readOnly(),hasUnsaved:projectId=>codeEditor.hasUnsaved(projectId),
 onSource:({path,...range})=>openPageCode({path,range}),
 onSetup:()=>prepareCodeQuestion('Set up the supported LaTeX compiler on this connected workspace. Check system pdfLaTeX, BibTeX, bubblewrap, prlimit and Poppler (pdfinfo, pdftotext, pdftoppm), then verify compile_latex can compile and inspect a small paper. Preserve project source and existing host environments. If administrator access is needed, explain the exact missing dependency and ask for that access. Do not use an external compiler service or search private service state.', 'Compiler setup message prepared. Send when ready.'),
 onSelection:record=>prepareCodeQuestion({kind:'pdf',project_id:state.projectId,path:record.source_path,label:record.source_path.split('/').at(-1)+' · p. '+record.page,text:'Compiled PDF · Source: '+record.source_path+' · PDF page '+record.page+' · Build '+record.build_id+'\nThis is PDF text, not a source-line mapping.\n'+record.text+(record.truncated?'\n[Selection truncated]':'')})});
const workspaceFiles=createRepositoryExplorer({api,onOpenFile:path=>openPageCode({path})});
let rightSidebarCollapsed=false;
function setRightSidebarCollapsed(value){
 rightSidebarCollapsed=value;document.body.classList.toggle('right-sidebar-collapsed',value);
 if(value){state.chatMaximized=false;panelFocus.closeContaining($('#chat-panel'));}
 else{state.chatVisible=true;chatRevealScope=chatLayoutKey();}
 const button=$('#right-sidebar-toggle');button.textContent=value?'‹':'›';button.title=button.ariaLabel=value?'Open right agent sidebar (⌘/Ctrl ⇧ B)':'Collapse right agent sidebar (⌘/Ctrl ⇧ B)';button.setAttribute('aria-expanded',String(!value));
 applyChatLayout();persistNavigation();
}
$('#right-sidebar-toggle').onclick=()=>setRightSidebarCollapsed(!rightSidebarCollapsed);
const portsPanel=createPorts();
const extraEditors=Object.fromEntries(['vscode','terminal'].map(kind=>[kind,createWorkbenchEditor({api,action,readOnly:()=>readOnly(),loadBytes:loadWorkspacePdf,onAskAgent:prepareCodeQuestion,onPickFile:pickWorkspaceFile,onUpload:()=>fileUploads.pick('editor'),onSave:record=>latexPanel.sourceSaved(record),onExtensions:()=>{state.view='settings';renderMain();}})]));
const repositoryExplorer=createRepositoryExplorer({api,onOpenFile:path=>openPageCode({path})});
const agentChangesTile=createAgentChanges({api,action,readOnly:()=>readOnly(),hasUnsaved:id=>codeEditor.hasUnsaved(id),onDecision:()=>Promise.all([codeEditor.refresh(),repositoryExplorer.refresh()]),onOpenChange:(scope,changeId)=>openPageCode({scope,changeId})});
const projectRuns = id => (state.data?.runs||[]).filter(r=>r.project_id===id);
const experimentRuns = id => (state.data?.runs||[]).filter(r=>r.experiment_id===id || (experiment()?.run_ids||[]).includes(r.id));
const readOnly = () => !!state.data?.read_only;
const disabled = () => readOnly()?' disabled title="Read-only connection"':'';
const empty = (title,description,button='') => `<div class="empty-state">${icon('layers')}<h2>${e(title)}</h2><p>${e(description)}</p>${button}</div>`;
function normalize(data){return {...data,projects:data.projects||[],experiments:data.experiments||[],agents:data.agents||[],runs:data.runs||[],hosts:data.hosts||[],queue:data.queue||{paused:false,run_ids:[]},settings:data.settings||{models:{},reasoning:{}},monitoring:data.monitoring||{}};}
const agentDirectories=new Map(),agentDirectoryVersions=new Map(),agentDirectoryBusy=new Set(),agentMutations=new Set(),conversationDrafts=new Map(),chatFetches=new Map();
let scopeSelectionRevision=0,scopeChoices={},surfboardPreviousChatVisible=null;
try{const saved=JSON.parse(localStorage.getItem('supersurfer-conversation-selection')||'{}');if(saved&&typeof saved==='object'&&!Array.isArray(saved))scopeChoices=saved;}catch{}
function surfboardScope(){return 'surfboard:'+(state.experimentId?'experiment:'+state.experimentId:state.projectId);}
function directoryKey(){if(isSurfboard())return surfboardScope();return state.view==='workspace'?(state.experimentId?'experiment:'+state.experimentId:state.projectId?'project:'+state.projectId:null):null;}
function currentAgentDirectory(){return isSurfboard()?{agents:scopedAgents()}:agentDirectories.get(directoryKey());}
function scopedAgents(){
 if(isSurfboard())return [{scope:surfboardScope(),name:'Surfboard configurator',owner:'supersurfer'}];
 const key=directoryKey(),directory=agentDirectories.get(key);if(directory?.agents)return directory.agents;
 if(state.view!=='workspace'||!state.projectId)return [{scope:'manager',name:'Workspace manager',owner:'supersurfer',archived:state.scope==='manager'&&state.chat?.archived}];
 if(state.experimentId)return [{scope:`experiment:${state.experimentId}`,name:itemLabel()+' agent',owner:'supersurfer',experiment_id:state.experimentId}];
 return [{scope:`project:${state.projectId}`,name:`${project()?.name||'Project'} ${leadLabel().toLowerCase()}`,owner:'supersurfer'}];
}
function selectedAgent(){return scopedAgents().find(agent=>agent.scope===state.scope)||(state.pinnedAgent?.scope===state.scope?{...state.pinnedAgent,name:state.pinnedAgent.name||state.chat?.agent?.name}:undefined);}
function chatOrigin(){
 if(state.pinnedAgent?.scope===state.scope)return state.pinnedAgent;
 const itemId=state.scope?.startsWith('experiment:')?state.scope.slice(11):selectedAgent()?.experiment_id||null;
 return {projectId:state.scope==='manager'?null:state.projectId,experimentId:itemId};
}
function chatAcceptsProject(id){return state.scope==='manager'||chatOrigin().projectId===id;}
function toggleAgentPin(){
 stashMessageDraft();
 if(state.pinnedAgent){state.pinnedAgent=null;syncAgentChooser();restoreMessageDraft();refreshChat(true);}
 else if(state.scope){const origin=chatOrigin();state.pinnedAgent={...origin,scope:state.scope,name:selectedAgent()?.name||state.chat?.agent?.name||'Agent',owner:'supersurfer'};}
 updateChatHeader();persistNavigation();
}
function rememberScope(scope){const key=directoryKey()||'manager';Object.defineProperty(scopeChoices,key,{value:scope,enumerable:true,writable:true,configurable:true});if(panelWindows.detached)return;try{localStorage.setItem('supersurfer-conversation-selection',JSON.stringify(scopeChoices));}catch{}}
const chatContext=createChatContext({scope:()=>state.scope,onChange:()=>updateChatHeader(),onError:error=>toast(error.message,true),onPickFile:()=>{const projectId=state.projectId,scope=state.scope;pickWorkspaceFile(async path=>{if(!chatAcceptsProject(projectId))throw new Error('This pinned agent belongs to another project. Unpin it or return to its project before attaching files.');if(state.projectId!==projectId||state.scope!==scope)throw new Error('The conversation changed. Choose the file again.');let text='Reference file '+path+' on the connected workspace. Read the current file before editing.';if(!/\.pdf$/i.test(path)){const file=await api('code/file?'+new URLSearchParams({project_id:projectId,path}));if(typeof file.content==='string')text+='\nSaved file excerpt:\n'+file.content.slice(0,16000)+(file.content.length>16000?'\n[Excerpt truncated]':'');}if(state.projectId!==projectId||state.scope!==scope)throw new Error('The conversation changed. Choose the file again.');await prepareCodeQuestion({kind:/\.pdf$/i.test(path)?'pdf':'file',project_id:projectId,path,label:path.split('/').at(-1),text});},{title:'Attach file',uploadTarget:'chat'});}});
const fileUploads=createFileUploads({
 capture(target){const p=project();if(!p||readOnly())throw new Error('Select a writable project before uploading.');if(target==='chat'&&!chatAcceptsProject(p.id))throw new Error('Return to the pinned agent’s project before attaching files.');if(target==='chat'&&(!state.scope||state.scope.startsWith('agent:')))throw new Error('Choose a SuperSurfer conversation first.');return {target,projectId:p.id,projectName:p.name,experimentId:state.experimentId,attachmentCount:target==='chat'?chatContext.get().length:0,scope:target==='chat'?state.scope:null};},
 onBusy:()=>updateChatHeader(),onError:error=>toast(error.message,true),notice:message=>toast(message),
 async onUploaded(file,original){
  for(const key of projectPanels.keys())if(key.startsWith('artifacts:'+original.projectId+':'))projectPanels.delete(key);
  if(original.target==='chat'){
   let text='User-uploaded file. Workspace path: '+file.absolute_path+'\nRead this file before drawing conclusions; uploading it does not request execution.';
   if(!file.name.toLowerCase().endsWith('.pdf')){const data=await api('code/file?'+new URLSearchParams({project_id:original.projectId,path:file.editor_path}));if(typeof data.content==='string')text+='\nSaved file excerpt:\n'+data.content.slice(0,16000)+(data.content.length>16000?'\n[Excerpt truncated]':'');}
   chatContext.add({kind:file.name.toLowerCase().endsWith('.pdf')?'pdf':'file',project_id:original.projectId,path:file.editor_path,label:file.name,text},original.scope);
  }else if(state.projectId===original.projectId&&state.experimentId===original.experimentId){await openPageCode({path:file.editor_path});}
  if(state.projectId===original.projectId){codeEditor.refresh();repositoryExplorer.refresh();}
 }
});
function stashMessageDraft(){if(state.scope)conversationDrafts.set(state.scope,$('#chat-input').value);}
function restoreMessageDraft(){ chatContext.render();$('#chat-input').value=conversationDrafts.get(state.scope)||'';resizeComposer(); }
function resizeComposer(){const input=$('#chat-input');input.style.height='auto';input.style.height=Math.min(140,Math.max(30,input.scrollHeight))+'px';}
function agentLabel(agent){
 if(agent.archived)return agent.busy?'Archived · Working':'Archived';
 if(agent.retired)return 'History only';
 if(agent.status==='awaiting_input')return 'Waiting for answer';
 if(agent.status==='awaiting_approval')return 'Waiting for approval';
 if(agent.busy)return 'Working';
 if(['error','failed','paused','stopped','interrupted'].includes(agent.status))return {error:'Failed',failed:'Failed',paused:'Paused',stopped:'Stopped',interrupted:'Interrupted'}[agent.status];
 return 'Idle';
}
let showArchivedAgents=false;
let agentsExpanded=false;try{agentsExpanded=localStorage.getItem("supersurfer-agents-expanded")==="true";}catch{}
function renderAgentChooser(){
 const container=$('#chat-agent-list');if(!container||!state.data)return;
 const directory=currentAgentDirectory(),agents=scopedAgents(),current=agents.filter(agent=>!agent.retired&&!agent.archived),previous=agents.filter(agent=>agent.retired&&!agent.archived),archived=agents.filter(agent=>agent.archived),creating=agentMutations.has('create:'+state.experimentId);
 const rows=items=>items.map(agent=>`<button class="agent-list-row ${state.scope===agent.scope?'selected':''}" data-conversation="${e(agent.scope)}" title="${e(agent.name)} · ${e(agentLabel(agent))}" aria-current="${state.scope===agent.scope?'true':'false'}"><span class="status-dot ${e(agent.retired?'unknown':agent.busy?'running':agent.status||'idle')}"></span><span class="agent-list-copy"><strong>${e(agent.name||'Agent')}</strong><small>${e(agentLabel(agent))}${agent.owner==='AutoML'?' · AutoML':''}${!state.experimentId&&agent.experiment_id?' · '+e(state.data.experiments.find(x=>x.id===agent.experiment_id)?.name||'Experiment'):''}</small></span>${icon('message')}</button>`).join('');
 const html=`<div class="agents-list-heading"><button type="button" class="agents-expand-button" data-action="toggle-agent-list" aria-expanded="${agentsExpanded}" aria-label="${agentsExpanded?'Collapse':'Expand'} agents section">${icon(agentsExpanded?'chevronDown':'chevron')}<span>Agents · ${current.length}</span></button><button type="button" class="icon-button" data-action="toggle-right-sidebar" aria-label="Hide right sidebar" title="Hide right sidebar">${icon('panel')}</button>${state.experimentId?`<button id="chat-new-agent" type="button" class="new-agent-button" data-action="new-experiment-agent" aria-label="New experiment agent" title="New agent" ${creating?'disabled':''}${disabled()}>${creating?'<span class="spinner"></span>':icon('plus')}<span>New agent</span></button>`:''}</div><div class="agent-list" ${agentsExpanded?'':'hidden'}>${rows(current)}${previous.length?`<div class="previous-agents-label">Previous agents</div>${rows(previous)}`:''}${archived.length?`<button type="button" class="archived-agents-toggle" data-action="toggle-archived-agents" aria-expanded="${showArchivedAgents}">${icon(showArchivedAgents?'chevronDown':'chevron')}Archived · ${archived.length}</button>${showArchivedAgents?rows(archived):''}`:''}</div>${directory?.error?`<div class="agent-list-error">${e(directory.error)} <button type="button" data-action="refresh-agents">Retry</button></div>`:directoryKey()&&!directory&&!isSurfboard()?'<div class="agent-list-loading">Loading conversations…</div>':''}`;
 if(container.dataset.signature===html)return;
 const scroll=container.querySelector('.agent-list')?.scrollTop||0,focused=container.contains(document.activeElement)?document.activeElement:null,focusedScope=focused?.dataset.conversation,focusedAction=focused?.dataset.action;
 container.dataset.signature=html;container.innerHTML=html;container.setAttribute('aria-label',`${state.experimentId?'Experiment':state.projectId&&state.view==='workspace'?'Project':'Workspace'} agents`);
 container.querySelector('.agent-list').scrollTop=scroll;
 if(focusedScope||focusedAction){[...container.querySelectorAll('button')].find(button=>focusedScope?button.dataset.conversation===focusedScope:button.dataset.action===focusedAction)?.focus({preventScroll:true});}
}
async function loadAgentDirectory({initial=false}={}){
 const key=directoryKey();if(!key||key.startsWith('surfboard:')||agentDirectoryBusy.has(key))return;
 const isExperiment=key.startsWith('experiment:'),id=key.slice(key.indexOf(':')+1),version=agentDirectoryVersions.get(key)||0,selectionRevision=scopeSelectionRevision;
 agentDirectoryBusy.add(key);
 try{
  const data=await api((isExperiment?'experiment-agents?experiment_id=':'project-agents?project_id=')+encodeURIComponent(id));
  if(version!==(agentDirectoryVersions.get(key)||0))return;
  agentDirectories.set(key,data);
  if(directoryKey()!==key)return;
  const preferred=isExperiment?data.selected_scope:scopeChoices[key],valid=data.agents?.some(agent=>agent.scope===preferred&&!agent.archived);
  if(initial&&!state.pinnedAgent&&scopeSelectionRevision===selectionRevision&&valid&&state.scope!==preferred)await selectConversation(preferred,{persist:false});
  syncAgentChooser();state.sidebarSignature='';syncNavigation();
 }catch(error){if(version!==(agentDirectoryVersions.get(key)||0))return;agentDirectories.set(key,{...(agentDirectories.get(key)||{}),error:error.message});if(directoryKey()===key){state.sidebarSignature='';syncNavigation();}}
 finally{agentDirectoryBusy.delete(key);}
}
async function selectConversation(scope,{persist=true}={}){
 const agents=scopedAgents(),agent=agents.find(item=>item.scope===scope);if(!agent)return;if(state.pinnedAgent?.scope!==scope)state.pinnedAgent=null;
 stashMessageDraft();scopeSelectionRevision++;const revision=scopeSelectionRevision,key=directoryKey();
 chatOpenPending=true;state.scope=scope;state.chat=null;state.chatSignature='';rememberScope(scope);restoreMessageDraft();state.chatVisible=true;applyChatLayout();persistNavigation();
 $('#chat-messages').innerHTML='<div class="chat-empty">Loading conversation…</div>';syncAgentChooser();state.sidebarSignature='';syncNavigation();refreshChat(true);
 if(persist&&!agent.retired&&!agent.archived&&key?.startsWith('experiment:')&&!readOnly()){
  const version=(agentDirectoryVersions.get(key)||0)+1;agentDirectoryVersions.set(key,version);
  try{const data=await action('experiment.agent.select',{experiment_id:state.experimentId,scope});if(version===agentDirectoryVersions.get(key)){agentDirectories.set(key,data);if(directoryKey()===key&&revision===scopeSelectionRevision){state.sidebarSignature='';syncNavigation();}}}
  catch(error){toast('Conversation opened, but its selection could not be saved: '+error.message,true);}
 }
}
async function createExperimentAgent(){
 const id=state.experimentId,key='experiment:'+id,busyKey='create:'+id;if(!id||readOnly()||agentMutations.has(busyKey))return;
 const selectionRevision=scopeSelectionRevision;agentMutations.add(busyKey);state.sidebarSignature='';syncNavigation();updateChatHeader();
 const version=(agentDirectoryVersions.get(key)||0)+1;agentDirectoryVersions.set(key,version);
 try{const result=await action('experiment.agent.create',{experiment_id:id});if(version===agentDirectoryVersions.get(key))agentDirectories.set(key,result);if(state.experimentId===id&&selectionRevision===scopeSelectionRevision)await selectConversation(result.scope,{persist:false});toast('New agent ready. Send a message to begin.');}
 catch(error){toast(error.message,true);}
 finally{agentMutations.delete(busyKey);state.sidebarSignature='';syncNavigation();updateChatHeader();}
}
async function resumeExperimentAgent(){
 const agent=selectedAgent(),scope=state.scope,id=agent?.experiment_id||state.experimentId,key='resume:'+scope;
 if(!id||!agent?.can_resume||agent.retired||readOnly()||agentMutations.has(key))return;
 agentMutations.add(key);updateChatHeader();
 try{await action('experiment.agent.resume',{experiment_id:id,scope});if(state.scope===scope){state.chat={...state.chat,busy:true};updateChatHeader();await refreshChat(true);}await loadAgentDirectory();}
 catch(error){toast(error.message,true);}
 finally{agentMutations.delete(key);updateChatHeader();}
}
function renderAgentSessionState(){
 const el=$('#chat-session-state'),agent=selectedAgent(),retired=state.chat?.retired===true||agent?.retired===true,archived=state.chat?.archived===true||agent?.archived===true,canResume=agent?.can_resume&&!retired&&!archived&&!readOnly()&&(['error','failed','interrupted','paused','stopped'].includes(agent?.status)||['incomplete','blocked'].includes(agent?.task_state)),status=agent?.status,failed=['error','failed','interrupted'].includes(status),paused=status==='paused',resuming=agentMutations.has('resume:'+state.scope);
 $('#chat-form').hidden=retired||archived;
 const note=archived?'Archived chat. History, existing work and monitoring are preserved. Restore to continue here.':retired?'Previous AutoML agent · saved history. Start a new agent for new work.':failed?'The previous turn ended. Continue this conversation or send a new message.':paused?'This agent is paused. Resume it to continue in its original conversation.':'';
 el.hidden=!note&&!canResume;
 el.innerHTML=`${note?`<p>${e(note)}</p>`:''}${archived?`<button type="button" class="button small-button" data-action="archive-agent"${disabled()}>Restore chat</button>`:''}${canResume?`<button type="button" class="button small-button" data-action="resume-experiment-agent" ${resuming||agent.busy||state.chat?.busy?'disabled':''}>${icon('play')}${resuming?'Continuing…':paused?'Resume agent':'Continue agent'}</button>`:''}`;
}

function experimentWorkerScope(x=state.experiment||experiment()){
 if(!x)return null;const own=`experiment:${x.id}`,directory=agentDirectories.get('experiment:'+x.id),candidate=x.work_scope;
 if(directory?.agents?.some(agent=>agent.scope===candidate&&!agent.archived))return candidate;
 if(directory?.agents?.some(agent=>agent.scope===directory.selected_scope&&!agent.retired&&!agent.archived))return directory.selected_scope;
 return own;
}
function currentScope(){if(state.pinnedAgent)return state.pinnedAgent.scope;const agents=scopedAgents(),directory=currentAgentDirectory(),key=directoryKey(),preferred=state.experimentId?directory?.selected_scope:scopeChoices[key||'manager'];return agents.some(agent=>agent.scope===preferred&&!agent.archived)?preferred:agents.find(agent=>!agent.archived&&!agent.retired)?.scope||agents[0]?.scope||'manager';}
const archivedItemProjects=new Set();
const visibleProjectItems=projectId=>(state.data?.experiments||[]).filter(item=>item.project_id===projectId&&(!item.archived||archivedItemProjects.has(projectId)));
function archivedItemsToggle(projectId){const count=(state.data?.experiments||[]).filter(item=>item.project_id===projectId&&item.archived).length;return count?`<button class="archived-items-toggle" data-action="toggle-archived-items" data-id="${e(projectId)}">${archivedItemProjects.has(projectId)?'Hide':'Show'} archived · ${count}</button>`:'';}
function sidebarTaskRow(x){return `<button class="experiment-row ${state.experimentId===x.id?'selected':''}" data-experiment="${e(x.id)}"><span class="status-dot ${e(x.status||'unknown')}"></span><span class="exp-name">${e(x.name)}</span></button>`;}
function archivedProjectFolder(id){const rows=(state.data?.experiments||[]).filter(item=>item.project_id===id&&item.archived);return rows.length?`<details class="archived-task-folder" data-archived-project="${e(id)}" ${archivedItemProjects.has(id)?'open':''}><summary>${icon('folder')}<span>Archived</span><small>${rows.length}</small></summary><div>${rows.map(sidebarTaskRow).join('')}</div></details>`:'';}
async function archiveTask(id,archived){await action('experiment.archive',{id,archived});await refreshState(true);toast(archived?'Archived. Existing work continues.':'Restored.');}
async function renameTask(id){
 let current=await api('experiment?id='+encodeURIComponent(id));
 openModal('Rename task',`<form>${field('Task name','name',{value:current.name,required:true,maxlength:160})}${formFooter('Rename')}</form>`,'rename-task');
 const input=$('#modal input[name=name]');input.focus();input.select();
 bindModalForm(async fd=>{
  const name=fd.get('name').trim();
  try{await action('experiment.rename',{id,name,version:current.version});}
  catch(error){if(error.status!==409)throw error;current=await api('experiment?id='+encodeURIComponent(id));throw new Error(`This task changed. Its current name is “${current.name}”. Your new name is kept; review it and press Rename again.`);}
  closeModal();await refreshState(true);toast('Task renamed.');
 });
}
let archivedProjectsExpanded=false;
function projectTreeGroup(p){return `<div class="project-group"><button class="project-row ${state.projectId===p.id&&!state.experimentId?'selected':''}" data-project="${e(p.id)}">${icon('folder')}<span class="project-name">${e(p.name)}</span><span class="chevron">${icon(state.projectId===p.id?'chevronDown':'chevron')}</span></button>${state.projectId===p.id?(state.data?.experiments||[]).filter(x=>x.project_id===p.id&&!x.archived).map(sidebarTaskRow).join('')+`<button class="new-experiment" data-action="add-experiment"${disabled()}>${icon('plus')}New ${e(itemLabel(p))}</button>${archivedProjectFolder(p.id)}`:''}</div>`;}
async function archiveProject(id,archived){await action('project.archive',{id,archived});await refreshState(true);toast(archived?'Project archived. Existing work continues.':'Project restored.');}
function syncNavigation(){
 $$('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===state.view));
 const p=project(),x=experiment();
 $('#breadcrumb').innerHTML=state.view==='compute'?`<span>Workspace</span><span class="divider">/</span><span>Compute</span>`:state.view==='settings'?`<span>Workspace</span><span class="divider">/</span><span>Settings</span>`:p?`<button data-project="${e(p.id)}">${e(p.name)}</button>${x?`<span class="divider">/</span><span>${e(x.name)}</span>`:''}`:'Workspace';
 const count=state.data?queuedRuns().length:0;$('#queue-count').textContent=count||'';
 const sig=JSON.stringify([state.data?.projects,state.data?.experiments,state.projectId,state.experimentId,[...archivedItemProjects],archivedProjectsExpanded]);if(sig!==state.sidebarSignature){state.sidebarSignature=sig;
 const projects=state.data?.projects||[],archivedProjects=projects.filter(p=>p.archived);
 $('#project-tree').innerHTML=projects.length?projects.filter(p=>!p.archived).map(projectTreeGroup).join('')+(archivedProjects.length?`<details class="archived-project-folder" ${archivedProjectsExpanded?'open':''}><summary>${icon('folder')}<span>Archived projects</span><small>${archivedProjects.length}</small></summary>${archivedProjects.map(projectTreeGroup).join('')}</details>`:''):'<div class="sidebar-placeholder">Your projects will appear here.</div>';
 }
 renderAgentChooser();
}
function connectionStatus(error){
 const connected=state.data?.connected&&!error;$('#connection-label').textContent=connected?'Workspace connected':state.data?'Connection interrupted':'Workspace unavailable';$('#connection-dot').className=`status-dot ${connected?'connected':'error'}`;
 const banner=$('#connection-banner');
 if(error||state.data?.error||!connected){banner.hidden=false;banner.textContent=`${state.data?'Showing last available workspace. ':''}${error?.message||state.data?.error||'AutoML is not connected.'}`;}
 else if(readOnly()){banner.hidden=false;banner.textContent='Read-only connection · Inspect your real workspace. Agent messages and run actions are disabled.';}
 else {banner.hidden=true;}
}
let editorDefaultsLoaded=false;
async function refreshState(force=false){if(stateBusy){if(force){await new Promise(resolve=>stateWaiters.push(resolve));return refreshState(true);}return;}stateBusy=true;try{
 const incoming=normalize(await api('state'));state.data=incoming;
 if(!editorDefaultsLoaded){try{await editorSettings.load();editorDefaultsLoaded=true;}catch{}}
 restoreNavigation(incoming);
 connectionStatus();syncNavigation();syncAgentChooser();
 const sig=JSON.stringify([incoming.projects,incoming.experiments,incoming.runs,incoming.hosts,incoming.queue,incoming.settings,incoming.monitoring,incoming.connected,incoming.read_only]);
 if(force||sig!==state.stateSignature){state.stateSignature=sig;if(!state.edit&&!$('#modal').open&&!(state.view==='settings'&&($('#settings-form')?.dataset.dirty==='true'||editorSettings.dirty()||workspacePermissionSaving))&&!$('#project-compute-form')?.dataset.dirty)renderMain();else renderPending=true;}
 if(!state.edit&&!$('#modal').open)await Promise.all([state.experimentId?fetchExperiment():Promise.resolve(),loadAgentDirectory({initial:!currentAgentDirectory()})]);
 }catch(error){connectionStatus(error);if(!state.data){$('#main').innerHTML=empty('Connect your research workspace',error.message,`<button class="button primary" data-action="${error.status===401?'auth':'refresh'}">${error.status===401?'Enter connection token':'Try again'}</button>`);if(error.status===401&&!$('#modal').open)showAuth();}}finally{stateBusy=false;const waiting=stateWaiters;stateWaiters=[];waiting.forEach(resolve=>resolve());}}
async function navigate({view='workspace',projectId=state.projectId,experimentId=null,tab}={}){
 persistNavigation();tab=tab??taskTabs[taskTabKey(projectId,experimentId)]??'overview';
 panelFocus.close();const wasBoard=!!isSurfboard();stashMessageDraft();scopeSelectionRevision++;if(isSurfboard()&&!['surfboard','workflow'].includes(tab)&&surfboardPreviousChatVisible!==null){state.chatVisible=surfboardPreviousChatVisible;surfboardPreviousChatVisible=null;applyChatLayout();}if(state.edit){stashEditor();}state.view=view;state.projectId=projectId;state.experimentId=experimentId;state.tab=tab;if(isSurfboard()&&!wasBoard&&!state.pinnedAgent){surfboardPreviousChatVisible=state.chatVisible;state.chatVisible=isWorkflow();state.chatMaximized=false;applyChatLayout();}state.edit=false;state.experiment=null;state.experimentRequest++;state.scope=state.pinnedAgent?.scope||null;if(!state.pinnedAgent){state.chat=null;state.chatSignature='';}state.sidebarSignature='';persistNavigation();syncNavigation();renderMain();syncAgentChooser();restoreMessageDraft();refreshChat(true);await Promise.all([experimentId?fetchExperiment(true):Promise.resolve(),!experimentId&&tab==='compute'?loadProjectCompute(projectId,{force:true}).catch(()=>{}):Promise.resolve(),loadAgentDirectory({initial:true})]);}
async function fetchExperiment(force=false){const id=state.experimentId;if(!id)return;const request=++state.experimentRequest;try{const data=await api('experiment?id='+encodeURIComponent(id));if(id!==state.experimentId||request!==state.experimentRequest)return;const firstLoad=!state.experiment;const changed=!state.experiment||data.version!==state.experiment.version||data.status!==state.experiment.status||data.archived!==state.experiment.archived||data.status_detail!==state.experiment.status_detail||JSON.stringify(data.brief)!==JSON.stringify(state.experiment.brief)||JSON.stringify(data.pages)!==JSON.stringify(state.experiment.pages)||JSON.stringify(data.results_review)!==JSON.stringify(state.experiment.results_review)||JSON.stringify(data.view_layout)!==JSON.stringify(state.experiment.view_layout)||data.markdown!==state.experiment.markdown||data.wandb_url!==state.experiment.wandb_url||JSON.stringify(data.wandb_sync)!==JSON.stringify(state.experiment.wandb_sync)||data.review_interval_minutes!==state.experiment.review_interval_minutes||data.work_scope!==state.experiment.work_scope||data.work_state!==state.experiment.work_state||data.work_error!==state.experiment.work_error;let pageCacheChanged=false;for(const page of data.pages||[]){const key=data.id+':'+page.id,cached=markdownPages.get(key);if(cached?.data&&page.version&&cached.data.version!==page.version&&!cached.loading){markdownPages.delete(key);pageCacheChanged=true;}}
 state.experiment=data;if((changed||force||pageCacheChanged)&&!state.edit&&!$('#modal').open)renderMain();if(pageHasTile('results')){loadResultPages(force||firstLoad).then(()=>{if(!chosenResultPage())loadMetrics(force||firstLoad);});}if(pageHasTile('overview'))loadWorkerWakeups(id);}catch(error){if(force)toast(error.message,true);}}
function renderMain(){
 if(tileLayout.active())return;
 const filesSection=$('#workspace-files-section'),showFiles=state.view==='workspace'&&!!state.projectId&&(pageHasTile('editor')||state.tab==='_files');filesSection.hidden=!showFiles;if(showFiles)workspaceFiles.mount($('#workspace-files-tree'),{projectId:state.projectId,repo:project()?.repo});else workspaceFiles.unmount();
 codeEditor.prepareScope({projectId:state.projectId,experimentId:state.experimentId});
 for(const editor of Object.values(extraEditors))editor.prepareScope?.({projectId:state.projectId,experimentId:state.experimentId});
 if(state.data)ensureLayoutTab();
 const archiveItem=$('#archive-item'),item=state.experiment||experiment();archiveItem.hidden=state.view!=='workspace'||!state.experimentId;archiveItem.disabled=readOnly();archiveItem.setAttribute('aria-label',item?.archived?'Restore work item':'Archive work item');archiveItem.title=(item?.archived?'Restore':'Archive')+' '+itemLabel()+' · existing work continues';archiveItem.innerHTML=icon(item?.archived?'history':'archive');
 for(const id of ['window-layout-toggle','dock-layout-toggle'])$('#'+id).hidden=!savedActivePage()||panelWindows.detached;
 const arrange=$('#arrange-page');arrange.hidden=state.view!=='workspace'||!state.projectId||panelWindows.detached;arrange.disabled=readOnly()||tileLayout.editing()||tileLayout.saving()||!!state.experimentId&&!state.experiment;arrange.setAttribute('aria-expanded',String(tileLayout.editing()));$('#rearrange-overlay').hidden=!tileLayout.editing();
 const arrangeControls=$('#tile-arrange-controls'),arrangeMarkup=tileLayout.toolbar();if(arrangeControls.innerHTML!==arrangeMarkup)arrangeControls.innerHTML=arrangeMarkup;
 const filesButton=$('#sidebar-add-files'),fileTile=activePage()?.tiles.find(tile=>tile.kind==='file_explorer');
 filesButton.hidden=!savedActivePage()||fileTile?.placement==='left'||!pageTileCatalog().some(tile=>tile.kind==='file_explorer');
 filesButton.disabled=readOnly()||!fileTile&&activePage()?.tiles.length>=16;filesButton.textContent=fileTile?'Move file browser here':'+ Add file browser';
 if(!isTilePage())clearPageTileDocks();
 if(!state.data)return;
 $('#layout-toggle').hidden=state.view!=='workspace'||!state.projectId;
 renderProjectSlots();
 const workflowMode=isWorkflow();$('.app-shell').classList.toggle('workflow-active',!!workflowMode);$('#main').classList.toggle('workflow-main',!!workflowMode);
 if(workflowMode){state.chatVisible=true;$('#main').classList.remove('surfboard-main');surfboardEditor.unmount();codeEditor.unmount();latexPanel.unmount();const main=$('#main');if(!$('#workflow-root')||$('#workflow-root').dataset.key!==state.projectId+':'+(state.experimentId||'')){ensureViewDock().append($('#chat-panel'));main.innerHTML=`<div class="sb-page-navigation"><button class="button small-button" data-tab="overview">← ${e(state.experimentId?experiment()?.name||'Task':project()?.name||'Project')}</button></div><div id="workflow-root" class="workflow-shell" data-key="${e(state.projectId+':'+(state.experimentId||''))}"></div>`;}workflowEditor.mount($('#workflow-root'),{projectId:state.projectId,experimentId:state.experimentId});dockChat();return;}
 if($('#workflow-root')?.contains($('#chat-panel')))ensureViewDock().append($('#chat-panel'));workflowEditor.unmount();
 const boardMode=isSurfboard(),boardMain=$('#main');boardMain.classList.toggle('surfboard-main',!!boardMode);
 if(boardMode){boardMain.classList.remove('tiled-page-main');delete boardMain.dataset.tilePageKey;repositoryExplorer.unmount();agentChangesTile.unmount();codeEditor.unmount();latexPanel.unmount();ensureViewDock().append($('#chat-panel'));if($('#surfboard-root')?.dataset.project!==state.projectId+':'+(state.experimentId||''))boardMain.innerHTML=`<div class="sb-page"><div class="sb-page-navigation">${projectTabs('surfboard')}</div><div id="surfboard-root"></div></div>`;const boardNav=$('.sb-page-navigation',boardMain),boardTabs=projectTabs('surfboard');if(boardNav&&boardNav.innerHTML!==boardTabs)boardNav.innerHTML=boardTabs;surfboardEditor.mount($('#surfboard-root'),state.projectId,state.experimentId);dockChat();return;}
 surfboardEditor.unmount();
 if(state.tab==='_files'){renderFileViewer();return;}
 if(state.tab==='_todos'){renderTodosPage();return;}
 $('#main').classList.toggle('tiled-page-main',!!isTilePage());
 if(!isTilePage())delete $('#main').dataset.tilePageKey;
 if(isTilePage()){renderTilePage();return;}
 repositoryExplorer.unmount();agentChangesTile.unmount();
 const layout=currentLayout(),scopeKey=state.projectId+':'+(state.experimentId||'');
 const special=layout&&(state.tab==='empty-layout'||['editor','chat','documents','preview'].includes(state.tab)||!state.experimentId&&['runs','results'].includes(state.tab));
 const specialMain=$('#main');specialMain.classList.toggle('configured-editor-main',!!special&&['editor','chat'].includes(state.tab));
 if(special){
  const key=scopeKey+':'+state.tab;
  if(specialMain.dataset.viewKey!==key||!['editor','chat'].includes(state.tab)){
   if($('#main').contains($('#chat-panel')))ensureViewDock().append($('#chat-panel'));
   codeEditor.unmount();specialMain.dataset.viewKey=key;
   const label=state.experimentId?(state.experiment||experiment())?.name:project()?.name;
   specialMain.innerHTML=`<div class="configured-page"><header class="configured-heading"><strong>${e(label||'Workspace')}</strong><span>${e(project()?.repo||'')}</span></header>${layoutTabsMarkup()}<div class="configured-view-content">${state.tab==='empty-layout'?empty('No main views','Use Layout to put a view in the main area.', '<button class="button" data-action="configure-layout">Configure layout</button>'):configuredViewBody(state.tab)}</div></div>`;
  }
  const currentTabs=specialMain.querySelector('.configured-tabs');const nextTabs=layoutTabsMarkup();if(currentTabs&&currentTabs.outerHTML!==nextTabs)currentTabs.outerHTML=nextTabs;
  specialMain.classList.remove('results-full-page');syncConfiguredEditors();bindMain();return;
 }
 delete specialMain.dataset.viewKey;
 if($('#main').contains($('#chat-panel')))ensureViewDock().append($('#chat-panel'));
 if(state.tab!=='editor'&&!$('#project-view-panels #code-editor-root'))codeEditor.unmount();
 const preview=$('#result-preview'),selected=state.view==='workspace'&&state.experimentId&&pageHasTile('results')&&chosenResultPage();
 $('#main').classList.toggle('results-full-page',!!selected);
 if(preview&&selected&&preview.getAttribute('src')===selected.preview_url){const tabs=$('#main .result-page-tabs'),markup=renderResultTabs();if(tabs&&tabs.outerHTML!==markup)tabs.outerHTML=markup;const attempts=$('#main .results-attempts'),attemptMarkup=renderResultAttempts();if(attempts&&attempts.outerHTML!==attemptMarkup)attempts.outerHTML=attemptMarkup;else if(!attempts&&attemptMarkup)preview.insertAdjacentHTML('beforebegin',attemptMarkup);dockChat();const current=state.experiment||experiment(),badge=$('#main .metadata-line .badge');if(current&&badge)badge.outerHTML=status(current.status,current.status_detail);return;}
 const main=$('#main');if(state.view==='settings'&&$('#settings-form')){syncSettingsView();renderPending=false;return;}const scroll=main.scrollTop,openHosts=$$('details[data-host][open]',main).map(d=>d.dataset.host);
 if(state.view==='compute')main.innerHTML=renderCompute();else if(state.view==='settings')main.innerHTML=renderSettings();else if(state.experimentId)main.innerHTML=renderExperiment();else main.innerHTML=renderProject();
 for(const details of $$('details[data-host]',main))if(openHosts.includes(details.dataset.host))details.open=true;main.scrollTop=scroll;renderPending=false;bindMain();syncConfiguredEditors();
}
const projectComputeCache=new Map(),projectComputeDrafts=new Map(),projectComputeRequests=new Map(),projectComputeSaving=new Set();
function computeDraft(id=state.projectId){return projectComputeDrafts.get(id)||projectComputeCache.get(id)?.data;}
function copyCompute(value){return JSON.parse(JSON.stringify(value));}
async function loadProjectCompute(id=state.projectId,{force=false}={}){
 if(!id)return null;if(projectComputeRequests.has(id))return projectComputeRequests.get(id);
 if(!force&&projectComputeCache.get(id)?.data)return projectComputeCache.get(id).data;
 const request=(async()=>{try{const data=await api('project-compute?project_id='+encodeURIComponent(id));const config={project_id:id,version:data.version??0,defaults:data.defaults||{},nodes:data.nodes||[]};projectComputeCache.set(id,{data:config});return config;}catch(error){projectComputeCache.set(id,{...projectComputeCache.get(id),error:error.message});throw error;}finally{projectComputeRequests.delete(id);if(state.projectId===id&&pageHasTile('compute')&&!state.experimentId&&!$('#project-compute-form')?.dataset.dirty)renderMain();}})();projectComputeRequests.set(id,request);return request;
}
function readComputeForm(){
 const form=$('#project-compute-form'),current=computeDraft();if(!form||!current)return;const draft=copyCompute(current);
 const fd=new FormData(form);draft.defaults=Object.fromEntries(['python','data_path','storage_path'].map(key=>[key,String(fd.get('default_'+key)||'').trim()]));
 draft.nodes=draft.nodes.map((node,index)=>{const repoInput=form.elements.namedItem(`node_${index}_repo_path`);if(repoInput)repoInput.required=fd.get(`node_${index}_enabled`)==='on';const next={host_id:node.host_id,enabled:fd.get(`node_${index}_enabled`)==='on',repo_path:String(fd.get(`node_${index}_repo_path`)||'').trim(),gpu_indices:fd.getAll(`node_${index}_gpu`).map(Number)};for(const key of ['python','data_path','storage_path']){const value=String(fd.get(`node_${index}_${key}`)||'').trim();if(value)next[key]=value;}return next;});projectComputeDrafts.set(state.projectId,draft);form.dataset.dirty='true';
}
function nodeGPUIndices(host,node){return [...new Set([...(host?.gpus||[]),...(node.gpu_indices||[])].map(Number).filter(Number.isInteger))].sort((a,b)=>a-b);}
function renderProjectCompute(p){
 const cached=projectComputeCache.get(p.id),draft=computeDraft(p.id);if(!cached&&!projectComputeRequests.has(p.id))loadProjectCompute(p.id).catch(()=>{});
 const heading=`<div class="page-eyebrow">${icon('server')}Project compute</div><div class="page-heading"><div><h1>${e(p.name)} compute</h1><p>Choose the machines and GPUs this project can use.</p></div><div class="heading-actions">${refreshComputeButton()}<button class="button" data-action="onboard-project-host"${disabled()}>${icon('message')}Ask lead</button></div></div>${projectTabs('compute')}`;
 if(!draft)return `<div class="page">${heading}${cached?.error?`<div class="notice error">${e(cached.error)} <button class="button small-button" data-action="reload-project-compute">Retry</button></div>`:'<div class="loading-state"><span class="spinner"></span><p>Loading project compute</p></div>'}</div>`;
 const unused=state.data.hosts.filter(host=>!draft.nodes.some(node=>node.host_id===host.id)),defaults=draft.defaults||{};
 return `<div class="page">${heading}<form id="project-compute-form" data-project="${e(p.id)}" data-dirty="${projectComputeDrafts.has(p.id)?'true':''}"><fieldset class="compute-fields" ${readOnly()||projectComputeSaving.has(p.id)?'disabled':''}><section class="settings-block"><h2>Shared defaults</h2><p>Absolute paths used on each machine unless that machine overrides them.</p><div class="compute-default-grid">${field('Python executable','default_python',{value:defaults.python,placeholder:'/opt/venv/bin/python'})}${field('Dataset path','default_data_path',{value:defaults.data_path,placeholder:'/data/dataset'})}${field('Storage path','default_storage_path',{value:defaults.storage_path,placeholder:'/data/runs'})}</div></section><section class="settings-block"><div class="compute-nodes-heading"><div><h2>Eligible machines</h2><p>The scheduler chooses an available machine and GPUs from this pool.</p></div></div><div class="compute-node-list">${draft.nodes.map((node,index)=>{const host=state.data.hosts.find(item=>item.id===node.host_id),indices=nodeGPUIndices(host,node),selected=node.gpu_indices||indices;return `<section class="compute-node" data-compute-node="${index}"><div class="compute-node-heading"><label><input type="checkbox" name="node_${index}_enabled" ${node.enabled!==false?'checked':''}><strong>${e(host?.name||node.host_id)}</strong></label><span class="compute-node-target">${e(host?.target||'Workspace computer')}</span><button type="button" class="icon-button" data-action="remove-compute-node" data-node-index="${index}" aria-label="Remove ${e(host?.name||'machine')} from project">${icon('close')}</button></div>${!host?'<p class="notice warn">This machine is no longer registered. Remove it or ask the lead to reconnect it.</p>':''}${field('Repository on this machine',`node_${index}_repo_path`,{value:node.repo_path,placeholder:'/home/researcher/project',required:node.enabled!==false})}<div class="compute-gpu-field"><span>Allowed GPUs</span><div class="compute-gpu-choices">${indices.length?indices.map(gpu=>`<label><input type="checkbox" name="node_${index}_gpu" value="${gpu}" ${selected.includes(gpu)?'checked':''}>GPU ${gpu}</label>`).join(''):'<span class="muted small">No registered GPUs. This machine can run CPU-only tasks.</span>'}</div><small>Select the subset available to this project. Leave empty for CPU-only runs.</small></div><details class="compute-node-overrides"><summary>Machine-specific paths <span class="muted">Optional overrides</span></summary><div class="compute-default-grid">${field('Python executable',`node_${index}_python`,{value:node.python,placeholder:defaults.python||'Use shared default'})}${field('Dataset path',`node_${index}_data_path`,{value:node.data_path,placeholder:defaults.data_path||'Use shared default'})}${field('Storage path',`node_${index}_storage_path`,{value:node.storage_path,placeholder:defaults.storage_path||'Use shared default'})}</div></details></section>`;}).join('')}</div>${!draft.nodes.length?'<p class="compute-pool-empty">Add a registered machine below, or ask your lead to set up a new host.</p>':''}<div class="compute-add-node"><label class="visually-hidden" for="compute-add-host">Registered machine</label><select id="compute-add-host" class="control" ${unused.length?'':'disabled'}>${unused.length?unused.map(host=>`<option value="${e(host.id)}">${e(host.name)}</option>`).join(''):'<option value="">No other registered machines</option>'}</select><button type="button" class="button" data-action="add-compute-node" ${unused.length?'':'disabled'}>${icon('plus')}Add machine</button></div></section><div id="compute-form-error" class="notice error" role="alert" hidden></div><div class="compute-save-row"><span class="muted small">Changes affect new run drafts.</span><button type="button" class="button" data-action="reload-project-compute">Reload saved</button><button type="submit" class="button primary">${icon('check')}Save compute pool</button></div></fieldset></form></div>`;
}
async function saveProjectCompute(event){
 event.preventDefault();const form=event.currentTarget,id=form.dataset.project;if(projectComputeSaving.has(id))return;
 readComputeForm();const draft=copyCompute(computeDraft(id)),fields=$('fieldset',form),error=$('#compute-form-error',form);
 projectComputeSaving.add(id);fields.disabled=true;error.hidden=true;
 try{
  const result=await action('project.compute.save',draft),saved={project_id:id,version:result.version??draft.version,defaults:result.defaults||draft.defaults,nodes:result.nodes||draft.nodes};
  projectComputeCache.set(id,{data:saved});projectComputeDrafts.delete(id);projectComputeSaving.delete(id);form.dataset.dirty='';
  if(state.projectId===id&&pageHasTile('compute')&&!state.experimentId)renderMain();toast('Project compute pool saved.');
 }catch(err){
  if(form.isConnected){error.textContent=err.status===409?err.message+' Your edits are preserved. Reload saved settings to resolve the conflict.':err.message;error.hidden=false;}
 }finally{
  projectComputeSaving.delete(id);if(fields.isConnected)fields.disabled=readOnly();
  const current=$('#project-compute-form');if(current?.dataset.project===id)$('fieldset',current).disabled=readOnly();
 }
}
async function addComputeNode(){readComputeForm();const draft=computeDraft(),host=state.data.hosts.find(item=>item.id===$('#compute-add-host')?.value);if(!draft||!host||draft.nodes.some(node=>node.host_id===host.id))return;draft.nodes.push({host_id:host.id,enabled:true,repo_path:host.target?'':project()?.repo||'',gpu_indices:nodeGPUIndices(host,{})});renderMain();$('#project-compute-form').dataset.dirty='true';$(`[data-compute-node="${draft.nodes.length-1}"] input[name$="repo_path"]`)?.focus();}
async function removeComputeNode(index){readComputeForm();const draft=computeDraft();if(!draft||!Number.isInteger(index))return;draft.nodes.splice(index,1);renderMain();$('#project-compute-form').dataset.dirty='true';}
async function reloadProjectCompute(){const id=state.projectId;projectComputeDrafts.delete(id);$('#project-compute-form')?.removeAttribute('data-dirty');await loadProjectCompute(id,{force:true});}
async function openHostOnboarding(){const id=state.projectId,p=project();if(!id)return;if(state.experimentId)await navigate({projectId:id,tab:'compute'});await loadAgentDirectory();await selectConversation('project:'+id,{persist:false});const prompt=`Help me add a compute host to project ${p.name}. Check its SSH connection, GPUs, repository, Python environment, dataset and storage paths, then configure the project compute pool. Ask me for any missing details.`;const existing=$('#chat-input').value.trim();$('#chat-input').value=existing?existing+'\n\n'+prompt:prompt;stashMessageDraft();$('#chat-input').focus();toast('Message prepared for your lead. Send when ready.');}


const projectPanels=new Map(),projectPanelRequests=new Set();
async function loadProjectPanel(kind,id=state.projectId,path=''){
 const key=kind+':'+id+':'+path;if(projectPanelRequests.has(key))return;projectPanelRequests.add(key);
 try{const data=await api((kind==='artifacts'?'artifacts':'project-activity')+'?project_id='+encodeURIComponent(id)+(kind==='artifacts'?'&path='+encodeURIComponent(path):''));projectPanels.set(key,{data,loadedAt:Date.now()});}
 catch(error){projectPanels.set(key,{...projectPanels.get(key),error:error.message,loadedAt:Date.now()});}
 finally{projectPanelRequests.delete(key);if(state.projectId===id){if(pageHasTile(kind)||kind==='activity'&&pageHasTile('preview'))renderMain();else renderProjectSlots();}}
}
const artifactPaths=new Map();
function renderArtifacts(p){
 const path=artifactPaths.get(p.id)||'',entry=projectPanels.get('artifacts:'+p.id+':'+path);if(!entry)loadProjectPanel('artifacts',p.id,path);
 const parts=path.split('/').filter(Boolean),data=entry?.data;
 return `<div class="page"><div class="page-eyebrow">${icon('folder')}Project artifacts</div><div class="page-heading"><div><h1>${e(p.name)} files</h1><p>Project artifacts and uploaded files. Drop files here, open them, or download them.</p></div><div class="heading-actions"><button class="button" data-action="upload-files"${disabled()}>Upload files…</button><button class="button" data-action="refresh-project-panel">${icon('refresh')}Refresh</button></div></div>${projectTabs('artifacts')}<nav class="artifact-breadcrumb" aria-label="Artifact path"><button data-artifact-path="">${e(data?.root_label||'Project files')}</button>${parts.map((part,i)=>`<span>/</span><button data-artifact-path="${e(parts.slice(0,i+1).join('/'))}">${e(part)}</button>`).join('')}</nav>${entry?.error?`<div class="notice error">${e(entry.error)}</div>`:''}${!entry?'<div class="loading-state"><span class="spinner"></span>Loading files…</div>':!data?.entries?.length?empty('No files here yet','Ask an agent to publish project artifacts. They will appear here.'): `<div class="artifact-list">${data.entries.map(file=>`<div class="artifact-row"><span>${icon(file.kind==='directory'||file.kind==='folder'?'folder':'file')}</span><button ${['directory','folder'].includes(file.kind)?`data-artifact-path="${e(file.path)}"`:`data-artifact-preview="${e(file.path)}"`} title="${e(file.path)}">${e(file.name)}</button><small>${file.size!==undefined?file.size>1048576?(file.size/1048576).toFixed(1)+' MB':Math.ceil(file.size/1024)+' KB':''}</small><button class="icon-button" data-copy-artifact="${e(file.absolute_path||file.path)}" aria-label="Copy path for ${e(file.name)}" title="Copy path">${icon('link')}</button>${file.download_url?`<a class="icon-button" href="${e(file.download_url)}" download title="Download ${e(file.name)}" aria-label="Download ${e(file.name)}">${icon('arrowRight')}</a>`:''}</div>`).join('')}</div>`}</div>`;
}
function activityCondition(item){const c=item.condition||{};if(c.kind==='interval'||c.event==='interval')return `Every ${c.minutes||c.interval_minutes||item.interval_minutes||10} minutes`;if(c.kind==='metric'||c.event==='metric')return `${c.metric||c.key||'Metric'} ${{lt:'<',lte:'≤',gt:'>',gte:'≥',eq:'='}[c.operator]||c.operator||''} ${c.value??c.threshold??''}`;if(c.kind==='run_status')return `Run ${(c.statuses||(c.status?[c.status]:[])).join(' / ')}`;return c.kind||item.run_status||'';}
function activityDetail(item){return `<div class="activity-detail">${item.condition?`<span>Trigger</span><p>${e(activityCondition(item))}</p>`:''}${item.task?`<span>Task</span><p>${e(item.task)}</p>`:''}${item.next_at?`<span>Next</span><p>${e(date(item.next_at))}</p>`:''}${item.attempts!==undefined?`<span>Retries</span><p>${e(item.attempts)} / ${e(item.max_attempts||3)}</p>`:''}${item.permissions?`<span>Permissions</span><p>${e(item.permissions)}</p>`:''}${item.stop_condition?`<span>Stops when</span><p>${e(item.stop_condition)}</p>`:''}${item.logs?`<span>Recent output</span><pre>${e(String(item.logs).slice(-6000))}</pre>`:''}</div>`;}
function activityGroups(data){return [['Agents',data.agents||[],item=>item.name||item.scope,item=>item.busy?'Working':item.status||'Idle'],['Scheduled work',data.rules||[],item=>item.name||item.task||item.prompt||item.id,item=>item.enabled===false?'Paused':'Enabled'],['Run recovery',data.recoveries||[],item=>item.name||item.task||item.run_id||item.runs?.at(-1)||item.id,item=>item.enabled===false?'Paused':item.run_status||'Monitoring'],['Checks & previews',data.actions||[],item=>item.label||item.node_label||item.node_id||item.id,item=>item.status||item.state||'Recorded'],['Paper builds',data.builds||[],item=>item.main_file,item=>item.status||'Recorded']];}
function activityBody(data){const groups=activityGroups(data);return `<div class="activity-summary"><span><strong>${(data.agents||[]).filter(x=>x.busy).length}</strong> agents working</span><span><strong>${(data.rules||[]).filter(x=>x.enabled).length}</strong> enabled wakeups</span><span><strong>${(data.recoveries||[]).filter(x=>x.enabled).length}</strong> recovery grants</span></div>${data.note?`<p class="muted small">${e(data.note)}</p>`:''}${groups.map(([label,rows,name,stateLabel])=>`<section class="project-activity-group"><div class="section-title"><span>${label}</span><span>${rows.length}</span></div>${rows.length?rows.map(item=>`<details class="project-activity-details"><summary class="project-activity-row"><div><strong>${e(name(item))}</strong>${item.command||item.argv?`<code>${e((item.argv||item.command||[]).join?.(' ')||item.command)}</code>`:''}${item.error||item.reason||item.last_error?`<p>${e(item.error||item.reason||item.last_error)}</p>`:''}</div><span class="badge">${e(stateLabel(item))}</span>${item.updated_at||item.updated?`<time>${e(elapsed(item.updated_at||item.updated))}</time>`:''}</summary>${activityDetail(item)}</details>`).join(''):'<p class="muted small">None recorded.</p>'}</section>`).join('')}${data.configured_timers?.length?`<details class="project-activity-group"><summary>Surfboard trigger templates · ${data.configured_timers.length}</summary><p class="muted small">Inactive until an agent configures an enabled wakeup for a requested task.</p>${data.configured_timers.map(item=>`<p class="small">${e(item.node_id)} · ${e(item.event||'interval')}${item.interval_minutes?' · '+e(item.interval_minutes)+' min':''}</p>`).join('')}</details>`:''}`;}
function renderProjectActivity(p){
 const key='activity:'+p.id+':',entry=projectPanels.get(key),data=entry?.data||{};if(!entry)loadProjectPanel('activity',p.id);
 return `<div class="page"><div class="page-eyebrow">${icon('activity')}Work while you are away</div><div class="page-heading"><div><h1>${e(p.name)} activity</h1><p>Agents, recurring work, recovery, and recorded workflow actions.</p></div><div class="heading-actions"><button class="button" data-action="export-diagnostics">${icon('file')}Export diagnostics</button><button class="button" data-action="refresh-project-panel">${icon('refresh')}Refresh</button></div></div>${projectTabs('activity')}${entry?.error?`<div class="notice error">${e(entry.error)}</div>`:''}${!entry?'<div class="loading-state"><span class="spinner"></span>Loading project activity…</div>':activityBody(data)}</div>`;
}
async function previewArtifact(path){await openPageCode({path:'artifact:'+path});}

async function exportProjectDiagnostics(){
 const data=await api('diagnostics?project_id='+encodeURIComponent(state.projectId)),blob=new Blob([data.markdown],{type:'text/markdown'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=data.filename||'supersurfer-diagnostics.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Diagnostics exported.');
}
let chatRevealScope=null;
function chatLayoutKey(){return state.projectId+':'+(state.experimentId||'');}
function currentLayout(){
 if(state.view!=='workspace'||!state.projectId||isSurfboard())return null;
 return state.experimentId?(state.experiment?.id===state.experimentId&&state.experiment.view_layout?.rows||project()?.surfboard?.layouts?.item):project()?.surfboard?.layouts?.project;
}
function currentPages(){
 if(state.view!=='workspace'||!state.projectId||isSurfboard())return null;
 return state.experimentId?(state.experiment?.id===state.experimentId&&state.experiment.view_layout?.pages||project()?.surfboard?.pages?.item):project()?.surfboard?.pages?.project;
}
function hiddenViewTabs(){return state.experimentId?state.experiment?.view_layout?.hidden_tabs||[]:project()?.surfboard?.hidden_tabs||[];}
function pageTabMarkup(id,label,active){
 return `<span class="page-tab"><button class="tab ${active===id?'active':''}" data-tab="${e(id)}">${e(label)}</button>${id!=='surfboard'&&!isSurfboard()?`<button type="button" class="page-tab-options" data-page-options="${e(id)}" aria-label="Page options: ${e(label)}" title="Page options">⋯</button>`:''}</span>`;
}
function savedActivePage(){return currentPages()?.find(page=>page.id===state.tab);}
function activePage(){return tileLayout.page(savedActivePage());}
function pageHasTile(kind){return state.view==='workspace'&&(activePage()?.tiles.some(tile=>tile.kind===kind)??state.tab===kind);}
function isTilePage(){return !!activePage();}
function layoutTabsMarkup(active=state.tab){
 const rows=currentLayout();if(!rows)return '';
 const documents=state.experiment?.pages||[],pages=currentPages();
 const hidden=hiddenViewTabs(),main=pages?.map(page=>({id:page.id,label:page.title}))||rows.filter(row=>row.placement==='main');if(!hidden.includes('_todos'))main.push({id:'_todos',label:'To-dos'});if(!hidden.includes('_files')&&(fileViewerScopes.has(chatLayoutKey())||state.tab==='_files'))main.push({id:'_files',label:'File viewer'});
 const hasDocuments=pages?pages.some(page=>page.tiles.some(tile=>tile.kind==='documents')):main.some(row=>row.id==='documents');
 return `<div class="tabs configured-tabs">${main.map(row=>pageTabMarkup(row.id,row.label,active)).join('')}${hasDocuments?documents.filter(page=>!hidden.includes('page:'+page.id)).map(page=>pageTabMarkup('page:'+page.id,page.title,active)).join(''):''}<button class="tab" data-tab="workflow">${state.experimentId?'Workflow':'Task defaults'}</button></div>`;
}
function ensureLayoutTab(){
 if(['_files','_todos'].includes(state.tab)&&!hiddenViewTabs().includes(state.tab))return;
 if(state.experimentId&&state.experiment?.id!==state.experimentId)return;
 const rows=currentLayout();if(!rows)return;
 const pages=currentPages(),allowed=pages?.map(page=>page.id)||rows.filter(row=>row.placement==='main').map(row=>row.id);
 if(state.tab.startsWith('page:')&&!hiddenViewTabs().includes(state.tab)&&(pages?pages.some(page=>page.tiles.some(tile=>tile.kind==='documents')):allowed.includes('documents')))return;
 if(!allowed.includes(state.tab))state.tab=allowed[0]||'empty-layout';
}
function ensureViewDock(){
 let dock=$('#view-dock');if(dock)return dock;
 dock=document.createElement('aside');dock.id='view-dock';dock.setAttribute('aria-label','Configured side views');
 $('#chat-panel').before(dock);dock.append($('#chat-panel'));return dock;
}
function dockChat(){
 const dock=ensureViewDock(),chat=$('#chat-panel'),rows=currentLayout();
 if(isWorkflow()&&$('.wf-chat')){$('.wf-chat').append(chat);chat.hidden=false;dock.hidden=true;$('#chat-resizer').hidden=true;return;}
 if(panelWindows.detached&&!panelWindows.page(activePage())?.tiles.some(tile=>tile.kind==='chat')){if(chat.parentElement!==dock)dock.append(chat);chat.hidden=!state.chatVisible||rightSidebarCollapsed;dock.hidden=!state.chatVisible||rightSidebarCollapsed;dock.classList.remove('views-only');$('.app-shell').classList.remove('main-chat-view');$('#chat-resizer').hidden=!state.chatVisible||state.chatMaximized;return;}
 const chatView=rows?.find(row=>row.id==='chat');const place=chatView?.placement||'right';
 chat.style.order=String(chatView?.order??1000);
 const pageChat=pageHasTile('chat');
 const mainChat=pageChat&&!state.chatMaximized;
 const host=mainChat?$('#main-chat-host'):dock;
 if(host&&chat.parentElement!==host)host.append(chat);
 chat.hidden=!state.chatVisible||rightSidebarCollapsed||(!pageChat&&place==='hidden'&&chatRevealScope!==chatLayoutKey())||(place==='main'&&!mainChat&&!state.chatMaximized);
 const panels=$('#project-view-panels');
 dock.hidden=(chat.parentElement!==dock||chat.hidden)&&(!panels||panels.hidden||!panels.querySelector('.project-view-slot:not([data-kind=activity]),.project-view-slot[open]'))&&!($('#page-right-tiles')&&!$('#page-right-tiles').hidden);
 dock.classList.toggle('views-only',chat.hidden||chat.parentElement!==dock);
 $('.app-shell').classList.toggle('main-chat-view',!!mainChat);
 $('#chat-resizer').hidden=dock.hidden||state.chatMaximized;
}
async function prepareCodeQuestion(text,notice='Selection context added to your agent message.'){
 const projectId=state.projectId,experimentId=state.experimentId,requestedScope=state.scope;
 if(!currentAgentDirectory())await loadAgentDirectory();if(state.projectId!==projectId||state.experimentId!==experimentId||requestedScope&&requestedScope!==state.scope)return;
 if(!state.scope||state.scope.startsWith('surfboard:'))syncAgentChooser();
 state.chatVisible=true;setRightSidebarCollapsed(false);chatRevealScope=chatLayoutKey();
 if(!panelWindows.detached&&currentLayout()?.find(row=>row.id==='chat')?.placement==='main'){state.tab='chat';renderMain();}
 applyChatLayout();dockChat();if(panelWindows.detached)startChatPolling();
 panelFocus.close();const input=$('#chat-input');if(typeof text==='object'){if(text.project_id!==state.projectId)return;if(!chatAcceptsProject(text.project_id))throw new Error('This pinned agent belongs to another project. Unpin it before attaching this selection.');chatContext.add(text);}else{const previous=input.value.trim();input.value=previous?previous+'\n\n'+text:text;}
 stashMessageDraft();resizeComposer();input.focus();toast(notice);
}
async function showViewLayout({addPage=false}={}){
 const selectedPageId=state.tab;
 if(!state.experimentId){await navigate({projectId:state.projectId,tab:'surfboard'});surfboardEditor.showLayout({level:'project',selectedPageId,addPage});return;}
 const projectId=state.projectId,experimentId=state.experimentId;
 const record=await api('view-layout?project_id='+encodeURIComponent(projectId)+'&experiment_id='+encodeURIComponent(experimentId));
 let draft=record.rows.map(({id,placement,order})=>({id,placement,order})),pages=structuredClone(record.pages||[]),pagesChanged=false;
 openModal('Layout for this '+itemLabel(),`<p class="modal-description">Create pages and arrange their tiles. This changes only this ${e(itemLabel())}; other items keep the Surfboard defaults.</p><div id="item-pages-editor"></div><details class="page-dock-settings"><summary>Side panel placement</summary><div id="item-layout-editor"></div></details><p id="item-layout-error" class="form-error" hidden></p><div class="modal-footer"><button class="button" id="layout-inherit"${disabled()}>Use Surfboard default</button><button class="button primary" id="layout-save"${disabled()}>Save layout</button></div>`,'item-layout');
 const editor=createViewLayoutEditor({onChange:rows=>{draft=rows;},readOnly:()=>readOnly()});
 editor.mount($('#item-layout-editor'),{rows:draft,available:record.available});
 const pageEditor=createPageLayoutEditor({chooseBlock:chooseReusableBlock,onChange:value=>{pages=value;pagesChanged=true;},readOnly:()=>readOnly()});
 pageEditor.mount($('#item-pages-editor'),{pages,available:record.available_tiles||record.available,selectedPageId:state.tab});
 if(addPage)$('#item-pages-editor [data-pages-action="add-page"]')?.click();
 async function save(rows){
  const selectedPage=$('#item-pages-editor [data-page-select].active')?.dataset.pageSelect;
  $('#layout-save').disabled=true;$('#layout-inherit').disabled=true;
  try{await action('view-layout.save',{project_id:projectId,experiment_id:experimentId,version:record.version,board_version:record.board_version,rows,...(rows===null?{pages:null}:pagesChanged?{pages}: {})});editor.unmount();pageEditor.unmount();closeModal();if(state.experimentId===experimentId){await fetchExperiment(true);if(rows!==null&&pagesChanged&&selectedPage&&currentPages()?.some(page=>page.id===selectedPage)){state.tab=selectedPage;persistNavigation();renderMain();}}toast(rows===null?'Using Surfboard defaults.':'Layout saved.');}
  catch(error){$('#item-layout-error').hidden=false;$('#item-layout-error').textContent=error.message;$('#layout-save').disabled=false;$('#layout-inherit').disabled=false;}
 }
 $('#layout-save').onclick=()=>save(draft);$('#layout-inherit').onclick=()=>save(null);
 $('#modal').addEventListener('close',()=>{editor.unmount();pageEditor.unmount();},{once:true});
}
const projectResultRequests=new Set();
async function loadProjectResults(){
 const projectId=state.projectId;
 for(const item of state.data.experiments.filter(x=>x.project_id===projectId)){
  if(projectResultRequests.has(item.id)||resultPages.get(item.id))continue;
  projectResultRequests.add(item.id);
  try{const data=await api('results?experiment_id='+encodeURIComponent(item.id));resultPages.set(item.id,{pages:data.pages||[],loadedAt:Date.now()});}
  catch(error){resultPages.set(item.id,{pages:[],error:error.message});}
  finally{projectResultRequests.delete(item.id);}
 }
 if(state.projectId===projectId&&!state.experimentId)renderMain();
}
// Page shells are reconciled by tile identity. Code buffers and embedded results
// stay mounted across workspace refreshes; switching pages never saves a file.
function tileBody(kind,tile){
 if(kind==='html')return `<div class=html-block-root data-html-block="${e(tile.block_id||'')}"></div>`;
 if(kind==='pdf'&&(tile?.path||!pageTileCatalog().find(row=>row.kind==='pdf')?.node_id))return '<div id="standalone-pdf-tile" class="standalone-pdf-tile"></div>';
 if(kind==='file_explorer')return '<div id="repository-explorer-tile" class="code-tile-root"></div>';
 if(kind==='agent_changes')return '<div id="agent-changes-tile" class="code-tile-root"></div>';
 let html;
 if(kind==='artifacts')html=renderArtifacts(project());
 else if(kind==='overview'&&!state.experimentId){
  const items=state.data.experiments.filter(item=>item.project_id===state.projectId);
  return `<div class="tile-work-items"><div class="document-toolbar"><strong>${e(pluralItems())}</strong><button class="button small-button" data-action="add-experiment"${disabled()}>${icon('plus')}New ${e(itemLabel())}</button></div>${project()?.goal?`<article class="markdown">${markdown(project().goal)}</article>`:''}${items.map(item=>`<button class="tile-work-item" data-experiment="${e(item.id)}"><strong>${e(item.name)}</strong>${status(item.status,item.status_detail)}<p>${e(item.summary||'')}</p></button>`).join('')||'<p class="muted">No work items yet.</p>'}</div>`;
 }else html=configuredViewBody(kind);
 // These legacy content renderers include their page navigation. The surrounding
 // page owns navigation; tile content keeps the useful controls only.
 const template=document.createElement('template');template.innerHTML=html;
 for(const nav of template.content.querySelectorAll('.configured-tabs,.sb-project-tabs,.page-eyebrow'))nav.remove();
 return template.innerHTML;
}
function pageTileContainers(){
 let left=$('#page-left-tiles'),right=$('#page-right-tiles');
 if(!left){left=document.createElement('section');left.id='page-left-tiles';left.className='page-tile-dock';left.dataset.tileDrop='left';left.setAttribute('aria-label','Left sidebar tiles');$('.sidebar-footer').before(left);}
 if(!right){right=document.createElement('section');right.id='page-right-tiles';right.className='page-tile-dock';right.dataset.tileDrop='right';right.setAttribute('aria-label','Right sidebar tiles');ensureViewDock().prepend(right);}
 return {main:$('#page-tile-grid'),left,right};
}
function clearPageTileDocks(){
 for(const id of ['page-left-tiles','page-right-tiles']){const root=$('#'+id);if(root){codeEditor.detachWithin(root);if(root.contains($('#chat-panel')))ensureViewDock().append($('#chat-panel'));root.replaceChildren();root.hidden=true;}}
 standalonePdf.unmount();$('.app-shell').classList.remove('has-page-left','arranging-page');applySidebarLayout();
}
function applyPageTileSizes(page){
 page=panelWindows.page(page);
 const canvas=$('#page-tile-grid'),floating=page.arrangement==='windows'&&!panelWindows.detached;canvas?.classList.toggle('window-canvas',floating);if(canvas)canvas.style.minHeight=floating?Math.max(500,...page.tiles.filter(t=>(t.placement||'main')==='main').map(t=>(t.bounds?.y||0)+(t.bounds?.height||t.height)+24))+'px':'';canvas?.classList.toggle('dock-canvas',!floating&&!panelWindows.detached);
 for(const element of $$('[data-live-tile]')){const tile=page.tiles.find(tile=>tile.id===element.dataset.tileId);if(tile){element.style.setProperty('--tile-span',tile.span);element.style.setProperty('--tile-height',tile.height+'px');const bounds=tile.bounds;if(floating&&(tile.placement||'main')==='main'&&bounds){Object.assign(element.style,{left:bounds.x+'px',top:bounds.y+'px',width:bounds.width+'px',height:bounds.height+'px'});}else for(const field of ['left','top','width','height'])element.style[field]='';}}
 if(canvas&&!floating&&!panelWindows.detached)renderDockLayout(canvas,page);else if(canvas){canvas.style.minWidth='';canvas.querySelectorAll('[data-dock-key]').forEach(el=>el.remove());}
 const shell=$('.app-shell');shell.classList.toggle('has-page-left',page.tiles.some(tile=>tile.placement==='left')||tileLayout.editing());
 applySidebarLayout(page);applyChatLayout();
}
function renderTilePage(){
 const original=activePage(),page=panelWindows.page(original),main=$('#main'),key=chatLayoutKey()+':'+page.id;
 main.classList.remove('configured-editor-main','results-full-page');
 if(main.dataset.tilePageKey!==key||!$('#page-tile-grid')){
  if(main.contains($('#chat-panel')))ensureViewDock().append($('#chat-panel'));
  codeEditor.unmount();clearPageTileDocks();repositoryExplorer.unmount();agentChangesTile.unmount();latexPanel.unmount();
  main.innerHTML='<div class="tile-page"><header class="tile-page-heading"><div class="tile-page-title"></div><div class="tile-page-tabs"></div></header><div id="page-tile-grid" data-tile-drop="main" class="page-tile-grid"></div></div>';
  main.dataset.tilePageKey=key;delete main.dataset.viewKey;
 }
 const editing=tileLayout.editing();$('.app-shell').classList.toggle('arranging-page',editing);
 const palette=$('#panel-palette');if(palette){const content=tileLayout.palette();if(palette.innerHTML!==content)palette.innerHTML=content;palette.hidden=panelWindows.detached;}
 const heading=$('.tile-page-title',main);
 const headingMarkup=`<h1 title="${e((state.experiment||experiment())?.name||project()?.name)}">${e(page.title)}</h1>`;
 if(heading.innerHTML!==headingMarkup)heading.innerHTML=headingMarkup;
 const tabs=$('.tile-page-tabs',main),markup=layoutTabsMarkup();if(tabs.innerHTML!==markup)tabs.innerHTML=markup;
 const containers=pageTileContainers(),catalog=pageTileCatalog(),elements=new Map($$('[data-live-tile]').map(element=>[element.dataset.tileId,element]));
 const ids=new Set(page.tiles.map(tile=>tile.id));
 for(const [id,element] of elements)if(!ids.has(id)){codeEditor.detachWithin(element);if(element.contains($('#chat-panel')))ensureViewDock().append($('#chat-panel'));element.remove();}
 const positions={main:0,left:0,right:0};
 for(const tile of page.tiles){
  const grid=containers[tile.placement||'main'];let element=elements.get(tile.id);
  if(!element||element.dataset.tileKind!==tile.kind){
   if(element?.contains($('#chat-panel')))ensureViewDock().append($('#chat-panel'));
   element?.remove();element=document.createElement('section');element.className='page-tile';element.dataset.liveTile='';element.dataset.tileId=tile.id;element.dataset.tileKind=tile.kind;
   element.innerHTML='<header class="page-tile-heading"></header><div class="page-tile-body"></div>';
  }
  tileLayout.decorate(element,tile,catalog.find(row=>row.kind===tile.kind)?.label||tile.kind.replaceAll('_',' '));
  const body=$('.page-tile-body',element),html=tileBody(tile.kind,tile);
  const persistent=['editor','vscode','terminal','ports','file_explorer','agent_changes','chat','pdf','todos'].includes(tile.kind);
  const editingContent=body.querySelector('#project-compute-form[data-dirty="true"],#document-editor')||body.contains(document.activeElement)&&document.activeElement?.matches('input,textarea,select');
  const pdfChanged=tile.kind==='pdf'&&(body.dataset.pdfPath!==(tile.path||'')||body.dataset.markup!==html);
  if(!body.hasChildNodes()||pdfChanged||(!persistent&&!editingContent&&body.dataset.markup!==html)){
   const opened=[...body.querySelectorAll('details[data-document-id][open]')].map(node=>node.dataset.documentId);body.innerHTML=html;body.dataset.markup=html;body.dataset.pdfPath=tile.path||'';for(const node of body.querySelectorAll('details[data-document-id]'))if(opened.includes(node.dataset.documentId))node.open=true;
  }
  const index=positions[tile.placement||'main']++,before=[...grid.children].filter(el=>el.hasAttribute('data-live-tile'))[index]||null;
  if(before!==element){if(grid.moveBefore&&element.isConnected)grid.moveBefore(element,before);else grid.insertBefore(element,before);}
 }
 for(const [placement,grid] of Object.entries(containers)){
  grid.querySelectorAll(':scope>.tile-drop-placeholder,:scope>.empty-state').forEach(el=>el.remove());
  grid.hidden=placement!=='main'&&!positions[placement]&&!editing;
  if(editing){const label=document.createElement('div');label.className='tile-drop-placeholder';label.textContent=placement==='main'?'Drop tiles on the page':placement==='left'?'Drop in the left sidebar':'Drop in the right sidebar';grid.append(label);}
  else if(placement==='main'&&!positions.main)grid.innerHTML=empty('This page uses its sidebars','Choose Arrange to move tiles onto the page.');
 }
 document.documentElement.style.setProperty('--rearrange-height',editing?$('#rearrange-overlay').getBoundingClientRect().height+'px':'0px');
 applyPageTileSizes(page);
 if(pageHasTile('results')&&state.experimentId&&!resultPages.has(state.experimentId))queueMicrotask(()=>loadResultPages().then(()=>{if(!chosenResultPage())loadMetrics();}));
 renderProjectSlots();bindMain();syncConfiguredEditors();renderPending=false;
}
function pageTileCatalog(){return (state.experimentId?state.experiment?.view_layout?.available_tiles:project()?.surfboard?.available_tiles?.project)||[];}
const tileLayout=createTileLayout({
 key:()=>chatLayoutKey()+':'+state.tab,page:savedActivePage,catalog:pageTileCatalog,readOnly:()=>readOnly()||panelWindows.detached,render:()=>renderMain(),resize:applyPageTileSizes,
 chooseBlock:chooseReusableBlock,editorCommand:(kind,tileKind)=>{const editor=tileKind==='pdf'?latexPanel:extraEditors[tileKind]||codeEditor;if(!editor.command?.(kind))toast('This action is unavailable in the current editor. Open Settings → Editor to choose its engine.',true);},project:page=>panelWindows.page(page),save:savePageLayout,configure:fields=>showViewLayout(fields),workflow:()=>navigate({projectId:state.projectId,experimentId:state.experimentId,tab:'surfboard'})
});
const rearrangeSize=new ResizeObserver(()=>{const overlay=$('#rearrange-overlay');document.documentElement.style.setProperty('--rearrange-height',overlay.hidden?'0px':overlay.getBoundingClientRect().height+'px');});rearrangeSize.observe($('#rearrange-overlay'));
async function savePageLayout(page,base){
 if(page.layout)ensureDockLayout(page);
  const projectId=state.projectId,experimentId=state.experimentId;
  const record=await api('view-layout?'+new URLSearchParams({project_id:projectId,...(experimentId?{experiment_id:experimentId}:{})}));
  const original=record.pages.find(row=>row.id===base.id);
  if(JSON.stringify(original)===JSON.stringify(page)){await refreshState(true);return;}
  if(JSON.stringify(original)!==JSON.stringify(base)){await refreshState(true);throw new Error('This page changed in another window or agent. Cancel and rearrange the latest page.');}
  await action('view-layout.save',{project_id:projectId,experiment_id:experimentId,version:record.version,board_version:record.board_version,pages:record.pages.map(row=>row.id===page.id?page:row)});
  await refreshState(true);toast('Page layout saved.');
 }
const standalonePdf=createPdfPreview({onChooseFile:()=>handleAction('choose-pdf'),
 async loadBytes(url,{signal}){const token=sessionStorage.getItem('supersurfer-token');const response=await fetch(url,{signal,headers:token?{Authorization:'Bearer '+token}:{}});if(!response.ok)throw new Error('PDF could not be opened ('+response.status+'). Check its repository path.');return new Uint8Array(await response.arrayBuffer());},
 onSelection:selection=>prepareCodeQuestion({kind:'pdf',project_id:state.projectId,path:selection.source_path,label:selection.source_path.split('/').at(-1)+' · p. '+selection.page,text:'PDF page '+selection.page+' (not a source-line mapping):\n'+selection.text+(selection.truncated?'\n[Selection truncated]':'')})
});
const todosView=createTodos({api,action,readOnly,onOpen:path=>openPageCode({path})});
function renderTodosPage(){
 const main=$('#main'),key=chatLayoutKey()+':_todos';main.classList.remove('tiled-page-main','results-full-page','configured-editor-main');
 if(main.dataset.viewKey!==key){codeEditor.unmount();main.dataset.viewKey=key;main.innerHTML='<div class="page"><div class="todo-page-tabs"></div><div id="todos-root"></div></div>';}
 main.querySelector('.todo-page-tabs').innerHTML=layoutTabsMarkup();syncConfiguredEditors();bindMain();renderPending=false;
}
function showCompareDialog(){
 const projectId=state.projectId,experimentId=state.experimentId;
 openModal('Compare revisions','<form id="compare-revisions"><label class="field">Base commit, branch or tag<input name="base" required placeholder="main"></label><label class="field">Compare to<input name="head" required placeholder="HEAD"></label><div class="modal-footer"><button type="button" class="button" data-action="close-modal">Cancel</button><button type="submit" class="button primary">Show diff</button></div></form>','compare');
 $('#compare-revisions').onsubmit=event=>{event.preventDefault();const values=Object.fromEntries(new FormData(event.target));closeModal();if(projectId===state.projectId&&experimentId===state.experimentId)openPageCode({comparison:values}).catch(error=>toast(error.message,true));};
}
const seenCodePresentations=new Set();
async function showCodePresentation(record){if(!record||record.project_id!==state.projectId)return;seenCodePresentations.add(record.id);await openPageCode(record.mode==='comparison'?{comparison:record}:{path:record.path});}
function renderCodePresentation(){
 let node=$('#chat-code-presentation');if(!node){node=document.createElement('div');node.id='chat-code-presentation';node.className='chat-code-presentation';$('#chat-messages').before(node);}
 const record=state.chat?.editor_presentation;node.hidden=!record;
 node.innerHTML=record?`<button type="button" class="button small-button" data-action="open-code-presentation">${icon('file')}${e(record.title)} · ${record.mode==='comparison'?'Open diff':'Open file'}</button>`:'';
 if(record&&!seenCodePresentations.has(record.id)&&!state.edit&&!tileLayout.editing()&&!$('#modal').open){seenCodePresentations.add(record.id);queueMicrotask(()=>{if(state.chat?.editor_presentation?.id===record.id)showCodePresentation(record).catch(error=>toast(error.message,true));});}
}
const fileViewerScopes=new Set();
function renderFileViewer(){
 const main=$('#main'),key=chatLayoutKey()+':_files';fileViewerScopes.add(chatLayoutKey());
 main.classList.remove('tiled-page-main','results-full-page');main.classList.add('configured-editor-main');
 if(main.dataset.viewKey!==key){codeEditor.unmount();main.dataset.viewKey=key;main.innerHTML='<div class="configured-page file-viewer-page"><header class="configured-heading"><strong>File viewer</strong><span></span></header><div class="file-viewer-tabs"></div><div class="configured-view-content"><div id="code-editor-root" class="code-editor-root"></div></div></div>';}
 const tabs=main.querySelector('.file-viewer-tabs'),markup=layoutTabsMarkup();if(tabs.innerHTML!==markup)tabs.innerHTML=markup;main.querySelector('.configured-heading span').textContent=project()?.repo||'';
 syncConfiguredEditors();bindMain();renderPending=false;
}
async function openPageCode({path,scope,changeId,range,comparison}){
 const projectId=state.projectId,experimentId=state.experimentId;
 if(!$('#code-editor-root')){
  const destination=currentPages()?.find(page=>page.tiles.some(tile=>tile.kind==='editor'&&(!tile.placement||tile.placement==='main')));
  let pageId=destination?.id;
  if(!pageId&&!readOnly()){
   const record=await api('view-layout?'+new URLSearchParams({project_id:projectId,...(experimentId?{experiment_id:experimentId}:{})}));
   if(projectId!==state.projectId||experimentId!==state.experimentId)return;
   pageId='files';let suffix=2;while(record.pages.some(page=>page.id===pageId))pageId='files-'+suffix++;
   const files=activePage()?.tiles.find(tile=>tile.kind==='file_explorer');
   const page={id:pageId,title:'File viewer',tiles:[{id:'source',kind:'editor',span:12,height:Math.min(1200,Math.max(400,innerHeight-220))},...(files?[{...files,placement:'left'}]:[])]};
   await action('view-layout.save',{project_id:projectId,experiment_id:experimentId,version:record.version,board_version:record.board_version,pages:[...record.pages,page]});
   if(projectId!==state.projectId||experimentId!==state.experimentId)return;
   await refreshState(true);
  }
  if(projectId!==state.projectId||experimentId!==state.experimentId)return;
  state.tab=pageId||'_files';persistNavigation();renderMain();
 }
 const root=$('#code-editor-root');if(!root)return;
 await codeEditor.mount(root,{projectId,repo:project()?.repo,experimentId,nodeId:currentLayout()?.find(row=>row.id==='editor')?.node_id||'editor',mode:'editor'});
 if(projectId!==state.projectId||experimentId!==state.experimentId||!root.isConnected)return;
 if(comparison)await codeEditor.showComparison(comparison);else if(path)await codeEditor.openFile(path,range);else await codeEditor.showAgentChange(scope,changeId);
}

function panelLoadError(entry){return entry?.error?`<div class="notice warn">${e(entry.error)} <button class="button small-button" data-action="refresh-project-panel" data-panel-kind="activity">Retry</button></div>`:'';}
function configuredViewBody(kind,{right=false}={}){
 const p=project(),x=state.experiment||experiment();
 if(kind==='todos')return '<div id="todos-root"></div>';
 if(['vscode','terminal','ports'].includes(kind))return '<div id="'+kind+'-block-root" class="code-editor-root standalone-native-block" data-native-kind="'+kind+'"></div>';
 if(kind==='editor')return '<div id="code-editor-root" class="code-editor-root"></div>';
 if(kind==='pdf')return '<div id="latex-panel-root" class="latex-panel-root"></div>';
 if(kind==='chat')return '<div id="main-chat-host"></div>';
 if(kind==='runs')return runBrowser(state.experimentId?experimentRuns(state.experimentId):projectRuns(p.id));
 if(kind==='overview')return x?renderExperimentOverview(x,experimentRuns(x.id)):`<div class="markdown">${markdown(p.goal||'No project brief yet.')}</div>`;
 if(kind==='activity'){const entry=projectPanels.get('activity:'+p.id+':');if(!entry&&!projectPanelRequests.has('activity:'+p.id+':'))loadProjectPanel('activity',p.id);return panelLoadError(entry)+(entry?.data?activityBody(entry.data):entry?.error?'':'<p class="muted">Loading activity…</p>');}
 if(kind==='compute')return renderProjectCompute(p);
 if(kind==='documents'){
  if(x){for(const page of x.pages||[])if(!markdownPages.has(x.id+':'+page.id))loadMarkdownPage(x.id,page.id);return (x.pages||[]).map(page=>{const entry=markdownPages.get(x.id+':'+page.id);return `<details class="layout-document" data-document-id="${e(page.id)}"><summary>${e(page.title)}</summary>${entry?.error?`<p class="notice warn">${e(entry.error)} <button class="button small-button" data-action="refresh-page" data-page-id="${e(page.id)}">Retry</button></p>`:''}<article class="markdown">${markdown(entry?.data?.markdown??(entry?.error?'':'Loading…'))}</article></details>`;}).join('')||`<article class="markdown">${markdown(x.markdown||x.summary||'No notes yet.')}</article>`;}

  return state.data.experiments.filter(item=>item.project_id===p.id).map(item=>`<details class="layout-document"><summary>${e(item.name)}</summary><article class="markdown">${markdown(item.markdown||item.summary||'No notes yet.')}</article></details>`).join('')||'<p class="muted">Notes from your work items appear here.</p>';
 }
 if(kind==='preview'){
  const entry=projectPanels.get('activity:'+p.id+':');if(!entry&&!projectPanelRequests.has('activity:'+p.id+':'))loadProjectPanel('activity',p.id);
  const previewNodes=currentLayout()?.find(row=>row.id==='preview')?.node_ids||[];
  const previews=(entry?.data?.actions||[]).filter(row=>previewNodes.includes(row.node_id)&&row.preview_url&&row.status==='running'&&(!state.experimentId||!row.experiment_id||row.experiment_id===state.experimentId));
  return panelLoadError(entry)+(previews.map(row=>`<iframe class="managed-preview" title="${e(row.node_label||'App preview')}" src="${e(row.preview_url)}" sandbox="allow-scripts allow-forms"></iframe>`).join('')||'<p class="muted">Ask your agent to start a configured preview. A running preview appears here.</p>');
 }
 if(kind==='results'&&!state.experimentId){
  const items=state.data.experiments.filter(item=>item.project_id===p.id);
  if(items.some(item=>!resultPages.has(item.id)&&!projectResultRequests.has(item.id)))loadProjectResults();
  return items.map(item=>`<section class="layout-result-group"><h3>${e(item.name)}</h3>${(resultPages.get(item.id)?.pages||[]).map(page=>`<h4>${e(page.title)}</h4><iframe data-layout-result="${e(page.id)}" data-result-experiment="${e(item.id)}" title="${e(page.title)}" src="${e(page.preview_url)}" sandbox="allow-scripts allow-downloads"></iframe>`).join('')||`<p class="muted">${e(resultPages.get(item.id)?.error||'No published results yet.')}</p>`}</section>`).join('')||'<p class="muted">Published work-item results appear here.</p>';
 }
 if(kind==='results')return renderResults();
 return '<p class="muted">Choose a view from your layout.</p>';
}
function syncConfiguredEditors(){
 for(const element of $$('[data-html-block]')){if(element.dataset.loadingBlock===element.dataset.htmlBlock)continue;element.dataset.loadingBlock=element.dataset.htmlBlock;api('view-block?id='+encodeURIComponent(element.dataset.htmlBlock)).then(block=>{if(!element.isConnected)return;const iframe=document.createElement('iframe');iframe.title=block.title;iframe.src=block.url;iframe.sandbox='allow-scripts allow-downloads';iframe.referrerPolicy='no-referrer';iframe.className='html-block-frame';element.replaceChildren(iframe);}).catch(error=>{element.textContent=error.message;delete element.dataset.loadingBlock;});}

 const todosRoot=$('#todos-root');if(todosRoot)todosView.mount(todosRoot,{projectId:state.projectId,experimentId:state.experimentId});else todosView.unmount();
 const portsRoot=$('#ports-block-root');if(portsRoot)portsPanel.mount(portsRoot,{projectId:state.projectId});else portsPanel.unmount();
 for(const [kind,editor]of Object.entries(extraEditors)){const element=$('#'+kind+'-block-root');if(element)editor.mount(element,{projectId:state.projectId,repo:project()?.repo,experimentId:state.experimentId,viewKind:kind}).catch(error=>toast(error.message,true));else editor.unmount();}
 const root=$('#code-editor-root'),filesSection=$('#workspace-files-section');filesSection.hidden=!root;if(root)workspaceFiles.mount($('#workspace-files-tree'),{projectId:state.projectId,repo:project()?.repo});else workspaceFiles.unmount();
 applyProjectTreeHeight();
 if(root)codeEditor.mount(root,{projectId:state.projectId,repo:project()?.repo,experimentId:state.experimentId,nodeId:currentLayout()?.find(row=>row.id==='editor')?.node_id||'editor',mode:'editor'}).catch(error=>toast(error.message,true));else codeEditor.unmount();
 const context={projectId:state.projectId,repo:project()?.repo,experimentId:state.experimentId};
 const pdfTile=activePage()?.tiles.find(tile=>tile.kind==='pdf'),pdfViewer=$('#standalone-pdf-tile');
 if(pdfViewer){if(pdfTile?.path){standalonePdf.mount(pdfViewer,{url:'/api/code/pdf?'+new URLSearchParams({project_id:state.projectId,path:pdfTile.path}),source_path:pdfTile.path,title:workspacePath(project()?.repo,state.projectId,pdfTile.path)});}else{standalonePdf.unmount();pdfViewer.innerHTML='<div class="empty-state"><strong>Choose a PDF</strong><p>Open a PDF from this project’s repository.</p><button type="button" class="button" data-action="choose-pdf">Choose PDF…</button></div>';}}else standalonePdf.unmount();
 const pdfRoot=$('#latex-panel-root');if(pdfRoot)latexPanel.mount(pdfRoot,context);else latexPanel.unmount();
 const explorer=$('#repository-explorer-tile'),changes=$('#agent-changes-tile');
 if(explorer)repositoryExplorer.mount(explorer,context).catch(error=>toast(error.message,true));else repositoryExplorer.unmount();
 if(changes)agentChangesTile.mount(changes,context).catch(error=>toast(error.message,true));else agentChangesTile.unmount();
 for(const [frame,bridge] of rightResultBridges){if(!frame.isConnected){bridge.dispose();rightResultBridges.delete(frame);}}
 for(const frame of $$('iframe[data-layout-result]')){
  if(rightResultBridges.has(frame))continue;const experimentId=frame.dataset.resultExperiment,id=frame.dataset.layoutResult;
  rightResultBridges.set(frame,connectLiveResults({api,frame:()=>frame.isConnected?frame:null,selection:()=>({...resultPages.get(experimentId)?.pages.find(page=>page.id===id),experimentId})}));
 }
 dockChat();
}

function projectTabs(tab='overview'){if(isSurfboard()&&project()?.surfboard?.pages?.project)return `<div class="sb-project-tabs">${(state.experimentId?state.experiment?.view_layout?.pages||[]:project().surfboard.pages.project).map(page=>`<button data-tab="${e(page.id)}">${e(page.title)}</button>`).join('')}<button data-tab="workflow" class="active">${state.experimentId?'Workflow':'Task defaults'}</button></div>`;if(currentLayout())return layoutTabsMarkup(tab);const views=project()?.surfboard?.views,panels=views?views.filter(v=>['artifacts','activity'].includes(v.kind)&&v.placement==='main'):[{kind:'artifacts',label:'Files'},{kind:'activity',label:'Activity'}];const seen=new Set();return `<div class="sb-project-tabs"><button data-tab="overview" class="${tab==='overview'?'active':''}">${e(pluralItems().replace(/^./,c=>c.toUpperCase()))}</button>${projectWorkflow()==='research'?`<button data-tab="compute" class="${tab==='compute'?'active':''}">Compute</button>`:''}<button data-tab="workflow" class="${tab==='surfboard'?'active':''}">Task defaults</button>${panels.filter(v=>!seen.has(v.kind)&&seen.add(v.kind)).map(v=>`<button data-tab="${e(v.kind)}" class="${tab===v.kind?'active':''}">${e(v.label)}</button>`).join('')}</div>`;}
const projectSlotOpen=new Set(),projectSlotSeen=new Set(),rightResultBridges=new Map();
function renderProjectSlots(){
 let container=$('#project-view-panels');if(!container){container=document.createElement('section');container.id='project-view-panels';ensureViewDock().prepend(container);container.addEventListener('toggle',event=>{if(!event.target.matches('details.project-view-slot'))return;const key=state.projectId+':'+(state.experimentId||'')+':'+event.target.dataset.node;if(!event.target.open){projectSlotOpen.delete(key);return;}if(!projectSlotOpen.has(key)){projectSlotOpen.add(key);const kind=event.target.dataset.kind;if(['artifacts','activity'].includes(kind))loadProjectPanel(kind,state.projectId,kind==='artifacts'?artifactPaths.get(state.projectId)||'':'');if(kind==='document'&&state.experimentId)Promise.all(((state.experiment||experiment())?.pages||[]).map(page=>loadMarkdownPage(state.experimentId,page.id))).then(renderProjectSlots);if(kind==='preview')loadProjectPanel('activity',state.projectId);if(['results','visualizer','preview'].includes(kind)&&state.experimentId)loadResultPages(true).then(renderProjectSlots);}},true);}
 const p=project(),layout=currentLayout(),views=state.view==='workspace'&&!isSurfboard()?(layout?layout.filter(v=>v.id!=='chat'&&v.placement==='right'&&!activePage()?.tiles.some(tile=>tile.kind===v.id)).map(v=>({...v,node_id:v.id,kind:v.id==='documents'?'document':v.id})):(p?.surfboard?.views||[]).filter(v=>v.placement==='right')):[];container.hidden=!views.length;if(!views.length){container.innerHTML='';dockChat();for(const bridge of rightResultBridges.values())bridge.dispose();rightResultBridges.clear();return;}
 for(const view of views){const key=p.id+':'+(state.experimentId||'')+':'+view.node_id;if(view.kind==='editor'&&!projectSlotSeen.has(key)){projectSlotSeen.add(key);projectSlotOpen.add(key);}}
 const opened=new Set(views.filter(v=>projectSlotOpen.has(p.id+':'+(state.experimentId||'')+':'+v.node_id)).map(v=>v.node_id)),x=state.experiment||experiment();
 const content=view=>{
  if(['editor','pdf','overview','runs','compute'].includes(view.kind))return configuredViewBody(view.kind,{right:true});
  if(view.kind==='results'&&!state.experimentId)return configuredViewBody('results',{right:true});
  if(view.kind==='activity'){const entry=projectPanels.get('activity:'+p.id+':');return entry?.data?activityBody(entry.data):`<p class="muted small">Expand to load current background work.</p>`;}
  if(view.kind==='artifacts'){const path=artifactPaths.get(p.id)||'',entry=projectPanels.get('artifacts:'+p.id+':'+path);return `<div class="artifact-breadcrumb"><button data-artifact-path="">Project files</button>${path?`<span>/ ${e(path)}</span>`:''}</div>${(entry?.data?.entries||[]).map(file=>`<div class="artifact-row"><span>${icon(file.kind==='directory'?'folder':'file')}</span><button ${['directory','folder'].includes(file.kind)?`data-artifact-path="${e(file.path)}"`:`data-artifact-preview="${e(file.path)}"`}>${e(file.name)}</button>${file.download_url?`<a href="${e(file.download_url)}" download aria-label="Download ${e(file.name)}">↓</a>`:''}</div>`).join('')||'<p class="muted small">No published files here.</p>'}`;}
  if(view.kind==='document')return x?((x.pages||[]).length?(x.pages||[]).map(page=>`<details><summary>${e(page.title)}</summary><div class="markdown project-slot-document">${markdown(markdownPages.get(x.id+':'+page.id)?.data?.markdown||'Loading notes…')}</div></details>`).join(''):`<div class="markdown project-slot-document">${markdown(x.markdown||x.summary||'No notes published yet.')}</div>`):'<p class="muted small">Open a work item to read its notes.</p>';
  if(view.kind==='preview'){const previews=(projectPanels.get('activity:'+p.id+':')?.data?.actions||[]).filter(row=>(view.node_ids||[view.node_id]).includes(row.node_id)&&row.preview_url&&row.status==='running'&&(!state.experimentId||!row.experiment_id||row.experiment_id===state.experimentId));if(previews.length)return previews.map(row=>`<iframe class="managed-preview" title="${e(view.label)}" src="${e(row.preview_url)}" sandbox="allow-scripts allow-forms"></iframe>`).join('');}
  if(['results','visualizer','preview'].includes(view.kind)){const pages=resultPages.get(x?.id)?.pages||[];return pages.length?pages.map(page=>`<details class="slot-result"><summary>${e(page.title)}</summary><iframe data-right-results="${e(page.id)}" title="${e(page.title)}" src="${e(page.preview_url)}" sandbox="allow-scripts allow-downloads" loading="lazy"></iframe></details>`).join(''):'<p class="muted small">Published results appear here when you open a work item.</p>';}
  return '<p class="muted small">Open a work item to view its content.</p>';
 };
 const html=views.map(view=>`<details class="project-view-slot" data-node="${e(view.node_id)}" data-kind="${e(view.kind)}" style="order:${Number(view.order)||0}" ${opened.has(view.node_id)?'open':''}><summary>${icon(view.kind==='activity'?'activity':view.kind==='artifacts'?'folder':'file')}<strong>${e(view.label)}</strong><button type="button" data-panel-fullscreen aria-label="Full screen" title="Full screen">⤢</button></summary><div class="project-view-slot-body">${content(view)}</div></details>`).join('');
 if(container.dataset.signature!==html){container.dataset.signature=html;const template=document.createElement('template');template.innerHTML=html;const next=[...template.content.children];for(const element of next){const existing=[...container.children].find(old=>old.dataset.node===element.dataset.node);if(existing){existing.open=element.open;existing.style.order=element.style.order;const oldSummary=existing.querySelector(':scope>summary'),newSummary=element.querySelector(':scope>summary');if(oldSummary.innerHTML!==newSummary.innerHTML)oldSummary.innerHTML=newSummary.innerHTML;const oldBody=existing.querySelector(':scope>.project-view-slot-body'),newBody=element.querySelector(':scope>.project-view-slot-body');if(!['editor','pdf'].includes(element.dataset.kind)&&oldBody.innerHTML!==newBody.innerHTML)oldBody.innerHTML=newBody.innerHTML;}else container.append(element);}const ids=new Set(next.map(el=>el.dataset.node));for(const el of [...container.children])if(!ids.has(el.dataset.node)){codeEditor.detachWithin(el);el.remove();}}
 for(const [frame,bridge] of rightResultBridges){if(!frame.isConnected){bridge.dispose();rightResultBridges.delete(frame);}}
 for(const frame of $$('iframe[data-right-results]',container)){if(rightResultBridges.has(frame))continue;const experimentId=x?.id;rightResultBridges.set(frame,connectLiveResults({api,frame:()=>frame.isConnected?frame:null,selection:()=>state.experimentId===experimentId?{...(resultPages.get(experimentId)?.pages||[]).find(page=>page.id===frame.dataset.rightResults),experimentId}:null}));}
}
function renderProject(){const p=project();if(!p)return empty('A home for your research','Connect a project to organize experiments, talk with its research lead, and queue GPU runs.',`<button class="button primary" data-action="add-project"${disabled()}>${icon('plus')}Connect project</button>`);
 if(state.tab==='compute')return renderProjectCompute(p);
 if(state.tab==='artifacts')return renderArtifacts(p);
 if(state.tab==='activity')return renderProjectActivity(p);
 if(state.tab==='runs')return runBrowser(projectRuns(p.id));
 const experiments=visibleProjectItems(p.id),runs=projectRuns(p.id),running=runs.filter(r=>active.has(r.status)).length;
 return `<div class="page"><div class="page-eyebrow">${icon('folder')}${projectWorkflow()==='research'?'Research':'Project'} workspace</div><div class="page-heading"><div><h1>${e(p.name)}</h1><p>Your ${e(pluralItems())}, conversations, and results. All in one place.</p></div><div class="heading-actions">${projectWorkflow()==='research'?`<button class="button" data-action="project-compute">${icon('server')}Compute</button>`:''}<button class="button" data-tab="workflow">${icon('branch')}Task defaults</button><button class="button primary" data-action="add-experiment"${disabled()}>${icon('plus')}New ${e(itemLabel())}</button></div></div>${projectTabs('overview')}<div class="metadata-line"><span class="meta-item">${icon('folder')}${e(p.repo||'Repository not configured')}</span><span class="meta-item">${icon('activity')}${running} running</span><span class="meta-item">${icon('file')}${experiments.length} ${e(pluralItems())}</span></div>${p.goal?`<div class="project-summary"><div class="page-eyebrow">Research direction</div>${e(p.goal)}</div>`:''}${!p.initialized?`<div class="notice">Save durable research context alongside your code in <code>.SuperSurfer</code>. <button class="button small-button" data-action="initialize-project"${disabled()}>Initialize project context</button></div>`:''}<div class="section-title"><span>${e(pluralItems().replace(/^./,c=>c.toUpperCase()))}</span>${archivedItemsToggle(p.id)}<span class="muted">Ideas begin here. Runs launch when you’re ready.</span></div>${experiments.length?`<div class="experiment-grid">${experiments.map(x=>`<button class="experiment-card" data-experiment="${e(x.id)}">${status(x.status,x.status_detail)}<h3>${e(x.name)}${x.archived?' · Archived':''}</h3><p>${e(x.summary||'Open this experiment to read its research context.')}</p><div class="card-footer">${(x.run_ids||[]).length||state.data.runs.filter(r=>r.experiment_id===x.id).length} runs<span>·</span>${e(elapsed(x.updated_at))}${icon('arrowRight')}</div></button>`).join('')}</div>`:empty('Create your first '+itemLabel(),'Describe the goal and what a good result looks like. You can customize its workflow later.',`<button class="button" data-action="add-experiment"${disabled()}>${icon('plus')}Create ${e(itemLabel())}</button>`)}${runs.some(r=>active.has(r.status))?`<div class="section-title">Running now</div>${runList(runs.filter(r=>active.has(r.status)))}`:''}</div>`;}
const workerWakeups=new Map(),workerWakeupRequests=new Map(),workerWakeupVersions=new Map(),workerWakeupMutations=new Set();
function wakeupCondition(rule){
 const condition=rule.condition||{},run=condition.run_id?state.data?.runs.find(item=>item.id===condition.run_id)?.name||condition.run_id:'latest run';
 if(condition.kind==='interval')return `Every ${condition.minutes} minute${condition.minutes===1?'':'s'}`;
 if(condition.kind==='run_status'){const description={queued:'is queued',starting:'starts',running:'is running',unreachable:'is unreachable',orphaned:'is orphaned',cancelling:'is cancelling',succeeded:'succeeds',failed:'fails',cancelled:'is cancelled',lost:'is lost'}[condition.status]||`is ${condition.status}`;return `When ${run} ${description}`;}
 if(condition.kind==='metric')return `When ${run} · ${condition.metric} ${{lt:'<',lte:'≤',gt:'>',gte:'≥'}[condition.operator]||condition.operator} ${condition.value}`;
 return 'Worker wakeup';
}
async function loadWorkerWakeups(id=state.experimentId,{force=false}={}){
 if(!id)return;if(workerWakeupRequests.has(id)&&!force)return workerWakeupRequests.get(id);
 const version=(workerWakeupVersions.get(id)||0)+1;workerWakeupVersions.set(id,version);
 const request=(async()=>{let changed=false;try{const data=await api('worker-wakeups?experiment_id='+encodeURIComponent(id));if(workerWakeupVersions.get(id)!==version)return;const next={rules:data.rules||[]};changed=JSON.stringify(next)!==JSON.stringify(workerWakeups.get(id));workerWakeups.set(id,next);}catch(error){if(workerWakeupVersions.get(id)!==version)return;const next={...workerWakeups.get(id),error:error.message};changed=JSON.stringify(next)!==JSON.stringify(workerWakeups.get(id));workerWakeups.set(id,next);}finally{if(workerWakeupVersions.get(id)===version)workerWakeupRequests.delete(id);if(changed&&state.experimentId===id&&pageHasTile('overview')&&!state.edit&&!$('#modal').open)renderMain();}})();workerWakeupRequests.set(id,request);return request;
}
function renderWorkerWakeups(experiment){
 const data=workerWakeups.get(experiment.id);if(!data&&!workerWakeupRequests.has(experiment.id))loadWorkerWakeups(experiment.id);
 return `<section class="worker-wakeups" aria-label="Worker wakeups"><div class="worker-wakeups-heading"><div><h2>Worker wakeups</h2><p>Continue a worker on a timer, a metric threshold or a run event.</p></div><button type="button" class="button small-button" data-action="add-worker-wakeup"${disabled()}>${icon('plus')}Add via chat</button></div>${data?.error?`<div class="notice warn">${e(data.error)} <button type="button" class="button small-button" data-action="refresh-worker-wakeups">Retry</button></div>`:''}${!data?'<p class="wakeups-empty">Loading wakeups…</p>':!data.rules?.length?'<p class="wakeups-empty">No worker wakeups configured.</p>':`<div class="worker-wakeup-list">${data.rules.map(rule=>{const busy=workerWakeupMutations.has(JSON.stringify([experiment.id,rule.id])),label={armed:'Armed',pending:'Waiting for worker',claimed:'Starting worker',fired:'Fired',paused:'Paused',uncertain:'Needs attention'}[rule.status]||rule.status||(rule.enabled?'Armed':'Paused');return `<article class="worker-wakeup-row" data-wakeup="${e(rule.id)}"><div class="worker-wakeup-copy"><div class="worker-wakeup-title"><strong>${e(wakeupCondition(rule))}</strong><span class="badge ${e(rule.status||'unknown')}">${e(label)}</span></div><p title="${e(rule.task)}">${e(rule.task||'No task recorded')}</p><small><button type="button" class="wakeup-worker-link" data-conversation="${e(rule.scope)}">${e(scopedAgents().find(agent=>agent.scope===rule.scope)?.name||'Open worker')}</button> · ${rule.last_fired_at?`Last wake ${e(elapsed(rule.last_fired_at))}`:'No wake yet'}${rule.next_at&&rule.enabled?` · Next ${e(date(rule.next_at,true))}`:''}</small>${rule.error?`<div class="worker-wakeup-error">${e(rule.error)}</div>`:''}${rule.status==='uncertain'?'<div class="worker-wakeup-error">Check the worker conversation before asking it to rearm this rule.</div>':''}</div><div class="worker-wakeup-actions">${rule.enabled?`<button type="button" class="icon-button" data-action="pause-worker-wakeup" data-wakeup-id="${e(rule.id)}" data-wakeup-experiment="${e(experiment.id)}" aria-label="Pause wakeup" title="Pause wakeup" ${busy?'disabled':''}${disabled()}>${icon('pause')}</button>`:''}<button type="button" class="icon-button" data-action="remove-worker-wakeup" data-wakeup-id="${e(rule.id)}" data-wakeup-experiment="${e(experiment.id)}" aria-label="Remove wakeup" title="Remove wakeup" ${busy?'disabled':''}${disabled()}>${icon('close')}</button></div></article>`;}).join('')}</div>`}</section>`;
}
async function changeWorkerWakeup(actionName,button){
 const experimentId=button.dataset.wakeupExperiment,id=button.dataset.wakeupId,key=JSON.stringify([experimentId,id]);if(readOnly()||workerWakeupMutations.has(key))return;workerWakeupMutations.add(key);renderMain();try{await action('worker.wakeup.'+actionName,{experiment_id:experimentId,id});await loadWorkerWakeups(experimentId,{force:true});toast(actionName==='pause'?'Worker wakeup paused.':'Worker wakeup removed.');}catch(error){toast(error.message,true);}finally{workerWakeupMutations.delete(key);if(state.experimentId===experimentId&&!state.edit&&!$('#modal').open)renderMain();}
}
async function addWorkerWakeup(){
 const id=state.experimentId;if(!id||readOnly())return;await loadAgentDirectory();if(state.experimentId!==id)return;const agents=scopedAgents(),selected=selectedAgent(),owned=selected?.owner==='supersurfer'&&!selected.retired?selected:agents.find(item=>item.scope===currentAgentDirectory()?.selected_scope&&item.owner==='supersurfer'&&!item.retired)||agents.find(item=>item.owner==='supersurfer'&&!item.retired);if(!owned){toast('Open or create a SuperSurfer worker for this experiment first.',true);return;}await selectConversation(owned.scope,{persist:false});if(state.experimentId!==id)return;const prompt='Set up a worker wakeup for this experiment. Help me choose an interval, a metric threshold or a run event, and what the worker should do when it wakes.';const existing=$('#chat-input').value.trim();$('#chat-input').value=existing?existing+'\n\n'+prompt:prompt;stashMessageDraft();$('#chat-input').focus();toast('Wakeup request prepared. Send when ready.');
}

function workItemTabs(x,runs){
 if(currentLayout())return layoutTabsMarkup();
 const views=project()?.surfboard?.views,mainViews=views?.filter(v=>v.placement==='main'),resultViews=views?.filter(v=>['results','visualizer','preview'].includes(v.kind));
 const rows=[{id:'overview',label:'Overview',icon:'file',order:-100}];
 if(projectWorkflow()==='research'||runs.length)rows.push({id:'runs',label:'Runs',icon:'activity',count:runs.length,order:-50});
 if(!resultViews?.length||mainViews.some(v=>['results','visualizer','preview'].includes(v.kind)))rows.push({id:'results',label:projectWorkflow()==='research'?'Results':'Review',icon:'chart',order:mainViews?.find(v=>['results','visualizer','preview'].includes(v.kind))?.order??0});
 const documentViews=views?.filter(v=>v.kind==='document');if(!documentViews?.length||mainViews.some(v=>v.kind==='document'))for(const page of x.pages||[])rows.push({id:'page:'+page.id,label:page.title,order:mainViews?.find(v=>v.kind==='document')?.order??50});
 return `<div class="tabs">${rows.sort((a,b)=>a.order-b.order).map(row=>`<button class="tab ${state.tab===row.id?'active':''}" data-tab="${e(row.id)}">${row.icon?icon(row.icon):''}${e(row.label)}${row.count!==undefined?` <span class="tab-count">${row.count}</span>`:''}</button>`).join('')}</div>`;
}
function renderExperiment(){if(state.tab==='artifacts')return renderArtifacts(project());if(state.tab==='activity')return renderProjectActivity(project());const x=state.experiment||experiment();if(!x)return empty('Experiment unavailable','Select an experiment from your project.');const runs=experimentRuns(x.id),p=project(),startable=x.status==='draft'&&!['dispatching','uncertain'].includes(x.work_state),starting=startingExperiments.has(x.id);
 return `<div class="page"><div class="page-eyebrow">${icon('file')}${e(itemLabel().replace(/^./,c=>c.toUpperCase()))}</div><div class="page-heading"><div><h1>${e(x.name)}</h1>${x.summary?`<p>${e(x.summary)}</p>`:''}</div><div class="heading-actions">${startable?`<button class="button primary" data-action="start-experiment" ${starting||state.edit?'disabled':''}${disabled()} title="Ask the worker to begin the requested work.">${icon('spark')}${starting?'Starting…':'Start working'}</button>`:''}${projectWorkflow()==='research'?`<button class="button ${startable?'':'primary'}" data-action="submit-run"${disabled()}>${icon('plus')}Queue run</button>`:''}</div></div><div class="metadata-line">${status(x.status,x.status_detail)}<span class="meta-item">${icon('play')}${runs.length} ${runs.length===1?'run':'runs'}</span><span class="meta-item">${icon('clock')}Updated ${e(elapsed(x.updated_at))}</span>${x.review_interval_minutes?`<button class="badge active" data-action="review-schedule"${disabled()}>${icon('refresh')}Review every ${e(x.review_interval_minutes)}m</button>`:''}</div>${x.work_error||x.work_state==='uncertain'?`<div class="notice warn work-notice"><strong>${x.work_state==='uncertain'?'Worker dispatch needs checking':'Worker preparation needs attention'}</strong><p>${x.work_state==='uncertain'?'The dispatch outcome is uncertain. Check the worker’s conversation before requesting more work.':e(x.work_error)}</p>${x.work_state==='uncertain'&&x.work_error?`<p>${e(x.work_error)}</p>`:''}<button class="button small-button" data-action="open-experiment-worker">${icon('message')}Open worker chat</button></div>`:''}${workItemTabs(x,runs)}${pageHasTile('results')?renderResults():state.tab==='runs'?runBrowser(runs):state.tab.startsWith('page:')?renderMarkdownPage(x,state.tab.slice(5)):renderExperimentOverview(x,runs)}</div>`;
}
function renderExperimentOverview(x,runs){
 const brief=x.brief||{},sections=projectWorkflow()==='research'?[['objective','Question'],['method','Method'],['findings','Findings'],['next_steps','Next steps']]:[['objective','Goal'],['method','Approach'],['findings','Progress'],['next_steps','Next steps']],running=recentRuns(runs.filter(r=>!terminal.has(r.status))).slice(0,4);
 const notes=state.edit?`<div class="document-toolbar"><strong>Edit technical notes</strong><div class="toolbar-actions"><button class="button small-button" data-action="cancel-edit">Cancel</button><button class="button primary small-button" data-action="save-experiment">Save notes</button></div></div><textarea class="doc-editor" id="document-editor" aria-label="Experiment document">${e(loadDraft(x.id)??x.markdown??'')}</textarea><label class="field">W&B link<input type="url" id="document-wandb" value="${e(x.wandb_url||'')}"></label>`:`<details class="technical-notes"><summary>Technical notes & provenance</summary><div class="document-toolbar"><span>Version ${e(x.version||1)}</span><div class="toolbar-actions"><button class="icon-button" data-action="document-history" aria-label="Document version history">${icon('history')}</button><button class="button small-button" data-action="edit-experiment"${disabled()}>Edit notes</button></div></div><article class="markdown">${markdown(x.markdown||'No technical notes yet.')}</article></details>`;
 return `<section class="experiment-brief"><div class="document-toolbar"><span>${e(itemLabel().replace(/^./,c=>c.toUpperCase()))} brief${brief.updated?` · ${e(elapsed(brief.updated))}`:''}</span><button class="button small-button" data-action="edit-brief"${disabled()}>${icon('edit')}Edit brief</button></div>${sections.map(([key,title])=>`<section class="brief-section"><h2>${title}</h2><div class="markdown">${brief[key]?markdown(brief[key]):`<p class="muted">${key==='objective'?(projectWorkflow()==='research'?'Describe the research question.':'Describe the goal and acceptance criteria.'):key==='method'?(projectWorkflow()==='research'?'Describe the intervention and evaluation protocol.':'Describe the implementation and validation plan.'):key==='findings'?'No findings recorded yet.':'No next step recorded yet.'}</p>`}</div></section>`).join('')}</section>${running.length?`<section class="brief-runs"><h2>Current runs</h2>${runList(running)}</section>`:''}${resourceLinks(x)}<details class="experiment-activity"><summary>Activity · ${(brief.activity||[]).length} updates</summary>${[...(brief.activity||[])].reverse().map(item=>`<div class="activity-entry"><time>${e(date(item.at,true))}</time><p>${e(item.text)}</p></div>`).join('')||'<p class="muted">No activity notes yet.</p>'}</details>${notes}${renderWorkerWakeups(x)}`;
}
function showEditBrief(){
 const x=state.experiment;if(!x||readOnly())return;const brief=x.brief||{version:0},fields=[['objective','Question',1500],['method','Method',3500],['findings','Findings',3500],['next_steps','Next steps',1500]];
 openModal('Edit experiment brief',`<form id="brief-form">${fields.map(([key,label,limit])=>`<label class="field">${label}<textarea name="${key}" aria-label="${e(label)}" rows="4" maxlength="${limit}">${e(brief[key]||'')}</textarea></label>`).join('')}<p class="form-error" id="brief-error" hidden></p><div class="modal-footer"><button class="button primary" type="submit">Save brief</button></div></form>`,'edit-brief');
 $('#brief-form').addEventListener('submit',async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button');button.disabled=true;try{await action('experiment.brief.save',{experiment_id:x.id,version:brief.version,...Object.fromEntries(new FormData(event.currentTarget))});closeModal();await fetchExperiment(true);}catch(error){$('#brief-error').hidden=false;$('#brief-error').textContent=error.message;button.disabled=false;}});
}
const markdownPages=new Map(),resultPages=new Map(),resultSelections=new Map(),resultPageRequests=new Map();
const liveResults=connectLiveResults({api,frame:()=>$('#result-preview'),selection:()=>state.view==='workspace'&&pageHasTile('results')?{...chosenResultPage(),experimentId:state.experimentId}:null});
async function loadMarkdownPage(experimentId,pageId){
 const key=experimentId+':'+pageId;if(markdownPages.get(key)?.loading)return;
 const revision=()=>state.experiment?.id===experimentId?state.experiment.pages?.find(page=>page.id===pageId)?.version:undefined;
 const requestedVersion=revision();
 markdownPages.set(key,{...markdownPages.get(key),loading:true});
 try{const data=await api('experiment-page?experiment_id='+encodeURIComponent(experimentId)+'&page_id='+encodeURIComponent(pageId));markdownPages.set(key,{data});
  // A metadata refresh can overtake an in-flight content read. Read the new
  // revision immediately rather than leaving that older response in the tile.
  if(revision()&&requestedVersion!==revision())return loadMarkdownPage(experimentId,pageId);
 }
 catch(error){markdownPages.set(key,{error:error.message});}
 if(state.experimentId===experimentId&&(state.tab==='page:'+pageId||pageHasTile('documents')))renderMain();
}

function renderMarkdownPage(x,id){
 const entry=markdownPages.get(x.id+':'+id),page=(x.pages||[]).find(p=>p.id===id);if(!page)return empty('Page unavailable','Choose another experiment tab.');
 if(!entry){loadMarkdownPage(x.id,id);return '<div class="loading-state">Loading page…</div>';}
 if(entry.error)return `<div class="notice warn">${e(entry.error)} <button class="button small-button" data-action="refresh-page">Retry</button></div>`;
 return `<div class="document-toolbar"><span>${e(page.title)} · Markdown</span><button class="icon-button" data-action="refresh-page" aria-label="Refresh page">${icon('refresh')}</button></div><article class="markdown experiment-custom-page">${markdown(entry.data?.markdown||'Loading…')}</article>`;
}
async function loadResultPages(force=false){
 const id=state.experimentId;if(!id)return;
 if(resultPageRequests.has(id)){if(force){await resultPageRequests.get(id);if(state.experimentId===id)return loadResultPages(true);}return;}
 const old=resultPages.get(id);if(!force&&old?.loadedAt&&Date.now()-old.loadedAt<10000)return;
 resultPages.set(id,{...old,loading:true});
 const request=(async()=>{
  try{const data=await api('results?experiment_id='+encodeURIComponent(id));const changed=JSON.stringify(data.pages)!==JSON.stringify(old?.pages)||data.version!==old?.version||JSON.stringify(data.review)!==JSON.stringify(old?.review);resultPages.set(id,{pages:data.pages||[],archived:data.archived||[],version:data.version,review:data.review,loadedAt:Date.now()});if(changed&&state.experimentId===id&&pageHasTile('results'))renderMain();}
  catch(error){resultPages.set(id,{...old,error:error.message,loadedAt:Date.now()});if(state.experimentId===id&&pageHasTile('results'))renderMain();}
 })();resultPageRequests.set(id,request);try{await request;}finally{resultPageRequests.delete(id);}
}
function chosenResultPage(){const id=state.experimentId,pages=resultPages.get(id)?.pages||[],selection=resultSelections.get(id);return selection==='metrics'?null:pages.find(p=>p.id===selection)||pages[0];}
function renderResultTabs(){
 const pages=resultPages.get(state.experimentId)?.pages||[],page=chosenResultPage(),x=state.experiment||experiment();
 const archived=resultPages.get(state.experimentId)?.archived||[];
 return `<div class="result-page-tabs" role="group" aria-label="Result pages">${pages.map(p=>`<span class="result-tab" data-result-tab="${e(p.id)}" draggable="${!readOnly()}"><button class="button small-button ${page?.id===p.id?'primary':''}" data-action="select-result" data-result-id="${e(p.id)}" title="${e(p.title)}">${e(p.title)}</button><button type="button" class="page-tab-options" data-result-options="${e(p.id)}" aria-label="Report options: ${e(p.title)}" title="Drag to reorder or open report actions">⋯</button></span>`).join('')}<button class="button small-button ${!page?'primary':''}" data-action="select-result" data-result-id="metrics">W&B metrics</button><button class="icon-button" data-action="refresh-results" aria-label="Refresh results">${icon('refresh')}</button>${archived.length?`<details class="result-archive tile-space-menu"><summary>Removed · ${archived.length}</summary><div>${archived.map(p=>`<button type="button" data-restore-result="${e(p.id)}"${disabled()}>Restore ${e(p.title)}</button>`).join('')}</div></details>`:''}${page&&x?.wandb_url?link(x.wandb_url,`${icon('external')}<span class="visually-hidden">Open W&amp;B</span>`,'icon-button result-wandb-link'):''}</div>`;
}
function renderResultAttempts(){
 const review=state.experiment?.results_review||resultPages.get(state.experimentId)?.review,attempts=experimentRuns(state.experimentId);if(!attempts.length)return '';
 const ordered=recentRuns(attempts),latest=ordered[0];
 return `<details class="results-attempts"><summary>Attempts · ${attempts.length} <span>${e(latest.name)} · ${e(latest.status)}</span>${review?.needs_review?'<small>Results review needed</small>':''}</summary><div>${ordered.map(run=>`<div><button type="button" data-run="${e(run.id)}">${e(run.name||run.id)}</button><span>${e(run.status)}</span>${run.wandb_url?link(run.wandb_url,'W&B'):''}</div>`).join('')}</div></details>`;
}
function renderResults(){
 const page=chosenResultPage(),tabs=(resultPages.get(state.experimentId)?.error?`<div class="notice warn">${e(resultPages.get(state.experimentId).error)}</div>`:'')+renderResultTabs()+renderResultAttempts();
 if(page){const url=/^\/result-preview\/[A-Za-z0-9_-]+$/.test(page.preview_url)?page.preview_url:null;return `<section class="results-surface" aria-label="Interactive results">${tabs}${url?`<iframe id="result-preview" title="${e(page.title)}" src="${e(url)}" sandbox="allow-scripts allow-downloads" referrerpolicy="no-referrer" class="result-preview"></iframe>`:'<div class="notice warn">Invalid result preview URL.</div>'}</section>`;}
 return tabs+renderWandbResults();
}
function resourceLinks(x){let links=[];if(x.wandb_url)links.push(link(x.wandb_url,`${icon('chart')}Weights & Biases ${icon('external')}`,'resource-link'));for(const a of x.artifacts||[]){const url=typeof a==='string'?a:a.url;if(safeUrl(url))links.push(link(url,`${icon('external')}${e(typeof a==='string'?'Open artifact':a.name||a.title||'Open artifact')}`,'resource-link'));}return links.length?`<div class="resource-links">${links.join('')}</div>`:'';}
function isQueued(run){return run.status==='queued';}
function queuedRuns(){const ids=state.data.queue.run_ids||[];const runs=state.data.runs.filter(isQueued);return runs.sort((a,b)=>{const ai=ids.indexOf(a.id),bi=ids.indexOf(b.id);return (ai<0?9999:ai)-(bi<0?9999:bi)||(a.queue_order||0)-(b.queue_order||0);});}
function runList(runs,queue=false){runs=queue?runs:recentRuns(runs);return `<div class="run-list">${runs.map((r,index)=>`<div class="run-row" data-run="${e(r.id)}" ${queue&&!readOnly()?'draggable="true"':''} tabindex="0" role="button" aria-label="Open ${e(r.name||r.id)}">${queue?`<span class="drag-handle" title="Drag to change queue order">${icon('grip')}</span><span class="run-order">${String(index+1).padStart(2,'0')}</span>`:''}<div class="run-main"><div class="run-name">${e(r.name||r.id)} ${status(r.status==='queued'&&r.ready===false?'held':r.status)}</div><div class="run-subtitle">${e(capacityWaitReason(r,state.data.projects,state.data.runs)||[state.data.projects.find(p=>p.id===r.project_id)?.name,r.host_name||state.data.hosts.find(h=>h.id===r.host_id)?.name].filter(Boolean).join(' · ')||'Awaiting resource assignment')}</div></div><div class="run-resources">${e(r.gpu_count??'?')} GPU${r.gpu_count===1?'':'s'}<span>${e(r.host_name||'Any host')}</span><span class="run-start">${runStartLabel(r)}</span><span class="run-duration" data-run-duration="${e(r.id)}">${e(runDuration(r))}</span></div>${queue?`<div class="run-actions"><button class="icon-button" data-action="move-run-up" data-id="${e(r.id)}" aria-label="Move ${e(r.name)} up" title="Move up" ${index===0?'disabled':''}${disabled()}>${icon('arrowUp')}</button></div>`:''}<span class="muted">${icon('chevron')}</span></div>`).join('')}</div>`;}
function isRegisteredDevice(host,device){if(device.allowed===false)return false;if(device.allowed===true)return true;return (host.gpus||[]).some(index=>String(index)===String(device.index));}
function runActivity(run){
 const value=run.last_activity_at??run.activity_at??run.finished_at??run.ended_at??run.started_at??run.created_at??run.created;
 if(value==null)return 0;const time=typeof value==='number'?value*1000:new Date(value).getTime();return Number.isFinite(time)?time:0;
}
function runTimestamp(value){if(value==null||value==='')return 0;const stamp=typeof value==='number'?value*1000:new Date(value).getTime();return Number.isFinite(stamp)&&stamp>0?stamp:0;}
function runStarted(run){return runTimestamp(run.started??run.started_at);}
function runStartLabel(run){const stamp=runStarted(run);return stamp?`Started <time datetime="${new Date(stamp).toISOString()}" title="${e(new Date(stamp).toLocaleString())}">${e(new Date(stamp).toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}))}</time>`:run.status==='queued'?'Not started':'Start time not recorded';}
function runDuration(run){
 const start=runStarted(run);if(!start)return '';
 const end=runTimestamp(run.finished??run.finished_at),done=terminal.has(run.status);
 if(done&&!end)return 'Duration not recorded';
 const seconds=Math.max(0,Math.floor(((end||Date.now())-start)/1000)),minutes=Math.floor(seconds/60),hours=Math.floor(minutes/60),days=Math.floor(hours/24);
 const duration=days?`${days}d ${hours%24}h ${minutes%60}m`:hours?`${hours}h ${minutes%60}m`:minutes?`${minutes}m ${seconds%60}s`:`${seconds}s`;
 return `${done?'Ran for':run.status==='running'?'Running for':'Elapsed'} ${duration}`;
}
function updateRunDurations(){for(const element of $$('[data-run-duration]')){const run=state.data?.runs.find(row=>row.id===element.dataset.runDuration);if(run)element.textContent=runDuration(run);}}
function recentRuns(runs){return [...runs].sort((a,b)=>runStarted(b)-runStarted(a)||runActivity(b)-runActivity(a)||String(b.id).localeCompare(String(a.id)));}
function visibleRuns(runs){return recentRuns(runs.filter(run=>state.runFilter==='archived'?run.presentation?.archived:!run.presentation?.archived&&(state.runFilter==='all'||state.runFilter==='active'&&!terminal.has(run.status)||state.runFilter==='finished'&&terminal.has(run.status)||state.runFilter==='failed'&&['failed','error'].includes(run.status))));}
function runBrowser(runs,{compute=false}={}){
 const priority=compute&&state.queuePriority,filtered=priority?queuedRuns():visibleRuns(runs);
 return `<div class="runs-toolbar"><div class="run-filter-group" role="group" aria-label="Filter runs">${[['active','Active'],['finished','Finished'],['failed','Failed'],['all','All'],['archived','Archived']].map(([value,label])=>`<button type="button" class="run-filter ${!priority&&state.runFilter===value?'selected':''}" data-action="filter-runs" data-filter="${value}" aria-pressed="${!priority&&state.runFilter===value}">${label}</button>`).join('')}</div>${compute?`<button type="button" class="button small-button queue-view-button ${priority?'selected':''}" data-action="queue-priority" aria-pressed="${priority}">${icon('grip')}Queue priority</button>`:''}</div><div class="runs-caption"><span>${filtered.length} of ${runs.length} runs</span><span>${priority?'Drag to set scheduler order':'Latest start first · unstarted below'}</span></div>${filtered.length?runList(filtered,priority):`<div class="document-empty run-empty"><h3>${priority?'The queue is clear':state.runFilter==='active'?'No active runs':state.runFilter==='finished'?'No finished runs':state.runFilter==='failed'?'No failed runs':'No runs yet'}</h3><p>${priority?'Prepare a run from an experiment when you’re ready.':runs.length?'Change the filter to see other runs.':'Prepare a run with its resource requirements and source PR.'}</p>${runs.length&&!priority?'<button class="button small-button" data-action="filter-runs" data-filter="all">Show all runs</button>':''}</div>`}`;
}
let refreshingCompute=false;
function refreshComputeButton(){return `<button type="button" class="button" data-action="refresh-compute" ${refreshingCompute?'disabled':''}${disabled()}>${refreshingCompute?'<span class="spinner"></span>':icon('refresh')}${refreshingCompute?'Requesting…':'Refresh availability'}</button>`;}
async function refreshComputeAvailability(){
 if(refreshingCompute||readOnly())return;refreshingCompute=true;
 const syncButtons=()=>$$('[data-action="refresh-compute"]').forEach(button=>{button.disabled=refreshingCompute||readOnly();button.innerHTML=refreshingCompute?'<span class="spinner"></span>Requesting…':icon('refresh')+'Refresh availability';});syncButtons();
 try{await action('compute.refresh');await refreshState(true);toast('GPU refresh requested. Readings update as each machine responds.');}
 catch(error){toast(error.message,true);}
 finally{refreshingCompute=false;syncButtons();}
}
function registeredGPUs(host){return [...new Set((host.gpus||[]).map(String))].map(index=>({index,device:(host.devices||[]).find(d=>String(d.index)===index)}));}
function gpuAvailability(host,device){
 if(device?.reserved_by)return 'reserved';
 if(!device||host.stale||device.stale||host.error||['offline','error','unreachable'].includes(host.status)||!isRegisteredDevice(host,device))return 'unknown';
 return device.occupied===false?'free':device.occupied===true?'busy':'unknown';
}
const gpuStateLabels={free:'Free',busy:'Busy',reserved:'Reserved',unknown:'Unknown'};
function projectCapacityCard(p){
 const use=projectCapacity(p,state.data.runs);return `<div class="project-capacity" data-capacity-project="${e(p.id)}"><strong>${e(p.name)}</strong><span><b>${use.gpus}</b> / ${e(use.gpuLimit)} GPUs</span><span><b>${use.runs}</b> / ${e(use.runLimit)} runs</span><button class="button small-button" data-action="edit-project-limits" data-project-id="${e(p.id)}">Edit limits</button></div>`;
}
function projectCapacityCards(){const projects=state.data.projects.filter(p=>projectWorkflow(p)==='research');return projects.length?`<section class="project-capacities" aria-label="Project allocation"><div class="section-title">Project allocation <small class="muted">Active and reserved usage</small></div>${projects.map(projectCapacityCard).join('')}</section>`:'';}
function runPlacement(run){const p=state.data.projects.find(p=>p.id===run.project_id),candidates=Array.isArray(run.candidate_hosts)?run.candidate_hosts:[];return `<section class="run-placement" aria-label="Placement"><h3>Placement</h3>${p?projectCapacityCard(p):''}${candidates.length?`<details><summary>${candidates.length} candidate node${candidates.length===1?'':'s'}</summary><div class="run-candidates">${candidates.map(node=>`<div><strong>${e(node.host_name||node.host_id)}</strong><span>${e(node.wait_reason||(node.wait_reasons||[]).join('; ')||node.state||'Awaiting check')}</span></div>`).join('')}</div></details>`:''}</section>`;}
function renderCompute(){
 const hosts=state.data.hosts,running=state.data.runs.filter(r=>active.has(r.status)),queue=queuedRuns(),availability=hosts.flatMap(h=>registeredGPUs(h).map(({device})=>gpuAvailability(h,device))),knownFree=availability.filter(value=>value==='free').length,unknown=availability.filter(value=>value==='unknown').length;
 return `<div class="page compute-page"><div class="page-eyebrow">${icon('server')}Across your projects</div><div class="page-heading"><div><h1>Compute</h1><p>Available GPUs, at a glance.</p></div><div class="heading-actions">${refreshComputeButton()}<button class="button" data-action="add-host"${disabled()}>${icon('plus')}Register machine</button></div></div><div class="compute-summary"><div><strong>${availability.length}</strong>Registered GPUs</div><div><strong>${knownFree}</strong>Observed available${unknown?`<small>${unknown} unknown</small>`:''}</div><div><strong>${running.length}</strong>Running now</div><button type="button" class="queue-summary-jump" data-action="jump-queue" aria-label="Show ${queue.length} queued runs"><strong>${queue.length}</strong>In the queue</button></div><div class="section-title machine-section-title">Registered machines <span class="muted">${hosts.length} nodes</span></div><div class="gpu-legend" aria-label="GPU availability legend">${Object.entries(gpuStateLabels).map(([value,label])=>`<span class="gpu-state-${value}"><i></i>${label}</span>`).join('')}<span class="gpu-legend-note">One bar per GPU · expand for memory and utilization</span></div>${hosts.length?`<div class="host-list">${hosts.map(renderHost).join('')}</div>`:empty('Register your compute','Add this workspace computer or an SSH target and select its GPUs.',`<button class="button" data-action="add-host"${disabled()}>${icon('plus')}Register machine</button>`)}<div class="compute-reading-note">Free means observed idle and unreserved. Unknown readings are excluded; project requirements still apply.</div>${projectCapacityCards()}<div class="queue-header"><div><h2 id="compute-runs-heading" tabindex="-1">Runs ${state.data.queue.paused?'<span class="badge held">Launches paused</span>':''}</h2><p>Active work first. Use Queue priority to reorder waiting runs.</p></div><button class="button small-button" data-action="${state.data.queue.paused?'resume-queue':'pause-queue'}"${disabled()}>${icon(state.data.queue.paused?'play':'pause')}${state.data.queue.paused?'Resume launches':'Pause launches'}</button></div>${state.data.queue.paused?'<div class="notice warn">New launches are paused. Existing training processes continue.</div>':''}${runBrowser(state.data.runs,{compute:true})}</div>`;
}
function renderWandbResults(){
 const x=state.experiment||experiment(),sync=x?.wandb_sync||{},syncNote=sync.status==='error'?`<div class="notice warn">W&B setup needs attention: ${e(sync.error||'The experiment could not be synchronized.')}</div>`:sync.status==='pending'?'<div class="notice"><span class="spinner"></span> Setting up this experiment in Weights & Biases…</div>':'';if(!x)return empty('Results unavailable','Select an experiment to view its results.');const cached=metricsCache.get(x.id),entry=cached?.url===x.wandb_url?cached:null;
 if(!x.wandb_url&&sync.status==='pending')return `${syncNote}<div class="document-empty"><h3>Your experiment link is being prepared</h3><p>Results and parameters will appear in its W&B workspace once setup finishes.</p><button class="button small-button" data-action="configure-wandb">Use an existing W&B link</button></div>`;
 if(!x.wandb_url)return syncNote+empty('Bring the evidence into view','Connect a Weights & Biases run, experiment group or project to see its measured curves here.',`<button class="button" data-action="configure-wandb">${icon('chart')}Connect Weights & Biases</button>`);
 if(!entry||entry.loading&&!entry.data)return `<div class="loading-state"><span class="spinner"></span><p>Reading Weights & Biases metrics…</p></div>`;
 const data=entry.data||{},series=data.series||[],keys=[...new Set(series.map(s=>s.key))].sort();
 if(!keys.includes(selectedMetric))selectedMetric=keys.find(k=>/loss/i.test(k))||keys.find(k=>/success/i.test(k))||keys[0];
 const selected=series.filter(s=>s.key===selectedMetric),runScoped=/\/runs\//.test(x.wandb_url),groupScoped=/\/groups\//.test(x.wandb_url),scoped=runScoped||groupScoped,runCount=(data.runs||[]).length;
 return `${syncNote}<div class="document-toolbar"><span>${icon('chart')}W&B · ${runScoped?'Linked run':groupScoped?`Experiment group · latest ${runCount} runs`:`latest ${runCount} runs`} · sampled</span><div class="toolbar-actions"><button class="icon-button" data-action="refresh-metrics" title="Refresh W&B metrics" aria-label="Refresh W&B metrics" ${entry.loading?'disabled':''}>${icon('refresh')}</button>${link(x.wandb_url,`${icon('external')}Open W&B`,'button small-button')}</div></div>${!scoped?'<div class="notice">This project link shows recent W&B runs. They may include work outside this experiment. Connect a specific run URL to narrow the view.</div>':''}${entry.error||data.error?`<div class="notice warn">${e(entry.error||data.error)}</div>`:''}${keys.length?`<div class="chart-toolbar"><label class="field"><span>Metric</span><select id="metric-select">${keys.map(k=>`<option value="${e(k)}" ${k===selectedMetric?'selected':''}>${e(k)}</option>`).join('')}</select></label><span class="small muted">${e(elapsed(data.updated_at))}</span></div><div class="metric-chart">${metricChart(selected,selectedMetric)}</div><div class="chart-legend">${selected.map((s,i)=>`<div><span style="background:${currentChartColors()[i%chartColors.length]}"></span>${e(s.run_name||s.run_id)}</div>`).join('')}</div><div class="section-title">Latest sampled values</div><div class="markdown"><table><thead><tr><th>Run</th><th>${e(selectedMetric)}</th><th>Step</th></tr></thead><tbody>${selected.map(s=>{const p=s.points?.at(-1);return `<tr><td>${e(s.run_name||s.run_id)}</td><td>${p?e(formatNumber(p.y)):'—'}</td><td>${p?e(formatNumber(p.x)):'—'}</td></tr>`;}).join('')}</tbody></table></div>`:`<div class="document-empty"><h3>No numeric history returned</h3><p>Parameters and scheduler status are recorded separately from measured results. Curves appear after training or evaluation logs metrics to this W&B destination.</p><button class="button small-button" data-action="configure-wandb">Edit W&B link</button></div>`}`;
}
const chartColors=['#55764a','#c09653','#748da4','#af7867','#8a7da3','#609995'];
function currentChartColors(){if(!document.documentElement.dataset.vscodeTheme)return chartColors;const style=getComputedStyle(document.documentElement);return chartColors.map((fallback,index)=>style.getPropertyValue('--theme-chart-'+(index+1)).trim()||fallback);}
function formatNumber(n){const value=Number(n);if(!Number.isFinite(value))return '—';if(value===0)return '0';if(Math.abs(value)>=10000||Math.abs(value)<.001)return value.toExponential(2);return new Intl.NumberFormat(undefined,{maximumSignificantDigits:4}).format(value);}
function metricChart(series,key){const width=720,height=300,pad={top:20,right:20,bottom:42,left:62},points=series.flatMap(s=>s.points||[]).filter(p=>p.x!=null&&p.y!=null&&Number.isFinite(Number(p.x))&&Number.isFinite(Number(p.y)));if(!points.length)return '<div class="document-empty">No finite metric points to display.</div>';let xmin=Math.min(...points.map(p=>Number(p.x))),xmax=Math.max(...points.map(p=>Number(p.x))),ymin=Math.min(...points.map(p=>Number(p.y))),ymax=Math.max(...points.map(p=>Number(p.y)));if(xmin===xmax)xmax=xmin+1;if(ymin===ymax){const margin=Math.abs(ymin)*.05||1;ymin-=margin;ymax+=margin;}const scaleX=x=>pad.left+(Number(x)-xmin)/(xmax-xmin)*(width-pad.left-pad.right),scaleY=y=>height-pad.bottom-(Number(y)-ymin)/(ymax-ymin)*(height-pad.top-pad.bottom);let svg='';for(let i=0;i<=4;i++){const value=ymin+(ymax-ymin)*i/4,y=scaleY(value);svg+=`<line x1="${pad.left}" y1="${y}" x2="${width-pad.right}" y2="${y}" stroke="#e6ebdf"/><text x="${pad.left-12}" y="${y+4}" text-anchor="end">${e(formatNumber(value))}</text>`;const xv=xmin+(xmax-xmin)*i/4;svg+=`<text x="${scaleX(xv)}" y="${height-17}" text-anchor="middle">${e(formatNumber(xv))}</text>`;}series.forEach((s,i)=>{const valid=(s.points||[]).filter(p=>p.x!=null&&p.y!=null&&Number.isFinite(Number(p.x))&&Number.isFinite(Number(p.y))),color=currentChartColors()[i%chartColors.length];if(valid.length>1)svg+=`<polyline points="${valid.map(p=>`${scaleX(p.x)},${scaleY(p.y)}`).join(' ')}" fill="none" stroke="${color}" stroke-width="2.2"/>`;if(valid.length===1)svg+=`<circle cx="${scaleX(valid[0].x)}" cy="${scaleY(valid[0].y)}" r="3" fill="${color}"/>`;});return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${e(key)} by training step">${svg}</svg><div class="chart-axis-label">Training step</div>`;}
async function loadMetrics(force=false){const x=state.experiment;if(!x?.wandb_url)return;const existing=metricsCache.get(x.id);if(existing?.loading&&existing.url===x.wandb_url||!force&&existing?.loadedAt&&Date.now()-existing.loadedAt<60000&&existing.url===x.wandb_url)return;const entry={...(existing?.url===x.wandb_url?existing:{}),loading:true,url:x.wandb_url};metricsCache.set(x.id,entry);if(pageHasTile('results')&&!state.edit&&!$('#modal').open)renderMain();try{entry.data=await api('metrics?id='+encodeURIComponent(x.id)+(force?'&refresh=1':''));entry.error=null;}catch(error){entry.error=error.message;}finally{entry.loading=false;entry.loadedAt=Date.now();if(state.experimentId===x.id&&pageHasTile('results')&&!state.edit&&!$('#modal').open)renderMain();}}
function hostObservation(h){const age=h.age_seconds!=null&&Number.isFinite(Number(h.age_seconds))?(Number(h.age_seconds)<60?'Just now':`${Math.floor(Number(h.age_seconds)/60)}m ago`):elapsed(h.observed_at),next=h.next_refresh_at?new Date(typeof h.next_refresh_at==='number'?h.next_refresh_at*1000:h.next_refresh_at).getTime():NaN,remaining=Number.isFinite(next)?Math.ceil((next-Date.now())/60000):null;return `Observed ${age}${remaining!==null?remaining>0?` · next refresh in ${remaining}m`:' · refresh due':''}`;}
function renderHost(h){
 const gpus=registeredGPUs(h),free=gpus.filter(({device})=>gpuAvailability(h,device)==='free').length,unknown=gpus.filter(({device})=>gpuAvailability(h,device)==='unknown').length,observation=hostObservation(h),devices=h.devices||[];
 const bars=gpus.map(({index,device})=>{const value=gpuAvailability(h,device),label=gpuStateLabels[value],memory=device?.memory_free_mib!=null?` · ${(device.memory_free_mib/1024).toFixed(1)} GiB free VRAM`:'',title=`GPU ${index} · ${device?.name||'Device not observed'} · ${label}${device?.reserved_by?' · '+device.reserved_by:''}${memory} · ${observation}`;return `<span class="gpu-slot gpu-state-${value}" data-gpu="${e(index)}" data-availability="${value}" title="${e(title)}" aria-label="${e(title)}"><span><b>${e(index)}</b><small>${label}</small></span><i></i></span>`;}).join('');
 return `<details class="host-card compact-host" data-host="${e(h.id)}"><summary><span class="host-identity"><span class="host-title" title="${e(h.name)}">${e(h.name)}</span><span class="host-target" title="${e((h.target||'Workspace computer')+' · '+observation)}">${e(h.target||'Workspace computer')}</span></span><span class="host-count" title="${free} observed free of ${gpus.length} registered GPUs${unknown?`; ${unknown} unknown`:''}">${gpus.length?`<strong>${free}<span> / ${gpus.length}</span></strong><small>free${unknown?` · ${unknown} ?`:''}</small>`:'CPU only'}</span><span class="host-gpu-strip" aria-label="${e(h.name)} GPUs">${bars||'<span class="muted">No registered GPUs</span>'}</span><span class="host-chevron">${icon('chevronDown')}</span></summary><div class="host-details"><div class="host-observation">${status(h.stale?'stale':h.status||'unknown')}<span>${e(observation)}</span></div>${h.error?`<details class="observation-error"><summary>Observation unavailable · Show details</summary><pre>${e(h.error)}</pre></details>`:''}${devices.length?devices.map(d=>{const used=d.memory_total_mib!=null&&d.memory_free_mib!=null?Math.max(0,d.memory_total_mib-d.memory_free_mib):null,ratio=used!==null&&d.memory_total_mib>0?Math.min(100,used/d.memory_total_mib*100):0,value=gpuAvailability(h,d),label=!isRegisteredDevice(h,d)?'Not registered':value==='free'?'Available':gpuStateLabels[value];return `<div class="gpu-device"><div class="gpu-device-heading"><strong>GPU ${e(d.index)} · ${e(d.name||'Unknown device')}</strong><span>${label}</span></div><div class="gpu-bar"><span style="width:${ratio}%"></span></div><div class="gpu-caption"><span>${used===null?'Memory not observed':`${(used/1024).toFixed(1)} / ${(d.memory_total_mib/1024).toFixed(0)} GiB used`}</span><span>${d.utilization==null?'Utilization unknown':`${e(d.utilization)}% utilization`}</span></div></div>`;}).join(''):'<div class="notice">No GPU observation available.</div>'}</div></details>`;
}
let workspacePermissionSaving=false;
function permissionLabel(mode){return {ask:'Ask for approval',auto_review:'Approve for me',yolo:'YOLO'}[mode]||'Ask for approval';}
function renderWorkspacePreferences(settings){
 const zone=Intl.DateTimeFormat().resolvedOptions().timeZone||settings.timezone||'Not reported';
 return `<section class="settings-block"><h2>Default permissions</h2><p>Saved automatically on this workspace, including after closing and reopening SuperSurfer. Used by conversations that inherit the default. Approval handling updates now; full access and automatic review begin with the next turn. Restricting an active full-access turn stops it.</p><label class="field workspace-permissions"><span>Permission mode</span><select id="workspace-approval-mode" name="approval_mode"${disabled()||(workspacePermissionSaving?' disabled':'')}>${['ask','auto_review','yolo'].map(mode=>`<option value="${mode}" ${settings.approval_mode===mode||!settings.approval_mode&&mode==='ask'?'selected':''}>${permissionLabel(mode)}</option>`).join('')}</select><small id="workspace-permissions-status" role="status">Saved on this workspace. YOLO gives full access without approval prompts.</small></label></section><section class="settings-block"><h2>Timezone</h2><p>Automatic · <strong>${e(zone)}</strong></p><div class="small muted">Uses this computer’s local timezone for agent context and recurring reviews.</div></section>`;
}
let timezoneSyncing=false,lastSyncedTimezone=null;
async function syncClientTimezone(){
 if(!state.data||readOnly()||timezoneSyncing)return;
 const zone=Intl.DateTimeFormat().resolvedOptions().timeZone;if(!zone)return;
 if(state.data.settings.timezone===zone||lastSyncedTimezone===zone){lastSyncedTimezone=zone;return;}
 timezoneSyncing=true;
 try{await action('settings.save',{timezone:zone});state.data.settings.timezone=zone;lastSyncedTimezone=zone;}
 catch(error){toast('Device timezone could not be saved: '+error.message,true);}
 finally{timezoneSyncing=false;}
}

function syncSettingsView(){
 const s=state.data.settings,form=$('#settings-form'),dirty=form?.dataset.dirty==='true';
 workspaceAccounts.mount($('#workspace-accounts'));
 if(form&&!dirty&&!form.contains(document.activeElement)&&!workspacePermissionSaving){for(const role of modelRoles){const model=$('#model-'+role),reasoning=$('#reasoning-'+role);model.value=s.models?.[role]||'';const value=s.reasoning?.[role]||'medium';if(![...reasoning.options].some(option=>option.value===value)){const option=document.createElement('option');option.value=value;option.textContent=value;reasoning.append(option);}reasoning.value=value;}form.elements.monitor_enabled.checked=!!s.monitor_enabled;form.elements.monitor_interval_minutes.value=s.monitor_interval_minutes||15;$('#workspace-approval-mode').value=s.approval_mode||'ask';}
 const models=$('#model-options'),markup=state.models.map(m=>`<option value="${e(m.id)}">${e(m.displayName||m.id)}</option>`).join('');if(models&&models.innerHTML!==markup)models.innerHTML=markup;
 const monitor=$('#settings-monitor-status');if(monitor)monitor.textContent='Last check: '+date(state.data.monitoring.last_check)+(state.data.monitoring.next_check?' · Next: '+date(state.data.monitoring.next_check):'');
}
async function configureEditorExtension(extensionId){
 if(editorSettings.get().engine!=='vscode')throw new Error('Select VS Code workbench in the Editor setting above, then save editor defaults.');
 const projectId=state.projectId||state.data.projects[0]?.id;if(!projectId)throw new Error('Connect a project to open the extension’s editor settings.');
 const session=await action('editor.open',{project_id:projectId,experiment_id:null,client_id:sessionStorage.getItem('supersurfer-editor-window')});
 await action('editor.command',{id:session.id,kind:'settings',extension_id:extensionId});
 await navigate({view:'workspace',projectId,experimentId:null,tab:'_files'});
}
function renderAgentDefaults(s){
 const catalog=state.codexModels||(modelCatalogBackend==='codex'?state.models:[]);
 return `<div class="agent-defaults"><h3>Agent defaults</h3><p class="small muted">New conversations use these defaults. Existing conversations keep their backend; Cursor and Claude models are chosen in chat.</p><datalist id="model-options">${catalog.map(m=>`<option value="${e(m.id)}">${e(m.displayName||m.id)}</option>`).join('')}</datalist>${modelRoles.map(role=>{const codex=(s.backends?.[role]||'codex')==='codex';return `<div class="agent-default-row" data-agent-role="${role}"><strong>${{manager:'Workspace manager',lead:'Project lead',worker:'Worker'}[role]}</strong><label class="field"><span>Provider</span><select class="control" name="backend_${role}" aria-label="${role} backend">${Object.entries(backendLabels).map(([id,label])=>`<option value="${id}" ${(s.backends?.[role]||'codex')===id?'selected':''}>${label}</option>`).join('')}</select></label><label class="field agent-default-model" ${codex?'':'hidden'}><span>Model</span><input class="control" id="model-${role}" name="model_${role}" list="model-options" placeholder="Provider default" value="${e(s.models?.[role]||'')}" ${codex?'':'disabled'}></label><label class="field agent-default-effort" ${codex?'':'hidden'}><span>Effort</span><select class="control" id="reasoning-${role}" name="reasoning_${role}" ${codex?'':'disabled'}>${[...new Set([...reasoningValues(catalog.find(m=>m.id===s.models?.[role])||catalog.find(m=>m.isDefault)),s.reasoning?.[role]||'medium'])].map(v=>`<option ${s.reasoning?.[role]===v?'selected':''} value="${v}">${effortLabel(v)}</option>`).join('')}</select></label><span class="agent-default-chat small muted" ${codex?'hidden':''}>Model selected in chat</span></div>`;}).join('')}</div>`;
}
function updateAgentDefaultFields(event){
 const select=event.target.closest('[name^="backend_"]');if(!select)return;
 const row=select.closest('.agent-default-row'),codex=select.value==='codex';if(!row)return;
 for(const field of row.querySelectorAll('.agent-default-model,.agent-default-effort')){field.hidden=!codex;field.querySelector('input,select').disabled=!codex;}
 row.querySelector('.agent-default-chat').hidden=codex;
}
function renderSettings(){const s=state.data.settings;return `<div class="page"><div class="page-eyebrow">${icon('settings')}Your workspace</div><div class="page-heading"><div><h1>Settings</h1><p>Defaults for this workspace. Projects can override them in their Surfboards.</p></div></div><form id="settings-form"><section class="settings-block coding-backends"><h2>Coding backends</h2><p>Connect the providers you use on this machine, then choose defaults for new agents.</p><div id="workspace-accounts"></div>${renderAgentDefaults(s)}</section>${renderWorkspacePreferences(s)}<section class="settings-block"><h2>Experiment monitoring</h2><p>Checks run status while the workspace computer is on, including when this app is closed. This does not run recurring agent turns or launch experiments.</p><div class="settings-row"><label class="toggle-label"><input type="checkbox" name="monitor_enabled" ${s.monitor_enabled?'checked':''}>Monitor run status</label><label class="field"><span>Check every (minutes)</span><input type="number" name="monitor_interval_minutes" min="1" max="1440" required value="${e(s.monitor_interval_minutes||15)}"></label></div><div class="small muted" id="settings-monitor-status">Last check: ${e(date(state.data.monitoring.last_check))}${state.data.monitoring.next_check?` · Next: ${e(date(state.data.monitoring.next_check))}`:''}</div>${state.data.monitoring.alerts?.length?`<div class="notice">${state.data.monitoring.alerts.slice(-5).map(a=>e(typeof a==='string'?a:a.message||JSON.stringify(a))).join('<br>')}</div>`:''}</section><div class="settings-footer"><button class="button primary" type="submit">Save settings</button></div></form>${renderAppearance()}<section class="settings-block" id="editor-settings"></section></div>`;}
function renderAppearance(){
 const themeApi=window.superSurferTheme,selected=themeApi?.preference||'system',themes=themeApi?.themes||[],custom=selected.startsWith('vscode:'),missing=custom&&!themes.some(theme=>theme.id===selected);
 return `<section class="settings-block appearance-block"><h2>Appearance</h2><p>Choose a theme for this app. System follows your device’s appearance.</p><div class="theme-picker" role="group" aria-label="Color theme">${['light','dark','system'].map(theme=>`<button type="button" class="theme-option ${selected===theme?'selected':''}" data-action="theme" data-theme-choice="${theme}" aria-pressed="${selected===theme}"><span class="theme-preview ${theme}" aria-hidden="true"><i></i><b></b><em></em></span><span>${theme.charAt(0).toUpperCase()+theme.slice(1)}</span>${icon('check')}</button>`).join('')}</div><div class="vscode-theme-controls"><label class="field"><span>VS Code color theme</span><select id="vscode-theme" aria-label="VS Code color theme"><option value="" ${!custom?'selected':''}>${themeApi?.loading?'Loading color themes…':'Choose a color theme…'}</option>${missing?`<option value="${e(selected)}" selected>${e(selected)} (unavailable)</option>`:''}${themes.map(theme=>`<option value="${e(theme.id)}" ${selected===theme.id?'selected':''}>${e(theme.name)} · ${theme.type==='light'||theme.type==='hcLight'?'Light':'Dark'}</option>`).join('')}</select><small>${themes.length} available themes${window.superSurferDesktop?.importTheme?' · Includes installed and imported VS Code themes.':'.'}</small></label>${window.superSurferDesktop?.importTheme?`<button type="button" class="button small-button" data-action="import-theme">${icon('plus')}Import theme JSON</button>`:''}</div>${themeApi?.error?`<div class="notice warn">${e(themeApi.error)}</div>`:''}</section>`;
}
function accountLabel(){const value=state.accounts?.codex||(state.account?.backend&&state.account.backend!=='codex'?null:state.account);const account=value?.account||value;if(!account)return 'Checking account…';if(account.error)return 'Codex unavailable';if(account.email)return account.email;if(account.type)return account.type==='chatgpt'?'ChatGPT connected':`${backendLabels[account.type]||account.type} connected`;return 'Not connected';}
function bindMain(){workspaceAccounts.mount($('#workspace-accounts'));const editorRoot=$('#editor-settings');if(editorRoot)editorSettings.mount(editorRoot);else editorSettings.unmount();const compute=$('#project-compute-form');if(compute){compute.addEventListener('input',readComputeForm);compute.addEventListener('change',readComputeForm);compute.addEventListener('submit',saveProjectCompute);}$('#vscode-theme')?.addEventListener('change',event=>{if(event.target.value)window.superSurferTheme?.setPreference(event.target.value);});const form=$('#settings-form');if(form){form.addEventListener('input',event=>{if(event.target.id!=='workspace-approval-mode')form.dataset.dirty='true';});form.addEventListener('change',updateAgentDefaultFields);$('#workspace-approval-mode',form)?.addEventListener('change',saveDefaultPermissions);form.addEventListener('submit',saveSettings);}$('#document-editor')?.addEventListener('input',stashEditor);$('#metric-select')?.addEventListener('change',event=>{selectedMetric=event.target.value;renderMain();});}
function syncAgentChooser(){
 if(!state.data)return;const agents=scopedAgents(),previous=state.scope;
 if(isSurfboard())state.scope=surfboardScope();else if(state.pinnedAgent)state.scope=state.pinnedAgent.scope;else if(!agents.some(agent=>agent.scope===state.scope))state.scope=currentScope();
 if(previous!==state.scope){state.chat=null;state.chatSignature='';restoreMessageDraft();}
 updateChatHeader();
}
function pendingQuestions(){return (state.chat?.questions||[]).some(item=>item.status==='pending');}
function pendingApprovals(){return (state.chat?.approvals||[]).some(item=>item.status==='pending');}
const chatSending = new Set();
function updateChatHeader(){
 const pin=$('#chat-pin');pin.hidden=!!state.scope?.startsWith('agent:');pin.disabled=!state.scope;pin.setAttribute('aria-pressed',String(!!state.pinnedAgent));pin.title=state.pinnedAgent?'Unpin agent · follow the current page':'Pin agent · keep this chat while navigating';pin.setAttribute('aria-label',state.pinnedAgent?'Unpin agent':'Pin agent');
 const native=state.scope?.startsWith('agent:'),a=native?state.data?.agents.find(a=>`agent:${a.id}`===state.scope):null,role=state.chat?.preferences?.role||(state.scope==='manager'?'manager':state.scope?.startsWith('project:')?'lead':'worker'),chatAgent=state.chat?.agent;
 const busy=!!state.chat?.busy,question=pendingQuestions(),approval=pendingApprovals(),sending=chatSending.has(state.scope),steerable=busy&&state.chat?.steerable===true&&!question&&!approval;
 const supportsSteering=!native&&state.chat?.capabilities?.steering!==false&&state.chat?.preferences?.capabilities?.steering!==false;
 $('#chat-name').textContent=selectedAgent()?.name||chatAgent?.name||a?.name||({manager:'Workspace manager',lead:leadLabel(),worker:itemLabel()+' agent'}[role]);
 $('#chat-meta').textContent=`${native?'AutoML-owned session':'SuperSurfer conversation'} · ${native?(chatAgent?.model||a?.model||state.chat?.preferences?.effective?.model||'Native Codex default / not reported'):(chatAgent?.model||state.chat?.preferences?.effective?.model||state.data?.settings.models?.[role]||'Codex default')}`;
 $('#chat-policy').textContent=isSurfboard()?'Describe changes to your workflow. Review the draft before applying.':native?'Message the existing agent in its original session.':role==='manager'?'Coordinate project work and shared resources.':projectWorkflow()==='research'?'Ideas are suggestions. Runs need your request and a verified PR.':'Work follows this project’s surfboard, permissions, and your instructions.';
 if(state.pinnedAgent){const origin=state.pinnedAgent,p=state.data?.projects.find(p=>p.id===origin.projectId),item=state.data?.experiments.find(x=>x.id===origin.experimentId);$('#chat-meta').textContent='Pinned · '+[p?.name,item?.name].filter(Boolean).join(' / ')+(origin.scope==='manager'?'Workspace manager':'');}
 $('#chat-name').title=$('#chat-name').textContent;$('#chat-meta').title=$('#chat-meta').textContent+' · '+$('#chat-policy').textContent;
 $('#chat-input').placeholder=busy?(supportsSteering?'Add direction for the current work…':'Draft your next message…'):isSurfboard()?'Describe a workflow change…':state.experimentId?`Ask about this ${itemLabel()}…`:'Discuss your next project step…';$('#chat-input').disabled=readOnly()||!accountGate.ready();
 chatContext.setDisabled(readOnly()||native||!state.scope||!chatAcceptsProject(state.projectId));const send=$('#chat-send');send.disabled=readOnly()||chatPreferenceSaveScope===state.scope||!accountGate.ready()||fileUploads.pending(state.scope)||sending||question||approval||(busy&&!steerable);send.hidden=false;send.classList.toggle('steer-button',busy&&supportsSteering);send.setAttribute('aria-label',busy&&supportsSteering?'Steer current work':'Send message');send.title=busy?(supportsSteering?'Add direction without stopping the current turn':'Wait for this turn to finish, or Stop before sending another message'):'Send message';send.innerHTML=sending?'<span class="spinner"></span>':icon('arrowUp');
 $('#chat-stop').hidden=!busy||native;
 $('#chat-hint').textContent=fileUploads.pending(state.scope)?'Uploading attachment…':readOnly()?'Read-only connection':!accountGate.ready()?accountGate.hint():question?'Answer the question above to continue':approval?'Review the approval request above':sending?(busy&&supportsSteering?'Sending direction…':'Sending message…'):steerable?'Steer adds direction to the current work':busy?(supportsSteering?'Agent is starting or finishing · Direction will be available shortly':'Wait for this turn to finish, or Stop before sending another message'):'Enter to send · Shift Enter for a new line';
 renderAgentChooser();renderChatPreferences();renderChatApprovals();renderChatQuestions();renderChatTasks();renderAgentSessionState();
 const archived=state.chat?.archived===true||selectedAgent()?.archived===true,archive=$('#chat-archive'),archiveLabel=archived?'Restore agent chat':'Archive agent chat';archive.setAttribute('aria-label',archiveLabel);archive.title=archived?'Restore chat':'Archive chat · existing work and monitoring continue';archive.disabled=readOnly()||!state.chat||agentMutations.has('archive:'+state.scope);archive.innerHTML=icon(archived?'history':'archive');
 $('#chat-archive').hidden=!!isSurfboard();$('#chat-rename').hidden=native||!!isSurfboard();$('#chat-rename').disabled=readOnly();
}
function reasoningValues(model) {
  return [...new Set((model?.supportedReasoningEfforts || model?.supported_reasoning || []).map(item => typeof item === 'string' ? item : item.reasoningEffort || item.reasoning_effort).filter(Boolean))];
}
function effortLabel(value) { return value ? String(value).charAt(0).toUpperCase() + String(value).slice(1) : currentBackend()==='codex'?'Codex default':'Not available'; }
function renderChatPreferences() {
  const container=$('#chat-preferences'),notices=$('#chat-preference-notices');if(!container||!notices)return;
  const preferences=state.chat?.preferences;
  if(!preferences){const signature=state.scope+':loading';if(container.dataset.signature!==signature){container.dataset.signature=signature;container.innerHTML='';notices.hidden=false;notices.innerHTML='<div class="chat-preference-note">Loading conversation settings…</div>';}return;}
  const native=state.scope?.startsWith('agent:');
  const defaults=preferences.defaults||{},overrides=preferences.overrides||{},effective=preferences.effective||{},role=preferences.role||'worker',saving=chatPreferenceSaveScope===state.scope,pending=chatPreferenceSaveScope!==null;
  const editable=preferences.editable===true&&!readOnly()&&!pending;
  const backend=preferences.backend||'codex',capabilities=preferences.capabilities||{reasoning:true,fast_mode:true,auto_review:true};
  const selectedModel=overrides.model??'',modelId=effective.model||selectedModel||defaults.model;
  const catalogModel=state.models.find(model=>model.id===modelId||model.model===modelId);
  const modelChoices=(modelCatalogBackend===backend?state.models:[]).map(model=>({id:model.id||model.model,label:model.displayName||model.display_name||model.id||model.model})).filter(model=>model.id);
  if(selectedModel&&!modelChoices.some(model=>model.id===selectedModel))modelChoices.unshift({id:selectedModel,label:selectedModel+' (current)'});
  const selectedEffort=overrides.reasoning??'';
  const currentSupport=reasoningValues({supported_reasoning:preferences.supported_reasoning});
  const supported=currentSupport.length?currentSupport:reasoningValues(catalogModel);
  const efforts=[...supported];
  if(selectedEffort&&!efforts.includes(selectedEffort))efforts.push(selectedEffort);
  const roleName={manager:'Manager',lead:leadLabel(),worker:'Worker'}[role]||role;
  const hasOverride=overrides.model!=null||overrides.reasoning!=null;
  const note=saving?'Saving conversation settings…':pending?'Finishing settings for the previous conversation…':readOnly()?'Read-only connection':preferences.error||preferences.note||(!preferences.editable?'This agent’s runtime settings are managed by AutoML.':state.chat?.busy?'Applies to the next turn. Current work continues.':'Applies to the next turn in this conversation.');
  const signature=JSON.stringify([state.scope,preferences,state.models,chatPreferenceSaveScope,readOnly(),!!state.chat?.busy]);
  if(container.dataset.signature===signature)return;
  // Polls do not replace an open selector; it catches up after the field loses focus.
  if(container.contains(document.activeElement)&&!pending)return;
  container.dataset.signature=signature;
  const fast=effective.fast_mode===true,approvalMode=effective.approval_mode||'ask',selectedApproval=overrides.approval_mode??'',defaultApproval=defaults.approval_mode||state.data?.settings.approval_mode||'ask';
  const runtime=preferences.runtime||{},runtimeMode=runtime.approval_mode||runtime.runtime_approval_mode,active=runtime.active===true,stopping=['stopping','interrupted'].includes(runtime.status),fullAccess=['danger-full-access','dangerFullAccess'].includes(runtime.active_sandbox);
  const permissionMismatch=active&&!stopping&&runtimeMode&&runtimeMode!==approvalMode;
  const reviewerChanges=active&&runtime.runtime_approval_mode&&runtime.runtime_approval_mode!==approvalMode&&(runtime.runtime_approval_mode==='auto_review'||approvalMode==='auto_review');
  const permissionNote=native?'':active&&(stopping||fullAccess&&approvalMode!=='yolo')?'Stopping current work. Continue when ready to use the selected permissions.':permissionMismatch?`Current turn: ${permissionLabel(runtimeMode)}. Selected: ${permissionLabel(approvalMode)}.`:approvalMode==='yolo'?active&&!fullAccess?(runtimeMode==='yolo'?'YOLO approvals apply now. Full access starts next turn.':'YOLO selected. Full access starts next turn.'):'':reviewerChanges?'Codex’s reviewer setting changes next turn. Current approval requests remain visible.':'';
  const prominentNote=saving||pending||readOnly()||preferences.error||preferences.note||!preferences.editable;
  const defaultModel=defaults.resolved_model||defaults.model||(native?'Not reported':'Codex default');
  const description=`${native?'AutoML runtime':roleName+' defaults'} · ${defaultModel} · ${effortLabel(defaults.resolved_reasoning??defaults.reasoning)}. ${note}`;
  const backendSelect=`<label class="composer-backend-field"><span>Backend</span><select id="chat-backend" aria-label="Conversation backend" ${editable&&!state.chat?.messages?.length&&!state.chat?.thread_id?'':'disabled'}>${Object.entries(backendLabels).map(([id,label])=>`<option value="${id}" ${backend===id?'selected':''}>${label}</option>`).join('')}</select></label>`;
  container.innerHTML=`${backendSelect}<div class="composer-settings-grid"><label class="composer-model-field"><span>Model</span><select id="chat-model" aria-label="Conversation model" ${editable?'':'disabled'} title="${e(description)}"><option value="" ${selectedModel===''?'selected':''}>${e(native?effective.model||'Native default':defaultModel)}${native?'':' (default)'}</option>${modelChoices.map(model=>`<option value="${e(model.id)}" ${selectedModel===model.id?'selected':''}>${e(model.label)}</option>`).join('')}</select></label><label class="composer-effort-field"><span>${selectedEffort===''?'Effort · default':'Effort'}</span><select id="chat-reasoning" aria-label="Conversation reasoning effort" ${editable&&capabilities.reasoning?'':'disabled'} title="${e(roleName)} default: ${e(effortLabel(defaults.resolved_reasoning??defaults.reasoning))}. Applies to the next turn."><optgroup label="${e(native?'Native runtime':roleName+' default')}"><option value="" ${selectedEffort===''?'selected':''}>${e(effortLabel(defaults.resolved_reasoning??defaults.reasoning))}</option></optgroup><optgroup label="Override">${efforts.map(value=>`<option value="${e(value)}" ${selectedEffort===value?'selected':''}>${e(effortLabel(value))}${value===selectedEffort&&!supported.includes(value)&&supported.length?' (current)':''}</option>`).join('')}</optgroup></select></label><label class="composer-permission-field"><span>Permissions</span><select id="chat-approval-mode" aria-label="Approval handling" ${editable?'':'disabled'} title="${e(selectedApproval?permissionLabel(approvalMode):'Workspace default: '+permissionLabel(defaultApproval))}. Updates approval handling now. Full access starts with the next turn; restricting an active full-access turn stops it.">${native?'<option value="">Native permissions</option>':`<option value="" ${selectedApproval===''?'selected':''}>Default · ${permissionLabel(defaultApproval)}</option>${(capabilities.auto_review?['ask','auto_review','yolo']:['ask','yolo']).map(mode=>`<option value="${mode}" ${selectedApproval===mode?'selected':''}>${permissionLabel(mode)}</option>`).join('')}`}</select></label><div class="composer-setting-actions"><button type="button" class="chat-fast-button ${fast?'selected':''}" data-action="toggle-fast" aria-pressed="${fast}" ${editable&&capabilities.fast_mode?'':'disabled'} title="Faster responses, higher usage. Applies to the next turn.">Fast</button><button type="button" class="chat-defaults-button" data-action="reset-chat-settings" ${editable&&(hasOverride||fast||selectedApproval!=='')?'':'disabled'} aria-label="Use defaults" title="Inherit project and workspace defaults for model, effort, Fast mode, and permissions">${icon('refresh')}</button></div></div>`;
  notices.hidden=!(permissionNote||prominentNote);
  notices.innerHTML=`${permissionNote?`<div class="permission-mode-note" role="status">${e(permissionNote)}${permissionMismatch?` <button type="button" class="apply-permission-button" data-action="apply-permission-mode" ${editable?'':'disabled'}>Apply now</button>`:''}</div>`:''}${prominentNote?`<div class="chat-preference-note ${preferences.error?'has-error':''}" role="status">${e(note)}</div>`:''}`;
}
async function fetchModelCatalog(force=false) {
  const backend=currentBackend();
  if(modelCatalogPromise)return modelCatalogPromise;
  if(!force&&modelCatalogBackend===backend&&modelCatalogLoadedAt&&Date.now()-modelCatalogLoadedAt<60000)return state.models;
  modelCatalogPromise=(async()=>{try{const data=await api(backend==='codex'?'models':'models?backend='+backend);modelCatalogBackend=backend;state.models=data.models||[];if(backend==='codex')state.codexModels=state.models;state.modelsError=null;modelCatalogLoadedAt=Date.now();return state.models;}catch(error){state.modelsError=error.message;return state.models;}finally{modelCatalogPromise=null;renderChatPreferences();}})();
  return modelCatalogPromise;
}
async function saveChatPreferences(changes) {
  const preferences=state.chat?.preferences,scope=state.scope;
  if(!preferences?.editable||readOnly()||chatPreferenceSaveScope)return;
  const params={scope,...changes};
  chatPreferenceSaveScope=scope;chatPreferenceRevisions.set(scope,(chatPreferenceRevisions.get(scope)||0)+1);renderChatPreferences();updateChatHeader();
  try {
    const result=await action('chat.settings',params);
    if(state.scope===scope){
      const updated=result.preferences||(result.effective&&result.defaults?result:null);
      if(updated){state.chat={...state.chat,preferences:updated};state.chatSignature='';if(Object.hasOwn(changes,'backend'))await Promise.allSettled([accountGate.refresh(),fetchModelCatalog(true)]);}
      else {const chat=await api('chat?scope='+encodeURIComponent(scope));if(state.scope===scope){state.chat=chat;state.chatSignature='';}}
    }
    const permission=result.permission_update;
    if(permission&&state.scope===scope)await refreshChat(true);
    const notice=permission?.applied==='interrupted'||permission?.applied==='stopping'?'Current work is stopping to apply the more restrictive permissions. Continue the agent when ready; work will not restart automatically.':permission?.applied==='approval_handling'?`${permissionLabel(permission.approval_mode)} approval handling applies now.${permission.approval_mode==='yolo'&&!['danger-full-access','dangerFullAccess'].includes(permission.active_sandbox)?' Full access starts next turn.':''}${permission.approved_count?` ${permission.approved_count} pending request${permission.approved_count===1?' was':'s were'} approved.`:''}`:changes.model===null&&changes.reasoning===null?'This conversation now uses its role defaults.':Object.hasOwn(changes,'approval_mode')?'Permissions saved for the next turn.':'Conversation settings saved for the next turn.';
    toast((state.scope!==scope?'Previous conversation: ':'')+notice);
  } catch(error) {toast(error.message,true);} finally {chatPreferenceSaveScope=null;chatPreferenceRevisions.set(scope,(chatPreferenceRevisions.get(scope)||0)+1);updateChatHeader();}
}
const approvalKey = (scope,id) => JSON.stringify([scope,String(id)]);
function approvalText(value){return typeof value==='string'?value:value==null?'':JSON.stringify(value,null,2);}
function renderChatApprovals(){
  const container=$('#chat-approvals');if(!container)return;
  const scope=state.scope,pending=(state.chat?.approvals||[]).filter(item=>item.status==='pending');
  const signature=JSON.stringify([scope,pending,readOnly(),pending.map(item=>[approvalBusy.has(approvalKey(scope,item.id)),approvalErrors.get(approvalKey(scope,item.id))])]);
  if(container.dataset.signature===signature)return;
  const openDetails=new Map($$('details[data-approval-details]',container).map(item=>[item.dataset.approvalDetails,item.open]));
  const scroll=container.scrollTop;
  container.dataset.signature=signature;container.hidden=!pending.length;
  if(!pending.length){container.replaceChildren();return;}
  container.innerHTML=pending.map(item=>{
    const key=approvalKey(scope,item.id),busy=approvalBusy.has(key),error=approvalErrors.get(key),disabled=readOnly()||scope?.startsWith('agent:')||busy;
    const title={command:'Run command',fileChange:'Change files',permissions:'Additional access',mcp:'Run workspace tool'}[item.kind]||'Agent action';
    const command=approvalText(item.command),paths=approvalText(item.paths),permissions=approvalText(item.kind==='mcp'?(item.permissions?.server?{server:item.permissions.server}:null):item.permissions),toolDescription=approvalText(item.tool_request?.tool_description),toolParams=approvalText(item.tool_request?.tool_params),network=approvalText(item.network),cwd=approvalText(item.cwd);
    const duration=item.kind==='mcp'?'Approves this single tool action once.':item.kind==='permissions'?'Requested access lasts for this agent turn only.':item.kind==='fileChange'?'Approves these file changes once.':'Approves this command once.';
    return `<article class="approval-card" data-approval-card="${e(item.id)}"><div class="approval-heading">${icon('lock')}<strong>${e(title)}</strong><span>Approval needed</span></div>${item.reason?`<p class="approval-reason">${e(approvalText(item.reason))}</p>`:''}${item.kind==='mcp'&&toolDescription?`<p class="approval-reason">${e(toolDescription)}</p>`:''}${item.kind==='mcp'&&toolParams?`<div class="approval-detail-label">Tool parameters</div><pre class="approval-command" aria-label="Requested tool parameters">${e(toolParams)}</pre>`:''}${command?`<pre class="approval-command" aria-label="Requested command">${e(command)}</pre>`:''}${cwd?`<div class="approval-working-directory"><span>Working directory</span><code>${e(cwd)}</code></div>`:''}${network?`<div class="approval-detail-label">Network access</div><pre class="approval-paths">${e(network)}</pre>`:''}${paths?`<div class="approval-detail-label">Requested paths</div><pre class="approval-paths">${e(paths)}</pre>`:''}${permissions?`<details class="approval-permissions" data-approval-details="${e(item.id)}" ${(openDetails.has(String(item.id))?openDetails.get(String(item.id)):item.kind==='permissions')?'open':''}><summary>Requested permissions</summary><pre>${e(permissions)}</pre></details>`:''}<p class="approval-duration">${e(duration)} Runs require an explicit request and a verified PR.${item.can_approve===false?' This request does not offer one-time approval. Deny it and ask for narrower access.':''}</p>${error?`<div class="approval-error" role="alert">${e(error)}</div>`:''}<div class="approval-actions"><button type="button" class="button small-button" data-action="deny-approval" data-approval="${e(item.id)}" data-approval-scope="${e(scope)}" ${disabled?'disabled':''}>Deny</button><button type="button" class="button primary small-button" data-action="approve-request" data-approval="${e(item.id)}" data-approval-scope="${e(scope)}" ${disabled||item.can_approve===false?'disabled':''}>${busy?'Saving…':'Approve once'}</button></div></article>`;
  }).join('');
  container.scrollTop=scroll;
}
async function decideApproval(element,decision){
  const scope=element.dataset.approvalScope,id=element.dataset.approval,key=approvalKey(scope,id);
  if(scope!==state.scope||readOnly()||scope.startsWith('agent:')||approvalBusy.has(key))return;
  const approval=(state.chat?.approvals||[]).find(item=>String(item.id)===id&&item.status==='pending');
  if(!approval){toast('This approval is no longer pending. Refresh the conversation.',true);return;}if(decision==='approve'&&approval.can_approve===false)return;
  approvalBusy.add(key);approvalErrors.delete(key);approvalRevisions.set(scope,(approvalRevisions.get(scope)||0)+1);renderChatApprovals();
  try{
    await action('chat.approve',{scope,approval_id:approval.id,decision});
    if(state.scope===scope&&state.chat){state.chat.approvals=(state.chat.approvals||[]).map(item=>String(item.id)===id?{...item,status:decision==='approve'?'approved':'denied'}:item);state.chatSignature='';}
    const confirmation=decision==='approve'?(approval.kind==='permissions'?'Requested access approved for this turn.':'Action approved once.'):'Action denied.';toast(state.scope===scope?confirmation:'Previous conversation: '+confirmation);
  }catch(error){approvalErrors.set(key,error.message);toast(error.message,true);}
  finally{approvalBusy.delete(key);approvalRevisions.set(scope,(approvalRevisions.get(scope)||0)+1);if(state.scope===scope){renderChatApprovals();refreshChat(true);}}
}
const questionKey = (scope,id) => JSON.stringify([scope,String(id)]);
const questionDrafts = new Map(), questionBusy = new Set(), questionErrors = new Map(), questionRevisions = new Map();
const questionStorageKey='supersurfer-question-drafts';
try {
  const saved=JSON.parse(localStorage.getItem(questionStorageKey)||'[]');
  if(Array.isArray(saved))for(const [key,value] of saved.slice(-40))if(typeof key==='string'&&value&&typeof value==='object'&&value.updated>Date.now()-7*86400000)questionDrafts.set(key,value);
} catch {}
function persistQuestionDrafts(){
  const records=[...questionDrafts].filter(([,value])=>value.updated>Date.now()-7*86400000).slice(-40).map(([key,value])=>[key,{updated:value.updated,answers:Object.fromEntries(Object.entries(value.answers||{}).filter(([,answer])=>!answer.secret))}]);
  try{localStorage.setItem(questionStorageKey,JSON.stringify(records));}catch{}
}
function questionDraft(scope,request,question){
  const key=questionKey(scope,request.id),record=questionDrafts.get(key)||{updated:Date.now(),answers:{}};
  const saved=record.answers?.[question.id];
  // A question newly marked secret must never retain a previous plaintext disk draft.
  if(question.isSecret&&saved&&!saved.secret){delete record.answers[question.id];questionDrafts.set(key,record);persistQuestionDrafts();return {};}
  return saved&&typeof saved==='object'?saved:{};
}
function updateQuestionDraft(event){
  const form=event.target.closest('form[data-question-request]'),field=event.target.closest('[data-question-index]');
  if(!form||!field)return;
  const scope=form.dataset.questionScope,request=(state.chat?.questions||[]).find(item=>String(item.id)===form.dataset.questionRequest);
  if(scope!==state.scope||!request)return;
  const question=request.questions?.[Number(field.dataset.questionIndex)];if(!question)return;
  const key=questionKey(scope,request.id),record=questionDrafts.get(key)||{updated:Date.now(),answers:{}};
  const selected=$('input[type="radio"]:checked',field),text=$('[data-question-text]',field);
  const answer={choice:selected?.value??'',text:text?.value||'',secret:!!question.isSecret};
  Object.defineProperty(record.answers,String(question.id),{value:answer,writable:true,enumerable:true,configurable:true});record.updated=Date.now();questionDrafts.set(key,record);persistQuestionDrafts();
  if((question.options||[]).length&&text){text.hidden=answer.choice!=='other';text.required=answer.choice==='other';}
  questionErrors.delete(key);const error=$('.question-error',form);if(error)error.hidden=true;
}
function renderChatQuestions(){
  const container=$('#chat-questions');if(!container)return;
  const scope=state.scope,questions=state.chat?.questions,shown=(questions||[]).filter(item=>item.status==='pending');
  const liveKeys=new Set(shown.map(item=>questionKey(scope,item.id)));
  let dirty=false;
  // Only a received question list can retire drafts; a failed fetch cannot.
  if(Array.isArray(questions))for(const records of [questionDrafts,questionErrors,questionBusy])for(const key of records.keys()){
    let owner;try{[owner]=JSON.parse(key);}catch{continue;}
    if(owner===scope&&!liveKeys.has(key)){records.delete(key);if(records===questionDrafts)dirty=true;}
  }
  if(dirty)persistQuestionDrafts();
  const signature=JSON.stringify([scope,shown,readOnly(),shown.map(item=>[questionBusy.has(questionKey(scope,item.id)),questionErrors.get(questionKey(scope,item.id))])]);
  if(container.dataset.signature===signature)return;
  container.dataset.signature=signature;container.hidden=!shown.length;
  if(!shown.length){container.replaceChildren();return;}
  const scroll=container.scrollTop;
  container.innerHTML=shown.map((request,requestIndex)=>{
    const key=questionKey(scope,request.id),busy=questionBusy.has(key),disabled=request.can_answer===false||busy||readOnly()||scope?.startsWith('agent:'),error=questionErrors.get(key);
    return `<form class="question-card" data-question-request="${e(request.id)}" data-question-scope="${e(scope)}"><div class="question-heading">${icon('message')}<strong>${e(request.title||'Question for you')}</strong><span>Awaiting answer</span></div>${(request.questions||[]).map((question,index)=>{
      const draft=questionDraft(scope,request,question),options=question.options||[],choice=typeof draft.choice==='string'?draft.choice:'',text=typeof draft.text==='string'?draft.text:'',free=!options.length,other=question.isOther===true,fieldId=`question-${requestIndex}-${index}`;
      return `<fieldset class="question-field" data-question-index="${index}" ${disabled?'disabled':''}><legend>${question.header?`<span>${e(question.header)}</span>`:''}${e(question.question||'Your answer')}</legend>${options.map((option,optionIndex)=>`<label class="question-option"><input type="radio" name="${fieldId}" value="${optionIndex}" ${choice===String(optionIndex)?'checked':''} required><span><strong>${e(option.label)}</strong>${option.description?`<small>${e(option.description)}</small>`:''}</span></label>`).join('')}${!free&&other?`<label class="question-option"><input type="radio" name="${fieldId}" value="other" ${choice==='other'?'checked':''} required><span><strong>Write another answer</strong></span></label>`:''}${free||other?`${question.isSecret?`<input type="password" data-question-text autocomplete="off" maxlength="16000" value="${e(text)}" aria-label="${e(question.question||'Your answer')}" placeholder="Enter your answer" ${free||choice==='other'?'required':'hidden'}>`:`<textarea data-question-text rows="2" maxlength="16000" aria-label="${e(question.question||'Your answer')}" placeholder="${free?'Write your answer…':'Your alternative…'}" ${free||choice==='other'?'required':'hidden'}>${e(text)}</textarea>`}`:''}${question.isSecret?'<small class="question-secret-note">Secret drafts stay in memory and are lost on reload.</small>':''}</fieldset>`;
    }).join('')}${request.can_answer===false?'<p class="question-note">This question cannot be answered from the current connection.</p>':''}<div class="question-error" role="alert" ${error?'':'hidden'}>${e(error||'')}</div><div class="question-footer"><span>Your answer continues this conversation.</span><button class="button primary small-button" type="submit" ${disabled?'disabled':''}>${busy?'Sending…':'Answer & continue'}</button></div></form>`;
  }).join('');container.scrollTop=scroll;
}
async function answerQuestion(event){
  event.preventDefault();const form=event.target.closest('form[data-question-request]');if(!form)return;
  const scope=form.dataset.questionScope,id=form.dataset.questionRequest,key=questionKey(scope,id);
  if(scope!==state.scope||readOnly()||scope.startsWith('agent:')||questionBusy.has(key))return;
  const request=(state.chat?.questions||[]).find(item=>String(item.id)===id&&item.status==='pending');if(!request||request.can_answer===false)return;
  const answers=Object.create(null);
  for(const [index,question] of (request.questions||[]).entries()){
    const field=$(`[data-question-index="${index}"]`,form),options=question.options||[],choice=$('input[type="radio"]:checked',field)?.value,text=$('[data-question-text]',field)?.value||'';
    const answer=!options.length||choice==='other'?text:options[Number(choice)]?.label;
    if(!answer||!answer.trim()){questionErrors.set(key,'Answer each question before continuing.');renderChatQuestions();return;}
    answers[question.id]=[answer];
  }
  if(!Object.keys(answers).length)return;
  questionBusy.add(key);questionErrors.delete(key);questionRevisions.set(scope,(questionRevisions.get(scope)||0)+1);renderChatQuestions();
  try{
    await action('chat.answer',{scope,question_id:id,answers});questionDrafts.delete(key);persistQuestionDrafts();
    if(state.scope===scope&&state.chat){state.chat.questions=(state.chat.questions||[]).map(item=>String(item.id)===id?{...item,status:'answered'}:item);state.chatSignature='';updateChatHeader();}
  }catch(error){questionErrors.set(key,error.message);}
  finally{questionBusy.delete(key);questionRevisions.set(scope,(questionRevisions.get(scope)||0)+1);if(state.scope===scope){renderChatQuestions();refreshChat(true);}}
}

async function refreshChat(force=false){for(const [scope,controller] of chatFetches){if(!state.chatVisible||scope!==state.scope)controller.abort();}if(!state.scope||!state.chatVisible||!force&&chatFetches.has(state.scope))return;const scope=state.scope;chatFetches.get(scope)?.abort();const controller=new AbortController();chatFetches.set(scope,controller);const preferenceRevision=chatPreferenceRevisions.get(scope)||0,approvalRevision=approvalRevisions.get(scope)||0,questionRevision=questionRevisions.get(scope)||0;try{const data=await api('chat?'+new URLSearchParams({scope,limit:chatHistoryCount.get(scope)||80}),undefined,{signal:controller.signal});if(scope!==state.scope||chatFetches.get(scope)!==controller)return;if(!force&&data[pollUnchanged]&&state.chatSignature)return;if(preferenceRevision!==(chatPreferenceRevisions.get(scope)||0)||chatPreferenceSaveScope===scope)data.preferences=state.chat?.preferences;if(approvalRevision!==(approvalRevisions.get(scope)||0))data.approvals=state.chat?.approvals||[];if(questionRevision!==(questionRevisions.get(scope)||0))data.questions=state.chat?.questions||[];const beforeBackend=currentBackend();state.chat=data;if(modelCatalogBackend!==currentBackend())void fetchModelCatalog(true);if(beforeBackend!==currentBackend())void accountGate.refresh();updateChatHeader();const sig=JSON.stringify(data);if(force||sig!==state.chatSignature){state.chatSignature=sig;renderChat();}}catch(error){if(scope===state.scope&&force&&!controller.signal.aborted){state.chat={messages:[],error:error.message};renderChat();}}finally{if(chatFetches.get(scope)===controller)chatFetches.delete(scope);}}
function renderChatTasks(){
 const container=$('#chat-tasks'),tasks=state.chat?.tasks||[],note=state.chat?.continuation_note;
 container.hidden=!tasks.length&&!note;if(container.hidden){container.innerHTML='';delete container.dataset.signature;delete container.dataset.scope;return;}
 const signature=JSON.stringify([state.scope,tasks,note]);if(container.dataset.signature===signature)return;
 const open=container.dataset.scope===state.scope&&container.querySelector('details')?.open===true;
 container.dataset.signature=signature;container.dataset.scope=state.scope;
 const labels={working:'In progress',blocked:'Blocked',completed:'Complete',watching:'Monitoring'};
 container.innerHTML=`<details ${open?'open':''}><summary>Deliverables <span>${tasks.filter(t=>t.status==='completed').length}/${tasks.length} complete</span></summary><div class="chat-task-list">${tasks.map(task=>`<div class="chat-task" data-task-id="${e(task.id)}"><div><span class="badge ${e(task.status)}">${e(labels[task.status]||task.status)}</span><strong>${e(task.title)}</strong></div>${task.summary?`<p>${e(task.summary)}</p>`:''}</div>`).join('')}${note?`<p class="chat-task-note">${e(note)}</p>`:''}</div></details>`;
}
async function toggleChatArchive(){
 const scope=state.scope,key='archive:'+scope,archived=!(state.chat?.archived||selectedAgent()?.archived);if(!scope||readOnly()||agentMutations.has(key))return;
 agentMutations.add(key);updateChatHeader();
 try{
  await action('chat.archive',{scope,archived});
  for(const [key,directory] of agentDirectories){agentDirectoryVersions.set(key,(agentDirectoryVersions.get(key)||0)+1);for(const agent of directory.agents||[])if(agent.scope===scope)agent.archived=archived;}
  if(state.scope===scope){state.chat={...state.chat,archived};await loadAgentDirectory();if(archived){state.pinnedAgent=null;persistNavigation();const next=scopedAgents().find(agent=>!agent.archived&&!agent.retired);if(next)await selectConversation(next.scope);}if(state.scope===scope)await refreshChat(true);}
  toast(archived?'Chat archived. Existing work and monitoring continue.':'Chat restored.');
 }catch(error){toast(error.message,true);}
 finally{agentMutations.delete(key);updateChatHeader();}
}
function showRenameAgent(){
 const scope=state.scope;if(!scope||scope.startsWith('agent:')||readOnly())return;
 const name=selectedAgent()?.name||state.chat?.agent?.name||'Agent';
 openModal('Rename agent',`<form id="rename-agent-form"><label>Agent name<input id="agent-name-input" name="name" maxlength="100" required value="${e(name)}"></label><p id="rename-agent-error" class="form-error" role="alert" hidden></p><div class="modal-footer"><button type="button" class="button" data-action="close-modal">Cancel</button><button type="submit" class="button primary">Save name</button></div></form>`,'rename-agent');
 $('#rename-agent-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=event.currentTarget.querySelector('[type=submit]'),name=$('#agent-name-input').value.trim();if(!name)return;button.disabled=true;
  try{await action('chat.rename',{scope,name});if(state.pinnedAgent?.scope===scope){state.pinnedAgent.name=name;persistNavigation();}if(state.scope===scope&&state.chat)state.chat.agent.name=name;await loadAgentDirectory();if(state.scope===scope)await refreshChat(true);if(state.modalKind==='rename-agent')closeModal();}
  catch(error){const el=$('#rename-agent-error');if(el){el.hidden=false;el.textContent=error.message;button.disabled=false;}}
 });
 $('#agent-name-input').select();
}
const chatCheckExpansion=new Map();
$('#chat-messages').addEventListener('toggle',event=>{const details=event.target;if(!details.isConnected||!details.matches('details[data-check-key]'))return;let expanded=chatCheckExpansion.get(state.scope);if(!expanded){expanded=new Set();chatCheckExpansion.set(state.scope,expanded);}const key=details.dataset.checkKey;if(expanded.has(key)===details.open)return;if(details.open)expanded.add(key);else expanded.delete(key);renderChat();},true);
const chatHistoryCount=new Map();
let chatRenderedScope=null,chatOpenPending=true;
function renderChat(){renderCodePresentation();const c=state.chat||{messages:[]},el=$('#chat-messages'),nearBottom=el.scrollHeight-el.scrollTop-el.clientHeight<100,old=el.scrollTop;const allMessages=c.messages||[],visibleCount=chatHistoryCount.get(state.scope)||80,messages=allMessages.slice(-visibleCount),earlier=Math.max(0,(c.message_count??allMessages.length)-visibleCount);const prompts=isSurfboard()?['Set up a research experiment with live comparisons','Build and review a software feature','Write a paper with LaTeX and a live PDF']:projectWorkflow()!=='research'?['Help me scope the next task','Review progress and blockers','Suggest checks for this project']:state.experimentId?['Explain the hypothesis and current evidence','Suggest the next experiment','Improve this experiment’s explanation']:['What should we focus on next?','Summarize the current experiments','Suggest a promising research direction'];el.innerHTML=messages.length?(earlier?`<button type="button" class="button small-button chat-earlier" data-action="earlier-chat">Show earlier messages · ${earlier}</button>`:'')+renderChatTimeline(messages,{renderMessage:m=>`<div class="message ${e(m.role)}"><div class="message-label"><strong>${m.role==='user'?'You':m.role==='system'?(m.agent_sender?e(m.agent_sender.name)+' · Agent':'System'):e(c.agent?.name||'Agent')}</strong><time>${e(date(m.created,true))}</time></div><div class="message-text markdown">${markdown(m.text||'')}</div>${contextMarkup(m.attachments)}${m.status==='steering'?'<div class="message-delivery" role="status">Sending direction to the active turn…</div>':['failed','uncertain'].includes(m.status)?`<div class="message-delivery error" role="status">${m.status==='uncertain'?'Delivery not confirmed':'Message failed'}${m.error?': '+e(m.error):''}</div>`:''}</div>`,escape:e,date,expanded:chatCheckExpansion.get(state.scope)||new Set(),busy:c.busy}):`<div class="chat-empty"><span class="agent-orb">${icon('spark')}</span><h3>${isSurfboard()?'What do you want to build today?':projectWorkflow()!=='research'?'Build with your project agent.':state.experimentId?'Stay close to the experiment.':'A thought partner for your research.'}</h3><p>${isSurfboard()?'Describe your goal or choose a saved Surfboard. I’ll suggest the views and agent workflow; you can refine them here before applying.':state.scope?.startsWith('agent:')?'Talk to this existing AutoML agent in its original conversation.':'Ask a question, explore an idea, or refine the explanation. Your conversation and project context stay here.'}</p><div class="chat-suggestions">${prompts.map(p=>`<button data-prompt="${e(p)}"${disabled()}>${e(p)}${icon('arrowRight')}</button>`).join('')}</div></div>`;
 if((c.questions||[]).some(item=>item.status==='pending'))el.innerHTML+=`<div class="chat-status">${icon('message')}Waiting for your answer</div>`;else if((c.approvals||[]).some(item=>item.status==='pending'))el.innerHTML+=`<div class="chat-status">${icon('lock')}Waiting for your approval</div>`;else if(c.busy)el.innerHTML+='<div class="chat-status"><span class="spinner"></span>Working in your workspace…</div>';if(c.error)el.innerHTML+=`<div class="chat-error">${e(c.error)}</div>`;const entering=chatOpenPending||chatRenderedScope!==state.scope;chatRenderedScope=state.scope;chatOpenPending=false;if(entering||nearBottom||!messages.length){el.scrollTop=el.scrollHeight;if(entering){const scope=state.scope;requestAnimationFrame(()=>{if(state.scope===scope)el.scrollTop=el.scrollHeight;});}}else el.scrollTop=old;}
async function sendChat(event){
 event?.preventDefault();const scope=state.scope,busy=!!state.chat?.busy;
 if(readOnly()||chatPreferenceSaveScope===scope||!accountGate.ready()||fileUploads.pending(scope)||selectedAgent()?.retired||state.chat?.retired||state.chat?.archived||chatSending.has(scope)||pendingQuestions()||pendingApprovals()||(busy&&!state.chat?.steerable))return;
 const input=$('#chat-input'),original=input.value,attachments=chatContext.get().slice(),text=original.trim()||(attachments.length?'Please review the attached context.':'');if(!text)return;
 chatSending.add(scope);updateChatHeader();
 try{
   await action(busy?'chat.steer':'chat.send',{scope,text,...(attachments.length?{attachments}:{}),...(activePage()&&!scope.startsWith('agent:')&&chatAcceptsProject(state.projectId)&&(!chatOrigin().experimentId||chatOrigin().experimentId===state.experimentId)?{view:{project_id:state.projectId,experiment_id:state.experimentId,page_id:activePage().id}}:{})});conversationDrafts.delete(scope);chatContext.sent(scope,attachments.map(row=>row.id));
   if(state.scope===scope){if(input.value===original){input.value='';resizeComposer();}state.chat={...state.chat,busy:true};state.chatSignature='';await refreshChat(true);}
 }catch(error){toast(error.message,true);if(error.status===403)await accountGate.refresh();}
 finally{chatSending.delete(scope);updateChatHeader();}
}
function stashEditor(){const editor=$('#document-editor');if(editor&&state.experimentId)sessionStorage.setItem(`ss-draft-${state.experimentId}`,editor.value);}
function loadDraft(id){return sessionStorage.getItem(`ss-draft-${id}`);}
async function saveExperiment(){const button=$('[data-action="save-experiment"]');button.disabled=true;try{const x=state.experiment;await action('experiment.save',{id:x.id,markdown:$('#document-editor').value,version:x.version,wandb_url:$('#document-wandb').value.trim()});sessionStorage.removeItem(`ss-draft-${x.id}`);state.edit=false;await fetchExperiment(true);toast('Experiment saved.');}catch(error){toast(error.status===409?'The document changed in your workspace. Your draft is kept; reload the latest version before saving.':error.message,true);button.disabled=false;}}
async function saveDefaultPermissions(event){
 if(workspacePermissionSaving||readOnly())return;
 workspacePermissionSaving=true;
 const select=event.currentTarget,mode=select.value,previous=state.data.settings.approval_mode||'ask',form=select.closest('form'),button=$('button[type="submit"]',form),status=$('#workspace-permissions-status',form);
 select.disabled=true;if(button)button.disabled=true;if(status)status.textContent='Saving workspace default…';
 try{
  const result=await action('settings.save',{approval_mode:mode});state.data.settings.approval_mode=mode;
  if(status)status.textContent='Saved on this workspace. This default stays after closing SuperSurfer.';
  const stopped=(result.permission_updates||[]).filter(update=>['interrupted','stopping'].includes(update.applied)).length;
  toast(stopped?`Default saved. ${stopped} full-access conversation${stopped===1?' is':'s are'} stopping to apply restricted permissions. Continue when ready.`:'Default permissions saved.');
 }catch(error){
  let confirmed=null;try{confirmed=(await api('state')).settings.approval_mode;}catch{}
  if(confirmed)state.data.settings.approval_mode=confirmed;select.value=confirmed||previous;
  if(status)status.textContent=confirmed===mode?'Default saved, but active conversations need attention.':confirmed?'Could not save. The previous default is still in use.':'Could not confirm the saved default. Reconnect to check.';
  toast(error.message,true);
 }finally{
  workspacePermissionSaving=false;
  const current=$('#workspace-approval-mode');if(current){current.disabled=readOnly();current.value=state.data.settings.approval_mode||previous;}
  if(button)button.disabled=readOnly();
 }
 await refreshChat(true);
}
async function saveSettings(event){event.preventDefault();if(workspacePermissionSaving)return;const form=event.currentTarget,fd=new FormData(form),button=$('button[type="submit"]',form);button.disabled=true;try{const models={},reasoning={},backends={};for(const role of modelRoles){models[role]=(form.elements.namedItem(`model_${role}`)?.value??state.data.settings.models?.[role]??'').trim();reasoning[role]=form.elements.namedItem(`reasoning_${role}`)?.value??state.data.settings.reasoning?.[role]??'medium';backends[role]=fd.get(`backend_${role}`)||'codex';}const result=await action('settings.save',{models,reasoning,backends,monitor_enabled:fd.get('monitor_enabled')==='on',monitor_interval_minutes:Number(fd.get('monitor_interval_minutes')),approval_mode:fd.get('approval_mode')||state.data.settings.approval_mode||'ask'});form.dataset.dirty='false';const stopped=(result.permission_updates||[]).filter(update=>['interrupted','stopping'].includes(update.applied)).length;toast(stopped?`Settings saved. ${stopped} full-access conversation${stopped===1?' is':'s are'} stopping to apply restricted permissions. Continue when ready.`:'Settings saved for SuperSurfer conversations.');await refreshState(true);await refreshChat(true);}catch(error){toast(error.message,true);}finally{if(button.isConnected)button.disabled=readOnly();}}
function openModal(title,body,kind){state.modalKind=kind;$('#modal-content').innerHTML=`<div class="modal-header"><h2>${e(title)}</h2><button class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></div><div class="modal-body">${body}</div>`;if(!$('#modal').open)$('#modal').showModal();$('input:not([type="hidden"]),textarea,select,button.primary',$('#modal-content'))?.focus();}
function closeModal(){const modal=$('#modal');if(modal.open)modal.close();state.modalKind=null;if(renderPending&&!state.edit&&!(state.view==='settings'&&($('#settings-form')?.dataset.dirty==='true'||editorSettings.dirty()||workspacePermissionSaving))&&!$('#project-compute-form')?.dataset.dirty)renderMain();}
function formFooter(label){return `<div class="field-error" id="form-error" role="alert" hidden></div><div class="modal-footer"><button type="button" class="button" data-action="close-modal">Cancel</button><button class="button primary" type="submit">${label}</button></div>`;}
function field(label,name,opts={}){const {value='',placeholder='',type='text',help='',required=false,full=false,min,max,maxlength,pattern}=opts;return `<label class="field ${full?'full-width':''}"><span>${e(label)}</span><input type="${e(type)}" name="${e(name)}" value="${e(value)}" placeholder="${e(placeholder)}" ${required?'required':''} ${min!==undefined?`min="${e(min)}"`:''} ${max!==undefined?`max="${e(max)}"`:''} ${maxlength!==undefined?`maxlength="${e(maxlength)}"`:''} ${pattern?`pattern="${e(pattern)}" title="${e(help)}"`:''}>${help?`<small>${e(help)}</small>`:''}</label>`;}
function textarea(label,name,opts={}){return `<label class="field ${opts.full?'full-width':''}"><span>${e(label)}</span><textarea name="${e(name)}" placeholder="${e(opts.placeholder||'')}" ${opts.required?'required':''}>${e(opts.value||'')}</textarea>${opts.help?`<small>${e(opts.help)}</small>`:''}</label>`;}
function bindModalForm(handler){
 const form=$('form',$('#modal-content'));let submitting=false;
 const jobType=$('[name=job_type]',form);if(jobType){const update=()=>{const training=jobType.value==='training';$('#training-telemetry-fields',form).hidden=!training;for(const input of $$('[name=mfu_source_path],[name=mfu_method]',form))input.required=training;};jobType.addEventListener('change',update);update();}
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(submitting)return;submitting=true;
  const buttons=$$('button[type="submit"]',form),error=$('#form-error',form),submitter=event.submitter;
  buttons.forEach(button=>{button.disabled=true;});error.hidden=true;
  try{await handler(new FormData(form),submitter,form);}
  catch(err){error.textContent=err.message;error.hidden=false;}
  finally{submitting=false;buttons.forEach(button=>{button.disabled=button.dataset.remainDisabled==='true';});}
 });
}
function showAuth(){openModal('Connect to your workspace',`<p class="modal-description">Paste the connection token shown by the SuperSurfer service. It is kept only for this browser session.</p><form>${field('Connection token','token',{type:'password',required:true})}${formFooter('Connect')}</form>`,'auth');bindModalForm(async fd=>{sessionStorage.setItem('supersurfer-token',fd.get('token').trim());await api('state');closeModal();await refreshState(true);});}
function projectDirectoryField(){return `<div class="field directory-field"><label for="project-repo">Project folder</label><div class="directory-combobox"><input id="project-repo" name="repo" placeholder="/home/researcher/projects/vla" required autocomplete="off" spellcheck="false" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="repo-options" aria-describedby="repo-help"><div class="directory-popup" id="repo-popup" hidden><ul id="repo-options" role="listbox" aria-label="Directories on the connected machine"></ul><div class="directory-status" id="repo-suggestion-status" role="status"></div></div></div><small id="repo-help">Browse this machine’s folders or type a new path. A folder and local Git repository are created if needed; GitHub is not required.</small></div>`;}
function bindDirectorySuggestions(){
  const input=$('#project-repo'),popup=$('#repo-popup'),list=$('#repo-options'),status=$('#repo-suggestion-status');if(!input)return;
  let timer,version=0,entries=[],selected=-1,loadedPath=null;
  const hide=()=>{popup.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');selected=-1;};
  const show=()=>{popup.hidden=false;input.setAttribute('aria-expanded','true');};
  const highlight=index=>{selected=index;$$('[role="option"]',list).forEach((el,i)=>el.setAttribute('aria-selected',String(i===selected)));if(selected>=0){input.setAttribute('aria-activedescendant',`repo-option-${selected}`);$(`#repo-option-${selected}`,list)?.scrollIntoView({block:'nearest'});}else input.removeAttribute('aria-activedescendant');};
  const lookup=async()=>{
    const request=++version,path=input.value.trim();if(!input.isConnected||state.modalKind!=='project')return;
    entries=[];highlight(-1);list.replaceChildren();status.textContent='Finding folders…';show();
    try{
      const result=await api('directories?path='+encodeURIComponent(path));
      if(request!==version||!input.isConnected||state.modalKind!=='project'||input.value.trim()!==path)return;
      entries=(result.entries||[]).filter(item=>typeof item.path==='string'&&typeof item.name==='string');loadedPath=path;
      list.innerHTML=entries.map((item,index)=>`<li id="repo-option-${index}" role="option" aria-selected="false" data-directory-index="${index}">${icon('folder')}<span><strong>${e(item.name)}</strong><small>${e(item.path)}</small></span>${item.is_symlink?'<span class="directory-symlink">Link</span>':''}</li>`).join('');
      status.textContent=entries.length?(result.truncated?'More folders available. Keep typing to narrow the list.':'↑ ↓ to browse · Enter to choose · Keep typing to create a new folder'):'No matching folders. You can keep typing a new path.';
      if(document.activeElement===input)show();else hide();
    }catch(error){if(request!==version||!input.isConnected||input.value.trim()!==path)return;loadedPath=path;list.replaceChildren();status.textContent=error.status===404?'No existing parent folder. You can still use this new path.':error.status===403?'These folders cannot be listed. You can still enter a path.':error.message;if(document.activeElement===input)show();else hide();}
  };
  const schedule=()=>{clearTimeout(timer);version++;loadedPath=null;entries=[];list.replaceChildren();hide();timer=setTimeout(lookup,220);};
  const choose=index=>{const item=entries[index];if(!item)return;input.value=item.path.endsWith('/')?item.path:item.path+'/';input.focus();input.setSelectionRange(input.value.length,input.value.length);loadedPath=null;hide();clearTimeout(timer);lookup();};
  input.addEventListener('input',schedule);
  input.addEventListener('focus',()=>{if(loadedPath===input.value.trim())show();else{clearTimeout(timer);timer=setTimeout(lookup,100);}});
  input.addEventListener('blur',()=>{clearTimeout(timer);hide();});
  input.addEventListener('keydown',event=>{
    if(event.isComposing)return;
    if(event.key==='Escape'&&!popup.hidden){event.preventDefault();event.stopPropagation();version++;clearTimeout(timer);hide();return;}
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();if(popup.hidden){if(loadedPath===input.value.trim())show();else{clearTimeout(timer);lookup();return;}}if(entries.length)highlight(event.key==='ArrowDown'?(selected+1)%entries.length:(selected<=0?entries.length-1:selected-1));return;}
    if(event.key==='Enter'&&!popup.hidden&&selected>=0){event.preventDefault();choose(selected);}
  });
  list.addEventListener('pointerdown',event=>{if(event.target.closest('[data-directory-index]'))event.preventDefault();});
  list.addEventListener('click',event=>{const option=event.target.closest('[data-directory-index]');if(option)choose(Number(option.dataset.directoryIndex));});
}

function showAddProject(){openModal('Add a project',`<p class="modal-description">Choose a shared project folder. Each task can choose its own workflow. Project context is saved in <code>.SuperSurfer</code>.</p><form><div class="field-stack">${field('Project name','name',{placeholder:'My project',required:true,maxlength:160,help:'Use any name. This does not rename your project folder.'})}${projectDirectoryField()}<label class="field"><span>Default surfboard for new tasks</span><select name="surfboard_template"><option value="research">Research · experiments, GPUs, W&B</option><option value="software">Software · features, checks, pull requests</option><option value="web">Web design · pages, browser, preview</option><option value="writing">Research writing · LaTeX, PDF, review</option></select></label>${textarea('Project goal','goal',{placeholder:'What would you like to build or discover?'})}<p class="muted small">No project GPU or concurrent-run cap by default. Add optional limits in the Surfboard’s Compute block.</p></div><p class="muted small">Connecting enables editor extensions, terminals and localhost previews for this folder.</p>${formFooter('Connect & enable tools')}</form>`,'project');bindDirectorySuggestions();bindModalForm(async fd=>{const result=await action('project.add',{name:fd.get('name').trim(),repo:fd.get('repo').trim(),goal:fd.get('goal').trim(),surfboard_template:fd.get('surfboard_template')});const added=result.project||result;await action('editor.trust',{project_id:added.id,repo:added.repo,trusted:true});closeModal();await refreshState(true);const id=result.id||result.project?.id||state.data.projects.find(p=>p.name===fd.get('name').trim())?.id;if(id)await navigate({projectId:id,tab:'workflow'});toast('Project connected.');});}
async function showAddExperiment(){
 const p=project();if(!p)return showAddProject();
 let library=[];try{library=(await api('workflow?'+new URLSearchParams({project_id:p.id}))).library.entries;}catch(error){toast(error.message,true);return;}
 openModal('What do you want to build today?',`<form><div class="field-stack">${textarea('Describe your goal','summary',{placeholder:'Compare two training methods, build a feature, write a paper…',required:true})}<label class="field"><span>Start with</span><select name="workflow"><option value="">Describe it with an agent</option>${library.map(row=>`<option value="saved:${e(row.id)}">${e(row.name)}</option>`).join('')}<option value="research">Research</option><option value="software">Software engineering</option><option value="writing">Writing · LaTeX & PDF</option><option value="web">Web design</option></select></label><details><summary>Task name</summary>${field('Name (optional)','name',{placeholder:'We’ll use your goal as the name',maxlength:160})}</details><p class="muted small">You’ll review the views and agent workflow before applying. No work starts yet.</p></div>${formFooter('Design workflow')}</form>`,'experiment');
 bindModalForm(async fd=>{
  const goal=fd.get('summary').trim(),choice=fd.get('workflow'),saved=library.find(row=>'saved:'+row.id===choice),name=fd.get('name').trim()||goal.split('\n')[0].slice(0,100);
  const result=await action('experiment.create',{project_id:p.id,name,summary:goal,...(choice&&!saved?{surfboard_template:choice}:{})});
  const id=result.id||result.experiment?.id;closeModal();await refreshState(true);if(!id)return;
  if(saved){const record=await api('surfboard?'+new URLSearchParams({project_id:p.id,experiment_id:id}));await action('workflow.stage',{project_id:p.id,experiment_id:id,expected_version:record.version,expected_draft_version:record.draft?.draft_version||0,library_id:saved.id,library_version:saved.version});}
  await navigate({projectId:p.id,experimentId:id,tab:'workflow'});
  if(!choice){const text='Design a simple workflow for this goal, with views and agent steps. Propose it for my review; do not start executing the task. Goal: '+goal;$('#chat-input').value=text;stashMessageDraft();if(accountGate.ready())$('#chat-form').requestSubmit();}
  toast('Task created. Refine its workflow in chat or review a saved Surfboard.');
 });
}
function showAddHost(){openModal('Register a machine',`<p class="modal-description">Register the GPU indices this workspace can use. Leave the SSH target empty to use the workspace computer itself.</p><form><div class="field-stack"><div class="field-grid">${field('Display name','name',{placeholder:'trinity',required:true,maxlength:64,pattern:'[a-z0-9]+(?:-[a-z0-9]+)*',help:'Lowercase letters, numbers and single hyphens; up to 64 characters.'})}${field('SSH target (optional)','target',{placeholder:'Empty = this workspace computer',help:'For another machine, use an SSH alias or user@hostname.'})}</div>${field('Working directory on this machine','root',{placeholder:'/home/researcher/supersurfer',required:true})}<div class="field-grid">${field('GPU indices','gpus',{placeholder:'0, 1, 2, 3',help:'Leave empty for a CPU-only machine.'})}${field('Runner Python (3.9+)','python',{value:'auto',required:true,help:'Auto finds a compatible interpreter. Separate from project Python; no AML installation is needed on the host.'})}</div></div>${formFooter('Register machine')}</form>`,'host');bindModalForm(async fd=>{const gpuText=fd.get('gpus').trim(),parts=gpuText?gpuText.split(',').map(s=>s.trim()):[];if(parts.some(p=>!/^[0-9]+$/.test(p)))throw new Error('Enter GPU indices separated by commas, such as 0, 1.');await action('host.add',{name:fd.get('name').trim(),target:fd.get('target').trim(),root:fd.get('root').trim(),gpus:[...new Set(parts.map(Number))],python:fd.get('python').trim()});closeModal();await refreshState(true);toast('Machine registered.');});}
async function openExperimentWorker(scope=experimentWorkerScope()){
 if(!scope)return;await loadAgentDirectory();
 if(!scopedAgents().some(agent=>agent.scope===scope)){toast('This worker conversation is not available in the experiment agent list.',true);return;}
 await selectConversation(scope,{persist:false});
}
async function startExperiment(){
 const x=state.experiment||experiment(),id=x?.id;
 if(!id||x.status!=='draft'||['dispatching','uncertain'].includes(x.work_state)||readOnly()||startingExperiments.has(id)||state.edit)return;
 startingExperiments.add(id);renderMain();
 try{
   const result=await action('experiment.start',{id});
   if(state.experimentId===id){
     if(result.experiment)state.experiment=result.experiment;
     await openExperimentWorker(result.scope||`experiment:${id}`);
   }
   toast(projectWorkflow()==='research'?'Worker preparation started. Runs need your request and a verified PR.':'Worker started on the requested task.');
   await refreshState(true);
 }catch(error){toast(error.message,true);await refreshState(true);if(state.experimentId===id)await fetchExperiment(true);}finally{startingExperiments.delete(id);if(state.experimentId===id&&!state.edit)renderMain();}
}
let runFormRequest=0;
function runRequestId(){
 if(crypto.randomUUID)return crypto.randomUUID();
 const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
 const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
async function showSubmitRun(){
 const p=project(),x=experiment();if(!p||!x)return;const request=++runFormRequest,requestId=runRequestId();let heldRunId=null;openModal('Queue a run','<div class="loading-state"><span class="spinner"></span><p>Loading project compute</p></div>','run-submit');let pool;
 try{pool=await loadProjectCompute(p.id,{force:true});}catch(error){if(request===runFormRequest&&state.modalKind==='run-submit'&&$('#modal').open)$('#modal-content').innerHTML=`<div class="notice error">${e(error.message)}</div><button class="button" data-action="submit-run">Try again</button>`;return;}
 if(request!==runFormRequest||state.modalKind!=='run-submit'||!$('#modal').open)return;
 const pooled=pool.nodes.length>0,enabled=pool.nodes.filter(node=>node.enabled!==false),defaults=pool.defaults||{};
 const runNameBase=String(x.name||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,58).replace(/-$/,'')||'experiment';
 openModal('Queue a run',`<p class="modal-description">Queue this run with its verified pull request, or save it as a draft for later.</p><form><div class="field-stack">${field('Run name','name',{placeholder:runNameBase+'-run-1',required:true,maxlength:64,pattern:'[a-z0-9]+(?:-[a-z0-9]+)*',help:'Lowercase letters, numbers and single hyphens; up to 64 characters.'})}<label class="field"><span>Job type</span><select name="job_type"><option value="training">Training</option><option value="evaluation">Evaluation</option><option value="data">Data preparation</option><option value="other">Other</option></select></label><div id="training-telemetry-fields"><p class="small muted">Training must log MFU to this run’s W&B destination. Ask the worker to include its logger in the PR.</p>${field('MFU logger source file','mfu_source_path',{placeholder:'training/metrics.py',required:true})}${textarea('MFU calculation','mfu_method',{placeholder:'Model FLOPs per step, synchronized step timing, and total GPU peak FLOP/s at training precision.',required:true})}</div>${pooled?`<div class="run-pool-summary">${icon('server')}<div><strong>Project compute pool</strong><span>${enabled.length} eligible machine${enabled.length===1?'':'s'} · available GPUs chosen by the scheduler</span></div></div>${!enabled.length?'<div class="notice warn">No machines are enabled in this pool. Enable one in project Compute before preparing a run.</div>':''}<div class="field-grid">${field('Python executable override','python',{placeholder:defaults.python||'Use eligible machine’s Python',help:'Optional absolute path. Defaults to the selected machine’s project settings.'})}${field('Dataset path override','data_path',{placeholder:defaults.data_path||'Use eligible machine’s dataset',help:'Optional absolute path.'})}</div>`:`<div class="notice">Manual machine selection · this project has no compute pool. <button type="button" class="button small-button" data-action="project-compute">Configure pool</button></div><label class="field"><span>Machine</span><select name="host_id" required>${state.data.hosts.length?state.data.hosts.map(h=>`<option value="${e(h.id)}">${e(h.name)}</option>`).join(''):'<option value="">Register a machine first</option>'}</select></label>${field('Repository on selected machine','repo',{value:p.repo||'',required:true})}`}<div class="field-grid">${field('Git revision','revision',{value:'HEAD',required:true,help:'Commit, branch or tag containing this run’s code.'})}${field('GPUs required','gpu_count',{type:'number',value:1,min:0,required:true,help:'Use 0 for a CPU-only run.'})}${field('Free storage required (GiB)','storage_gib',{type:'number',value:10,min:0,required:true})}${field('Free VRAM per GPU (MiB)','min_free_mib',{type:'number',value:0,min:0,required:true})}</div>${field('Pull request URL','pr_url',{type:'url',placeholder:'https://github.com/organization/repository/pull/123',help:'Required to queue. You can save a draft without a PR.'})}${textarea('Training command (JSON argument array)','command',{value:pooled?'["{python}", "train.py"]':'["python", "train.py"]',required:true,help:pooled?'Use {python} and {data} for the selected machine’s configured paths. One argument per item; no shell.':'One argument per item. Commands execute without a shell.'})}</div><div id="run-retained-draft" class="notice" hidden></div><div class="field-error" id="form-error" role="alert" hidden></div><div class="modal-footer run-submit-actions"><button type="submit" class="button primary run-queue-button" name="run_intent" value="queue">Queue run</button><button type="submit" class="button run-save-draft" name="run_intent" value="draft">Save draft</button><button type="button" class="button" data-action="close-modal">Cancel</button></div></form>`,'run-submit');
 bindModalForm(async (fd,submitter,form)=>{const queue=submitter?.value!=='draft';if(queue&&!fd.get('pr_url').trim())throw new Error('Add a pull request URL to queue this run, or choose Save draft.');let command;try{command=JSON.parse(fd.get('command'));}catch{throw new Error('Enter the command as a JSON array, for example ["{python}", "train.py"].');}if(!Array.isArray(command)||!command.length||command.some(v=>typeof v!=='string')||!command[0].trim())throw new Error('The command must be a non-empty array of strings.');const params={project_id:p.id,experiment_id:x.id,name:fd.get('name').trim(),job_type:fd.get('job_type'),revision:fd.get('revision').trim(),gpu_count:Number(fd.get('gpu_count')),storage_gib:Number(fd.get('storage_gib')),min_free_mib:Number(fd.get('min_free_mib')),pr_url:fd.get('pr_url').trim(),command};if(params.job_type==='training')params.training_metrics={mfu_metric:'train/mfu',mfu_unit:'fraction',mfu_method:fd.get('mfu_method').trim(),source_path:fd.get('mfu_source_path').trim()};if(pooled){params.use_project_pool=true;for(const key of ['python','data_path']){const value=String(fd.get(key)||'').trim();if(value)params[key]=value;}}else{params.host_id=fd.get('host_id');params.repo=fd.get('repo').trim();}try{await action(queue?'run.queue':'run.submit',queue?{...params,request_id:requestId}:params);}catch(error){
   if(error.run_id){heldRunId=error.run_id;const notice=$('#run-retained-draft',form);if(notice){notice.hidden=false;notice.textContent=`Draft ${heldRunId} is saved on hold. Correct the PR and retry Queue run; the existing draft will be reused.`;}const draftButton=$('.run-save-draft',form);if(draftButton){draftButton.dataset.remainDisabled='true';draftButton.textContent='Draft saved';}await refreshState(true);}throw error;
  }
  if(form.isConnected)closeModal();if(state.experimentId===x.id){state.tab='runs';persistNavigation();}await refreshState(true);toast(queue?'Run queued. The scheduler will start it when resources are available.':'Draft saved on hold. Queue it when ready.');});
}
const runTelemetry=new Map(),runTelemetryBusy=new Set(),runMetricChoices=new Map();
function metricValue(value,suffix=''){return typeof value==='number'&&Number.isFinite(value)?formatNumber(value)+suffix:'Not reported';}
function runTelemetryPanel(id){
 const run=state.data.runs.find(row=>row.id===id);
 if(run&&isQueued(run))return '<p class="muted">Statistics appear after this run starts.</p>';
 const entry=runTelemetry.get(id);if(!entry)return '<p class="muted">Loading live run metrics…</p>';
 const metrics=entry.metrics||{},system=entry.system_metrics||{},first=keys=>keys.map(key=>metrics[key]).find(value=>typeof value==='number'&&Number.isFinite(value));
 const loss=first(['train/loss','training/loss','loss','eval/loss']),throughput=first(['perf/samples_per_second','train/samples_per_second','samples_per_second']),step=first(['perf/step_seconds','train/step_time','step_time']);
 const gpuRows=new Map();for(const [key,value] of Object.entries(system)){const match=key.match(/^gpu\.(\d+)\.(gpu|memoryAllocatedBytes|memoryAllocated|powerWatts|temp)$/);if(match){if(!gpuRows.has(match[1]))gpuRows.set(match[1],{index:match[1]});gpuRows.get(match[1])[match[2]]=value;}}
 const memory=first(['gpu/allocated_bytes','gpu/memory_allocated_bytes']),maxMemory=memory??(gpuRows.size?Math.max(...[...gpuRows.values()].map(row=>row.memoryAllocatedBytes||0)):null);
 const mfu=entry.mfu?entry.mfu.value===null?metricValue(entry.mfu.raw)+' (unit unknown)':metricValue(entry.mfu.value,'%'):'Not reported';
 const training=!['data','evaluation','other'].includes(entry.requirement?.job_type||run?.config?.telemetry?.job_type);
 const cards=[['MFU',mfu],['VRAM allocated'+(memory==null?' · max GPU':''),maxMemory!=null?metricValue(maxMemory/1073741824,' GiB'):'Not reported'],['Loss',metricValue(loss)],['Throughput',metricValue(throughput,' samples/s')],['Step time',metricValue(step,' s')]].filter(([,value])=>training||value!=='Not reported');
 const series=entry.series||[],choice=runMetricChoices.get(id)||series.find(row=>row.key==='train/loss')?.key||series[0]?.key,selected=series.filter(row=>row.key===choice);
 const freshness=entry.observed_at?`Metric sample ${elapsed(entry.observed_at)}`:'Metric sample time unavailable';
 const gpuTable=gpuRows.size?`<p class="muted small">W&B system metrics · ${entry.system_observed_at?elapsed(entry.system_observed_at):'Sample time unavailable'}. GPU indices are as reported by W&B.</p><table><thead><tr><th>GPU</th><th>VRAM</th><th>Utilization</th><th>Power</th></tr></thead><tbody>${[...gpuRows.values()].map(row=>`<tr><td>${e(row.index)}</td><td>${row.memoryAllocatedBytes!=null?e(metricValue(row.memoryAllocatedBytes/1073741824,' GiB')):e(metricValue(row.memoryAllocated,'%'))}</td><td>${e(metricValue(row.gpu,'%'))}</td><td>${e(metricValue(row.powerWatts,' W'))}</td></tr>`).join('')}</tbody></table>`:(entry.gpus||[]).length?`<p class="muted small">Last host readings · device-wide, including other processes.</p><table><thead><tr><th>GPU</th><th>VRAM used / total</th><th>Utilization</th><th>Observed</th></tr></thead><tbody>${entry.gpus.map(gpu=>`<tr><td>${e(gpu.index)}</td><td>${gpu.memory_total_mib!=null&&gpu.memory_free_mib!=null?e(((gpu.memory_total_mib-gpu.memory_free_mib)/1024).toFixed(1)+' / '+(gpu.memory_total_mib/1024).toFixed(1)+' GiB'):'Not reported'}</td><td>${e(metricValue(gpu.utilization,'%'))}</td><td>${gpu.stale?'Stale · ':''}${e(elapsed(gpu.observed_at))}</td></tr>`).join('')}</tbody></table>`:'<p class="muted">No GPU telemetry reported for this run yet.</p>';
 return `${entry.notice?`<p class="muted">${e(entry.notice)}</p>`:''}${entry.error?`<div class="notice warn">${e(entry.error)}</div>`:''}<div class="run-metrics-grid">${cards.map(([label,value])=>`<div class="run-stat"><span>${e(label)}</span><strong>${e(value)}</strong></div>`).join('')}</div>${entry.missing_required_mfu?'<div class="notice warn">Required MFU has not been reported. The training worker must verify its W&B logger.</div>':''}${entry.mfu&&!entry.mfu.valid?'<div class="notice warn">MFU needs checking: verify its units, FLOP estimate, hardware peak and timing.</div>':''}<p class="muted small">${e(freshness)} · ${entry.observed_at&&Date.now()/1000-entry.observed_at>60?'No recent metric sample · ':''}Checked ${e(elapsed(entry.updated_at))}. Refreshes every 10 seconds while open.</p>${entry.mfu?`<p class="muted small">MFU sample: ${entry.mfu.observed_at?e(elapsed(entry.mfu.observed_at)):'time unavailable'}. ${entry.mfu.observed_at&&Date.now()/1000-entry.mfu.observed_at>60?'No recent MFU sample.':''}</p>`:''}${entry.requirement?.mfu_method?`<details><summary>MFU calculation</summary><p>${e(entry.requirement.mfu_method)}</p><code>${e(entry.requirement.source_path)}</code></details>`:''}${selected.length?`<label class="field"><span>Metric</span><select data-run-metric="${e(id)}">${series.map(row=>`<option value="${e(row.key)}" ${row.key===choice?'selected':''}>${e(row.key)}</option>`).join('')}</select></label><div class="metric-chart">${metricChart(selected,choice)}</div>`:''}${training||run?.gpu_count>0||gpuRows.size||(entry.gpus||[]).length?`<h3>GPU readings</h3>${gpuTable}`:''}${Object.keys(metrics).length?`<details><summary>All latest metrics</summary><table><tbody>${Object.entries(metrics).slice(0,80).map(([key,value])=>`<tr><td class="metric-name">${e(key)}</td><td>${e(metricValue(value))}</td></tr>`).join('')}</tbody></table></details>`:''}`;
}
async function refreshRunTelemetry(id){
 if(!id||runTelemetryBusy.has(id))return;runTelemetryBusy.add(id);
 const run=state.data.runs.find(row=>row.id===id);if(run&&isQueued(run)){runTelemetryBusy.delete(id);return;}
 try{runTelemetry.set(id,await api('run-metrics?id='+encodeURIComponent(id)));}
 catch(error){runTelemetry.set(id,{...(runTelemetry.get(id)||{}),error:error.message});}
 finally{runTelemetryBusy.delete(id);const panel=$('#run-telemetry-body');if($('#modal').open&&panel?.dataset.runId===id){const expanded=$$('details[open]',panel).map(d=>$('summary',d)?.textContent);panel.innerHTML=runTelemetryPanel(id);for(const d of $$('details',panel))d.open=expanded.includes($('summary',d)?.textContent);}}
}
function showRun(id){const r=state.data.runs.find(r=>r.id===id);if(!r)return;const queued=isQueued(r),done=terminal.has(r.status),command=r.config?.command||r.command;openModal(r.name||r.id,`<div class="metadata-line" style="margin-top:0">${status(r.status==='queued'&&r.ready===false?'held':r.status)}<span class="meta-item">${icon('clock')}${e(date(r.created))}</span></div><dl class="detail-grid"><dt>Started</dt><dd>${runStartLabel(r).replace(/^Started /,'')}</dd><dt>Runtime</dt><dd data-run-duration="${e(r.id)}">${e(runDuration(r)||'Not started')}</dd><dt>Project</dt><dd>${e(state.data.projects.find(p=>p.id===r.project_id)?.name||r.project_id||'Unassigned')}</dd><dt>Machine</dt><dd>${e(r.host_name||state.data.hosts.find(h=>h.id===r.host_id)?.name||'Unassigned')}</dd><dt>GPUs</dt><dd>${e(r.gpu_count??'Unknown')}${r.allocated_gpus?.length?` · device ${e(r.allocated_gpus.join(', '))}`:''}</dd><dt>Storage</dt><dd>${e(r.config?.storage_gib??r.storage_gib??'Not recorded')}${r.config?.storage_gib!=null||r.storage_gib!=null?' GiB':''}</dd><dt>Revision</dt><dd>${r.revision?`<code class="inline-code">${e(r.revision)}</code>`:'Not recorded'}</dd><dt>Pull request</dt><dd>${r.pr_url?link(r.pr_url,`Open pull request ${icon('external')}`):'No PR attached'}</dd></dl>${queued?runPlacement(r):''}${r.waiting_reason||r.error?`<div class="notice ${r.error?'error':'warn'}">${e(capacityWaitReason(r,state.data.projects,state.data.runs))}</div>`:''}<section class="run-telemetry" aria-label="Run statistics"><div class="section-title"><span>Live statistics</span><button type="button" class="icon-button" data-action="refresh-run-metrics" data-id="${e(r.id)}" aria-label="Refresh run statistics">${icon('refresh')}</button></div><div id="run-telemetry-body" data-run-id="${e(r.id)}">${runTelemetryPanel(r.id)}</div></section>${command?`<h3>Command</h3><pre class="detail-command">${e(Array.isArray(command)?JSON.stringify(command,null,2):String(command))}</pre>`:''}${r.wandb_url?`<div class="resource-links">${link(r.wandb_url,`${icon('chart')}Open Weights & Biases ${icon('external')}`,'resource-link')}</div>`:''}${queued?`<form id="review-pr-form"><h3>${r.pr_url?'Update pull request':'Attach the required pull request'}</h3>${field('Pull request URL','pr_url',{type:'url',required:true,value:r.pr_url||'',placeholder:'https://github.com/…/pull/123'})}<input type="hidden" name="run_id" value="${e(r.id)}"><div class="field-error" id="form-error" role="alert" hidden></div><div style="margin-top:10px"><button class="button small-button" type="submit"${disabled()}>${icon('branch')}Verify PR</button></div></form><div class="notice">${r.ready?'This run is eligible for the scheduler. Hold it to prevent launch.':'Releasing explicitly authorizes the scheduler to launch this PR-backed run when resources are available.'}</div>`:''}${r.presentation?.reason?`<details><summary>Retirement evidence</summary><p>${e(r.presentation.reason)}</p><p>${e(r.presentation.evidence)}</p>${r.presentation.parent_run_id?`<p>Related run: ${e(r.presentation.parent_run_id)}</p>`:''}</details>`:''}<div class="modal-footer">${done?`<button class="button" data-action="run-presentation" data-id="${e(r.id)}"${disabled()}>${r.presentation?.archived?'Restore':'Archive retired run'}</button>`:''}${!done?`<button class="button danger" data-action="cancel-run" data-id="${e(r.id)}"${disabled()}>Cancel run</button>`:''}${queued?`<button class="button ${r.ready?'':'primary'}" data-action="${r.ready?'hold-run':'ready-run'}" data-id="${e(r.id)}"${disabled()} ${!r.ready&&!r.pr_url?'disabled title="Attach and verify a PR first"':''}>${icon(r.ready?'pause':'play')}${r.ready?'Hold run':'Release run'}</button>`:'<button class="button" data-action="close-modal">Close</button>'}</div>`,'run-detail');refreshRunTelemetry(id);if(queued)bindModalForm(async fd=>{await action('run.review',{run_id:id,pr_url:fd.get('pr_url').trim()});await refreshState(true);showRun(id);toast('Pull request verified.');});}
function showReviewSchedule(){const x=state.experiment;if(!x)return;const interval=Number(x.review_interval_minutes||0);openModal('Recurring experiment review',`<p class="modal-description">The experiment worker reviews current evidence and updates this document while the workspace computer is on, even with this app closed. Reviews use your worker model and never release or launch runs.</p><form><label class="field"><span>Review interval</span><select name="interval_minutes">${[[0,'Off'],[15,'Every 15 minutes'],[30,'Every 30 minutes'],[60,'Every hour'],[240,'Every 4 hours']].map(([value,label])=>`<option value="${value}" ${interval===value?'selected':''}>${label}</option>`).join('')}</select><small>Enabling a schedule explicitly starts recurring agent turns using this conversation’s connected backend account.</small></label>${x.last_review_at?`<div class="notice">Last review: ${e(date(x.last_review_at))}${x.next_review_at?`<br>Next review: ${e(date(x.next_review_at))}`:''}</div>`:''}${x.review_error?`<div class="notice warn">${e(x.review_error)}</div>`:''}${formFooter('Save review schedule')}</form>`,'review-schedule');bindModalForm(async fd=>{const interval_minutes=Number(fd.get('interval_minutes'));await action('experiment.schedule',{id:x.id,interval_minutes});closeModal();await fetchExperiment(true);toast(interval_minutes?'Recurring worker reviews enabled.':'Recurring worker reviews turned off.');});}
function showHistory(){const x=state.experiment;if(!x)return;const entries=[...(x.history||[])].sort((a,b)=>b.version-a.version);openModal('Document history',`<p class="modal-description">Restore a previous version as a new revision. Your current document stays in the history.</p>${entries.length?entries.map(h=>`<div class="run-row"><div class="run-main"><div class="run-name">Version ${e(h.version)}${h.version===x.version?' · current':''}</div><div class="run-subtitle">${e(date(h.created))}</div></div><button class="button small-button" data-action="restore-document" data-version="${e(h.version)}" ${h.version===x.version?'disabled':''}>Restore</button></div>`).join(''):'<div class="notice">No previous versions yet. Saved edits will appear here.</div>'}`,'history');}
function showJump(){openModal('Go to anything',`<input class="jump-input" id="jump-input" placeholder="Search projects, experiments, or views" aria-label="Search workspace"><div class="jump-results" id="jump-results"></div>`,'jump');const fill=()=>{const query=$('#jump-input').value.toLowerCase();const items=[{name:'Workspace',kind:'View',view:'workspace',icon:'layers'},{name:'Compute',kind:'View',view:'compute',icon:'cpu'},{name:'Settings',kind:'View',view:'settings',icon:'settings'},...(state.data?.projects||[]).map(p=>({name:p.name,kind:'Project',project:p.id,icon:'folder'})),...(state.data?.experiments||[]).map(x=>({name:x.name,kind:state.data.projects.find(p=>p.id===x.project_id)?.name||'Experiment',experiment:x.id,icon:'file'}))].filter(i=>`${i.name} ${i.kind}`.toLowerCase().includes(query));$('#jump-results').innerHTML=items.length?items.map(i=>`<button class="jump-item" ${i.view?`data-view="${i.view}"`:i.project?`data-project="${e(i.project)}"`:`data-experiment="${e(i.experiment)}"`}>${icon(i.icon)}${e(i.name)}<small>${e(i.kind)}</small></button>`).join(''):'<div class="sidebar-placeholder">No matching projects or experiments.</div>';};$('#jump-input').addEventListener('input',fill);$('#jump-input').addEventListener('keydown',event=>{if(event.key==='ArrowDown'){$('#jump-results button')?.focus();event.preventDefault();}if(event.key==='Enter'){$('#jump-results button')?.click();}});fill();}
async function showLogin(){accountGate.open();}
async function perform(op,params={},success){try{await action(op,params);await refreshState(true);if(success)toast(success);return true;}catch(error){toast(error.message,true);return false;}}
async function handleAction(name,el){switch(name){
 case 'pin-agent':toggleAgentPin();break;
 case 'toggle-agent-list':agentsExpanded=!agentsExpanded;try{localStorage.setItem('supersurfer-agents-expanded',String(agentsExpanded));}catch{}renderAgentChooser();break;
 case 'edit-brief':showEditBrief();break;
 case 'refresh-page':await loadMarkdownPage(state.experimentId,el.dataset.pageId||state.tab.slice(5));break;
 case 'select-result':resultSelections.set(state.experimentId,el.dataset.resultId);renderMain();if(el.dataset.resultId==='metrics')await loadMetrics(true);else await liveResults.refresh();break;
 case 'refresh-results':await loadResultPages(true);if(chosenResultPage())await liveResults.refresh();else await loadMetrics(true);break;
 case 'archive-item':{const id=state.experimentId,archived=!(state.experiment||experiment())?.archived;await archiveTask(id,archived);break;}
 case 'toggle-archived-items':{const id=el.dataset.id;if(archivedItemProjects.has(id))archivedItemProjects.delete(id);else archivedItemProjects.add(id);state.sidebarSignature='';syncNavigation();renderMain();break;}
 case 'archive-agent':await toggleChatArchive();break;
 case 'toggle-archived-agents':showArchivedAgents=!showArchivedAgents;renderAgentChooser();break;
 case 'refresh-compute':await refreshComputeAvailability();break;
 case 'edit-project-limits':closeModal();await navigate({projectId:el.dataset.projectId,tab:'surfboard'});surfboardEditor.showBlock('compute');break;
 case 'rename-agent':showRenameAgent();break;
 case 'approve-request':await decideApproval(el,'approve');break;
 case 'deny-approval':await decideApproval(el,'deny');break;
 case 'reset-chat-settings':await saveChatPreferences({model:null,reasoning:null,fast_mode:null,approval_mode:null});break;
 case 'toggle-fast':await saveChatPreferences({fast_mode:state.chat?.preferences?.effective?.fast_mode!==true});break;
 case 'import-theme':el.disabled=true;try{const imported=await window.superSurferTheme?.importTheme();if(imported)toast(imported.name+' applied.');}catch(error){toast(error.message,true);}finally{if(el.isConnected)el.disabled=false;}break;
 case 'theme':window.superSurferTheme?.setPreference(el.dataset.themeChoice);$$('[data-theme-choice]').forEach(button=>{button.classList.toggle('selected',button.dataset.themeChoice===el.dataset.themeChoice);button.setAttribute('aria-pressed',String(button.dataset.themeChoice===el.dataset.themeChoice));});break;
 case 'jump':showJump();break;
 case 'filter-runs':state.runFilter=el.dataset.filter;state.queuePriority=false;renderMain();break;
 case 'queue-priority':state.queuePriority=!state.queuePriority;renderMain();break;
 case 'jump-queue':state.queuePriority=true;renderMain();{const heading=$('#compute-runs-heading');heading?.scrollIntoView({block:'start'});heading?.focus({preventScroll:true});}break;
 case 'refresh':await refreshState(true);if(state.view==='workspace'&&!state.experimentId&&state.tab==='compute')await loadProjectCompute(state.projectId,{force:true});await refreshChat(true);break;
 case 'auth':showAuth();break;
 case 'new-window':if(window.superSurferDesktop?.newWindow)await window.superSurferDesktop.newWindow();break;
 case 'configure-layout':await showViewLayout();break;
 case 'add-view-page':await showViewLayout({addPage:true});break;
 case 'toggle-right-sidebar':$('#right-sidebar-toggle').click();break;
 case 'toggle-chat':state.chatVisible=$('#chat-panel').hidden;if(state.chatVisible)chatOpenPending=true;chatRevealScope=state.chatVisible?chatLayoutKey():null;if(state.chatVisible&&currentLayout()?.find(row=>row.id==='chat')?.placement==='main'){state.tab='chat';renderMain();}applyChatLayout();dockChat();persistNavigation();if(state.chatVisible)refreshChat(true);break;
 case 'maximize-chat':state.chatVisible=true;state.chatMaximized=!state.chatMaximized;applyChatLayout();dockChat();persistNavigation();break;
 case 'close-modal':closeModal();break;
 case 'add-project':showAddProject();break;
 case 'add-experiment':await showAddExperiment();break;
 case 'new-experiment-agent':await createExperimentAgent();break;
 case 'resume-experiment-agent':await resumeExperimentAgent();break;
 case 'refresh-agents':await loadAgentDirectory();break;
 case 'add-host':showAddHost();break;
 case 'open-code-presentation':await showCodePresentation(state.chat?.editor_presentation);break;
 case 'upload-files':fileUploads.pick('editor');break;
 case 'refresh-project-panel':{const kind=el.dataset.panelKind||el.closest('[data-tile-kind]')?.dataset.tileKind||state.tab;await loadProjectPanel(kind,state.projectId,kind==='artifacts'?artifactPaths.get(state.projectId)||'':'');break;}
 case 'export-diagnostics':await exportProjectDiagnostics();break;
 case 'project-compute':closeModal();await navigate({projectId:state.projectId,tab:'compute'});break;
 case 'onboard-project-host':await openHostOnboarding();break;
 case 'add-compute-node':await addComputeNode();break;
 case 'remove-compute-node':await removeComputeNode(Number(el.dataset.nodeIndex));break;
 case 'reload-project-compute':await reloadProjectCompute();break;
 case 'submit-run':await showSubmitRun();break;
 case 'add-worker-wakeup':await addWorkerWakeup();break;
 case 'refresh-worker-wakeups':await loadWorkerWakeups(state.experimentId,{force:true});break;
 case 'pause-worker-wakeup':await changeWorkerWakeup('pause',el);break;
 case 'remove-worker-wakeup':await changeWorkerWakeup('remove',el);break;
 case 'start-experiment':await startExperiment();break;
 case 'open-experiment-worker':await openExperimentWorker();break;
 case 'initialize-project':if(await perform('project.initialize',{project_id:state.projectId},'Project context initialized.'))await refreshState(true);break;
 case 'edit-experiment':state.edit=true;renderMain();$('#document-editor')?.focus();break;
 case 'cancel-edit':state.edit=false;sessionStorage.removeItem(`ss-draft-${state.experimentId}`);renderMain();break;
 case 'save-experiment':await saveExperiment();break;
 case 'document-history':showHistory();break;
 case 'review-schedule':showReviewSchedule();break;
 case 'restore-document':el.disabled=true;try{await action('experiment.restore',{id:state.experimentId,version:Number(el.dataset.version),current_version:state.experiment.version});closeModal();await fetchExperiment(true);toast('Previous document restored as a new version.');}catch(error){toast(error.message,true);el.disabled=false;}break;
 case 'apply-permission-mode':await saveChatPreferences({approval_mode:state.chat?.preferences?.overrides?.approval_mode??null});break;
 case 'earlier-chat':{const scope=state.scope,messages=$('#chat-messages'),before=messages.scrollHeight,top=messages.scrollTop;chatHistoryCount.set(scope,Math.min(100000,(chatHistoryCount.get(scope)||80)+80));await refreshChat(true);if(state.scope===scope)messages.scrollTop=top+messages.scrollHeight-before;break;}
 case 'stop-chat':if(await perform('chat.stop',{scope:state.scope},'Stop requested.'))refreshChat(true);break;
 case 'pause-queue':await perform('queue.pause',{},'New launches paused. Active training continues.');break;
 case 'resume-queue':await perform('queue.resume',{},'Scheduler launches resumed.');break;
 case 'move-run-up':{const id=el.dataset.id,focused=document.activeElement===el,queue=queuedRuns(),index=queue.findIndex(r=>r.id===id);if(index>0)await perform('run.move',{run_id:id,before_id:queue[index-1].id},'Queue order updated.');if(focused&&state.view==='compute'&&state.queuePriority&&document.activeElement===document.body){const row=$$('.run-row').find(row=>row.dataset.run===id),button=row?.querySelector('[data-action=move-run-up]');(button&&!button.disabled?button:row)?.focus({preventScroll:true});}break;}
 case 'ready-run':case 'hold-run':el.disabled=true;if(await perform(name==='ready-run'?'run.ready':'run.hold',{run_id:el.dataset.id},name==='ready-run'?'Run released to the scheduler.':'Run placed on hold.'))showRun(el.dataset.id);else el.disabled=false;break;
 case 'run-presentation':{const run=state.data.runs.find(r=>r.id===el.dataset.id);if(!run)break;if(run.presentation?.archived){if(await perform('run.presentation',{run_id:run.id,version:run.presentation.version,archived:false},'Run restored.')){showRun(run.id);renderMain();}break;}openModal('Archive retired run',`<p>Archive only confirmed retired work. The run, checkpoints, metrics and source links remain available under Archived, with Restore.</p><form>${field('Retirement reason','reason',{required:true})}${field('Evidence or authoritative stop/continuation receipt','evidence',{required:true})}${field('Related run ID (optional)','parent_run_id')}<label><input type="checkbox" name="finished" required> This run has no unfinished evaluation, analysis or recovery.</label><div class="field-error" id="form-error" role="alert" hidden></div>${formFooter('Archive run')}</form>`,'run-archive');bindModalForm(async fd=>{await action('run.presentation',{run_id:run.id,version:run.presentation?.version||0,archived:true,reason:fd.get('reason'),evidence:fd.get('evidence'),parent_run_id:fd.get('parent_run_id').trim()||null,unfinished_work:false});await refreshState(true);closeModal();renderMain();toast('Run archived. Restore is available under Archived.');});break;}
 case 'cancel-run':if(window.confirm('Cancel this run? If it is training, its process will be terminated.')){el.disabled=true;if(await perform('run.cancel',{run_id:el.dataset.id},'Run cancelled.'))showRun(el.dataset.id);else el.disabled=false;}break;
 case 'provider-login':accountGate.open(el.dataset.backend);break;
 case 'login':accountGate.open('codex');break;
 case 'refresh-run-metrics':await refreshRunTelemetry(el.dataset.id);break;
 case 'refresh-metrics':await loadMetrics(true);break;
 case 'choose-pdf':{if(tileLayout.editing()){toast('Save or cancel the current arrangement before choosing a PDF.',true);break;}const page=activePage(),base=structuredClone(savedActivePage()),projectId=state.projectId,experimentId=state.experimentId,pageId=state.tab;pickWorkspaceFile(async path=>{if(state.projectId!==projectId||state.experimentId!==experimentId||state.tab!==pageId)throw new Error('Return to the original page before choosing its PDF.');const changed=structuredClone(page);changed.tiles.find(row=>row.kind==='pdf').path=path;await savePageLayout(changed,base);},{pdfOnly:true,title:'Choose PDF'});break;}
 case 'configure-wandb':state.tab='overview';persistNavigation();state.edit=true;renderMain();$('#document-wandb')?.focus();break;
 }}
document.addEventListener('click',async event=>{const target=event.target.closest('button,a,[data-run]');if(!target)return;if(target.disabled)return;try{
 if(target.dataset.workspaceFile){event.preventDefault();if(target.dataset.workspaceProject===state.projectId)await openPageCode({path:target.dataset.workspaceFile});return;}
 if(target.hasAttribute('data-artifact-path')){artifactPaths.set(state.projectId,target.dataset.artifactPath);if(target.closest('#project-view-panels')){await loadProjectPanel('artifacts',state.projectId,target.dataset.artifactPath);renderProjectSlots();}else renderMain();return;}
 if(target.dataset.artifactPreview){await previewArtifact(target.dataset.artifactPreview);return;}
 if(target.dataset.copyArtifact){await navigator.clipboard.writeText(target.dataset.copyArtifact);toast('Artifact path copied.');return;}
 if(target.dataset.action){event.preventDefault();await handleAction(target.dataset.action,target);return;}
 if(target.dataset.conversation){await selectConversation(target.dataset.conversation);return;}
 if(target.dataset.view){closeModal();await navigate({view:target.dataset.view});if(target.dataset.view==='settings')refreshAccountModels();return;}
 if(target.dataset.project){closeModal();await navigate({projectId:target.dataset.project});return;}
 if(target.dataset.experiment){const x=state.data.experiments.find(x=>x.id===target.dataset.experiment);if(x){closeModal();await navigate({projectId:x.project_id,experimentId:x.id});}return;}
 if(target.dataset.tab){if(state.edit)stashEditor();state.edit=false;const wasBoard=!!isSurfboard();state.tab=target.dataset.tab;if(isSurfboard()&&!wasBoard&&!state.pinnedAgent){surfboardPreviousChatVisible=state.chatVisible;state.chatVisible=isWorkflow();state.chatMaximized=false;applyChatLayout();}else if(wasBoard&&!isSurfboard()&&surfboardPreviousChatVisible!==null){state.chatVisible=surfboardPreviousChatVisible;surfboardPreviousChatVisible=null;applyChatLayout();}persistNavigation();syncAgentChooser();renderAgentChooser();refreshChat(true);renderMain();if(pageHasTile('results')){if(state.experimentId)loadResultPages(true).then(()=>chosenResultPage()?liveResults.refresh():loadMetrics(true));else{for(const item of state.data.experiments.filter(x=>x.project_id===state.projectId))resultPages.delete(item.id);loadProjectResults();}}if(pageHasTile('compute')&&!state.experimentId)loadProjectCompute(state.projectId,{force:true}).catch(()=>{});return;}
 if(target.dataset.prompt){$('#chat-input').value=target.dataset.prompt;$('#chat-input').focus();return;}
 if(target.dataset.run){showRun(target.dataset.run);return;}
 }catch(error){toast(error.message,true);}});
document.addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();showJump();}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='s'&&state.edit){event.preventDefault();saveExperiment();}if((event.key==='Enter'||event.key===' ')&&event.target.matches('[data-run]')){event.preventDefault();showRun(event.target.dataset.run);}});
$('#modal').addEventListener('click',event=>{if(event.target===$('#modal')){const rect=$('#modal').getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)closeModal();}});
$('#modal').addEventListener('close',()=>{state.modalKind=null;if(renderPending&&!state.edit&&!(state.view==='settings'&&($('#settings-form')?.dataset.dirty==='true'||editorSettings.dirty()||workspacePermissionSaving))&&!$('#project-compute-form')?.dataset.dirty)renderMain();});
const chatDivider=$('#chat-resizer');
let resizingChat=false;
chatDivider.addEventListener('pointerdown',event=>{if(event.button!==0||state.chatMaximized||!state.chatVisible)return;event.preventDefault();resizingChat=true;chatDivider.setPointerCapture(event.pointerId);document.body.classList.add('resizing-chat');});
chatDivider.addEventListener('pointermove',event=>{if(resizingChat)resizeChat($('.workspace-body').getBoundingClientRect().right-event.clientX);});
function endChatResize(event){if(!resizingChat)return;resizingChat=false;document.body.classList.remove('resizing-chat');if(chatDivider.hasPointerCapture(event.pointerId))chatDivider.releasePointerCapture(event.pointerId);tileLayout.commitResize();persistNavigation();}
chatDivider.addEventListener('pointerup',endChatResize);chatDivider.addEventListener('pointercancel',endChatResize);
chatDivider.addEventListener('keydown',event=>{const bounds=chatWidthBounds(),current=Number(chatDivider.getAttribute('aria-valuenow'));if(event.key==='ArrowLeft')resizeChat(current+24);else if(event.key==='ArrowRight')resizeChat(current-24);else if(event.key==='Home')resizeChat(bounds.min);else if(event.key==='End')resizeChat(bounds.max);else return;event.preventDefault();tileLayout.commitResize();persistNavigation();});
chatDivider.addEventListener('dblclick',()=>{resizeChat(390);persistNavigation();});
function toggleSidebar(){state.sidebarCollapsed=!state.sidebarCollapsed;applyChatLayout();persistNavigation();}
$('#sidebar-toggle').onclick=toggleSidebar;$('#left-sidebar-toggle').onclick=toggleSidebar;
document.addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&!event.shiftKey&&!event.altKey&&event.key.toLowerCase()==='b'&&!document.querySelector('dialog[open]')){event.preventDefault();event.stopImmediatePropagation();toggleSidebar();}},true);
document.addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&event.shiftKey&&!event.altKey&&event.key.toLowerCase()==='b'&&!document.querySelector('dialog[open]')){event.preventDefault();event.stopImmediatePropagation();setRightSidebarCollapsed(!rightSidebarCollapsed);}},true);
const sidebarDivider=$('#sidebar-resizer');let sidebarDrag=null;
sidebarDivider.addEventListener('pointerdown',event=>{if(event.button!==0||sidebarDivider.getAttribute('aria-disabled')==='true')return;event.preventDefault();sidebarDrag={x:event.clientX,width:$('.sidebar').getBoundingClientRect().width};sidebarDivider.setPointerCapture(event.pointerId);document.body.classList.add('resizing-sidebar');});
sidebarDivider.addEventListener('pointermove',event=>{if(sidebarDrag)resizeSidebar(sidebarDrag.width+event.clientX-sidebarDrag.x);});
function endSidebarResize(){if(!sidebarDrag)return;sidebarDrag=null;document.body.classList.remove('resizing-sidebar');tileLayout.commitResize();persistNavigation();}
sidebarDivider.addEventListener('pointerup',endSidebarResize);sidebarDivider.addEventListener('pointercancel',endSidebarResize);sidebarDivider.addEventListener('lostpointercapture',endSidebarResize);
sidebarDivider.addEventListener('keydown',event=>{const bounds=sidebarWidthBounds(),width=Number(sidebarDivider.getAttribute('aria-valuenow'));if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();resizeSidebar(event.key==='Home'?bounds.min:event.key==='End'?bounds.max:width+(event.key==='ArrowLeft'?-20:20));tileLayout.commitResize();persistNavigation();});
sidebarDivider.addEventListener('dblclick',()=>{resizeSidebar(206);persistNavigation();});
const projectDivider=$('#sidebar-projects-resizer');let projectDrag=null;
projectDivider.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();projectDrag={y:event.clientY,height:$('#project-tree').getBoundingClientRect().height};projectDivider.setPointerCapture(event.pointerId);document.body.classList.add('resizing-project-tree');});
function resizeProjectTree(height){const bounds=projectTreeBounds();state.projectTreeHeight=Math.round(Math.max(bounds.min,Math.min(bounds.max,height)));applyProjectTreeHeight();}
projectDivider.addEventListener('pointermove',event=>{if(projectDrag)resizeProjectTree(projectDrag.height+event.clientY-projectDrag.y);});
function endProjectResize(){if(!projectDrag)return;projectDrag=null;document.body.classList.remove('resizing-project-tree');persistNavigation();}
for(const name of ['pointerup','pointercancel','lostpointercapture'])projectDivider.addEventListener(name,endProjectResize);
projectDivider.addEventListener('keydown',event=>{const bounds=projectTreeBounds(),height=Number(projectDivider.getAttribute('aria-valuenow'));if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key))return;event.preventDefault();resizeProjectTree(event.key==='Home'?bounds.min:event.key==='End'?bounds.max:height+(event.key==='ArrowUp'?-20:20));persistNavigation();});
projectDivider.addEventListener('dblclick',()=>{state.projectTreeHeight=null;applyProjectTreeHeight();persistNavigation();});
window.addEventListener('resize',()=>{if(!resizingChat&&!sidebarDrag)applyChatLayout();});
new ResizeObserver(()=>{const canvas=$('#page-tile-grid'),page=panelWindows.page(activePage());if(canvas?.classList.contains('dock-canvas')&&page)renderDockLayout(canvas,page);}).observe($('#main'));
$('#chat-questions').addEventListener('input',updateQuestionDraft);
$('#chat-questions').addEventListener('change',updateQuestionDraft);
$('#chat-questions').addEventListener('submit',answerQuestion);
$('#chat-form').addEventListener('submit',sendChat);
$('#chat-input').addEventListener('input',resizeComposer);
$('#chat-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();sendChat();}});
$('#chat-preferences').addEventListener('change',event=>{if(event.target.id==='chat-backend')saveChatPreferences({backend:event.target.value,model:null,reasoning:null,fast_mode:null,approval_mode:null});if(event.target.id==='chat-model')saveChatPreferences({model:event.target.value||null});if(event.target.id==='chat-reasoning')saveChatPreferences({reasoning:event.target.value||null});if(event.target.id==='chat-approval-mode')saveChatPreferences({approval_mode:event.target.value||null});});
$('#chat-preferences').addEventListener('focusout',()=>setTimeout(renderChatPreferences,0));
$('#chat-input').addEventListener('input',stashMessageDraft);
document.addEventListener('dragstart',event=>{const row=event.target.closest('[draggable="true"][data-run]');if(!row)return;draggedRun=row.dataset.run;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',draggedRun);row.classList.add('dragging');});
document.addEventListener('dragover',event=>{const row=event.target.closest('[draggable="true"][data-run]');if(row&&draggedRun&&row.dataset.run!==draggedRun){event.preventDefault();$$('.drag-over').forEach(el=>el.classList.remove('drag-over'));row.classList.add('drag-over');row.dataset.dropAfter=String(event.clientY>row.getBoundingClientRect().top+row.getBoundingClientRect().height/2);}});
document.addEventListener('dragleave',event=>event.target.closest('.drag-over')?.classList.remove('drag-over'));
document.addEventListener('drop',async event=>{const row=event.target.closest('[draggable="true"][data-run]');if(row&&draggedRun&&row.dataset.run!==draggedRun){event.preventDefault();const runId=draggedRun;draggedRun=null;const rows=queuedRuns(),index=rows.findIndex(r=>r.id===row.dataset.run),after=event.clientY>row.getBoundingClientRect().top+row.getBoundingClientRect().height/2;const before=after?(rows[index+1]?.id||null):row.dataset.run;if(before!==runId)await perform('run.move',{run_id:runId,before_id:before},'Queue order updated.');}});
document.addEventListener('dragend',()=>{draggedRun=null;$$('.dragging,.drag-over').forEach(el=>el.classList.remove('dragging','drag-over'));});
async function refreshAccountModels(){await Promise.allSettled([accountGate.refresh(),fetchModelCatalog(),...(state.view==='settings'?[workspaceAccounts.refresh()]:[])]);renderChatPreferences();if(state.view==='settings'&&$('#settings-form')?.dataset.dirty!=='true'&&!editorSettings.dirty()&&!$('#modal').open)renderMain();}
let chatPollingStarted=false;
function startChatPolling(){if(chatPollingStarted)return;chatPollingStarted=true;refreshAccountModels();chatPoll();}
async function chatPoll(){await refreshChat();setTimeout(chatPoll,state.chat?.busy?800:3000);}
const accountGate=createAccountGate({api,action,readOnly,getBackend:currentBackend,getSetupRequired:()=>state.data?.account_setup?.required===true,onChoose:async result=>{state.data.settings=result.settings;state.data.account_setup=result.setup;await refreshState(true);await refreshChat(true);await fetchModelCatalog(true);},onAccount:account=>{state.accounts||={};state.accounts[account.backend||'codex']=account;state.account=account;workspaceAccounts.observe(account);if(state.data)updateChatHeader();}});
const workspaceAccounts=createWorkspaceAccounts({api,action,gate:accountGate,readOnly,onError:message=>toast(message,true)});
await readNavigation();
await refreshState(true);
if(panelWindows.detached&&panelWindows.path)await openPageCode({path:panelWindows.path}).catch(error=>toast(error.message,true));
syncClientTimezone();
if(!panelWindows.detached||panelWindows.page(activePage())?.tiles.some(tile=>tile.kind==='chat')){startChatPolling();}
setInterval(()=>refreshState(),5000);
setInterval(updateRunDurations,1000);
setInterval(()=>{if(!document.hidden&&$('#modal').open)refreshRunTelemetry($('#run-telemetry-body')?.dataset.runId);},10000);
$('#modal-content').addEventListener('change',event=>{const id=event.target.dataset.runMetric;if(id){runMetricChoices.set(id,event.target.value);$('#run-telemetry-body').innerHTML=runTelemetryPanel(id);}});
setInterval(()=>{if(state.view==='settings')refreshAccountModels();},15000);
window.addEventListener('supersurfer-theme',()=>{
 const appearance=$('.appearance-block');
 if(appearance){appearance.outerHTML=renderAppearance();$('#vscode-theme')?.addEventListener('change',event=>{if(event.target.value)window.superSurferTheme?.setPreference(event.target.value);});}
 if(state.view==='workspace'&&pageHasTile('results')&&!state.edit&&!$('#modal').open)renderMain();
});
window.addEventListener('focus',syncClientTimezone);
window.addEventListener('beforeunload',stashEditor);

document.addEventListener('keydown',event=>{if(!event.defaultPrevented&&(event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='p'&&!event.shiftKey&&project()&&!document.querySelector('dialog[open]')){event.preventDefault();pickWorkspaceFile(path=>openPageCode({path}));}});

const taskContextMenu=document.createElement('div');taskContextMenu.className='task-context-menu';taskContextMenu.setAttribute('role','menu');taskContextMenu.hidden=true;document.body.append(taskContextMenu);
function closeTaskContextMenu(){taskContextMenu.hidden=true;}
let reportDrag=null;
async function manageReports(experimentId,fields,version){
 if(readOnly())return;
 if(state.experimentId===experimentId&&!resultSelections.has(experimentId))resultSelections.set(experimentId,chosenResultPage()?.id||'metrics');
 if(fields.archived===true&&resultSelections.get(experimentId)===fields.result_id)resultSelections.set(experimentId,resultPages.get(experimentId)?.pages.find(page=>page.id!==fields.result_id)?.id||'metrics');
 try{await action('experiment.results.manage',{experiment_id:experimentId,version,...fields});if(state.experimentId===experimentId)await loadResultPages(true);else resultPages.delete(experimentId);}
 catch(error){toast(error.message,true);if(state.experimentId===experimentId)await loadResultPages(true);}
}
function showReportOptions(button,id){
 const experimentId=state.experimentId,entry=resultPages.get(experimentId),pages=entry?.pages||[],index=pages.findIndex(p=>p.id===id);if(index<0)return;
 closeTaskContextMenu();taskContextMenu.innerHTML=`<button role="menuitem" data-report-move="-1" ${readOnly()||index===0?'disabled':''}>Move earlier</button><button role="menuitem" data-report-move="1" ${readOnly()||index===pages.length-1?'disabled':''}>Move later</button><button role="menuitem" data-report-remove ${readOnly()?'disabled':''}>Remove report</button>`;
 taskContextMenu.querySelector('[data-report-remove]').onclick=()=>{closeTaskContextMenu();void manageReports(experimentId,{result_id:id,archived:true},entry.version);};
 for(const move of taskContextMenu.querySelectorAll('[data-report-move]'))move.onclick=()=>{closeTaskContextMenu();const order=pages.map(p=>p.id),target=index+Number(move.dataset.reportMove);[order[index],order[target]]=[order[target],order[index]];void manageReports(experimentId,{order},entry.version);};
 taskContextMenu.hidden=false;const rect=button.getBoundingClientRect();taskContextMenu.style.left=Math.max(4,Math.min(innerWidth-taskContextMenu.offsetWidth-4,rect.left))+'px';taskContextMenu.style.top=Math.max(4,Math.min(innerHeight-taskContextMenu.offsetHeight-4,rect.bottom))+'px';taskContextMenu.querySelector('button:not(:disabled)')?.focus({preventScroll:true});
}
document.addEventListener('click',event=>{const options=event.target.closest('[data-result-options]'),restore=event.target.closest('[data-restore-result]');if(!options&&!restore)return;event.preventDefault();event.stopImmediatePropagation();if(options)showReportOptions(options,options.dataset.resultOptions);else if(!restore.disabled)void manageReports(state.experimentId,{result_id:restore.dataset.restoreResult,archived:false},resultPages.get(state.experimentId)?.version);},true);
document.addEventListener('contextmenu',event=>{const tab=event.target.closest('[data-result-tab]');if(!tab)return;event.preventDefault();event.stopImmediatePropagation();showReportOptions(tab,tab.dataset.resultTab);},true);
document.addEventListener('dragstart',event=>{const tab=event.target.closest('[data-result-tab]');if(!tab||readOnly())return;const entry=resultPages.get(state.experimentId);reportDrag={id:tab.dataset.resultTab,experimentId:state.experimentId,version:entry.version,order:entry.pages.map(p=>p.id)};event.dataTransfer.setData('application/x-supersurfer-report',reportDrag.id);event.dataTransfer.effectAllowed='move';event.stopImmediatePropagation();},true);
document.addEventListener('dragover',event=>{if(reportDrag&&reportDrag.experimentId===state.experimentId&&event.target.closest('[data-result-tab]')){event.preventDefault();event.dataTransfer.dropEffect='move';}},true);
document.addEventListener('drop',event=>{const target=event.target.closest('[data-result-tab]'),drag=reportDrag;reportDrag=null;if(!target||!drag||drag.experimentId!==state.experimentId)return;event.preventDefault();event.stopImmediatePropagation();if(target.dataset.resultTab===drag.id)return;const order=drag.order.filter(id=>id!==drag.id),index=order.indexOf(target.dataset.resultTab);if(index<0)return;order.splice(index,0,drag.id);void manageReports(drag.experimentId,{order},drag.version);},true);
document.addEventListener('dragend',()=>{reportDrag=null;});
function showPageOptions(button,id){
 if(!state.projectId||id==='surfboard'||panelWindows.detached)return;
 const scope={project_id:state.projectId,experiment_id:state.experimentId},hidden=hiddenViewTabs(),documents=state.experiment?.pages||[];
 const title=currentPages()?.find(page=>page.id===id)?.title||documents.find(page=>'page:'+page.id===id)?.title||({'_todos':'To-dos','_files':'File viewer'})[id]||id;
 closeTaskContextMenu();
 taskContextMenu.innerHTML=`<button type="button" role="menuitem" data-remove-page ${readOnly()?'disabled':''}>Remove page</button>${hidden.map(tab=>`<button type="button" role="menuitem" data-restore-tab="${e(tab)}" ${readOnly()?'disabled':''}>Restore ${e(documents.find(page=>'page:'+page.id===tab)?.title||({'_todos':'To-dos','_files':'File viewer'})[tab]||tab)}</button>`).join('')}`;
 taskContextMenu.querySelector('[data-remove-page]').onclick=()=>{closeTaskContextMenu();void removeViewPage(scope,id,title);};
 for(const restore of taskContextMenu.querySelectorAll('[data-restore-tab]'))restore.onclick=()=>{closeTaskContextMenu();void action('view-tab.hide',{...scope,tab:restore.dataset.restoreTab,hidden:false}).then(()=>refreshState(true)).catch(error=>toast(error.message,true));};
 taskContextMenu.hidden=false;const rect=button.getBoundingClientRect();taskContextMenu.style.left=Math.max(4,Math.min(innerWidth-taskContextMenu.offsetWidth-4,rect.left))+'px';taskContextMenu.style.top=Math.max(4,Math.min(innerHeight-taskContextMenu.offsetHeight-4,rect.bottom))+'px';taskContextMenu.querySelector('button').focus({preventScroll:true});
}
async function removeViewPage(scope,id,title){
 if(readOnly())return;
 if(tileLayout.editing()||tileLayout.saving()){toast('Finish saving or cancel Rearrange before removing a page.',true);return;}
 const record=await api('view-layout?'+new URLSearchParams({project_id:scope.project_id,...(scope.experiment_id?{experiment_id:scope.experiment_id}:{})})).catch(error=>{toast(error.message,true);return null;});if(!record)return;
 const page=record.pages.find(page=>page.id===id),utility=id.startsWith('page:')||['_todos','_files'].includes(id);
 if(!page&&!utility){toast('This page has already changed. Refresh and try again.',true);return;}
 openModal('Remove “'+title+'”?',`<p class="modal-description">Remove this page from this ${scope.experiment_id?'task':'project'} only. Files, notes, results, conversations and running work are kept.</p><form>${formFooter('Remove page')}</form>`,'remove-page');
 bindModalForm(async()=>{
  if(utility)await action('view-tab.hide',{...scope,tab:id,hidden:true});
  else await action('view-layout.save',{...scope,version:record.version,board_version:record.board_version,pages:record.pages.filter(row=>row.id!==id)});
  closeModal();if(state.projectId===scope.project_id&&state.experimentId===scope.experiment_id){if(state.tab===id)state.tab=record.pages.find(row=>row.id!==id)?.id||'empty-layout';persistNavigation();await refreshState(true);}
  toast('Page removed. Its content is kept.');
 });
}
document.addEventListener('click',event=>{const button=event.target.closest('[data-page-options]');if(!button)return;event.preventDefault();event.stopImmediatePropagation();showPageOptions(button,button.dataset.pageOptions);},true);
document.addEventListener('contextmenu',event=>{const button=event.target.closest('.page-tab [data-tab]');if(!button)return;event.preventDefault();event.stopImmediatePropagation();showPageOptions(button,button.dataset.tab);},true);
document.addEventListener('contextmenu',event=>{
 const row=event.target.closest('[data-experiment],.project-row[data-project]'),isProject=!!row?.dataset.project,item=isProject?state.data?.projects.find(item=>item.id===row.dataset.project):state.data?.experiments.find(item=>item.id===row?.dataset.experiment);
 if(!item)return;event.preventDefault();
 taskContextMenu.innerHTML=`${!isProject?`<button type="button" role="menuitem" data-rename-task ${readOnly()?'disabled':''}>Rename task…</button>`:''}<button type="button" role="menuitem" data-archive-task ${readOnly()?'disabled':''}>${item.archived?'Restore':'Archive'} ${isProject?'project':'task'}</button>`;
 const rename=taskContextMenu.querySelector('[data-rename-task]');if(rename)rename.onclick=()=>{closeTaskContextMenu();renameTask(item.id).catch(error=>toast(error.message,true));};
 taskContextMenu.querySelector('[data-archive-task]').onclick=()=>{closeTaskContextMenu();(isProject?archiveProject:archiveTask)(item.id,!item.archived).catch(error=>toast(error.message,true));};
 taskContextMenu.hidden=false;const bounds=row.getBoundingClientRect();taskContextMenu.style.left=Math.max(4,Math.min(innerWidth-taskContextMenu.offsetWidth-4,event.clientX||bounds.left+12))+'px';taskContextMenu.style.top=Math.max(4,Math.min(innerHeight-taskContextMenu.offsetHeight-4,event.clientY||bounds.bottom))+'px';taskContextMenu.querySelector('button:not(:disabled)')?.focus({preventScroll:true});
});

document.addEventListener('pointerdown',event=>{if(!taskContextMenu.contains(event.target))closeTaskContextMenu();});document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!taskContextMenu.hidden){event.preventDefault();closeTaskContextMenu();}});document.addEventListener('scroll',closeTaskContextMenu,true);window.addEventListener('resize',closeTaskContextMenu);
$('#project-tree').addEventListener('toggle',event=>{const id=event.target.dataset.archivedProject;if(!id||event.target.open===archivedItemProjects.has(id))return;if(event.target.open)archivedItemProjects.add(id);else archivedItemProjects.delete(id);state.sidebarSignature='';},true);

$('#project-tree').addEventListener('toggle',event=>{if(!event.target.classList.contains('archived-project-folder')||event.target.open===archivedProjectsExpanded)return;archivedProjectsExpanded=event.target.open;state.sidebarSignature='';},true);

function chooseReusableBlock(){return new Promise(async resolve=>{try{const data=await api('view-blocks');if(!data.blocks.length){toast('Ask an agent to publish a custom HTML block first.');resolve(null);return;}openModal('Reusable blocks',`<p class=modal-description>Published views persist in this workspace. Adding one does not change agent permissions.</p><div class=block-library>${data.blocks.map(block=>`<button class=button data-pick-block="${e(block.id)}">${e(block.title)} <small>v${block.version}</small></button>`).join('')}</div>`,'blocks');const dialog=$('#modal');const done=()=>resolve(null);dialog.addEventListener('close',done,{once:true});for(const button of $$('[data-pick-block]',dialog))button.onclick=()=>{dialog.removeEventListener('close',done);resolve(button.dataset.pickBlock);closeModal();};}catch(error){toast(error.message,true);resolve(null);}});}

{
 const handle=$('#workspace-files-divider'),section=$('#workspace-files-section');let drag=null;
 const resize=height=>{const bounds=filesHeightBounds();state.filesHeight=Math.round(Math.max(bounds.min,Math.min(bounds.max,height)));applyProjectTreeHeight();};
 handle.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();drag={y:event.clientY,height:section.getBoundingClientRect().height};handle.setPointerCapture(event.pointerId);document.body.classList.add('resizing-files');});
 handle.addEventListener('pointermove',event=>{if(drag)resize(drag.height+event.clientY-drag.y);});
 const finish=()=>{if(!drag)return;drag=null;document.body.classList.remove('resizing-files');persistNavigation();};
 for(const name of ['pointerup','pointercancel','lostpointercapture'])handle.addEventListener(name,finish);
 handle.addEventListener('keydown',event=>{if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key))return;event.preventDefault();const bounds=filesHeightBounds(),height=section.getBoundingClientRect().height;resize(event.key==='Home'?bounds.min:event.key==='End'?bounds.max:height+(event.key==='ArrowUp'?-20:20));persistNavigation();});
 handle.addEventListener('dblclick',()=>{state.filesHeight=null;applyProjectTreeHeight();persistNavigation();});
 section.addEventListener('toggle',applyProjectTreeHeight);
}
