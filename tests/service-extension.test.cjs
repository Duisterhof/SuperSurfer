"use strict";
const {test}=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),os=require("node:os"),path=require("node:path"),Module=require("node:module");
test("VS Code opens existing agents and creates chats from an unregistered folder without an Agent Host",async t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),"ss-extension-"));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const folder=path.join(root,"new-folder");fs.mkdirSync(folder);
 const calls=[],commands=new Map(),projects=[{id:"p",name:"Research",repo:root}],opened=[];let tree,onMessage;
 const uri=p=>({fsPath:p,toString:()=>p});
 const vscode={
  EventEmitter:class{event=()=>{};fire(){}dispose(){}},TreeItem:class{constructor(label,state){this.label=label;this.collapsibleState=state;}},ThemeIcon:class{},TreeItemCollapsibleState:{Expanded:2,None:0},ViewColumn:{Active:1,Beside:2},
  Uri:{joinPath:(a,...b)=>uri(path.join(a.fsPath,...b))},
  workspace:{isTrusted:true,workspaceFolders:[{name:"New folder",uri:uri(folder)}],getConfiguration:()=>({get:()=>undefined}),getWorkspaceFolder:()=>undefined},
  window:{createOutputChannel:()=>({appendLine(){},dispose(){}}),registerTreeDataProvider:(_,value)=>{tree=value;return {dispose(){}};},
   showQuickPick:()=>{throw Error("A single current folder must not require a registered-project picker");},showErrorMessage:message=>{throw Error(message);},
   createWebviewPanel:()=>({visible:true,webview:{cspSource:"test:",asWebviewUri:v=>v,onDidReceiveMessage:fn=>{onMessage=fn;},postMessage:async m=>{}},onDidDispose(fn){this.close=fn;},onDidChangeViewState(){},dispose(){this.close?.();},reveal(){}})},
  commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};}},
 };
 class Service {
  async request(route){calls.push({route});if(route==="/api/state")return {projects,read_only:false};if(route.startsWith("/api/project-agents"))return {agents:[{scope:"conversation:original",name:"Existing worker",owner:"supersurfer",busy:true}]};if(route.startsWith("/api/chat"))return {scope:"conversation:original",thread_id:"preserved",messages:[]};throw Error(route);}
  async action(op,args){calls.push({op,args});if(op==="project.add"){const row={...args,id:"new"};projects.push(row);return row;}if(op==="experiment.create")return {id:"fresh"};throw Error("Opening a conversation must not send a turn");}
 }
 const original=Module._load;Module._load=function(name,parent,...rest){if(name==="vscode")return vscode;if(name==="./service-host-client.cjs"&&parent.filename.endsWith("extension.cjs"))return {NativeServiceChats:class {constructor(){this.provider={update(){}};} async open(binding,split){opened.push({binding,split});}}};if(name==="./service.cjs"&&parent.filename.endsWith("extension.cjs"))return {Service};return original.call(this,name,parent,...rest);};
 let extension;try{delete require.cache[require.resolve("../native_extension/extension.cjs")];extension=require("../native_extension/extension.cjs");}finally{Module._load=original;}
 const subscriptions=[],context={subscriptions,globalStorageUri:uri(path.join(root,"storage")),extensionUri:uri(path.join(__dirname,"../native_extension")),workspaceState:{get:(_,d)=>d,update:async()=>{}}};
 t.after(()=>subscriptions.forEach(s=>s?.dispose?.()));
 const app=extension.activate(context);await app.refresh();
 const project=tree.getChildren().find(x=>x.kind==="project");const row=tree.getChildren(project)[0];assert.equal(row.scope,"conversation:original");
 assert.equal(tree.getTreeItem(row).command.command,"supersurferNative.openChat");
 await commands.get("supersurferNative.openChat")(row);assert.equal(opened[0].binding.scope,"conversation:original");
 await commands.get("supersurferNative.openChatBeside")(row);assert.equal(opened[1].split,true);
 await commands.get("supersurferNative.newChat")();
 assert.deepEqual(calls.filter(x=>x.op).map(x=>x.op),["project.add","experiment.create"]);
 assert.equal(calls.find(x=>x.op==="project.add").args.repo,fs.realpathSync(folder));
 assert.equal(opened.at(-1).binding.scope,"experiment:fresh");
 assert.equal(tree.getChildren().filter(x=>x.kind==="project").length,2);
});
