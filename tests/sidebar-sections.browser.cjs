'use strict';
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..'),child=spawn('python3',['tests/layout_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','inherit']});let browser;
 try{
  const fixture=await new Promise((resolve,reject)=>{let out='';child.stdout.on('data',chunk=>{out+=chunk;if(out.includes('\n'))resolve(JSON.parse(out.split('\n')[0]));});child.on('error',reject);child.on('exit',code=>reject(Error('Fixture exited '+code)));});
  const token=fs.readFileSync(fixture.directory+'/token','utf8').trim(),pid=fixture.projects.software,base='http://127.0.0.1:'+fixture.port;
  const call=async(route,body)=>{const r=await fetch(base+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data;};
  const layout=await call('view-layout?project_id='+pid);
  await call('action',{op:'view-layout.save',params:{project_id:pid,experiment_id:null,version:layout.version,board_version:layout.board_version,pages:[
   {id:'desk',title:'Desk',tiles:[{id:'code',kind:'editor',span:12,height:600},{id:'files',kind:'file_explorer',placement:'left',span:12,height:250}]},
   {id:'plain',title:'Plain',tiles:[{id:'overview',kind:'overview',span:12,height:500}]}
  ]}});
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
  for(const desktop of [false,true]){
   const context=await browser.newContext({viewport:{width:1440,height:1100}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(({pid,token,desktop})=>{sessionStorage.setItem('supersurfer-token',token);if(!localStorage.getItem('supersurfer-workspace'))localStorage.setItem('supersurfer-workspace',JSON.stringify({projectId:pid,tab:'desk',view:'workspace',chatVisible:false}));if(desktop)document.addEventListener('DOMContentLoaded',()=>document.body.classList.add('desktop-app'));},{pid,token,desktop});
   await page.goto(base);await page.locator('#workspace-files-tree [data-tile-file="main.py"]').waitFor();
   const files=page.locator('#workspace-files-section'),projects=page.locator('#project-tree'),fileHandle=page.locator('#workspace-files-divider'),projectHandle=page.locator('#sidebar-projects-resizer');
   const drag=async(handle,section,delta)=>{const before=await section.boundingBox(),bar=await handle.boundingBox();assert.ok(bar.height>=6,'Divider must have a usable hit area');const x=bar.x+bar.width/2,y=bar.y+bar.height/2;assert.equal(await page.evaluate(({x,y})=>document.elementFromPoint(x,y)?.id,{x,y}),await handle.getAttribute('id'));await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x,y+delta,{steps:8});await page.mouse.up();const after=await section.boundingBox();assert.ok(Math.abs(after.height-before.height-delta)<2,JSON.stringify({before,after,delta}));return after.height;};
   const fileHeight=await drag(fileHandle,files,55),projectHeight=await drag(projectHandle,projects,-35);
   await page.reload();await page.locator('#workspace-files-tree [data-tile-file="main.py"]').waitFor();assert.equal((await files.boundingBox()).height,fileHeight);assert.equal((await projects.boundingBox()).height,projectHeight);
   await fileHandle.focus();await page.keyboard.press('ArrowUp');assert.equal((await files.boundingBox()).height,fileHeight-20);
   await files.locator('summary').click();assert.equal(await fileHandle.isVisible(),false);assert.ok((await files.boundingBox()).height<40);
   await files.locator('summary').click();assert.equal((await files.boundingBox()).height,fileHeight-20);
   await page.locator('[data-tab=plain]').click();assert.equal(await files.isVisible(),false);assert.equal(await projectHandle.isVisible(),false);
   await page.locator('[data-tab=desk]').click();await page.locator('#workspace-files-tree [data-tile-file="main.py"]').waitFor();assert.equal((await files.boundingBox()).height,fileHeight-20);
   await page.setViewportSize({width:1440,height:650});await page.waitForTimeout(100);
   const sidebar=await page.locator('.sidebar').boundingBox(),footer=await page.locator('.sidebar-footer').boundingBox();assert.ok(footer.y+footer.height<=sidebar.y+sidebar.height+1,'Footer must stay within sidebar on a shorter window');assert.ok((await projects.boundingBox()).height>25);assert.ok((await fileHandle.boundingBox()).height>=6);
   await page.setViewportSize({width:1440,height:1100});await page.waitForTimeout(100);assert.equal((await files.boundingBox()).height,fileHeight-20);
   assert.deepEqual(errors,[]);await context.close();console.log('PASS '+(desktop?'desktop':'browser')+' Files/Projects vertical drag, saved sizes, collapse/navigation and short-window bounds');
  }
 }finally{await browser?.close();child.stdin.end();}
})().catch(error=>{console.error(error);process.exitCode=1;});
