// Real page layout service, with controlled data-source delays and failures.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..');

async function fixture(){
 const child=spawn('python3',['tests/layout_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','pipe']});
 let errors='';child.stderr.on('data',chunk=>errors+=chunk);
 const data=await new Promise((resolve,reject)=>{
  let output='';child.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))try{resolve(JSON.parse(output.split('\n')[0]));}catch(error){reject(error);}});
  child.on('error',reject);child.on('exit',code=>reject(new Error('Fixture stopped '+code+' '+errors)));
 });
 return {...data,stop:()=>child.stdin.end()};
}

(async()=>{
 let service,browser;
 try{
  service=await fixture();
  const token=fs.readFileSync(path.join(service.directory,'token'),'utf8').trim(),base='http://127.0.0.1:'+service.port;
  browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.setDefaultTimeout(15000);page.on('pageerror',error=>errors.push(error.message));
  const projectId=service.projects.software,itemId=service.items.software;
  await page.addInitScript(({token,projectId})=>{
   if(window!==window.top)return;
   sessionStorage.setItem('supersurfer-token',token);
   if(!localStorage.getItem('supersurfer-workspace'))localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId,tab:'overview',chatVisible:true}));
  },{token,projectId});
  await page.goto(base);await page.locator('#arrange-page').waitFor();
  const request=(route,body)=>page.evaluate(async({route,body})=>{
   const response=await fetch('/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+sessionStorage.getItem('supersurfer-token'),'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
   const data=await response.json();if(!response.ok)throw new Error(JSON.stringify(data));return data;
  },{route,body});
  async function apply(modify){
   const data=await request('surfboard?project_id='+projectId+'&experiment_id='+itemId),board=modify(data.board)||data.board;
   const saved=await request('action',{op:'surfboard.draft',params:{project_id:projectId,experiment_id:itemId,expected_version:data.version,expected_draft_version:data.draft?.draft_version||0,board}});
   return request('action',{op:'surfboard.apply',params:{project_id:projectId,experiment_id:itemId,expected_version:saved.version,expected_draft_version:saved.draft.draft_version}});
  }
  async function open(tab){
   await page.evaluate(value=>localStorage.setItem('supersurfer-workspace',JSON.stringify(value)),{view:'workspace',projectId,experimentId:itemId,tab,chatVisible:false});
   await page.reload();await page.locator('#main [data-tab="'+tab+'"].active').waitFor();
  }
  async function refreshItem(){
   const refreshed=page.waitForResponse(response=>response.url().includes('/api/experiment?')&&new URL(response.url()).searchParams.get('id')===itemId);
   await page.locator('[data-action="refresh"]').first().click();await refreshed;
  }
  const tile=kind=>page.locator('#main [data-tile-kind="'+kind+'"]');
  await apply(board=>{
   const preview=board.nodes.find(node=>node.kind==='preview'),old=preview.id;preview.id='scoped-preview';
   for(const edge of board.edges){if(edge.source===old)edge.source=preview.id;if(edge.target===old)edge.target=preview.id;}
   const pages=['preview','activity','documents','artifacts'].map(kind=>({id:'view-'+kind,title:kind+' data',tiles:[{id:kind,kind,span:12,height:600}]}));
   board.pages={item:pages};board.layouts={item:[{id:'chat',placement:'hidden'}]};
  });

  let activityError=false,holdActivity=false,activityCalls=0;
  const activityWaiters=[];
  const actions=[
   {id:'own',node_id:'scoped-preview',experiment_id:itemId,status:'running',preview_url:'/board-preview/own-fixture/'},
   {id:'shared',node_id:'scoped-preview',status:'running',preview_url:'/board-preview/shared-fixture/'},
   {id:'sibling',node_id:'scoped-preview',experiment_id:'sibling-item',status:'running',preview_url:'/board-preview/sibling-fixture/'},
   {id:'removed',node_id:'preview',experiment_id:itemId,status:'running',preview_url:'/board-preview/removed-fixture/'},
   {id:'stopped',node_id:'scoped-preview',experiment_id:itemId,status:'stopped',preview_url:'/board-preview/stopped-fixture/'},
  ];
  await page.route('**/api/project-activity?*',async route=>{
   activityCalls++;
   if(holdActivity)await new Promise(resolve=>activityWaiters.push(resolve));
   return activityError?route.fulfill({status:503,json:{error:'Activity source temporarily unavailable'}}):
    route.fulfill({json:{agents:[{scope:'fixture-agent',name:'Recovered activity worker',status:'idle'}],actions,rules:[],recoveries:[]}});
  });
  await page.route('**/board-preview/*-fixture/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><p>Managed preview fixture</p><input id="kept" value="default">'}));
  holdActivity=true;
  const requested=page.waitForRequest(request=>request.url().includes('/api/project-activity?'));
  await open('view-preview');await requested;
  assert.equal(await tile('preview').locator('iframe').count(),0,'The preview must wait for its asynchronous data source');
  holdActivity=false;for(const release of activityWaiters.splice(0))release();
  await tile('preview').locator('iframe').first().waitFor();
  assert.deepEqual((await tile('preview').locator('iframe').evaluateAll(frames=>frames.map(frame=>new URL(frame.src).pathname))).sort(),['/board-preview/own-fixture/','/board-preview/shared-fixture/']);
  await page.frameLocator('[data-tile-kind="preview"] iframe').first().locator('#kept').fill('preserved preview state');
  await refreshItem();
  assert.equal(await page.frameLocator('[data-tile-kind="preview"] iframe').first().locator('#kept').inputValue(),'preserved preview state');
  console.log('PASS delayed preview-only tile updates on arrival, filters node/item/status, and preserves embedded state');

  for(const kind of ['activity','preview']){
   activityError=true;await open('view-'+kind);
   await tile(kind).getByText('Activity source temporarily unavailable',{exact:false}).waitFor();
   assert.equal(await tile(kind).getByText('Loading activity…',{exact:true}).count(),0);
   const before=activityCalls;activityError=false;
   await tile(kind).getByRole('button',{name:'Retry',exact:true}).click();
   if(kind==='activity')await tile(kind).getByText('Recovered activity worker',{exact:true}).waitFor();
   else await tile(kind).locator('iframe').first().waitFor();
   assert.ok(activityCalls>before);assert.equal(await tile(kind).getByRole('button',{name:'Retry',exact:true}).count(),0);
  }
  console.log('PASS activity and preview source errors are visible and Retry recovers each tile');

  let documentVersion=1,documentError=true,holdDocument=false,documentCalls=0;
  const documentWaiters=[];
  await page.route('**/api/experiment?*',async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),data=await response.json();
   if(new URL(route.request().url()).searchParams.get('id')===itemId)data.pages=[{id:'protocol',title:'Method protocol',version:documentVersion}];
   await route.fulfill({response,json:data});
  });
  await page.route('**/api/experiment-page?*',async route=>{
   documentCalls++;const version=documentVersion;
   if(holdDocument)await new Promise(resolve=>documentWaiters.push(resolve));
   return documentError?route.fulfill({status:503,json:{error:'Document temporarily unavailable'}}):
    route.fulfill({json:{id:'protocol',title:'Method protocol',version,markdown:'# Protocol revision '+version+'\n\nMeasured details for revision '+version+'.'}});
  });
  await open('view-documents');
  const protocol=tile('documents').locator('[data-document-id="protocol"]');
  await protocol.locator('summary').click();
  await protocol.getByText('Document temporarily unavailable',{exact:false}).waitFor();
  documentError=false;await protocol.getByRole('button',{name:'Retry',exact:true}).click();
  await protocol.getByText('Protocol revision 1',{exact:true}).waitFor();
  assert.equal(await protocol.getAttribute('open'),'');
  documentVersion=2;await refreshItem();
  await protocol.getByText('Protocol revision 2',{exact:true}).waitFor();
  assert.equal(await protocol.getAttribute('open'),'','Loading new document content must preserve the expanded document');
  assert.equal(await protocol.getByText('Protocol revision 1',{exact:true}).count(),0);
  console.log('PASS document errors retry successfully and changed page versions refresh visible content without collapsing it');

  // An old in-flight document must not win over a newer version observed in metadata.
  documentVersion=3;holdDocument=true;
  const pendingDocument=page.waitForRequest(request=>request.url().includes('/api/experiment-page?'));
  await open('view-documents');await pendingDocument;
  await protocol.locator('summary').click();
  documentVersion=4;await refreshItem();
  holdDocument=false;for(const release of documentWaiters.splice(0))release();
  await protocol.getByText('Protocol revision 4',{exact:true}).waitFor();
  assert.equal(await protocol.getAttribute('open'),'');
  assert.ok(documentCalls>=4);
  console.log('PASS stale in-flight document response cannot leave a newer visible page at the old revision');

  let artifactError=true,artifactCalls=0;
  await page.route('**/api/artifacts?*',route=>{
   artifactCalls++;
   return artifactError?route.fulfill({status:503,json:{error:'Artifact source temporarily unavailable'}}):
    route.fulfill({json:{root_label:'Project files',path:'',entries:[{kind:'file',name:'evidence.md',path:'evidence.md',size:64,mime:'text/markdown',download_url:'/project-artifact/fixture/evidence.md?download=1'}]}});
  });
  await open('view-artifacts');await tile('artifacts').getByText('Artifact source temporarily unavailable',{exact:true}).waitFor();
  artifactError=false;await tile('artifacts').getByRole('button',{name:'Refresh',exact:true}).click();
  await tile('artifacts').getByRole('button',{name:'evidence.md',exact:true}).waitFor();
  assert.ok(artifactCalls>=2);
  assert.deepEqual(errors,[]);
  console.log('PASS artifact error/refresh recovery and zero browser exceptions');
 }finally{
  await browser?.close();service?.stop();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
