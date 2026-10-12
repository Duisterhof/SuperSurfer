"use strict";
const {chromium}=require("playwright"),fs=require("node:fs"),path=require("node:path"),assert=require("node:assert/strict");
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1150,height:850}}),errors=[];page.on("pageerror",e=>errors.push(e.message));
  const root=path.resolve(__dirname,"../native_extension/media");
  await page.route("http://chat.test/**",route=>{
   const file=new URL(route.request().url()).pathname;
   if(file==="/")return route.fulfill({contentType:"text/html",body:`<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/chat.css"></head><body><div id="app"></div><script>window.sent=[];window.acquireVsCodeApi=()=>({postMessage:m=>sent.push(m)});window.receive=m=>window.dispatchEvent(new MessageEvent('message',{data:m}));</script><script src="/chat.js"></script></body></html>`});
   return route.fulfill({contentType:file.endsWith(".css")?"text/css":"application/javascript",body:fs.readFileSync(path.join(root,file))});
  });
  await page.goto("http://chat.test/");
  const binding={scope:"conversation:saved",project_id:"p",projectName:"Research project",name:"Evaluation agent",owner:"supersurfer"};
  let chat={scope:binding.scope,thread_id:"same-provider-thread",status:"working",busy:true,steerable:true,agent:{name:binding.name,model:"Existing model"},messages:[
   {id:"u1",role:"user",text:"Check the existing training run and report its progress.",created:100},
   {id:"a1",role:"assistant",text:"The existing run is healthy. **No restart was needed.**\n\n- Training updates are advancing.\n- The evaluation is using the same checkpoint.\n\n```text\nrun: existing-run\nstate: running\n```",created:101},
  ],activity:[{id:"tool-1",type:"commandExecution",status:"completed",text:"Read the existing run status"}],tasks:[{title:"Verify current training progress",status:"working"}],questions:[],approvals:[]};
  const update=()=>page.evaluate(({chat,binding})=>receive({type:"chat",chat,binding}),{chat,binding});
  await update();await page.getByRole("heading",{name:binding.name,exact:true}).waitFor();
  assert.deepEqual(await page.evaluate(()=>sent.filter(x=>x.op.startsWith("chat."))),[]);
  await page.getByRole("textbox",{name:"Message this agent"}).fill("Please continue");
  await update();assert.equal(await page.getByRole("textbox",{name:"Message this agent"}).inputValue(),"Please continue");
  await page.getByRole("button",{name:"Send direction"}).click();
  assert.deepEqual(await page.evaluate(()=>sent.filter(x=>x.op.startsWith("chat."))),[{op:"chat.steer",args:{text:"Please continue"}}]);
  await page.evaluate(()=>receive({type:"actionError",op:"chat.steer",message:"Delivery uncertain. Check history before retrying."}));
  await update();assert.equal(await page.evaluate(()=>sent.filter(x=>x.op==="chat.steer").length),1);
  assert.equal(await page.getByRole("textbox",{name:"Message this agent"}).inputValue(),"Please continue");
  await page.evaluate(()=>receive({type:"result",op:"chat.steer",text:"Please continue"}));assert.equal(await page.getByRole("textbox",{name:"Message this agent"}).inputValue(),"");
  await page.getByRole("button",{name:"Split view"}).click();assert.ok(await page.evaluate(()=>sent.some(x=>x.op==="split")));
  chat.questions=[{id:"question-1",status:"pending",can_answer:true,questions:[{id:"choice",question:"Which result should be summarized?",options:[{label:"Current result",description:"Use the existing run."},{label:"Previous result",description:"Use saved history."}],isOther:true}]}];await update();
  await page.getByRole("radio",{name:"Current result"}).check();await update();assert.ok(await page.getByRole("radio",{name:"Current result"}).isChecked());
  await page.getByRole("button",{name:"Answer & continue"}).click();assert.deepEqual(await page.evaluate(()=>sent.find(x=>x.op==="chat.answer").args),{question_id:"question-1",answers:{choice:["Current result"]}});
  await page.evaluate(()=>receive({type:"result",op:"chat.answer"}));chat.questions=[];
  chat.approvals=[{id:"approval-1",kind:"command",status:"pending",command:"echo example",can_approve:true}];await update();
  assert.equal(await page.evaluate(()=>sent.filter(x=>x.op==="chat.approve").length),0);await page.getByRole("button",{name:"Approve once"}).click();
  assert.deepEqual(await page.evaluate(()=>sent.find(x=>x.op==="chat.approve").args),{approval_id:"approval-1",decision:"approve"});
  await page.evaluate(()=>receive({type:"result",op:"chat.approve"}));chat.approvals=[];
  chat.messages.push({id:"malicious",role:"assistant",text:'<img src=x onerror="window.pwned=true"> [bad](javascript:alert(1))'});await update();assert.equal(await page.evaluate(()=>window.pwned),undefined);assert.equal(await page.locator(".content img").count(),0);
  chat.messages.pop();await update(); await page.getByText("Activity · 1 events",{exact:true}).click({timeout:3000});await page.getByText("commandExecution · completed",{exact:true}).click();
  chat.messages.push({id:"a2",role:"assistant",text:"The latest status is saved in this conversation. You can close the editor; the agent remains on the host.",created:102});await update();
  assert.ok(await page.locator('details[data-key="event:tool-1"]').evaluate(e=>e.open));
  const shot=process.env.SS_SERVICE_CHAT_SHOT;if(shot){fs.mkdirSync(path.dirname(shot),{recursive:true});await page.screenshot({path:shot});}
  chat.read_only=true;await update();assert.ok(await page.getByRole("textbox",{name:"Message this agent"}).isDisabled());
  assert.deepEqual(errors,[]);console.log("PASS service chat: saved history, live updates, scoped steering, draft retention, uncertain delivery, questions, approvals, split, safe rendering, read-only state");
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
