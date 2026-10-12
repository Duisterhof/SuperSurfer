"use strict";
const { test } = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path"), { pathToFileURL } = require("node:url");
const { ServiceAgents, sameFolder, sessionFolder } = require("../native_extension/service-agents.cjs");
test("existing research conversations load without a native host or any write", async () => {
  const calls=[];
  const api = new ServiceAgents({request:async route=>{
    calls.push(route);
    if(route==="/api/state")return {projects:[{id:"p",name:"Research",repo:"/repo"}],read_only:false};
    if(route.startsWith("/api/project-agents"))return {agents:[
      {scope:"experiment:idle",name:"Earlier work",status:"completed",updated_at:100},
      {scope:"conversation:running",name:"Worker",busy:true,status:"working",updated_at:50},
      {scope:"experiment:old",name:"Archived",archived:true},
      {scope:"agent:retired",name:"Retired",retired:true},
    ]};
    return {scope:"conversation:running",thread_id:"original",messages:[{text:"Saved history"}]};
  },action:()=>{throw Error("Read-only discovery must not send actions");}});
  const projects=await api.list();assert.equal(projects[0].agents[0].scope,"conversation:running");assert.equal(projects[0].agents.length,2);
  assert.equal((await api.chat(projects[0].agents[0].scope)).thread_id,"original");assert.equal(calls.length,3);
});
test("chat actions keep their bound scope and never switch provider/model or retry errors", async()=>{
  const sent=[];const api=new ServiceAgents({action:async(op,args)=>{sent.push({op,args});throw Error("uncertain outcome");}});
  await assert.rejects(api.action("conversation:original","chat.steer",{text:"Continue this task"}),/uncertain/);
  assert.deepEqual(sent,[{op:"chat.steer",args:{scope:"conversation:original",text:"Continue this task"}}]);
  assert.throws(()=>api.action("original","chat.send",{scope:"wrong",text:"x"}),/Unsupported/);
  assert.throws(()=>api.action("original","chat.settings",{model:"different"}),/Unsupported/);
});
test("new folder registers once and creates a blank chat without inference",async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),"ss-folder-"));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const real=path.join(dir,"project"),alias=path.join(dir,"alias");fs.mkdirSync(real);fs.symlinkSync(real,alias);
  const projects=[],calls=[];let count=0;
  const api=new ServiceAgents({request:async()=>({projects}),action:async(op,args)=>{
    calls.push({op,args});
    if(op==="project.add"){const project={...args,id:"p"};projects.push(project);return {project,initialized:true};}
    if(op==="experiment.create")return {id:"task"+(++count)};
    throw Error("No provider calls allowed");
  }});
  const first=await api.newChat(alias),second=await api.newChat(real);
  assert.equal(first.scope,"experiment:task1");assert.equal(second.scope,"experiment:task2");
  assert.equal(calls.filter(c=>c.op==="project.add").length,1);assert.equal(calls[0].args.surfboard_template,"software");
  assert.ok(sameFolder(alias,real));assert.deepEqual(sessionFolder({workingDirectories:[pathToFileURL(alias).href]}),[fs.realpathSync(real)]);
  assert.deepEqual(sessionFolder({workingDirectories:["https://example.com/project"]}),[]);
});
test("unconfirmed creation is not retried or followed by another write",async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),"ss-folder-"));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));let calls=0;
  const api=new ServiceAgents({request:async()=>({projects:[]}),action:async()=>{calls++;throw Error("disconnected");}});
  await assert.rejects(api.newChat(dir),/disconnected/);assert.equal(calls,1);
});
test("Surfboard edits stay with their existing agent and project",async()=>{
  const calls=[];const api=new ServiceAgents({request:async()=>({busy:true,steerable:true}),action:async(op,args)=>{calls.push({op,args});return {};}});
  const b={scope:"conversation:existing",project_id:"p",experiment_id:"e"};
  await api.boardAction(b,"ask",{text:"Rename the check"});
  assert.equal(calls[0].op,"chat.steer");assert.equal(calls[0].args.scope,b.scope);assert.match(calls[0].args.text,/configuration only/);
  await api.boardAction(b,"save",{project_id:"wrong",experiment_id:"wrong",scope:"wrong",board:{name:"A"},expected_version:2});
  assert.deepEqual(calls[1].args,{project_id:"p",experiment_id:"e",board:{name:"A"},expected_version:2});
});
