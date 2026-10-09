// A small binary split tree. Leaves stay in the same DOM so editors keep buffers.
const clone=value=>structuredClone(value);
export const dockLeaf=id=>({tile:id});
export function dockLeaves(tree,result=[]){if(!tree)return result;if(tree.tile)result.push(tree.tile);else if(tree.axis){dockLeaves(tree.first,result);dockLeaves(tree.second,result);}return result;}
export function pruneDock(tree,keep){if(!tree)return null;if(tree.tile)return keep.has(tree.tile)?clone(tree):null;if(tree.empty)return clone(tree);const first=pruneDock(tree.first,keep),second=pruneDock(tree.second,keep);return first&&second?{...tree,first,second}:first||second;}
function stack(nodes,axis,weights=nodes.map(()=>1)){if(!nodes.length)return {empty:true};if(nodes.length===1)return nodes[0];return {axis,ratio:Math.max(.05,Math.min(.95,weights[0]/weights.reduce((a,b)=>a+b,0))),first:nodes[0],second:stack(nodes.slice(1),axis,weights.slice(1))};}
export function ensureDockLayout(page){
 const main=page.tiles.filter(row=>(row.placement||'main')==='main'),keep=new Set(main.map(row=>row.id));
 const current=dockLeaves(page.layout);if(page.layout&&current.length===keep.size&&new Set(current).size===current.length&&current.every(id=>keep.has(id)))return page.layout;
 if(!page.layout){let rows=[],row=[],weights=[],span=0;for(const tile of main){if(span+tile.span>12.01&&row.length){rows.push(stack(row,'x',weights));row=[];weights=[];span=0;}row.push(dockLeaf(tile.id));weights.push(tile.span||6);span+=tile.span||6;}if(row.length)rows.push(stack(row,'x',weights));page.layout=stack(rows,'y');}
 else{page.layout=pruneDock(page.layout,keep)||{empty:true};const present=new Set(dockLeaves(page.layout));for(const tile of main)if(!present.has(tile.id))page.layout=page.layout.empty?dockLeaf(tile.id):{axis:'x',ratio:.5,first:page.layout,second:dockLeaf(tile.id)};}
 return page.layout;
}
export function dockNode(tree,path=''){return path?path.split('.').reduce((node,key)=>node?.[key],tree):tree;}
export function replaceDock(tree,path,replacement){if(!path)return replacement;const parts=path.split('.'),key=parts.pop();dockNode(tree,parts.join('.'))[key]=replacement;return tree;}
export function dropDock(page,id,target,edge='right'){
 const incoming=dockLeaf(id),existing=page.layout||ensureDockLayout(page);
 // Remove first, then resolve the target by tile identity or the original empty leaf.
 if(target?.tile===id)return;
 const marker=target?.empty?dockNode(existing,target.path||''):null;
 const remove=node=>{if(node.tile===id)return null;if(!node.axis)return node;const first=remove(node.first),second=remove(node.second);return first&&second?{...node,first,second}:first||second;};
 page.layout=remove(existing)||{empty:true};
 const insert=node=>{if(target?.tile&&node.tile===target.tile||marker&&node===marker||!target&&node===page.layout){if(node.empty)return incoming;const before=['left','top'].includes(edge);return {axis:['left','right'].includes(edge)?'x':'y',ratio:.5,first:before?incoming:node,second:before?node:incoming};}return node.axis?{...node,first:insert(node.first),second:insert(node.second)}:node;};
 page.layout=insert(page.layout);
 if(!dockLeaves(page.layout).includes(id))page.layout={axis:'x',ratio:.5,first:page.layout,second:incoming};
}
export function reserveDockSpace(page,id,edge){ensureDockLayout(page);const insert=node=>{if(node.tile===id){const before=['left','top'].includes(edge);return {axis:['left','right'].includes(edge)?'x':'y',ratio:before ? .35 : .65,first:before?{empty:true}:node,second:before?node:{empty:true}};}return node.axis?{...node,first:insert(node.first),second:insert(node.second)}:node;};page.layout=insert(page.layout);}
export function dockMinimum(tree){if(!tree?.axis)return {width:180,height:160};const a=dockMinimum(tree.first),b=dockMinimum(tree.second);return tree.axis==='x'?{width:a.width+b.width+8,height:Math.max(a.height,b.height)}:{width:Math.max(a.width,b.width),height:a.height+b.height+8};}
export function dockRects(tree,width,height){const leaves=[],splits=[];function walk(node,rect,path){if(!node.axis){leaves.push({node,rect,path});return;}const x=node.axis==='x',length=x?rect.width:rect.height,cut=(length-8)*node.ratio,a={...rect},b={...rect};if(x){a.width=cut;b.x+=cut+8;b.width=length-cut-8;}else{a.height=cut;b.y+=cut+8;b.height=length-cut-8;}splits.push({node,path,rect,bar:x?{x:rect.x+cut,y:rect.y,width:8,height:rect.height}:{x:rect.x,y:rect.y+cut,width:rect.width,height:8}});walk(node.first,a,path?path+'.first':'first');walk(node.second,b,path?path+'.second':'second');}walk(tree,{x:0,y:0,width,height},'');return {leaves,splits};}
const styles=(element,r)=>Object.assign(element.style,{left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px'});
export function renderDockLayout(canvas,page){
 if(!page.layout)page={...page,tiles:page.tiles};
 ensureDockLayout(page);const minimum=dockMinimum(page.layout);canvas.style.minWidth=minimum.width+'px';canvas.style.minHeight=minimum.height+'px';
 const rectangles=dockRects(page.layout,canvas.clientWidth,canvas.clientHeight),keep=new Set();
 for(const leaf of rectangles.leaves){if(leaf.node.tile){const tile=[...canvas.children].find(el=>el.dataset.tileId===leaf.node.tile);if(tile)styles(tile,leaf.rect);continue;}const key='empty:'+leaf.path;keep.add(key);let empty=[...canvas.children].find(el=>el.dataset.dockKey===key);if(!empty){empty=document.createElement('div');empty.className='dock-empty';empty.dataset.dockKey=key;empty.dataset.dockEmpty=leaf.path;empty.innerHTML='<span>Drop a panel here</span>';if(leaf.path){const close=document.createElement('button');close.type='button';close.dataset.dockClose=leaf.path;close.textContent='×';close.setAttribute('aria-label','Close empty space');empty.append(close);}canvas.append(empty);}styles(empty,leaf.rect);}
 for(const split of rectangles.splits){const key='split:'+split.path;keep.add(key);let divider=[...canvas.children].find(el=>el.dataset.dockKey===key);if(!divider){divider=document.createElement('button');divider.type='button';divider.className='dock-divider';divider.dataset.dockKey=key;divider.dataset.dockSplit=split.path;divider.setAttribute('role','separator');divider.setAttribute('aria-label','Resize panels');canvas.append(divider);}divider.dataset.axis=split.node.axis;divider.setAttribute('aria-orientation',split.node.axis==='x'?'vertical':'horizontal');divider.setAttribute('aria-valuenow',String(Math.round(split.node.ratio*100)));styles(divider,split.bar);}
 for(const node of canvas.querySelectorAll('[data-dock-key]'))if(!keep.has(node.dataset.dockKey))node.remove();
 return rectangles;
}
