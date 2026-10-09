'use strict';
const {_electron:electron}=require('playwright');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'ss-windows-native-')),root=path.resolve(__dirname,'..');let app;
 const packaged=path.dirname(process.env.ELECTRON_PATH||path.join(root,'dist/SuperSurfer-linux-x64/SuperSurfer'));
 const runtime=path.join(profile,'runtime'),fixture=path.join(runtime,'resources/app');fs.mkdirSync(fixture,{recursive:true});
 for(const name of fs.readdirSync(packaged))if(name!=='resources'){
  const from=path.join(packaged,name),to=path.join(runtime,name);
  if(name===path.basename(process.env.ELECTRON_PATH||'SuperSurfer'))fs.copyFileSync(from,to,fs.constants.COPYFILE_FICLONE);else fs.symlinkSync(from,to);
 }
 fs.writeFileSync(path.join(fixture,'package.json'),JSON.stringify({name:'supersurfer',productName:'SuperSurfer',version:'0.1.16',main:'fixture.cjs'}));
 fs.writeFileSync(path.join(fixture,'fixture.cjs'),`
 const http=require('node:http'),{EventEmitter}=require('node:events');
 const root=${JSON.stringify(root)};
 global.__fixture={calls:[],aborted:[],killed:[],unavailable:new Set(['offline']),children:new Map(),origins:new Map()};
 const connection=require(root+'/desktop/connection.cjs');
 connection.connect=async(raw,status,{signal}={})=>{
  const config=connection.validateConfig(raw),id=config.target||'local';__fixture.calls.push(id);
  await new Promise((resolve,reject)=>{const timer=setTimeout(resolve,id==='slow'?60000:100);signal?.addEventListener('abort',()=>{__fixture.aborted.push(id);clearTimeout(timer);reject(new Error('Cancelled fixture connection'));},{once:true});});
  signal?.throwIfAborted();if(__fixture.unavailable.has(id))throw new Error('Fixture host unavailable');
  let origin=__fixture.origins.get(id);
  if(!origin){const server=http.createServer((req,res)=>{
   res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Allow-Headers','*');
   if(req.url.startsWith('/api/')){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({id,authorization:req.headers.authorization||null}));}
   res.setHeader('Content-Type','text/html');res.end('<title>Fixture</title><h1>'+id+'</h1>');
  });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;__fixture.origins.set(id,origin);}
  const child=new EventEmitter();child.exitCode=null;child.kill=()=>{if(child.exitCode!==null)return;child.exitCode=0;__fixture.killed.push(id);setImmediate(()=>child.emit('exit',0));};__fixture.children.set(id,child);
  return {config,origin,token:'fixture-token-'+id,child};
 };
 Object.defineProperty(require('electron').app,'dock',{value:{setMenu:menu=>{__fixture.dockMenu=menu;}}});
 require(root+'/desktop/main.cjs');
 `);
 const launch=()=>electron.launch({executablePath:path.join(runtime,path.basename(process.env.ELECTRON_PATH||'SuperSurfer')),chromiumSandbox:true,colorScheme:null,args:['--disable-dev-shm-usage'],env:{...process.env,HOME:profile,XDG_CONFIG_HOME:path.join(profile,'config'),XDG_CACHE_HOME:path.join(profile,'cache')}});
 const menu=async(label)=>app.evaluate(({Menu},label)=>{const visit=items=>{for(const item of items){if(item.label===label){item.click();return true;}if(item.submenu&&visit(item.submenu.items))return true;}return false;};if(!visit(Menu.getApplicationMenu().items))throw new Error('Missing menu '+label);},label);
 const newWindow=async()=>{const opened=app.waitForEvent('window');await app.evaluate(()=>{const item=global.__fixture.dockMenu.items.find(item=>item.label==='New Window');if(!item)throw new Error('Dock New Window missing');item.click();});return opened;};
 const waitWindows=async n=>{for(let i=0;i<300;i++){const pages=await app.windows();if(pages.length===n)return pages;await new Promise(resolve=>setTimeout(resolve,20));}throw new Error('Window count did not reach '+n);};
 const connect=async(page,target)=>{
  await page.waitForFunction(()=>!document.querySelector('#connect-button')?.disabled);
  await page.locator('#mode').selectOption('remote');await page.locator('#host').selectOption('__custom');await page.locator('#target').fill(target);
  await page.locator('#connect-button').click();await page.getByRole('heading',{name:target,exact:true}).waitFor();
 };
 const probe=page=>page.evaluate(async()=>fetch('/api/probe').then(r=>r.json()));
 try{
  app=await launch();let a=await app.firstWindow();await connect(a,'tulip');
  await a.evaluate(()=>superSurferDesktop.setWorkspace({projectId:'vla',tab:'page:page_abcdef',chatWidth:510}));
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setBounds({x:40,y:50,width:1120,height:740}));
  const newFromHeader=app.waitForEvent('window');await a.evaluate(()=>superSurferDesktop.newWindow());let b=await newFromHeader;await connect(b,'trinity');
  await b.evaluate(()=>superSurferDesktop.setWorkspace({projectId:'different',tab:'runs'}));
  assert.equal((await probe(a)).authorization,'Bearer fixture-token-tulip');assert.equal((await probe(b)).authorization,'Bearer fixture-token-trinity');
  const foreign=await b.evaluate(async origin=>fetch(origin+'/api/probe').then(r=>r.json()),new URL(a.url()).origin);assert.equal(foreign.authorization,null,'Other host must not receive this window’s credentials');
  const framed=await a.evaluate(async()=>{const frame=document.createElement('iframe');frame.src='/embedded';document.body.append(frame);await new Promise(resolve=>frame.onload=resolve);return frame.contentWindow.fetch('/api/probe').then(r=>r.json());});assert.equal(framed.authorization,null,'Embedded content must not receive native credentials');
  await assert.rejects(a.evaluate(()=>superSurferDesktop.openPanel({project:'p1',page:'writing',tile:'pdf',item:'',title:'PDF',url:'https://outside.invalid'})),/project panel/);
  const panelEvent=app.waitForEvent('window');await a.evaluate(()=>superSurferDesktop.openPanel({project:'p1',page:'writing',tile:'pdf',item:'',title:'PDF'}));const panel=await panelEvent;await panel.waitForURL('http://127.0.0.1:*/**');
  assert.equal((await probe(panel)).authorization,'Bearer fixture-token-tulip');assert.equal(new URL(panel.url()).searchParams.get('panel_tile'),'pdf');
  const embeddedProbe=await panel.evaluate(async()=>{const iframe=document.createElement('iframe');iframe.src='/embedded';document.body.append(iframe);await new Promise(resolve=>iframe.onload=resolve);return iframe.contentWindow.fetch('/api/probe').then(r=>r.json());});assert.equal(embeddedProbe.authorization,null);
  await a.evaluate(()=>{window.__closedPanels=[];superSurferDesktop.onPanelClosed(event=>window.__closedPanels.push(event.id));});const detached=await a.evaluate(()=>superSurferDesktop.listPanels());assert.equal(detached.length,1);assert.equal(detached[0].tile,'pdf');await panel.close();await a.waitForFunction(()=>window.__closedPanels.length===1);assert.equal(await a.evaluate(()=>superSurferDesktop.listPanels().then(rows=>rows.length)),0);assert.equal((await probe(a)).authorization,'Bearer fixture-token-tulip');console.log('PASS detached native panel shares the correct host, limits credentials to its main frame, and closes independently');
  const userData=await app.evaluate(({app})=>app.getPath('userData'));
  await app.close();app=await launch();
  let pages=await waitWindows(2);
  for(const p of pages)await p.waitForURL('http://127.0.0.1:*/**');a=pages.find(p=>p.url().startsWith('http:')&&p!==undefined);
  const named=await Promise.all(pages.map(async p=>[await p.locator('h1').innerText(),p]));a=named.find(([name])=>name==='tulip')[1];b=named.find(([name])=>name==='trinity')[1];
  assert.equal((await a.evaluate(()=>superSurferDesktop.getWorkspace())).projectId,'vla');assert.equal((await b.evaluate(()=>superSurferDesktop.getWorkspace())).projectId,'different');
  assert.deepEqual((await app.evaluate(()=>__fixture.calls)).sort(),['trinity','tulip']);
  const bounds=await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().find(w=>w.getTitle().startsWith('tulip')).getNormalBounds());assert.equal(bounds.width,1120);assert.equal(bounds.height,740);
  // A dropped tunnel reconnects once to the remembered host, without a form submission.
  await app.evaluate(()=>__fixture.children.get('tulip').kill());
  for(let i=0;i<200;i++){if((await app.evaluate(()=>__fixture.calls.filter(id=>id==='tulip').length))===2)break;await new Promise(resolve=>setTimeout(resolve,20));}
  await a.waitForURL('http://127.0.0.1:*/**');assert.equal((await probe(a)).authorization,'Bearer fixture-token-tulip');
  const stored=fs.readFileSync(path.join(userData,'windows.json'),'utf8');assert.ok(!stored.includes('fixture-token'));assert.ok(!stored.includes('http://127.0.0.1:'));
  console.log('PASS automatic two-host restore, separate navigation/bounds, main-frame-only credentials and token-free saved state');
  const keepPanelEvent=app.waitForEvent('window');await a.evaluate(()=>superSurferDesktop.openPanel({project:'p1',page:'writing',tile:'pdf',item:'',title:'PDF'}));const keepPanel=await keepPanelEvent;await keepPanel.waitForURL('http://127.0.0.1:*/**');
  await a.close();assert.equal((await probe(keepPanel)).authorization,'Bearer fixture-token-tulip');assert.equal((await probe(b)).authorization,'Bearer fixture-token-trinity');await keepPanel.close();console.log('PASS detached panel retains its connection when its parent closes');
  await menu('tulip');await waitWindows(2);
  const offline=await newWindow();
  await offline.waitForFunction(()=>!document.querySelector('#connect-button')?.disabled);
  // Persist a successful association, then make it unavailable before reopening.
  await app.evaluate(()=>__fixture.unavailable.delete('offline'));await connect(offline,'offline');
  await app.close();app=await launch();await waitWindows(3);await new Promise(resolve=>setTimeout(resolve,300));
  const failed=(await app.windows()).find(p=>p.url().startsWith('file:'));await failed.getByText('Fixture host unavailable',{exact:true}).waitFor();
  assert.equal(await failed.locator('#host').inputValue(),'offline');assert.equal(await failed.locator('#connect-button').isEnabled(),true);
  await app.evaluate(()=>__fixture.unavailable.delete('offline'));await failed.locator('#connect-button').click();await failed.getByRole('heading',{name:'offline',exact:true}).waitFor();
  assert.equal((await app.evaluate(()=>__fixture.calls)).filter(id=>id==='offline').length,2);
  console.log('PASS closing one window preserves another; Open Recent restores the host; unavailable auto-restore keeps a one-click retry');
  const slow=await newWindow();await slow.waitForFunction(()=>!document.querySelector('#connect-button')?.disabled);
  await slow.locator('#mode').selectOption('remote');await slow.locator('#host').selectOption('__custom');await slow.locator('#target').fill('slow');await slow.locator('#connect-button').click();
  await slow.locator('#cancel-connect').click();await slow.getByText('Connection cancelled. Your saved workspace is still available.',{exact:true}).waitFor();assert.equal(await slow.locator('#connect-button').isEnabled(),true);
  assert.equal((await app.evaluate(()=>__fixture.aborted)).filter(id=>id==='slow').length,1);
  await slow.locator('#connect-button').click();await slow.locator('#cancel-connect').waitFor();
  for(let i=0;i<200;i++){if((await app.evaluate(()=>__fixture.calls.filter(id=>id==='slow').length))===2)break;await new Promise(resolve=>setTimeout(resolve,20));}
  assert.equal((await app.evaluate(()=>__fixture.calls)).filter(id=>id==='slow').length,2);
  await slow.close();
  for(let i=0;i<200;i++){if((await app.evaluate(()=>__fixture.aborted.filter(id=>id==='slow').length))===2)break;await new Promise(resolve=>setTimeout(resolve,20));}
  assert.equal((await app.evaluate(()=>__fixture.aborted)).filter(id=>id==='slow').length,2);
  const hostile=failed,origin=new URL(hostile.url()).origin;
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().find(w=>w.getTitle().startsWith('offline')).loadURL('data:text/html,<h1>Untrusted</h1>'));
  assert.equal((await hostile.evaluate(async origin=>fetch(origin+'/api/probe').then(r=>r.json()),origin)).authorization,null,'Untrusted main documents must not inherit native credentials');
  await assert.rejects(hostile.evaluate(()=>superSurferDesktop.getWorkspace()),/trusted workspace/);
  await assert.rejects(hostile.evaluate(()=>superSurferDesktop.newWindow()),/trusted workspace/);
  await assert.rejects(hostile.evaluate(()=>superSurferDesktop.configuration()),/setup window/);
  console.log('PASS connection cancellation and untrusted-document IPC denial');
 }finally{if(app)await app.close();fs.rmSync(profile,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
