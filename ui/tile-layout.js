import {ensureDockLayout,dockNode,replaceDock,dockRects,dockMinimum,dropDock,reserveDockSpace,renderDockLayout,dockLeaves} from './dock-layout.js';
// Direct manipulation saves presentation through the version-checked layout API.
// Arrange mode keeps an explicit draft; source buffers are never saved.
const copy=value=>structuredClone(value);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clamp=(value,min,max)=>Math.max(min,Math.min(max,Math.round(value)));
const place=tile=>tile.placement||'main';
export function createTileLayout(options){
 const drafts=new Map();let dragging=null,resizing=null,windowMove=null,splitResize=null;
 const key=()=>options.key(),draft=()=>drafts.get(key());
 const enabled=()=>!!draft()&&!draft().saving&&!options.readOnly();
 const changed=()=>{options.render();};
 function start(automatic=false){const page=options.page();if(options.readOnly()||draft()?.saving)return;if(!page){options.configure?.();return;}if(!draft()){drafts.set(key(),{base:copy(page),page:copy(page),automatic,error:''});ensureDockLayout(draft().page);}else if(!automatic)draft().automatic=false;if(!automatic)changed();}
 function cancel(){if(draft()?.saving)return;drafts.delete(key());changed();}
 function tile(id){return draft()?.page.tiles.find(row=>row.id===id);}
 function move(id,placement,before){if(!enabled())return;const row=tile(id);if(!row||id===before)return;row.placement=placement;const rows=draft().page.tiles.filter(item=>item!==row),index=rows.findIndex(item=>item.id===before);rows.splice(index<0?rows.length:index,0,row);draft().page.tiles=rows;changed();}
 function add(kind,placement='main',before){
  if(!enabled())return;const page=draft().page;if(page.tiles.length>=16||page.tiles.some(row=>row.kind===kind)||!options.catalog().some(row=>row.kind===kind))return;
  const row={id:'tile_'+crypto.randomUUID().replaceAll('-','').slice(0,12),kind,span:kind==='file_explorer'?3:6,height:kind==='pdf'?600:400,placement};page.tiles.push(row);move(row.id,placement,before);
 }
 async function addHtml(placement='main'){const scope=key(),blockId=await options.chooseBlock?.();if(!blockId||key()!==scope)return;if(!draft())start(true);if(!enabled())return;const page=draft().page;if(page.tiles.length>=16)return;page.tiles.push({id:'tile_'+crypto.randomUUID().replaceAll('-','').slice(0,12),kind:'html',block_id:blockId,span:6,height:400,placement});if(draft().automatic)await save();else changed();}
 async function save(){
  if(!enabled())return;const id=key(),value=draft(),baseline=copy(value.base);ensureDockLayout(baseline);if(JSON.stringify(baseline)===JSON.stringify(value.page)){drafts.delete(id);changed();return;}value.saving=true;value.error='';changed();
  try{await options.save(copy(value.page),copy(value.base));drafts.delete(id);}
  catch(error){value.error=error.message;value.saving=false;value.automatic=false;}
  changed();
 }
 async function remove(id){
  if(options.readOnly()||draft()?.saving)return;
  if(!draft())start(true);if(!enabled())return;
  const value=draft();value.page.tiles=value.page.tiles.filter(row=>row.id!==id);
  ensureDockLayout(value.page);
  if(value.automatic)await save();else changed();
 }
 function toolbar(){const value=draft();if(!value||value.automatic)return '';const disabled=value.saving||options.readOnly();
  return `<div class="tile-arrange-toolbar"><span class="arrange-label">Rearrange · ${esc(value.page.title)}</span><button class="button small-button" data-tile-command="cancel" ${disabled?'disabled':''}>Cancel</button><button class="button small-button primary" data-tile-command="save" ${disabled?'disabled':''}>${value.saving?'Saving…':'Done'}</button>${value.error?`<p class="notice error arrange-error" role="alert">${esc(value.error)} Your layout draft is kept.</p>`:''}</div>`;
 }
 function controls(row,label){
    const compact=['editor','pdf','vscode','terminal','ports'].includes(row.kind);
    const floating=(draft()?.page||options.page())?.arrangement==='windows'&&place(row)==='main';
    const grip=`<button type="button" class="tile-grip" ${floating?'data-window-drag':'data-tile-grip'}="${esc(row.id)}" draggable="${!floating&&!options.readOnly()}" aria-label="Move ${esc(label)}" title="Drag to move or split panels" ${options.readOnly()||draft()?.saving?'disabled':''}>⠿</button>`;
    const space=`<details class="tile-space-menu"><summary title="Panel actions">⋯</summary><div>${[['left','Space on left'],['right','Space on right'],['top','Space above'],['bottom','Space below']].map(([edge,label])=>`<button type="button" data-tile-space="${esc(row.id)}" data-space-edge="${edge}">${label}</button>`).join('')}${compact?'':`<button type="button" data-tile-remove="${esc(row.id)}" ${options.readOnly()||draft()?.saving?'disabled':''}>Remove block</button>`}</div></details>`;
    const windowButton=`<button type="button" data-panel-window="${esc(row.id)}" aria-label="Open ${esc(label)} in a separate window" title="Open in separate window">↗</button>`;

  if(compact){
    const actions=row.kind==='pdf'?[['compile','Compile'],['stop','Stop compile'],['auto','Auto compile'],['options','Build options'],['history','Build history'],['logs','Compiler details'],['refresh','Refresh']]:['terminal','ports'].includes(row.kind)?[]:[['save','Save'],['files','Files'],['changes','Changes'],['open','Open file…'],['upload','Upload…'],['new-file','New file'],['new-folder','New folder'],['extensions','Extensions'],['theme','Theme'],['selection','Add selection to chat']];
    return `<details class="editor-panel-handle"><summary ${floating?'data-window-drag':'data-tile-grip'}="${esc(row.id)}" draggable="${!floating&&!options.readOnly()}" aria-label="Move ${esc(label)}" title="Drag to move or snap. Click for panel actions.">⠿</summary><div class="editor-panel-actions"><strong>${esc(label)}</strong><code class="editor-panel-path"></code>${actions.map(([kind,text])=>`<button type="button" data-editor-panel-command="${kind}" data-editor-panel-kind="${row.kind}">${text}</button>`).join('')}${space}${windowButton}<button type="button" data-panel-fullscreen>Full screen</button><button type="button" data-tile-remove="${esc(row.id)}" ${options.readOnly()||draft()?.saving?'disabled':''}>Remove block</button>${draft()&&!draft().automatic?`<select data-tile-placement="${esc(row.id)}" aria-label="Place ${esc(label)}">${[['main','Page'],['left','Left sidebar'],['right','Right sidebar']].map(([value,text])=>`<option value="${value}" ${place(row)===value?'selected':''}>${text}</option>`).join('')}</select>`:''}</div></details>`;
  }
  if(!draft()||draft().automatic)return `${grip}<span ${floating?`data-window-drag="${esc(row.id)}"`:""}>${esc(label)}</span>${space}${windowButton}<button type="button" data-panel-fullscreen aria-label="Full screen" title="Full screen">⤢</button>`;
  const disabled=!enabled();
  return `${grip}<span>${esc(label)}</span>${space}${windowButton}<select data-tile-placement="${esc(row.id)}" aria-label="Place ${esc(label)}" ${disabled?'disabled':''}>${[['main','Page'],['left','Left sidebar'],['right','Right sidebar']].map(([value,text])=>`<option value="${value}" ${place(row)===value?'selected':''}>${text}</option>`).join('')}</select><button type="button" data-tile-up="${esc(row.id)}" title="Move earlier" aria-label="Move ${esc(label)} earlier" ${disabled?'disabled':''}>↑</button><button type="button" data-tile-remove="${esc(row.id)}" title="Remove tile; keep its content" aria-label="Remove ${esc(label)} tile" ${disabled?'disabled':''}>×</button>`;
 }
 function decorate(element,row,label){
  const header=element.querySelector('.page-tile-heading'),html=controls(row,label);if(header.innerHTML!==html)header.innerHTML=html;
  let handle=element.querySelector('.tile-resize');
  if(!handle){handle=document.createElement('button');handle.type='button';handle.className='tile-resize';handle.dataset.tileResize=row.id;handle.setAttribute('aria-label','Resize '+label);handle.title='Drag to resize. Left/Right change width; Up/Down change height.';element.append(handle);}
  if(handle)handle.disabled=options.readOnly()||!!draft()?.saving;
  for(const axis of ['x','y']){
   let edge=element.querySelector('.tile-edge-'+axis);
   if(!edge){edge=document.createElement('button');edge.type='button';edge.className='tile-edge tile-edge-'+axis;edge.dataset.tileResize=row.id;edge.dataset.resizeAxis=axis;edge.setAttribute('role','separator');edge.setAttribute('aria-orientation',axis==='x'?'vertical':'horizontal');edge.setAttribute('aria-label','Resize '+label+' '+(axis==='x'?'width':'height'));edge.title='Drag to resize '+label+'; arrow keys also work';element.append(edge);}
   edge.disabled=options.readOnly()||!!draft()?.saving;
  }
  element.dataset.tilePlacement=place(row);
 }
 function applySize(row,dx,dy,base,width){
  if((draft()?.page||options.page())?.arrangement==='windows'&&place(row)==='main'){
      row.bounds={...base.bounds,width:clamp(base.bounds.width+dx,200,5000),height:clamp(base.bounds.height+dy,160,5000)};row.height=row.bounds.height;return;
    }
    row.height=clamp(base.height+dy,160,5000);
  if(place(row)==='main'&&dx)row.span=Math.max(1,Math.min(12,base.span+dx/(width/12)));else if(place(row)==='main')row.span=base.span;
  else if(dx) {const field=place(row)==='left'?'left_width':'right_width',direction=place(row)==='left'?1:-1;draft().page[field]=clamp(base.width+direction*dx,place(row)==='left'?160:280,place(row)==='left'?600:760);}
 }
 document.addEventListener('click',event=>{const handle=event.target.closest('.editor-panel-handle>summary');if(handle){const panel=handle.closest('[data-live-tile]');handle.parentElement.querySelector('.editor-panel-path').textContent=panel.querySelector('.workbench-toolbar code,.code-location code')?.textContent||'';}});
 document.addEventListener('click',event=>{
  const button=event.target.closest('[data-editor-panel-command],[data-tile-command],[data-add-tile],[data-tile-remove],[data-tile-up],[data-tile-space],[data-dock-close]');if(!button||button.disabled)return;event.preventDefault();event.stopImmediatePropagation();
  if(button.dataset.editorPanelCommand){options.editorCommand?.(button.dataset.editorPanelCommand,button.dataset.editorPanelKind);button.closest('details').open=false;return;}
  if(button.hasAttribute('data-dock-close')){if(!draft())start(true);if(enabled()){const path=button.dataset.dockClose,parts=path.split('.'),side=parts.pop(),parentPath=parts.join('.'),parent=dockNode(draft().page.layout,parentPath);if(parent?.axis)draft().page.layout=replaceDock(draft().page.layout,parentPath,parent[side==='first'?'second':'first']);if(draft().automatic)void save();else changed();}return;}
  if(button.dataset.tileSpace){if(!draft())start(true);if(enabled()){reserveDockSpace(draft().page,button.dataset.tileSpace,button.dataset.spaceEdge);if(draft().automatic)void save();else changed();}return;}
  const command=button.dataset.tileCommand;if(command==='start')start();if(command==='pages'||command==='workflow'||command==='addpage'){void(async()=>{if(draft()){await save();if(draft())return;}if(command==='workflow')options.workflow?.();else options.configure?.({addPage:command==='addpage'});})();return;}if(command==='windows'||command==='docked'){
      if(!draft())start(true);if(enabled()){const page=draft().page;page.arrangement=command;
      if(command==='windows')for(const row of page.tiles){if(place(row)!=='main'||row.bounds)continue;const element=[...document.querySelectorAll('[data-live-tile]')].find(el=>el.dataset.tileId===row.id),area=element?.parentElement,a=area?.getBoundingClientRect(),r=element?.getBoundingClientRect();row.bounds={x:Math.max(0,Math.round((r?.left||0)-(a?.left||0))),y:Math.max(0,Math.round((r?.top||0)-(a?.top||0))),width:Math.max(200,Math.round(r?.width||500)),height:Math.max(160,Math.round(r?.height||row.height))};}
      options.resize?.(page);if(draft().automatic)void save();else changed();}}
if(command==='files-left'){start();if(enabled()){const existing=draft().page.tiles.find(row=>row.kind==='file_explorer');if(existing)move(existing.id,'left');else add('file_explorer','left');}}if(command==='cancel')cancel();if(command==='save')void save();
  if(button.dataset.addTile==='html'){void addHtml();return;}if(button.dataset.addTile){if(!draft())start(true);add(button.dataset.addTile);if(draft()?.automatic)void save();}
  if(button.dataset.tileRemove)void remove(button.dataset.tileRemove);
  if(enabled()&&button.dataset.tileUp){const row=tile(button.dataset.tileUp),rows=draft().page.tiles.filter(item=>place(item)===place(row)),i=rows.indexOf(row);if(i>0)move(row.id,place(row),rows[i-1].id);}
 },true);
 document.addEventListener('change',event=>{const id=event.target.dataset.tilePlacement;if(id&&enabled()){event.stopImmediatePropagation();move(id,event.target.value);}},true);
 document.addEventListener('dragstart',event=>{
  const handle=event.target.closest('[data-tile-grip],[data-add-tile]');if(!handle||handle.disabled)return;if(handle.dataset.addTile==='html'){event.preventDefault();return;}if(!draft())start(true);if(!enabled())return;
  dragging={key:key(),id:handle.dataset.tileGrip,kind:handle.dataset.addTile};event.dataTransfer.setData('application/x-supersurfer-tile',JSON.stringify(dragging));event.dataTransfer.effectAllowed=dragging.id?'move':'copy';document.body.classList.add('dragging-page-tile');document.querySelectorAll('[data-tile-drop]').forEach(area=>area.hidden=false);event.stopPropagation();
 });
 document.addEventListener('dragover',event=>{if(!dragging||dragging.key!==key()||!enabled())return;const area=event.target.closest('[data-tile-drop]');if(!area)return;event.preventDefault();event.dataTransfer.dropEffect=dragging.id?'move':'copy';document.querySelectorAll('.tile-drop-active').forEach(el=>el.classList.remove('tile-drop-active'));area.classList.add('tile-drop-active');});
 function endDrag(){document.querySelector('.dock-drop-preview')?.remove();if(dragging&&draft()?.automatic&&JSON.stringify(draft().base)===JSON.stringify(draft().page))drafts.delete(key());dragging=null;document.body.classList.remove('dragging-page-tile');document.querySelectorAll('.tile-drop-active').forEach(el=>el.classList.remove('tile-drop-active'));}
 document.addEventListener('drop',event=>{
  if(!dragging||dragging.key!==key()||!enabled())return;const area=event.target.closest('[data-tile-drop]');if(!area)return;event.preventDefault();event.stopImmediatePropagation();
  const target=event.target.closest('[data-tile-id]'),before=target?.dataset.tileId,empty=event.target.closest('[data-dock-empty]');
  if(area.dataset.tileDrop==='main'&&draft().page.arrangement!=='windows'){
   const rect=target?.getBoundingClientRect();let row=dragging.id?tile(dragging.id):null;if(!row&&draft().page.tiles.length<16&&!draft().page.tiles.some(row=>row.kind===dragging.kind)&&options.catalog().some(row=>row.kind===dragging.kind)){row={id:'tile_'+crypto.randomUUID().replaceAll('-','').slice(0,12),kind:dragging.kind,span:6,height:400};draft().page.tiles.push(row);}if(row){row.placement='main';const dx=rect?(event.clientX-rect.left)/rect.width:.75,dy=rect?(event.clientY-rect.top)/rect.height:.5,edge=Math.min(dx,1-dx)<Math.min(dy,1-dy)?dx<.5?'left':'right':dy<.5?'top':'bottom';dropDock(draft().page,row.id,empty?{empty:true,path:empty.dataset.dockEmpty}:before?{tile:before}:null,edge);options.render();}endDrag();if(draft()?.automatic)void save();return;
  }
  if(dragging.id){
    const row=tile(dragging.id),other=tile(before);let order=before;
    if(area.dataset.tileDrop==='main'&&other&&other!==row&&draft().page.arrangement!=='windows'){
      const rect=target.getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width,y=(event.clientY-rect.top)/rect.height;
      if(x<.25||x>.75){const total=Math.min(12,other.span+row.span);row.span=other.span=total/2;if(x>.75)order=draft().page.tiles[draft().page.tiles.indexOf(other)+1]?.id;}
      else{row.span=other.span=12;if(y>.5)order=draft().page.tiles[draft().page.tiles.indexOf(other)+1]?.id;}
    }move(dragging.id,area.dataset.tileDrop,order);
   }else add(dragging.kind,area.dataset.tileDrop,before);endDrag();if(draft()?.automatic)void save();
 },true);
 document.addEventListener('dragend',endDrag);
 document.addEventListener('dragover',event=>{if(!dragging)return;const target=event.target.closest('[data-live-tile],[data-dock-empty]');if(!target||!target.closest('.dock-canvas')){document.querySelector('.dock-drop-preview')?.remove();return;}const r=target.getBoundingClientRect(),dx=(event.clientX-r.left)/r.width,dy=(event.clientY-r.top)/r.height,edge=Math.min(dx,1-dx)<Math.min(dy,1-dy)?dx<.5?'left':'right':dy<.5?'top':'bottom';let box={left:r.left,top:r.top,width:r.width,height:r.height};if(!target.hasAttribute('data-dock-empty')){if(['left','right'].includes(edge)){box.width/=2;if(edge==='right')box.left+=box.width;}else{box.height/=2;if(edge==='bottom')box.top+=box.height;}}let overlay=document.querySelector('.dock-drop-preview');if(!overlay){overlay=document.createElement('div');overlay.className='dock-drop-preview';document.body.append(overlay);}Object.assign(overlay.style,Object.fromEntries(Object.entries(box).map(([k,v])=>[k,v+'px'])));});
 function visibleSplitSource(tree,node,visible){
  if(!tree?.axis)return null;
  const signature=value=>dockLeaves(value).filter(id=>visible.has(id)).sort().join('|');
  if(tree.axis===node.axis&&signature(tree)===signature(node)&&signature(tree.first)&&signature(tree.second))return tree;
  return visibleSplitSource(tree.first,node,visible)||visibleSplitSource(tree.second,node,visible);
 }
 function windowSnap(event,row){
  const target=document.elementsFromPoint(event.clientX,event.clientY).map(el=>el.closest('[data-live-tile]')).find(el=>el&&el.dataset.tileId!==row.id&&el.closest('.window-canvas'));
  if(!target){document.querySelector('.dock-drop-preview')?.remove();return null;}
  const r=target.getBoundingClientRect(),dx=(event.clientX-r.left)/r.width,dy=(event.clientY-r.top)/r.height;
  if(dx<0||dx>1||dy<0||dy>1||Math.min(dx,1-dx,dy,1-dy)>.22){document.querySelector('.dock-drop-preview')?.remove();return null;}
  const edge=Math.min(dx,1-dx)<Math.min(dy,1-dy)?dx<.5?'left':'right':dy<.5?'top':'bottom';
  let preview=document.querySelector('.dock-drop-preview');if(!preview){preview=document.createElement('div');preview.className='dock-drop-preview';document.body.append(preview);}
  const horizontal=['left','right'].includes(edge);Object.assign(preview.style,{left:(r.left+(edge==='right'?r.width/2:0))+'px',top:(r.top+(edge==='bottom'?r.height/2:0))+'px',width:(horizontal?r.width/2:r.width)+'px',height:(horizontal?r.height:r.height/2)+'px'});
  return {tile:target.dataset.tileId,edge};
 }
 document.addEventListener('pointerdown',event=>{
  const divider=event.target.closest('[data-dock-split]');if(divider&&!options.readOnly()&&event.button===0){if(!draft())start(true);if(!enabled())return;const canvas=divider.closest('.dock-canvas'),path=divider.dataset.dockSplit,shown=options.project?.(draft().page)||draft().page,rectangles=dockRects(shown.layout,canvas.clientWidth,canvas.clientHeight),split=rectangles.splits.find(s=>s.path===path);if(!split)return;event.preventDefault();divider.setPointerCapture(event.pointerId);splitResize={key:key(),node:visibleSplitSource(draft().page.layout,split.node,new Set(dockLeaves(shown.layout)))||split.node,rect:split.rect,canvasRect:canvas.getBoundingClientRect(),canvas};document.body.classList.add('resizing-page-tile');return;}
  const mover=event.target.closest('[data-window-drag]');
  if(mover&&!options.readOnly()&&event.button===0){if(!draft())start(true);const row=tile(mover.dataset.windowDrag);if(!row?.bounds||!enabled())return;event.preventDefault();mover.setPointerCapture(event.pointerId);windowMove={row,startX:event.clientX,startY:event.clientY,base:{...row.bounds},key:key()};document.body.classList.add('resizing-page-tile');return;}
  const handle=event.target.closest('[data-tile-resize]');if(!handle||handle.disabled||options.readOnly()||event.button!==0)return;if(!draft())start(true);if(!enabled())return;const row=tile(handle.dataset.tileResize);if(!row)return;
  event.preventDefault();handle.setPointerCapture(event.pointerId);const element=handle.closest('.page-tile'),area=element.parentElement;
  resizing={key:key(),handle,row,axis:handle.dataset.resizeAxis||'both',startX:event.clientX,startY:event.clientY,base:{bounds:row.bounds?{...row.bounds}:null,height:row.height,span:row.span,width:(place(row)==='left'?document.querySelector('.sidebar'):place(row)==='right'?document.querySelector('#view-dock'):area).getBoundingClientRect().width},width:area.getBoundingClientRect().width};const rect=element.getBoundingClientRect(),next=element.nextElementSibling;
  if(place(row)==='main'&&next?.hasAttribute('data-live-tile')&&Math.abs(next.getBoundingClientRect().top-rect.top)<3){resizing.neighbor=tile(next.dataset.tileId);resizing.neighborSpan=resizing.neighbor?.span;}
  resizing.maxSpan=12-[...area.children].filter(el=>el!==element&&el.hasAttribute('data-live-tile')&&Math.abs(el.getBoundingClientRect().top-rect.top)<3).reduce((sum,el)=>sum+(tile(el.dataset.tileId)?.span||0),0);
  document.body.classList.add('resizing-page-tile');
 });
 document.addEventListener('pointermove',event=>{if(splitResize&&splitResize.key===key()){const r=splitResize,x=r.node.axis==='x',position=x?event.clientX-r.canvasRect.left-r.rect.x:event.clientY-r.canvasRect.top-r.rect.y,length=(x?r.rect.width:r.rect.height)-8,a=dockMinimum(r.node.first),b=dockMinimum(r.node.second),min=(x?a.width:a.height)/length,max=1-(x?b.width:b.height)/length;r.node.ratio=Math.max(.05,Math.min(.95,Math.max(Math.min(min,.45),Math.min(Math.max(max,.55),position/length))));options.resize?.(draft().page);return;}if(windowMove&&windowMove.key===key()){const r=windowMove;r.row.bounds={...r.base,x:clamp(r.base.x+event.clientX-r.startX,0,10000),y:clamp(r.base.y+event.clientY-r.startY,0,10000)};options.resize?.(draft().page);r.snap=windowSnap(event,r.row);return;}if(!resizing||resizing.key!==key()||!enabled())return;const r=resizing,dx=r.axis==='y'?0:event.clientX-r.startX,dy=r.axis==='x'?0:event.clientY-r.startY;
  applySize(r.row,dx,dy,r.base,r.width);
  if(draft().page.arrangement!=='windows'&&place(r.row)==='main'&&r.axis!=='y'){
   const total=r.base.span+(r.neighborSpan||0),max=r.neighbor?total-1:r.maxSpan;
   r.row.span=Math.round(Math.max(1,Math.min(max,r.base.span+dx/(r.width/12)))*100)/100;
   if(r.neighbor)r.neighbor.span=Math.round((total-r.row.span)*100)/100;
  }
  options.resize?.(draft().page);});
 const endResize=()=>{if(splitResize){const same=splitResize.key===key();splitResize=null;document.body.classList.remove('resizing-page-tile');if(same&&draft()?.automatic)void save();else changed();return;}if(windowMove){const samePage=windowMove.key===key(),snap=windowMove.snap,row=windowMove.row;windowMove=null;document.querySelector('.dock-drop-preview')?.remove();if(samePage&&snap&&enabled()){draft().page.arrangement='docked';dropDock(draft().page,row.id,{tile:snap.tile},snap.edge);options.resize?.(draft().page);}document.body.classList.remove('resizing-page-tile');if(samePage&&draft()?.automatic)void save();else changed();return;}if(!resizing)return;const samePage=resizing.key===key();resizing=null;document.body.classList.remove('resizing-page-tile');if(samePage&&draft()?.automatic)void save();else changed();};
 document.addEventListener('pointerup',endResize);document.addEventListener('pointercancel',endResize);
 document.addEventListener('keydown',event=>{
  const divider=event.target.closest('[data-dock-split]');if(divider&&!options.readOnly()&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();if(!draft())start(true);if(!enabled())return;const shown=options.project?.(draft().page)||draft().page,target=dockNode(shown.layout,divider.dataset.dockSplit),node=visibleSplitSource(draft().page.layout,target,new Set(dockLeaves(shown.layout)))||target;if(node){node.ratio=Math.max(.05,Math.min(.95,node.ratio+(['ArrowLeft','ArrowUp'].includes(event.key)?-.03:.03)));options.resize?.(draft().page);if(draft().automatic)void save();}return;}
  const handle=event.target.closest('[data-tile-resize]');if(!handle||handle.disabled||options.readOnly()||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
  const horizontal=['ArrowLeft','ArrowRight'].includes(event.key);if(handle.dataset.resizeAxis===(horizontal?'y':'x'))return;
  event.preventDefault();if(!draft())start(true);if(!enabled())return;const row=tile(handle.dataset.tileResize),element=handle.closest('.page-tile'),area=element.parentElement,width=area.getBoundingClientRect().width;
  const original=row.span,neighbors=[...area.children].filter(el=>el!==element&&el.hasAttribute('data-live-tile')&&Math.abs(el.getBoundingClientRect().top-element.getBoundingClientRect().top)<3),next=element.nextElementSibling,neighbor=neighbors.includes(next)?tile(next.dataset.tileId):null,total=original+(neighbor?.span||0);
  applySize(row,event.key==='ArrowLeft'?-width/12:event.key==='ArrowRight'?width/12:0,event.key==='ArrowUp'?-20:event.key==='ArrowDown'?20:0,{...row,bounds:row.bounds?{...row.bounds}:null,width:(place(row)==='left'?document.querySelector('.sidebar'):place(row)==='right'?document.querySelector('#view-dock'):area).getBoundingClientRect().width},width);
  if(draft().page.arrangement!=='windows'&&place(row)==='main'&&horizontal){row.span=Math.max(1,Math.min(neighbor?total-1:12-neighbors.reduce((sum,el)=>sum+(tile(el.dataset.tileId)?.span||0),0),row.span));if(neighbor)neighbor.span=total-row.span;}
  options.resize?.(draft().page);if(draft()?.automatic)void save();
 });
 let topWindow=10;document.addEventListener('pointerdown',event=>{const window=event.target.closest('.window-canvas>.page-tile');if(window)window.style.zIndex=String(++topWindow);},true);
 return {page:page=>page?(draft()?.page||page):undefined,editing:()=>!!draft()&&!draft().automatic,saving:()=>!!draft()?.saving,toolbar,decorate,palette(){return `<summary>Blocks</summary><div class="tile-palette">${options.catalog().map(row=>`<button type="button" class="button small-button" data-add-tile="${esc(row.kind)}" draggable="true" ${options.readOnly()||row.kind!=='html'&&options.page()?.tiles.some(tile=>tile.kind===row.kind)?'disabled':''}>${esc(row.label)}</button>`).join('')}</div>`;},active:()=>!!resizing||!!windowMove||!!splitResize, resizeSidebar(width){if(!draft())start(true);if(enabled()){draft().page.left_width=clamp(width,160,600);options.resize?.(draft().page);}},resizeDock(width){if(!draft())start(true);if(enabled()){draft().page.right_width=clamp(width,280,760);options.resize?.(draft().page);}},commitResize(){if(draft()?.automatic)void save();},start};
}
