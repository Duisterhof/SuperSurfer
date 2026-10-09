// Direct manipulation saves presentation through the version-checked layout API.
// Arrange mode keeps an explicit draft; source buffers are never saved.
const copy=value=>structuredClone(value);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clamp=(value,min,max)=>Math.max(min,Math.min(max,Math.round(value)));
const place=tile=>tile.placement||'main';
export function createTileLayout(options){
 const drafts=new Map();let dragging=null,resizing=null,windowMove=null;
 const key=()=>options.key(),draft=()=>drafts.get(key());
 const enabled=()=>!!draft()&&!draft().saving&&!options.readOnly();
 const changed=()=>{options.render();};
 function start(automatic=false){const page=options.page();if(!page||options.readOnly())return;if(!draft())drafts.set(key(),{base:copy(page),page:copy(page),automatic,error:''});else if(!automatic)draft().automatic=false;if(!automatic)changed();}
 function cancel(){if(draft()?.saving)return;drafts.delete(key());changed();}
 function tile(id){return draft()?.page.tiles.find(row=>row.id===id);}
 function move(id,placement,before){if(!enabled())return;const row=tile(id);if(!row||id===before)return;row.placement=placement;const rows=draft().page.tiles.filter(item=>item!==row),index=rows.findIndex(item=>item.id===before);rows.splice(index<0?rows.length:index,0,row);draft().page.tiles=rows;changed();}
 function add(kind,placement='main',before){
  if(!enabled())return;const page=draft().page;if(page.tiles.length>=16||page.tiles.some(row=>row.kind===kind)||!options.catalog().some(row=>row.kind===kind))return;
  const row={id:'tile_'+crypto.randomUUID().replaceAll('-','').slice(0,12),kind,span:kind==='file_explorer'?3:6,height:kind==='pdf'?600:400,placement};page.tiles.push(row);move(row.id,placement,before);
 }
 async function save(){
  if(!enabled())return;const id=key(),value=draft();value.saving=true;value.error='';changed();
  try{await options.save(copy(value.page),copy(value.base));drafts.delete(id);}
  catch(error){value.error=error.message;value.saving=false;value.automatic=false;}
  changed();
 }
 function toolbar(){const value=draft();if(!value||value.automatic)return '';const disabled=value.saving||options.readOnly();
  return `<div class="tile-arrange-toolbar"><span class="arrange-label" title="Drag tiles into the page or either sidebar; drag corners to resize.">Arranging ${esc(value.page.title)}</span><details class="tile-palette-menu"><summary class="button small-button">Add tile</summary><div class="tile-palette" aria-label="Add a page tile">${options.catalog().map(row=>`<button type="button" class="button small-button" data-add-tile="${esc(row.kind)}" draggable="${!disabled}" ${disabled||value.page.tiles.some(tile=>tile.kind===row.kind)||value.page.tiles.length>=16?'disabled':''}>+ ${esc(row.label)}</button>`).join('')}</div></details><button class="button small-button" data-tile-command="cancel" ${disabled?'disabled':''}>Cancel</button><button class="button small-button primary" data-tile-command="save" ${disabled?'disabled':''}>${value.saving?'Saving…':'Save layout'}</button>${value.error?`<p class="notice error arrange-error" role="alert">${esc(value.error)} Your layout draft is kept.</p>`:''}</div>`;
 }
 function controls(row,label){
    const floating=(draft()?.page||options.page())?.arrangement==='windows'&&place(row)==='main';
    const grip=`<button type="button" class="tile-grip" ${floating?'data-window-drag':'data-tile-grip'}="${esc(row.id)}" draggable="${!floating&&!options.readOnly()}" aria-label="Move ${esc(label)}" title="Drag to move or split panels" ${options.readOnly()||draft()?.saving?'disabled':''}>⠿</button>`;
    const windowButton=`<button type="button" data-panel-window="${esc(row.id)}" aria-label="Open ${esc(label)} in a separate window" title="Open in separate window">↗</button>`;

  if(!draft()||draft().automatic)return `${grip}<span ${floating?`data-window-drag="${esc(row.id)}"`:""}>${esc(label)}</span>${windowButton}<button type="button" data-panel-fullscreen aria-label="Full screen" title="Full screen">⤢</button>`;
  const disabled=!enabled();
  return `${grip}<span>${esc(label)}</span>${windowButton}<select data-tile-placement="${esc(row.id)}" aria-label="Place ${esc(label)}" ${disabled?'disabled':''}>${[['main','Page'],['left','Left sidebar'],['right','Right sidebar']].map(([value,text])=>`<option value="${value}" ${place(row)===value?'selected':''}>${text}</option>`).join('')}</select><button type="button" data-tile-up="${esc(row.id)}" title="Move earlier" aria-label="Move ${esc(label)} earlier" ${disabled?'disabled':''}>↑</button><button type="button" data-tile-remove="${esc(row.id)}" title="Remove tile; keep its content" aria-label="Remove ${esc(label)} tile" ${disabled?'disabled':''}>×</button>`;
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
 document.addEventListener('click',event=>{
  const button=event.target.closest('[data-tile-command],[data-add-tile],[data-tile-remove],[data-tile-up]');if(!button||button.disabled)return;event.preventDefault();event.stopImmediatePropagation();
  const command=button.dataset.tileCommand;if(command==='start')start();if(command==='windows'||command==='docked'){
      if(!draft())start(true);if(enabled()){const page=draft().page;page.arrangement=command;
      if(command==='windows')for(const row of page.tiles){if(place(row)!=='main'||row.bounds)continue;const element=[...document.querySelectorAll('[data-live-tile]')].find(el=>el.dataset.tileId===row.id),area=element?.parentElement,a=area?.getBoundingClientRect(),r=element?.getBoundingClientRect();row.bounds={x:Math.max(0,Math.round((r?.left||0)-(a?.left||0))),y:Math.max(0,Math.round((r?.top||0)-(a?.top||0))),width:Math.max(200,Math.round(r?.width||500)),height:Math.max(160,Math.round(r?.height||row.height))};}
      options.resize?.(page);if(draft().automatic)void save();else changed();}}
if(command==='files-left'){start();if(enabled()){const existing=draft().page.tiles.find(row=>row.kind==='file_explorer');if(existing)move(existing.id,'left');else add('file_explorer','left');}}if(command==='cancel')cancel();if(command==='save')void save();
  if(button.dataset.addTile)add(button.dataset.addTile);
  if(enabled()&&button.dataset.tileRemove){draft().page.tiles=draft().page.tiles.filter(row=>row.id!==button.dataset.tileRemove);changed();}
  if(enabled()&&button.dataset.tileUp){const row=tile(button.dataset.tileUp),rows=draft().page.tiles.filter(item=>place(item)===place(row)),i=rows.indexOf(row);if(i>0)move(row.id,place(row),rows[i-1].id);}
 },true);
 document.addEventListener('change',event=>{const id=event.target.dataset.tilePlacement;if(id&&enabled()){event.stopImmediatePropagation();move(id,event.target.value);}},true);
 document.addEventListener('dragstart',event=>{
  const handle=event.target.closest('[data-tile-grip],[data-add-tile]');if(!handle||handle.disabled)return;if(!draft())start(true);if(!enabled())return;
  dragging={key:key(),id:handle.dataset.tileGrip,kind:handle.dataset.addTile};event.dataTransfer.setData('application/x-supersurfer-tile',JSON.stringify(dragging));event.dataTransfer.effectAllowed=dragging.id?'move':'copy';document.body.classList.add('dragging-page-tile');document.querySelectorAll('[data-tile-drop]').forEach(area=>area.hidden=false);event.stopPropagation();
 });
 document.addEventListener('dragover',event=>{if(!dragging||dragging.key!==key()||!enabled())return;const area=event.target.closest('[data-tile-drop]');if(!area)return;event.preventDefault();event.dataTransfer.dropEffect=dragging.id?'move':'copy';document.querySelectorAll('.tile-drop-active').forEach(el=>el.classList.remove('tile-drop-active'));area.classList.add('tile-drop-active');});
 function endDrag(){if(dragging&&draft()?.automatic&&JSON.stringify(draft().base)===JSON.stringify(draft().page))drafts.delete(key());dragging=null;document.body.classList.remove('dragging-page-tile');document.querySelectorAll('.tile-drop-active').forEach(el=>el.classList.remove('tile-drop-active'));}
 document.addEventListener('drop',event=>{
  if(!dragging||dragging.key!==key()||!enabled())return;const area=event.target.closest('[data-tile-drop]');if(!area)return;event.preventDefault();event.stopImmediatePropagation();
  const target=event.target.closest('[data-tile-id]'),before=target?.dataset.tileId;
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
 document.addEventListener('pointerdown',event=>{
  const mover=event.target.closest('[data-window-drag]');
  if(mover&&!options.readOnly()&&event.button===0){if(!draft())start(true);const row=tile(mover.dataset.windowDrag);if(!row?.bounds||!enabled())return;event.preventDefault();mover.setPointerCapture(event.pointerId);windowMove={row,startX:event.clientX,startY:event.clientY,base:{...row.bounds},key:key()};document.body.classList.add('resizing-page-tile');return;}
  const handle=event.target.closest('[data-tile-resize]');if(!handle||handle.disabled||options.readOnly()||event.button!==0)return;if(!draft())start(true);if(!enabled())return;const row=tile(handle.dataset.tileResize);if(!row)return;
  event.preventDefault();handle.setPointerCapture(event.pointerId);const element=handle.closest('.page-tile'),area=element.parentElement;
  resizing={key:key(),handle,row,axis:handle.dataset.resizeAxis||'both',startX:event.clientX,startY:event.clientY,base:{bounds:row.bounds?{...row.bounds}:null,height:row.height,span:row.span,width:(place(row)==='left'?document.querySelector('.sidebar'):place(row)==='right'?document.querySelector('#view-dock'):area).getBoundingClientRect().width},width:area.getBoundingClientRect().width};const rect=element.getBoundingClientRect(),next=element.nextElementSibling;
  if(place(row)==='main'&&next?.hasAttribute('data-live-tile')&&Math.abs(next.getBoundingClientRect().top-rect.top)<3){resizing.neighbor=tile(next.dataset.tileId);resizing.neighborSpan=resizing.neighbor?.span;}
  resizing.maxSpan=12-[...area.children].filter(el=>el!==element&&el.hasAttribute('data-live-tile')&&Math.abs(el.getBoundingClientRect().top-rect.top)<3).reduce((sum,el)=>sum+(tile(el.dataset.tileId)?.span||0),0);
  document.body.classList.add('resizing-page-tile');
 });
 document.addEventListener('pointermove',event=>{if(windowMove&&windowMove.key===key()){const r=windowMove;r.row.bounds={...r.base,x:clamp(r.base.x+event.clientX-r.startX,0,10000),y:clamp(r.base.y+event.clientY-r.startY,0,10000)};options.resize?.(draft().page);return;}if(!resizing||resizing.key!==key()||!enabled())return;const r=resizing,dx=r.axis==='y'?0:event.clientX-r.startX,dy=r.axis==='x'?0:event.clientY-r.startY;
  applySize(r.row,dx,dy,r.base,r.width);
  if(draft().page.arrangement!=='windows'&&place(r.row)==='main'&&r.axis!=='y'){
   const total=r.base.span+(r.neighborSpan||0),max=r.neighbor?total-1:r.maxSpan;
   r.row.span=Math.round(Math.max(1,Math.min(max,r.base.span+dx/(r.width/12)))*100)/100;
   if(r.neighbor)r.neighbor.span=Math.round((total-r.row.span)*100)/100;
  }
  options.resize?.(draft().page);});
 const endResize=()=>{if(windowMove){const samePage=windowMove.key===key();windowMove=null;document.body.classList.remove('resizing-page-tile');if(samePage&&draft()?.automatic)void save();else changed();return;}if(!resizing)return;const samePage=resizing.key===key();resizing=null;document.body.classList.remove('resizing-page-tile');if(samePage&&draft()?.automatic)void save();else changed();};
 document.addEventListener('pointerup',endResize);document.addEventListener('pointercancel',endResize);
 document.addEventListener('keydown',event=>{
  const handle=event.target.closest('[data-tile-resize]');if(!handle||handle.disabled||options.readOnly()||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
  const horizontal=['ArrowLeft','ArrowRight'].includes(event.key);if(handle.dataset.resizeAxis===(horizontal?'y':'x'))return;
  event.preventDefault();if(!draft())start(true);if(!enabled())return;const row=tile(handle.dataset.tileResize),element=handle.closest('.page-tile'),area=element.parentElement,width=area.getBoundingClientRect().width;
  const original=row.span,neighbors=[...area.children].filter(el=>el!==element&&el.hasAttribute('data-live-tile')&&Math.abs(el.getBoundingClientRect().top-element.getBoundingClientRect().top)<3),next=element.nextElementSibling,neighbor=neighbors.includes(next)?tile(next.dataset.tileId):null,total=original+(neighbor?.span||0);
  applySize(row,event.key==='ArrowLeft'?-width/12:event.key==='ArrowRight'?width/12:0,event.key==='ArrowUp'?-20:event.key==='ArrowDown'?20:0,{...row,bounds:row.bounds?{...row.bounds}:null,width:(place(row)==='left'?document.querySelector('.sidebar'):place(row)==='right'?document.querySelector('#view-dock'):area).getBoundingClientRect().width},width);
  if(draft().page.arrangement!=='windows'&&place(row)==='main'&&horizontal){row.span=Math.max(1,Math.min(neighbor?total-1:12-neighbors.reduce((sum,el)=>sum+(tile(el.dataset.tileId)?.span||0),0),row.span));if(neighbor)neighbor.span=total-row.span;}
  options.resize?.(draft().page);if(draft()?.automatic)void save();
 });
 let topWindow=10;document.addEventListener('pointerdown',event=>{const window=event.target.closest('.window-canvas>.page-tile');if(window)window.style.zIndex=String(++topWindow);},true);
 return {page:page=>page?(draft()?.page||page):undefined,editing:()=>!!draft()&&!draft().automatic,toolbar,decorate,active:()=>!!resizing||!!windowMove, resizeSidebar(width){if(!draft())start(true);if(enabled()){draft().page.left_width=clamp(width,160,600);options.resize?.(draft().page);}},resizeDock(width){if(!draft())start(true);if(enabled()){draft().page.right_width=clamp(width,280,760);options.resize?.(draft().page);}},commitResize(){if(draft()?.automatic)void save();},start};
}
