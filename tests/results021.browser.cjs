'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {install}=require('./fixtures/workspace-demo.cjs');
(async()=>{
const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await install(page);
 const source={id:'method',url:'https://wandb.ai/team/project/runs/a',keys:['loss']};let value=1,fetched=100,broken=false,calls=0,hold=null,release=null;
 const report={id:'live-report',title:'Live training',sha256:'abc',updated:1,preview_url:'/result-preview/live',wandb_sources:[source]};
 await page.route('http://demo.test/api/results?*',route=>route.fulfill({json:{pages:[report]}}));
 const html='<!doctype html><head><script>'+fs.readFileSync(path.join(__dirname,'../ui/results-client.js'),'utf8')+'</script></head><body><h1>Live comparison</h1><input id="control" value="keep zoom"><p id="status"></p><output id="value"></output><output id="fetched"></output><script>SuperSurferResults.subscribe(s=>{document.querySelector("#status").textContent=s.loading?"Updating":s.error?"Stale: "+s.error:"Current";const r=s.sources?.[0];if(r){document.querySelector("#value").textContent=r.rows.at(-1).loss;document.querySelector("#fetched").textContent=r.fetched_at;}})</script></body>';
 await page.route('http://demo.test/result-preview/live',route=>route.fulfill({contentType:'text/html',body:html,headers:{'Content-Security-Policy':"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'"}}));
 await page.route('http://demo.test/api/result-data?*',async route=>{
  const url=new URL(route.request().url());assert.equal(url.searchParams.get('experiment_id'),'demo-e14');assert.equal(url.searchParams.get('result_id'),'live-report');assert.equal(url.searchParams.get('refresh'),'1');assert.equal(url.searchParams.get('revision'),'1');calls++;
  const captured={sources:[{...source,rows:[{_step:value,loss:value}],fetched_at:fetched,observed_at:fetched-10,stale:false,error:null}]};
  if(hold){const wait=hold;hold=null;await wait;}
  return route.fulfill({status:broken?503:200,json:broken?{error:'W&B unavailable'}:captured});
 });
 await page.goto('http://demo.test/');let frame=()=>page.frameLocator('#result-preview');await frame().locator('#value').getByText('1',{exact:true}).waitFor();assert.equal(calls,1);
 await frame().locator('#control').fill('preserved setting');value=2;fetched=200;await page.locator('[data-action="refresh-results"]').click();await frame().locator('#value').getByText('2',{exact:true}).waitFor();assert.equal(await frame().locator('#control').inputValue(),'preserved setting');assert.equal(calls,2);
 // Leaving and reopening immediately bypasses the old cache.
 value=3;fetched=300;await page.locator('[data-tab="overview"]').click();await page.locator('[data-tab="results"]').click();await frame().locator('#value').getByText('3',{exact:true}).waitFor();assert.equal(calls,3);
 // No request from an unrelated window is accepted.
 await page.evaluate(()=>postMessage({type:'supersurfer:results:subscribe',instance:'attacker',experimentId:'foreign'},'*'));await page.waitForTimeout(80);assert.equal(calls,3);
 broken=true;await page.locator('[data-action="refresh-results"]').click();await frame().getByText('Stale: W&B unavailable',{exact:true}).waitFor();assert.equal(await frame().locator('#value').innerText(),'3');assert.equal(await frame().locator('#fetched').innerText(),'300');
 broken=false;value=4;hold=new Promise(resolve=>release=resolve);await page.locator('[data-action="refresh-results"]').click();await frame().getByText('Updating',{exact:true}).waitFor();
 // A response for the removed document must not overwrite its replacement.
 await page.locator('[data-tab="overview"]').click();value=5;fetched=500;await page.locator('[data-tab="results"]').click();await frame().locator('#value').getByText('5',{exact:true}).waitFor();release();await page.waitForTimeout(100);assert.equal(await frame().locator('#value').innerText(),'5');
 let metricCalls=0;
 await page.route('http://demo.test/api/metrics?*',route=>{const url=new URL(route.request().url());assert.equal(url.searchParams.get('refresh'),'1');metricCalls++;return route.fulfill({json:{series:[{run_id:'a',run_name:'A',key:'loss',points:[{x:1,y:metricCalls},{x:2,y:metricCalls+.1}]}],runs:[{id:'a'}],updated_at:metricCalls}})});
 await page.getByRole('button',{name:'W&B metrics',exact:true}).click();await page.locator('.metric-chart svg').waitFor();const firstCount=metricCalls;
 await page.locator('[data-tab="overview"]').click();await page.locator('[data-tab="results"]').click();await page.waitForFunction(()=>document.querySelector('.metric-chart polyline')?.getAttribute('points'));await page.waitForTimeout(80);assert.equal(metricCalls,firstCount+1);
 assert.deepEqual(errors,[]);console.log('PASS live W&B on every open, force refresh, retained controls, stale-data provenance, unrelated-window rejection, and navigation race isolation');
}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
