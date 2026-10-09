const test=require('node:test'),assert=require('node:assert/strict');
test('nested docking fills the canvas and preserves independent branches',async()=>{
 const d=await import('../ui/dock-layout.js');const page={tiles:[{id:'code',span:6},{id:'pdf',span:6}]};d.ensureDockLayout(page);
 page.tiles.push({id:'files',span:6});d.dropDock(page,'files',{tile:'code'},'bottom');
 assert.equal(page.layout.axis,'x');assert.equal(page.layout.first.axis,'y');assert.equal(page.layout.second.tile,'pdf');
 const r=d.dockRects(page.layout,1200,800).leaves,code=r.find(x=>x.node.tile==='code').rect,files=r.find(x=>x.node.tile==='files').rect,pdf=r.find(x=>x.node.tile==='pdf').rect;
 assert.equal(code.x,files.x);assert.equal(code.width,files.width);assert(files.y>code.y+code.height);assert.equal(pdf.height,800);assert(pdf.x>code.width);
 d.dropDock(page,'files',{tile:'pdf'},'bottom');assert.equal(page.layout.first.tile,'code');assert.equal(page.layout.second.axis,'y');assert.deepEqual(d.dockLeaves(page.layout).sort(),['code','files','pdf']);
});
test('an empty split accepts a new panel without duplicating or losing panels',async()=>{
 const d=await import('../ui/dock-layout.js');const page={tiles:[{id:'code',span:12}]};d.reserveDockSpace(page,'code','right');assert.equal(page.layout.second.empty,true);
 page.tiles.push({id:'pdf',span:6});d.dropDock(page,'pdf',{empty:true,path:'second'},'right');assert.equal(page.layout.second.tile,'pdf');assert.deepEqual(d.dockLeaves(page.layout),['code','pdf']);
 d.dropDock(page,'code',{tile:'code'},'left');assert.deepEqual(d.dockLeaves(page.layout),['code','pdf']);
});
test('removing a panel and moving it to a sidebar repairs its old split',async()=>{
 const d=await import('../ui/dock-layout.js');const page={tiles:[{id:'code',span:6},{id:'pdf',span:6}]};d.ensureDockLayout(page);page.tiles[1].placement='right';d.ensureDockLayout(page);assert.deepEqual(page.layout,{tile:'code'});page.tiles[1].placement='main';d.ensureDockLayout(page);assert.deepEqual(d.dockLeaves(page.layout).sort(),['code','pdf']);
});
