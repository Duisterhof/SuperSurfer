/* Separate views never save a source buffer or overwrite main-window navigation. */
const identifier=value=>typeof value==='string'&&/^[A-Za-z0-9_:-]{1,128}$/.test(value);
export function createPanelWindows(options){
 const query=new URLSearchParams(location.search),detached=query.has('panel_tile');
 const navigation=detached?{view:'workspace',projectId:query.get('panel_project'),experimentId:query.get('panel_item')||null,tab:query.get('panel_page'),chatVisible:false,chatMaximized:false,sidebarCollapsed:true}:null;
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
   let presentation={};if(tile.dataset.tileKind==='editor'){presentation=options.presentation?.()||{};
    await options.prepareEditor?.();
    if(options.hasUnsaved())throw new Error('Save your editor changes before opening its separate window. Your draft is kept.');
   }
   const fields={project:scope.projectId,item:scope.experimentId||'',page:scope.page,tile:tile.dataset.tileId,path:presentation.path||'',title:tile.querySelector('.page-tile-heading>span')?.textContent||'Panel'};
   if(![fields.project,fields.page,fields.tile].every(identifier)||fields.item&&!identifier(fields.item))throw new Error('Choose a saved project page before detaching this panel.');
   if(window.superSurferDesktop?.openPanel)await window.superSurferDesktop.openPanel(fields);
   else{
    const url=new URL('/',location.href);for(const name of ['project','item','page','tile','path'])url.searchParams.set('panel_'+name,fields[name]);
    const popup=window.open(url.href,'supersurfer-panel-'+crypto.randomUUID(),'popup,width=900,height=700');
    if(!popup)throw new Error('Allow popups for this workspace to open a separate panel window.');
   }
  }catch(error){options.onError(error);}finally{button.disabled=false;}
 },true);
 return {detached,navigation,path:query.get('panel_path'),page(page){if(!page||!detached)return page;const tile=page.tiles.find(row=>row.id===query.get('panel_tile'));return {...page,arrangement:'docked',tiles:tile?[{...tile,span:12,placement:'main'}]:[]};}};
}
