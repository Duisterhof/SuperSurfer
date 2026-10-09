/* Separate views never save a source buffer or overwrite main-window navigation. */
import {ensureDockLayout,pruneDock} from './dock-layout.js';
const identifier=value=>typeof value==='string'&&/^[A-Za-z0-9_:-]{1,128}$/.test(value);
export function createPanelWindows(options){
 const moved=new Map();
 const scopeKey=fields=>[fields.project,fields.item||'',fields.page,fields.tile].join('\u001f');
 const restore=key=>{const row=moved.get(key);if(!row)return;clearInterval(row.timer);moved.delete(key);document.body.classList.add('panel-reflow');setTimeout(()=>document.body.classList.remove('panel-reflow'),250);options.onChange?.();};
 window.superSurferDesktop?.onPanelClosed?.(message=>{for(const [key,row] of moved)if(row.id===message.id)restore(key);});
 const query=new URLSearchParams(location.search),detached=query.has('panel_tile');
 const navigation=detached?{view:'workspace',projectId:query.get('panel_project'),experimentId:query.get('panel_item')||null,tab:query.get('panel_page'),chatVisible:false,chatMaximized:false,sidebarCollapsed:true}:null;
 if(!detached)window.superSurferDesktop?.listPanels?.().then(rows=>{for(const row of rows)moved.set(scopeKey(row),{id:row.id});if(rows.length)document.body.classList.add('panel-reflow');setTimeout(()=>document.body.classList.remove('panel-reflow'),250);options.onChange?.();}).catch(()=>{});
 if(detached){
  if(!sessionStorage.getItem('supersurfer-panel-client')){sessionStorage.setItem('supersurfer-editor-window',Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join(''));sessionStorage.setItem('supersurfer-panel-client','1');}
  document.body.classList.add('detached-panel');
  const button=document.createElement('button');button.className='panel-return';button.textContent='Close window';button.onclick=()=>window.close();document.querySelector('.topbar').append(button);
 }
 document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-panel-window]');if(!button||detached)return;
  event.preventDefault();event.stopImmediatePropagation();button.disabled=true;
  try{
   const scope=options.capture(),tile=button.closest('[data-live-tile]');
   if(!tile)throw new Error('Open this panel on a task page first.');
   let presentation={};if(['editor','vscode'].includes(tile.dataset.tileKind)){presentation=options.presentation?.(tile.dataset.tileKind)||{};
    await options.prepareEditor?.(tile.dataset.tileKind);
    if(options.hasUnsaved(tile.dataset.tileKind))throw new Error('Save your editor changes before opening its separate window. Your draft is kept.');
   }
   const fields={project:scope.projectId,item:scope.experimentId||'',page:scope.page,tile:tile.dataset.tileId,path:presentation.path||'',title:tile.querySelector('.editor-panel-actions>strong,.page-tile-heading>span')?.textContent||'Panel'};
   if(![fields.project,fields.page,fields.tile].every(identifier)||fields.item&&!identifier(fields.item))throw new Error('Choose a saved project page before detaching this panel.');
   const key=scopeKey(fields);if(moved.has(key))return;
   if(window.superSurferDesktop?.openPanel){const opened=await window.superSurferDesktop.openPanel(fields);moved.set(key,{id:opened.id});}
   else{
    const url=new URL('/',location.href);for(const name of ['project','item','page','tile','path'])url.searchParams.set('panel_'+name,fields[name]);
    const popup=window.open(url.href,'supersurfer-panel-'+crypto.randomUUID(),'popup,width=900,height=700');
    if(!popup)throw new Error('Allow popups for this workspace to open a separate panel window.');
    moved.set(key,{popup,timer:setInterval(()=>{if(popup.closed)restore(key);},300)});
   }
   document.body.classList.add('panel-reflow');setTimeout(()=>document.body.classList.remove('panel-reflow'),250);options.onChange?.();
  }catch(error){options.onError(error);}finally{button.disabled=false;}
 },true);
 return {detached,navigation,path:query.get('panel_path'),page(page){if(!page)return page;if(!detached){const scope=options.capture(),hidden=new Set(page.tiles.filter(tile=>moved.has(scopeKey({project:scope.projectId,item:scope.experimentId,page:page.id,tile:tile.id}))).map(tile=>tile.id));if(!hidden.size)return page;const result=structuredClone(page);ensureDockLayout(result);result.tiles=result.tiles.filter(tile=>!hidden.has(tile.id));result.layout=pruneDock(result.layout,new Set(result.tiles.filter(tile=>(tile.placement||'main')==='main').map(tile=>tile.id)))||{empty:true};result.arrangement='docked';return result;}const tile=page.tiles.find(row=>row.id===query.get('panel_tile'));return {...page,layout:tile?{tile:tile.id}:{empty:true},arrangement:'docked',tiles:tile?[{...tile,span:12,placement:'main'}]:[]};}};
}
