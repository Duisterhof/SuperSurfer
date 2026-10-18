'use strict';
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{let browser,child;try{
 child=spawn('python3',['tests/block_navigation_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','pipe']});let stderr='';child.stderr.on('data',d=>stderr+=d);
 const service=await new Promise((resolve,reject)=>{let output='';child.stdout.on('data',d=>{output+=d;if(output.includes('\n'))resolve(JSON.parse(output.split('\n')[0]));});child.on('error',reject);child.on('exit',code=>reject(new Error('Fixture stopped '+code+' '+stderr)));});
 const token=fs.readFileSync(path.join(service.directory,'token'),'utf8').trim();browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/action'))calls.push(r.postDataJSON().op);});
 await page.addInitScript(({token,project})=>{if(window!==window.top)return;sessionStorage.setItem('supersurfer-token',token);localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId:project,tab:'overview',chatVisible:false}));},{token,project:service.project});
 await page.goto('http://127.0.0.1:'+service.port);await page.frameLocator('.html-block-frame').getByRole('button',{name:'Open current Results',exact:true}).click();
 await page.frameLocator('#result-preview').getByRole('heading',{name:'Exact current fixture evidence',exact:true}).waitFor();
 assert.equal(await page.locator('[data-result-id="'+service.result+'"].primary').count(),1);
 assert.ok(calls.every(op=>op==='settings.save'));assert.deepEqual(errors,[]);
 console.log('PASS real isolated owned block -> same-project exact current Results navigation; source/report identity retained, no execution mutations');
}finally{await browser?.close();child?.stdin.end();}})().catch(e=>{console.error(e);process.exitCode=1;});
