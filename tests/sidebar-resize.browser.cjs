'use strict';
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const child=spawn('python3',['tests/layout_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','inherit']});
 let browser;
 try{
  const fixture=await new Promise((resolve,reject)=>{
   let output='';child.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))resolve(JSON.parse(output.split('\n')[0]));});
   child.on('error',reject);child.on('exit',code=>reject(Error('Fixture exited '+code)));
  });
  const token=fs.readFileSync(path.join(fixture.directory,'token'),'utf8').trim(),pid=fixture.projects.software,base='http://127.0.0.1:'+fixture.port;
  const call=async(route,body)=>{
   const response=await fetch(base+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
   const data=await response.json();assert.ok(response.ok,JSON.stringify(data));return data;
  };
  const initial=await call('view-layout?project_id='+pid);
  await call('action',{op:'view-layout.save',params:{project_id:pid,experiment_id:null,version:initial.version,board_version:initial.board_version,pages:[
   {id:'plain',title:'Plain',tiles:[{id:'overview',kind:'overview',span:12,height:450}]},
   {id:'docked',title:'Docked',left_width:280,tiles:[{id:'files',kind:'file_explorer',placement:'left',span:3,height:450},{id:'notes',kind:'overview',span:12,height:450}]}
  ]}});
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
  for(const desktop of [false,true]){
   const context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage(),errors=[];
   page.on('pageerror',error=>errors.push(error.message));
   await page.addInitScript(({pid,token,desktop})=>{
    sessionStorage.setItem('supersurfer-token',token);
    if(!localStorage.getItem('supersurfer-workspace'))localStorage.setItem('supersurfer-workspace',JSON.stringify({projectId:pid,tab:'plain',chatVisible:true,view:'workspace'}));
    if(desktop)document.addEventListener('DOMContentLoaded',()=>document.body.classList.add('desktop-app'));
   },{pid,token,desktop});
   await page.goto(base);await page.locator('[data-tab=docked]').waitFor();
   const sidebar=page.locator('.sidebar'),divider=page.locator('#sidebar-resizer');
   const drag=async(delta)=>{
    const before=await sidebar.boundingBox(),handle=await divider.boundingBox();
    assert.ok(handle.height>before.height*.9,'Sidebar divider must cover the content height');
    const x=handle.x+handle.width/2,y=handle.y+handle.height/2;
    assert.equal(await page.evaluate(({x,y})=>document.elementFromPoint(x,y)?.id,{x,y}),'sidebar-resizer','Divider must receive real pointer input');
    await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+delta,y,{steps:8});await page.mouse.up();
    const after=await sidebar.boundingBox();assert.ok(Math.abs(after.width-before.width-delta)<2,JSON.stringify({before,after,delta}));return after.width;
   };
   const wider=await drag(90);await page.reload();await page.locator('[data-tab=docked]').waitFor();assert.equal((await sidebar.boundingBox()).width,wider);
   await drag(-60);
   await divider.focus();await page.keyboard.press('Home');assert.equal((await sidebar.boundingBox()).width,160);
   await divider.dblclick();assert.equal((await sidebar.boundingBox()).width,206);
   await page.locator('[data-tab=docked]').click();await page.locator('#page-left-tiles [data-tile-id=files]').waitFor();
   const savedWidth=await drag(50);
   await page.waitForFunction(width=>document.querySelector('#sidebar-resizer')?.getAttribute('aria-valuenow')===String(width),savedWidth);
   await assert.doesNotReject(async()=>{
    for(let attempt=0;attempt<30;attempt++){
     if((await call('view-layout?project_id='+pid)).pages.find(p=>p.id==='docked').left_width===savedWidth)return;
     await new Promise(resolve=>setTimeout(resolve,100));
    }
    throw Error('Docked page width was not persisted');
   });
   await page.reload();await page.locator('#page-left-tiles [data-tile-id=files]').waitFor();assert.equal((await sidebar.boundingBox()).width,savedWidth);
   await page.locator('#left-sidebar-toggle').click();assert.equal(await divider.isVisible(),false);
   await page.locator('#left-sidebar-toggle').click();assert.equal((await sidebar.boundingBox()).width,savedWidth);
   assert.deepEqual(errors,[]);await context.close();
   console.log('PASS '+(desktop?'desktop':'browser')+' real sidebar drag, shrink, keyboard/reset, saved layout reload and collapse/restore');
  }
 }finally{await browser?.close();child.stdin.end();}
})().catch(error=>{console.error(error);process.exitCode=1;});
