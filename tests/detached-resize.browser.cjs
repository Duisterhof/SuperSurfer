'use strict';
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..'),child=spawn('python3',['tests/layout_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','inherit']});let browser;
 try{
  const f=await new Promise((resolve,reject)=>{let out='';child.stdout.on('data',chunk=>{out+=chunk;if(out.includes('\n'))resolve(JSON.parse(out.split('\n')[0]));});child.on('error',reject);child.on('exit',code=>reject(Error('Fixture exited '+code)));});
  const token=fs.readFileSync(f.directory+'/token','utf8').trim(),pid=f.projects.software,base='http://127.0.0.1:'+f.port;
  const api=async(route,body)=>{const r=await fetch(base+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data;};
  const project=(await api('state')).projects.find(p=>p.id===pid);fs.writeFileSync(path.join(project.repo,'paper.pdf'),require('./fixtures/pdf.cjs')());
  const layout=await api('view-layout?project_id='+pid),pages=['docked','windows'].map(arrangement=>({id:arrangement,title:arrangement,arrangement,layout:{axis:'x',ratio:.5,first:{tile:'code'},second:{tile:'pdf'}},tiles:[{id:'code',kind:'editor',span:6,height:500,bounds:{x:0,y:0,width:450,height:500}},{id:'pdf',kind:'pdf',path:'paper.pdf',span:6,height:500,bounds:{x:470,y:0,width:450,height:500}}]}));
  await api('action',{op:'view-layout.save',params:{project_id:pid,experiment_id:null,version:layout.version,board_version:layout.board_version,pages}});
  const saved=(await api('view-layout?project_id='+pid)).pages;
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
  for(const tab of ['docked','windows']){
   const context=await browser.newContext({viewport:{width:1650,height:1050}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await context.addInitScript(({pid,token,tab})=>{sessionStorage.setItem('supersurfer-token',token);if(!location.search.includes('panel_tile'))localStorage.setItem('supersurfer-workspace',JSON.stringify({projectId:pid,tab,view:'workspace',chatVisible:false}));},{pid,token,tab});
   await page.goto(base);await page.locator('#workspace-files-tree [data-tile-file="main.py"]').click();await page.locator('.code-monaco .monaco-editor').waitFor();
   await page.evaluate(async()=>{const m=await import('/vendor/monaco/editor.js');window.retainedModel=m.editor.getModels().find(m=>m.uri.path.endsWith('/main.py'));retainedModel.setValue('print("my unsaved draft")\n');});
   const editor=page.locator('[data-tile-kind=editor]'),pdf=page.locator('[data-tile-kind=pdf]');
   const opened=context.waitForEvent('page',{timeout:10000}).catch(()=>null);await pdf.locator('.editor-panel-handle>summary').click();await pdf.getByRole('button',{name:/separate window/}).click();const popup=await opened;assert.ok(popup,'No popup in '+tab);await popup.locator('body.detached-panel').waitFor();await page.locator('[data-tile-kind=pdf]').waitFor({state:'detached'});await page.waitForTimeout(300);
   await page.evaluate(()=>{
    window.resizeRatios=[];const tile=document.querySelector('[data-tile-kind=editor]'),canvas=document.querySelector('#page-tile-grid');
    window.measureResize=()=>resizeRatios.push(tile.getBoundingClientRect().width/canvas.getBoundingClientRect().width);
    window.resizeProbe=new ResizeObserver(measureResize);resizeProbe.observe(tile);measureResize();
   });
   for(const width of [1400,1800,1500]){await page.setViewportSize({width,height:1050});await page.waitForTimeout(100);}
   const ratios=await page.evaluate(()=>{resizeProbe.disconnect();return resizeRatios;});assert.ok(ratios.length>=3,JSON.stringify(ratios));assert.ok(ratios.every(ratio=>ratio>.95),'Detached panel reclaimed space during resize: '+JSON.stringify(ratios));
   assert.equal(await page.evaluate(()=>retainedModel.getValue()),'print("my unsaved draft")\n');assert.deepEqual((await api('view-layout?project_id='+pid)).pages,saved);
   await popup.close();await pdf.waitFor();assert.equal(await page.evaluate(()=>retainedModel.getValue()),'print("my unsaved draft")\n');
   if(tab==='docked')assert.ok((await editor.boundingBox()).width<(await page.locator('#page-tile-grid').boundingBox()).width*.6);
   assert.deepEqual(errors,[]);await context.close();console.log('PASS '+tab+' detached PDF keeps editor full width across resize, preserves draft/layout and returns on close');
  }
 }finally{await browser?.close();child.stdin.end();}
})().catch(error=>{console.error(error);process.exitCode=1;});
