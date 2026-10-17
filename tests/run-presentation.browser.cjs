'use strict';
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
async function fixture(){const child=spawn('python3',['tests/run_presentation_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','pipe']});let errors='';child.stderr.on('data',data=>errors+=data);const data=await new Promise((resolve,reject)=>{let output='';child.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))resolve(JSON.parse(output.split('\n')[0]));});child.on('error',reject);child.on('exit',code=>reject(new Error('Fixture stopped '+code+' '+errors)));});return{...data,stop:()=>child.stdin.end()};}
(async()=>{let service,browser;try{
 service=await fixture();const token=fs.readFileSync(path.join(service.directory,'token'),'utf8').trim(),base='http://127.0.0.1:'+service.port;
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH||undefined,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(15000);const errors=[],mutations=[];
 page.on('pageerror',error=>errors.push(error.message));page.on('request',request=>{if(request.url().endsWith('/api/action'))mutations.push(request.postDataJSON().op);});
 await page.addInitScript(({token})=>{sessionStorage.setItem('supersurfer-token',token);localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'compute',chatVisible:false}));},{token});
 await page.goto(base);await page.locator('[data-action="filter-runs"][data-filter="finished"]').click();
 await page.locator('.run-row[data-run="r1"]').click();await page.getByRole('button',{name:'Archive retired run',exact:true}).click();
 await page.locator('[name="reason"]').fill('User-retired fixture baseline');await page.locator('[name="evidence"]').fill('Fixture stop receipt; unique evidence retained');await page.locator('[name="finished"]').check();
 await page.getByRole('button',{name:'Archive run',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
 assert.equal(await page.locator('.run-row[data-run="r1"]').count(),0);
 await page.locator('[data-action="filter-runs"][data-filter="archived"]').click();await page.locator('.run-row[data-run="r1"]').waitFor();
 await page.reload();await page.locator('[data-action="filter-runs"][data-filter="archived"]').click();await page.locator('.run-row[data-run="r1"]').click();
 await page.getByText('Retirement evidence',{exact:true}).click();await page.getByText('User-retired fixture baseline',{exact:true}).waitFor();
 const out=process.env.SUPERSURFER_QA_OUTPUT||'/tmp';await page.getByRole('button',{name:'Restore',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'run-archive-desktop.png')});
 await page.setViewportSize({width:650,height:900});await page.getByRole('button',{name:'Restore',exact:true}).scrollIntoViewIfNeeded();assert.ok(await page.locator('#modal').evaluate(el=>el.scrollWidth<=el.clientWidth+1));await page.screenshot({path:path.join(out,'run-archive-narrow.png')});
 await page.getByRole('button',{name:'Restore',exact:true}).click();await page.getByRole('button',{name:'Archive retired run',exact:true}).waitFor();
 await page.getByRole('button',{name:'Close',exact:true}).click();await page.locator('[data-action="filter-runs"][data-filter="finished"]').click();await page.locator('.run-row[data-run="r1"]').waitFor();
 await page.locator('[data-action="filter-runs"][data-filter="active"]').click();await page.locator('.run-row[data-run="r2"]').click();assert.equal(await page.getByRole('button',{name:'Archive retired run',exact:true}).count(),0);
 assert.deepEqual(mutations.filter(op=>op.startsWith('run.')),['run.presentation','run.presentation']);assert.ok(mutations.every(op=>['settings.save','run.presentation'].includes(op)));assert.deepEqual(errors,[]);
 console.log('PASS real isolated HTTP/UI archive + persisted readback + Restore, evidence preserved, active run visible, desktop/narrow; no execution mutations');
}finally{await browser?.close();service?.stop();}})().catch(error=>{console.error(error);process.exitCode=1;});
