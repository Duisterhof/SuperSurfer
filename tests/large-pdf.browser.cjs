/* Real authenticated PDF route and bundled viewer, in an isolated workspace. */
'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{createHash}=require('node:crypto');
const root=path.resolve(__dirname,'..');

(async()=>{
  const fixtureArgs=process.env.SUPERSURFER_TEST_SERVICE_ROOT?
    ['-c','import runpy,sys; sys.path.insert(0,sys.argv[1]); import server; runpy.run_path(sys.argv[2],run_name="__main__")',process.env.SUPERSURFER_TEST_SERVICE_ROOT,path.join(root,'tests/layout_runtime_fixture.py')]:
    ['tests/layout_runtime_fixture.py'];
  const child=spawn('python3',fixtureArgs,{cwd:root,stdio:['pipe','pipe','pipe']});
  let browser,stderr='';child.stderr.on('data',chunk=>stderr+=chunk);
  try{
    const fixture=await new Promise((resolve,reject)=>{
      let output='';child.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))resolve(JSON.parse(output.split('\n')[0]));});
      child.on('error',reject);child.on('exit',code=>reject(Error('Fixture exited '+code+' '+stderr)));
    });
    const token=fs.readFileSync(path.join(fixture.directory,'token'),'utf8').trim();
    const base='http://127.0.0.1:'+fixture.port,pid=fixture.projects.software;
    const call=async(route,body)=>{
      const reply=await fetch(base+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
      const data=await reply.json();assert.equal(reply.ok,true,'Fixture API failed: '+reply.status+' '+JSON.stringify(data));return data;
    };
    const project=(await call('state')).projects.find(project=>project.id===pid);
    const bytes=process.env.SUPERSURFER_TEST_PDF?fs.readFileSync(process.env.SUPERSURFER_TEST_PDF):require('./fixtures/pdf.cjs')(33*1024*1024);
    assert.ok(bytes.length>32*1024*1024,'Regression requires a PDF above the old cap');
    fs.writeFileSync(path.join(project.repo,'large.pdf'),bytes);
    const layout=await call('view-layout?project_id='+pid);
    await call('action',{op:'view-layout.save',params:{project_id:pid,experiment_id:null,version:layout.version,board_version:layout.board_version,pages:[{id:'writing',title:'Writing',tiles:[{id:'pdf',kind:'pdf',path:'large.pdf',span:12,height:720}]}]}});
    const route=base+'/api/code/pdf?project_id='+pid+'&path=large.pdf';
    assert.equal((await fetch(route)).status,401);
    const delivered=await fetch(route,{headers:{Authorization:'Bearer '+token}});
    assert.equal(delivered.status,200);
    const hash=value=>createHash('sha256').update(value).digest('hex');
    assert.equal(hash(Buffer.from(await delivered.arrayBuffer())),hash(bytes),'HTTP delivery must preserve full PDF bytes');
    browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
    const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];
    page.setDefaultTimeout(30000);page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript(({token,pid})=>{sessionStorage.setItem('supersurfer-token',token);localStorage.setItem('supersurfer-workspace',JSON.stringify({projectId:pid,tab:'writing',view:'workspace',chatVisible:false}));},{token,pid});
    await page.goto(base);
    const viewer=page.locator('#standalone-pdf-tile');
    await viewer.locator('.pdf-sheet canvas').waitFor();
    await page.waitForFunction(()=>document.querySelector('#standalone-pdf-tile .textLayer')?.textContent);
    const count=Number((await viewer.locator('.pdf-page-count').innerText()).replace('/','').trim());
    assert.ok(count>=2);assert.ok(await viewer.locator('.pdf-sheet canvas').first().evaluate(canvas=>canvas.width>200));
    await viewer.getByLabel('PDF page',{exact:true}).fill(String(count));
    await viewer.getByLabel('PDF page',{exact:true}).press('Tab');
    const lastPage=viewer.locator('.pdf-sheet[data-page="'+count+'"]');
    await lastPage.locator('canvas').waitFor();
    await lastPage.locator('.textLayer span').first().waitFor();
    await lastPage.locator('.textLayer span').first().evaluate(span=>{const range=document.createRange();range.selectNodeContents(span);const selected=window.getSelection();selected.removeAllRanges();selected.addRange(range);});
    await viewer.locator('.pdf-selection').waitFor({state:'visible'});
    assert.deepEqual(errors,[]);
    const out=process.env.SUPERSURFER_QA_OUTPUT||'/tmp/supersurfer-large-pdf-qa';fs.mkdirSync(out,{recursive:true});
    await page.screenshot({path:path.join(out,'large-pdf-last-page.png')});
    const download=page.waitForEvent('download');await viewer.locator('.pdf-download').click();
    const file=await download;await file.saveAs(path.join(out,'download.pdf'));
    assert.equal(hash(fs.readFileSync(path.join(out,'download.pdf'))),hash(bytes));
    console.log('PASS authenticated '+bytes.length+'-byte PDF, '+count+' pages, first/last-page canvas and selectable text, exact download, zero browser errors');
  }finally{await browser?.close();child.stdin.end();}
})().catch(error=>{console.error(error);process.exitCode=1;});
