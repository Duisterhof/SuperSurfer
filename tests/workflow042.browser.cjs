const {chromium}=require('playwright'),{spawn}=require('node:child_process'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const child=spawn('python3',['tests/layout_runtime_fixture.py'],{stdio:['pipe','pipe','inherit']});let browser;
 try{
 const fixture=await new Promise((res,rej)=>{let s='';child.stdout.on('data',c=>{s+=c;if(s.includes('\n'))res(JSON.parse(s.split('\n')[0]));});child.on('exit',code=>rej(Error('fixture '+code)));});
 const token=fs.readFileSync(fixture.directory+'/token','utf8').trim(),origin='http://127.0.0.1:'+fixture.port,pid=fixture.projects.software,eid=fixture.items.software;
 const api=async(route,body)=>{const r=await fetch(origin+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const result=await r.json();assert.ok(r.ok,JSON.stringify(result));return result;};
 browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:980}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(({token,pid,eid})=>{sessionStorage.setItem('supersurfer-token',token);localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId:pid,experimentId:eid,tab:'workflow',chatVisible:true}));},{token,pid,eid});
 await page.goto(origin);await page.getByText('What do you want to build today?',{exact:true}).waitFor();await page.locator('.wf-start [data-wf=toggle]').waitFor();
 assert.equal(await page.locator('.wf-proposal').isVisible(),false);assert.ok((await page.locator('#chat-panel').boundingBox()).width>1000);
 await page.locator('#chat-input').fill('Preserve my configurator draft');await page.locator('[data-wf=toggle]').click();await page.getByLabel('Surfboard name',{exact:true}).fill('Software / Café');await page.locator('[data-wf=save]').click();await page.getByLabel('Saved Surfboard',{exact:true}).locator('option').filter({hasText:'Software / Café'}).waitFor({state:'attached'});
 await page.locator('[data-wf=choose]').click();await page.getByRole('button',{name:'Apply these changes',exact:true}).click();await page.getByText('Workflow applied',{exact:true}).waitFor();
 assert.equal(await page.locator('#chat-input').inputValue(),'Preserve my configurator draft');const linked=await api('workflow?project_id='+pid+'&experiment_id='+eid);assert.equal(linked.link.id,linked.library.entries[0].id);
 await page.locator('.wf-toolbar [data-wf=advanced]').click();await page.locator('.sb-canvas').waitFor();await page.locator('[data-tab=workflow]').first().click();await page.locator('.wf-start').waitFor();assert.equal(await page.locator('#chat-input').inputValue(),'Preserve my configurator draft');
 for(const workflow of ['research','software','writing']){
  await page.locator('#project-tree [data-action=add-experiment]').click();await page.locator('#modal [name=summary]').fill('Test '+workflow+' workflow / Café');await page.locator('#modal [name=workflow]').selectOption(workflow);await page.getByRole('button',{name:'Design workflow',exact:true}).click();
  await page.locator('#modal').waitFor({state:'hidden'});await page.locator('.wf-start [data-wf=toggle]').waitFor();
  const state=await api('state'),task=state.experiments.find(x=>x.name==='Test '+workflow+' workflow / Café');assert.ok(task);
  const configured=await api('workflow?project_id='+pid+'&experiment_id='+task.id);assert.equal(configured.source.board.workflow,workflow);
 }
 await page.screenshot({path:'/tmp/supersurfer-workflow042.png'});assert.deepEqual(errors,[]);console.log('PASS chat-first full-width entry, saved Unicode Surfboard, preview/apply/link, draft retained across Advanced navigation');
 }finally{await browser?.close();child.stdin.end();}
})().catch(e=>{console.error(e);process.exitCode=1;});
