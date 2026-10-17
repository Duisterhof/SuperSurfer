/* Compile on Save with real containment and files above the old size limits. */
'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..');
(async()=>{
  const child=spawn('python3',['tests/writing_runtime_fixture.py','--large-source'],{cwd:root,stdio:['pipe','pipe','pipe']});
  let browser,stderr='';child.stderr.on('data',chunk=>stderr+=chunk);
  try{
    const fixture=await new Promise((resolve,reject)=>{let output='';child.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))resolve(JSON.parse(output.split('\n')[0]));});child.on('error',reject);child.on('exit',code=>reject(Error('Fixture exited '+code+' '+stderr)));});
    assert.equal(fixture.compiler.available,true);
    const token=fs.readFileSync(path.join(fixture.directory,'token'),'utf8').trim(),base='http://127.0.0.1:'+fixture.port;
    const status=async()=>{const response=await fetch(base+'/api/latex?'+new URLSearchParams({project_id:fixture.project,main_file:'main.tex'}),{headers:{Authorization:'Bearer '+token}});assert.equal(response.status,200);return response.json();};
    browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
    const page=await browser.newPage({viewport:{width:1680,height:1050}}),errors=[],pdfReads=[];
    page.setDefaultTimeout(30000);page.on('pageerror',error=>errors.push(error.message));
    page.on('response',response=>{if(response.url().includes('/latex-output/'))pdfReads.push(response.url());});
    await page.addInitScript(({token,pid})=>{sessionStorage.setItem('supersurfer-token',token);localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId:pid,tab:'writing',chatVisible:false}));},{token,pid:fixture.project});
    await page.goto(base);
    await page.locator('[data-latex="compile"]:not([disabled])').waitFor();
    await page.locator('[data-latex-auto]').check();
    await page.locator('[data-tile-file="main.tex"]').first().click();
    await page.locator('.monaco-editor').waitFor();
    await page.locator('[data-latex="compile"]').click();
    async function complete(after){const deadline=Date.now()+150000;while(Date.now()<deadline){const data=await status(),row=data.build;if(row&&row.build_id!==after){assert.ok(!['failed','cancelled','interrupted','timed_out'].includes(row.status),JSON.stringify({status:row.status,error:row.error,logs:row.logs?.slice(-2000)}));if(row.status==='succeeded')return row;}await new Promise(resolve=>setTimeout(resolve,500));}throw Error('No successful new build');}
    const before=await complete();assert.ok(before.pdf_size>50*1024*1024);assert.equal(before.stale,false);
    await page.locator('.pdf-sheet canvas').first().waitFor();
    const initial=fs.readFileSync(path.join(fixture.repo,'main.tex'),'utf8');
    const marker='% verified editor Save starts a fresh full build';
    await page.evaluate(async marker=>{const monaco=await import('/vendor/monaco/editor.js');const model=monaco.editor.getModels().find(model=>model.uri.path.endsWith('/main.tex'));model.setValue(model.getValue()+'\n'+marker+'\n');},marker);
    assert.equal(fs.readFileSync(path.join(fixture.repo,'main.tex'),'utf8'),initial);
    await page.locator('[data-code="save"]').click();
    const after=await complete(before.build_id);assert.equal(after.stale,false);assert.notEqual(after.source_fingerprint,before.source_fingerprint);
    assert.ok(fs.readFileSync(path.join(fixture.repo,'main.tex'),'utf8').includes(marker));
    await page.waitForFunction(id=>document.querySelector('[data-latex-history] option:nth-child(2)')?.value===id,after.build_id);
    const deadline=Date.now()+30000;while(!pdfReads.some(url=>url.endsWith(after.pdf_url))&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,100));
    assert.ok(pdfReads.some(url=>url.endsWith(after.pdf_url)),'Viewer must fetch the new build PDF');
    await page.locator('.textLayer span').first().waitFor();assert.deepEqual(errors,[]);
    const out=process.env.SUPERSURFER_QA_OUTPUT||'/tmp/supersurfer-large-latex-qa';fs.mkdirSync(out,{recursive:true});
    await page.screenshot({path:path.join(out,'compile-on-save.png')});
    fs.writeFileSync(path.join(out,'receipts.json'),JSON.stringify({before:{build_id:before.build_id,status:before.status,pdf_size:before.pdf_size},after:{build_id:after.build_id,status:after.status,pdf_size:after.pdf_size,source_state:after.source_state},pages:await page.locator('.pdf-page-count').innerText()},null,2));
    console.log('PASS full compilation, editor Save, new current-source build, refreshed PDF ('+after.pdf_size+' bytes), selectable text and no browser errors');
  }finally{await browser?.close();child.stdin.end();}
})().catch(error=>{console.error(error);process.exitCode=1;});
