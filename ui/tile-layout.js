// Direct manipulation changes a page draft. One explicit save uses the same
// version-checked presentation API as agents; source buffers are never saved.
const copy=value=>structuredClone(value);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clamp=(value,min,max)=>Math.max(min,Math.min(max,Math.round(value)));
const place=tile=>tile.placement||'main';
export function createTileLayout(options){
 const drafts=new Map();let dragging=null,resizing=null;
 const key=()=>options.key(),draft=()=>drafts.get(key());
 const enabled=()=>!!draft()&&!draft().saving&&!options.readOnly();
 const changed=()=>{options.render();};
 function start(){const page=options.page();if(!page||options.readOnly())return;if(!draft())drafts.set(key(),{base:copy(page),page:copy(page),error:''});changed();}
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
  catch(error){value.error=error.message;value.saving=false;}
  changed();
 }
 function toolbar(){const value=draft();if(!value)return '';const disabled=value.saving||options.readOnly();
  return `<div class="tile-arrange-toolbar"><span>Drag tiles into the page or either sidebar. Drag a corner to resize.</span><div><button class="button small-button" data-tile-command="cancel" ${disabled?'disabled':''}>Cancel</button><button class="button small-button primary" data-tile-command="save" ${disabled?'disabled':''}>${value.saving?'Saving…':'Save layout'}</button></div></div><div class="tile-palette" aria-label="Add a page tile">${options.catalog().map(row=>`<button type="button" class="button small-button" data-add-tile="${esc(row.kind)}" draggable="${!disabled}" ${disabled||value.page.tiles.some(tile=>tile.kind===row.kind)||value.page.tiles.length>=16?'disabled':''}>+ ${esc(row.label)}</button>`).join('')}</div>${value.error?`<p class="notice error" role="alert">${esc(value.error)} Your layout draft is kept. Cancel to load the latest layout.</p>`:''}`;
 }
 function controls(row,label){
  if(!draft())return `<span>${esc(label)}</span><button type="button" data-panel-fullscreen aria-label="Full screen" title="Full screen">⤢</button>`;
  const disabled=!enabled();
  return `<button type="button" class="tile-grip" data-tile-grip="${esc(row.id)}" draggable="${!disabled}" aria-label="Drag ${esc(label)}" title="Drag this tile" ${disabled?'disabled':''}>⠿</button><span>${esc(label)}</span><select data-tile-placement="${esc(row.id)}" aria-label="Place ${esc(label)}" ${disabled?'disabled':''}>${[['main','Page'],['left','Left sidebar'],['right','Right sidebar']].map(([value,text])=>`<option value="${value}" ${place(row)===value?'selected':''}>${text}</option>`).join('')}</select><button type="button" data-tile-up="${esc(row.id)}" title="Move earlier" aria-label="Move ${esc(label)} earlier" ${disabled?'disabled':''}>↑</button><button type="button" data-tile-remove="${esc(row.id)}" title="Remove tile; keep its content" aria-label="Remove ${esc(label)} tile" ${disabled?'disabled':''}>×</button>`;
 }
 function decorate(element,row,label){
  const header=element.querySelector('.page-tile-heading'),html=controls(row,label);if(header.innerHTML!==html)header.innerHTML=html;
  let handle=element.querySelector('.tile-resize');
  if(draft()&&!handle){handle=document.createElement('button');handle.type='button';handle.className='tile-resize';handle.dataset.tileResize=row.id;handle.setAttribute('aria-label','Resize '+label);handle.title='Drag to resize. Left/Right change width; Up/Down change height.';element.append(handle);}
  if(!draft())handle?.remove();else if(handle)handle.disabled=!enabled();
  element.dataset.tilePlacement=place(row);
 }
 function applySize(row,dx,dy,base,width){
  row.height=clamp(base.height+dy,row.kind==='pdf'?400:160,1200);
  if(place(row)==='main')row.span=clamp(base.span+dx/(width/12),1,12);
  else if(dx) {const field=place(row)==='left'?'left_width':'right_width',direction=place(row)==='left'?1:-1;draft().page[field]=clamp(base.width+direction*dx,place(row)==='left'?200:280,place(row)==='left'?600:760);}
 }
 document.addEventListener('click',event=>{
  const button=event.target.closest('[data-tile-command],[data-add-tile],[data-tile-remove],[data-tile-up]');if(!button||button.disabled)return;event.preventDefault();event.stopImmediatePropagation();
  const command=button.dataset.tileCommand;if(command==='start')start();if(command==='cancel')cancel();if(command==='save')void save();
  if(button.dataset.addTile)add(button.dataset.addTile);
  if(enabled()&&button.dataset.tileRemove){draft().page.tiles=draft().page.tiles.filter(row=>row.id!==button.dataset.tileRemove);changed();}
  if(enabled()&&button.dataset.tileUp){const row=tile(button.dataset.tileUp),rows=draft().page.tiles.filter(item=>place(item)===place(row)),i=rows.indexOf(row);if(i>0)move(row.id,place(row),rows[i-1].id);}
 },true);
 document.addEventListener('change',event=>{const id=event.target.dataset.tilePlacement;if(id&&enabled()){event.stopImmediatePropagation();move(id,event.target.value);}},true);
 document.addEventListener('dragstart',event=>{
  const handle=event.target.closest('[data-tile-grip],[data-add-tile]');if(!handle||handle.disabled||!enabled())return;
  dragging={key:key(),id:handle.dataset.tileGrip,kind:handle.dataset.addTile};event.dataTransfer.setData('application/x-supersurfer-tile',JSON.stringify(dragging));event.dataTransfer.effectAllowed=dragging.id?'move':'copy';document.body.classList.add('dragging-page-tile');event.stopPropagation();
 });
 document.addEventListener('dragover',event=>{if(!dragging||dragging.key!==key()||!enabled())return;const area=event.target.closest('[data-tile-drop]');if(!area)return;event.preventDefault();event.dataTransfer.dropEffect=dragging.id?'move':'copy';document.querySelectorAll('.tile-drop-active').forEach(el=>el.classList.remove('tile-drop-active'));area.classList.add('tile-drop-active');});
 function endDrag(){dragging=null;document.body.classList.remove('dragging-page-tile');document.querySelectorAll('.tile-drop-active').forEach(el=>el.classList.remove('tile-drop-active'));}
 document.addEventListener('drop',event=>{
  if(!dragging||dragging.key!==key()||!enabled())return;const area=event.target.closest('[data-tile-drop]');if(!area)return;event.preventDefault();event.stopImmediatePropagation();
  const target=event.target.closest('[data-tile-id]'),before=target?.dataset.tileId;
  if(dragging.id)move(dragging.id,area.dataset.tileDrop,before);else add(dragging.kind,area.dataset.tileDrop,before);endDrag();
 },true);
 document.addEventListener('dragend',endDrag);
 document.addEventListener('pointerdown',event=>{
  const handle=event.target.closest('[data-tile-resize]');if(!handle||!enabled()||event.button!==0)return;const row=tile(handle.dataset.tileResize);if(!row)return;
  event.preventDefault();handle.setPointerCapture(event.pointerId);const element=handle.closest('.page-tile'),area=element.parentElement;
  resizing={key:key(),handle,row,startX:event.clientX,startY:event.clientY,base:{height:row.height,span:row.span,width:(place(row)==='left'?document.querySelector('.sidebar'):place(row)==='right'?document.querySelector('#view-dock'):area).getBoundingClientRect().width},width:area.getBoundingClientRect().width};document.body.classList.add('resizing-page-tile');
 });
 document.addEventListener('pointermove',event=>{if(!resizing||resizing.key!==key()||!enabled())return;applySize(resizing.row,event.clientX-resizing.startX,event.clientY-resizing.startY,resizing.base,resizing.width);options.resize?.(draft().page);});
 const endResize=()=>{if(!resizing)return;resizing=null;document.body.classList.remove('resizing-page-tile');changed();};
 document.addEventListener('pointerup',endResize);document.addEventListener('pointercancel',endResize);
 document.addEventListener('keydown',event=>{const handle=event.target.closest('[data-tile-resize]');if(!handle||!enabled()||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const row=tile(handle.dataset.tileResize),area=handle.closest('.page-tile').parentElement,width=area.getBoundingClientRect().width;applySize(row,event.key==='ArrowLeft'?-width/12:event.key==='ArrowRight'?width/12:0,event.key==='ArrowUp'?-20:event.key==='ArrowDown'?20:0,{...row,width:(place(row)==='left'?document.querySelector('.sidebar'):place(row)==='right'?document.querySelector('#view-dock'):area).getBoundingClientRect().width},width);options.resize?.(draft().page);});
 return {page:page=>page?(draft()?.page||page):undefined,editing:()=>!!draft(),toolbar,decorate,active:()=>!!resizing, resizeDock(width){if(!draft())start();if(enabled()){draft().page.right_width=clamp(width,280,760);options.resize?.(draft().page);}},start};
}
