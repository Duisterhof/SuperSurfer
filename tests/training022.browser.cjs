'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process'),{chromium}=require('playwright'),{install}=require('./fixtures/workspace-demo.cjs');
const spec={title:'Measured training comparison',sources:[{id:'A',label:'Method A',url:'https://wandb.ai/team/project/runs/a'},{id:'B',label:'Method B',url:'https://wandb.ai/team/project/runs/b'}],plots:[{title:'Native loss',x_label:'Joint updates',y_label:'Native MSE',traces:['A','B'].flatMap(source=>[{source,metric:'loss',x:'joint',split:'training',where:{key:'phase',equals:'joint'}},{source,metric:'val/loss',x:'joint',split:'validation'}])},{title:'EEF error',x_label:'Joint updates',y_label:'EEF error (mm)',secondary:true,traces:[{source:'A',metric:'val/eef',x:'joint',split:'validation'}]}],details_html:'<h2>Requested method schematic</h2><p>Encoder → learned projection → policy</p>'};
const compiled=JSON.parse(execFileSync('python3',['-c','import json,sys;from server.training_results import compile_report;print(json.dumps(compile_report(json.load(sys.stdin))))'],{cwd:path.resolve(__dirname,'..'),input:JSON.stringify(spec),encoding:'utf8',maxBuffer:4_000_000}));
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1080}});page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await install(page);
  let slow=true,failed=false,version=1,force=0,polls=0;
  const rows=[{_step:0,joint:0,loss:16,phase:'warmup'},{_step:1,joint:1,loss:14,phase:'joint',_timestamp:100},{_step:2,joint:2,loss:13,phase:'joint',_timestamp:200},{_step:3,joint:3,loss:12,phase:'joint',_timestamp:300},{_step:4,joint:3,'val/loss':13,'val/eef':24,_timestamp:400}];
  await page.route('http://demo.test/api/results?*',route=>route.fulfill({json:{pages:[{id:'training',title:spec.title,sha256:'hash',updated:1,preview_url:'/result-preview/training',wandb_sources:compiled.wandb_sources}]}}));
  const html=compiled.html.replace('<head>','<head><script>'+fs.readFileSync(path.join(__dirname,'../ui/results-client.js'),'utf8')+'</script>');
  await page.route('http://demo.test/result-preview/training',route=>route.fulfill({contentType:'text/html',body:html,headers:{'Content-Security-Policy':"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:"}}));
  await page.route('http://demo.test/api/result-data?*',route=>{const url=new URL(route.request().url());assert.equal(url.searchParams.get('background'),'1');assert.equal(url.searchParams.get('experiment_id'),'demo-e14');if(url.searchParams.get('refresh')==='1')force++;else polls++;
   return route.fulfill({json:{loading:slow,sources:compiled.wandb_sources.map((s,i)=>({...s,rows:i&&slow?[]:rows,fetched_at:i&&slow?null:version*1000,observed_at:400,loading:!!i&&slow,stale:!!i&&failed,error:i&&failed?'Comparison source unavailable':null}))}});
  });
  await page.goto('http://demo.test/');const fl=()=>page.frameLocator('#result-preview');await fl().locator('#training-chart-0 .scatterlayer .trace').first().waitFor();
  const chart=()=>fl().locator('#training-chart-0'),rf=()=>page.frames().find(f=>f.url().includes('/result-preview/'));
  assert.equal(force,1);
  let values=await chart().evaluate(el=>({x:el.data[0].x,y:el.data[0].y,axis:el.layout.yaxis,zoom:el._context.scrollZoom}));
  assert.deepEqual(values.x,[1,2,3]);assert.deepEqual(values.y,[14,13,12]);assert.equal(values.axis.type,'linear');assert.equal(values.axis.exponentformat,'none');assert.equal(values.zoom,true);
  assert.match(await fl().locator('#freshness').innerText(),/waiting for Method B/);
  // Fast source is visible while B is pending, then B appears in the same frame.
  slow=false;await fl().getByText('Updated directly from W&B',{exact:false}).waitFor();assert.ok(polls>0);assert.equal(force,1);
  await chart().evaluate(el=>window.Plotly.relayout(el,{'xaxis.range':[1.5,2.5],'yaxis.range':[12,14]}));
  version=2;await page.locator('[data-action="refresh-results"]').click();await rf().waitForFunction(()=>JSON.parse(document.querySelector('#provenance').textContent)[0].fetched_at===new Date(2000000).toLocaleString());
  assert.equal(force,2);assert.deepEqual(await chart().evaluate(el=>el.layout.xaxis.range),[1.5,2.5]);
  await fl().locator('#smoothing').focus();await page.keyboard.press('Home');for(let i=0;i<10;i++)await page.keyboard.press('ArrowRight');
  const traces=await chart().evaluate(el=>el.data.map(t=>({name:t.name,dash:t.line.dash,y:t.y,opacity:t.opacity})));
  assert.equal(traces.length,6);assert.equal(traces[0].opacity,.2);assert.deepEqual(traces[1].y,[14,13.5,12.75]);assert.equal(traces[2].dash,'dash');assert.deepEqual(traces[2].y,[13]);
  await fl().locator('#reset').click();assert.equal(await chart().evaluate(el=>el.layout.xaxis.autorange),true);
  await fl().getByRole('button',{name:'Expand Native loss',exact:true}).click();assert.equal(await fl().locator('.panel.expanded').count(),1);await chart().click();await page.keyboard.press('Escape');assert.equal(await fl().locator('.panel.expanded').count(),0);
  await fl().locator('#secondary summary').click();await fl().locator('#training-chart-1 .scatterlayer .trace').first().waitFor();
  // Legend interaction remains functional after refresh/smoothing.
  await chart().locator('.legendtoggle').first().click();await page.waitForTimeout(350);assert.equal(await chart().evaluate(el=>el.data[1].visible),'legendonly');
  failed=true;version=3;await page.locator('[data-action="refresh-results"]').click();await fl().getByText('Some data is stale or unavailable:',{exact:false}).waitFor();assert.ok((await chart().evaluate(el=>el.data[0].y.length))>0);
  const before=force;await page.locator('[data-tab="overview"]').click();await page.locator('[data-tab="results"]').click();await fl().locator('.js-plotly-plot').first().waitFor();assert.equal(force,before+1);
  await page.setViewportSize({width:900,height:900});await fl().locator('#columns').selectOption('3');await page.waitForTimeout(150);
  assert.ok(await fl().locator('body').evaluate(el=>el.scrollWidth<=el.clientWidth+2));assert.equal(await fl().locator('#secondary').getAttribute('open'),null);
  if(process.env.SUPERSURFER_QA_OUTPUT)await page.screenshot({path:path.join(process.env.SUPERSURFER_QA_OUTPUT,'training-results-narrow.png')});assert.deepEqual(errors,[]);console.log('PASS canonical training Results: partial sources, live overlays, held-out data, decimal axes, smoothing/raw, zoom, legend, expand, refresh, stale recovery and narrow layout');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
