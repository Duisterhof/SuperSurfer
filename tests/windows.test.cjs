'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {WindowStore,configKey}=require('../desktop/windows.cjs');
const config=target=>({mode:'remote',target,remoteRoot:'~/.local/share/supersurfer',amlHome:'~/.auto-ml',remotePort:8765});
function directory(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ss-windows-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));return dir;}
test('legacy host/navigation migrate once without copying credentials',t=>{
 const dir=directory(t);fs.writeFileSync(path.join(dir,'connection.json'),JSON.stringify({...config('tulip'),token:'secret'}));
 fs.writeFileSync(path.join(dir,'workspace.json'),JSON.stringify({projectId:'vla',tab:'page:page_abcdef',chatWidth:550}));
 const store=new WindowStore(dir),[window]=store.restore();assert.equal(window.config.target,'tulip');assert.equal(window.workspace.tab,'page:page_abcdef');store.save();
 assert.ok(!fs.readFileSync(path.join(dir,'windows.json'),'utf8').includes('secret'));
 assert.equal(new WindowStore(dir).restore()[0].id,window.id);
 assert.equal(fs.statSync(path.join(dir,'windows.json')).mode & 0o777,0o600);
});
test('quit restores open windows separately; closing all reopens the latest host',t=>{
 const dir=directory(t),store=new WindowStore(dir),a=store.restore()[0];store.connected(a,config('tulip'));a.workspace={projectId:'vla'};
 const b=store.create(config('trinity'));b.workspace={projectId:'second'};store.save();
 const restored=new WindowStore(dir).restore();assert.deepEqual(restored.map(r=>r.config.target),['tulip','trinity']);assert.notDeepEqual(restored[0].workspace,restored[1].workspace);
 a.open=false;b.open=false;b.updated=a.updated+1;store.save();assert.equal(new WindowStore(dir).restore()[0].config.target,'trinity');
});
test('changing host preserves old recent navigation and starts new host clean',t=>{
 const store=new WindowStore(directory(t)),a=store.restore()[0];store.connected(a,config('tulip'));a.workspace={projectId:'vla'};store.connected(a,config('trinity'));
 assert.equal(a.workspace,null);assert.equal(store.recent().find(r=>r.config.target==='tulip').workspace.projectId,'vla');
 store.create(config('trinity'));assert.equal(store.recent().filter(r=>r.config.target==='trinity').length,1);
 assert.notEqual(configKey(config('tulip')),configKey({...config('tulip'),remoteRoot:'~/other-workspace'}));
});
test('damaged records cannot turn saved state into executable configuration',t=>{
 const dir=directory(t),file=path.join(dir,'windows.json');fs.writeFileSync(file,JSON.stringify({windows:[{id:'bad',config:config('tulip')},{id:'a'.repeat(36),config:config('-oProxyCommand=bad')}]}));
 const store=new WindowStore(dir);assert.equal(store.restore()[0].config,null);
 fs.writeFileSync(file,'{bad');assert.equal(new WindowStore(dir).restore()[0].config,null);
});
