'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {install}=require('./fixtures/workspace-demo.cjs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const {data}=await install(page,{tab:'overview'});
  data.agent_usage={reserved_tokens:1000000,workspace_limit:20000000,agent_limit:4000000,turn_response_limit:24,turn_token_limit:1000000,turn_seconds:900,input_tokens:10000,cached_input_tokens:9000,output_tokens:200};
  await page.goto('http://demo.test/');await page.locator('[data-view=settings]').click();
  await page.getByRole('heading',{name:'Agent usage',exact:true}).waitFor();
  const section=page.locator('.settings-block').filter({has:page.getByRole('heading',{name:'Agent usage',exact:true})});
  const text=await section.innerText();
  assert.match(text,/Automatic continuation/);assert.match(text,/1,000,000 \/ 20,000,000/);
  assert.match(text,/Cached input \(included\): 9,000/);assert.match(text,/not a bill/);
  assert.deepEqual(errors,[]);console.log('Agent usage settings render with separate cached-input accounting.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
