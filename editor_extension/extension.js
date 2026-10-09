'use strict';
const vscode = require('vscode'), http = require('node:http'), path = require('node:path');
let timer, stopped=false;
function activate(context) {
  const session=vscode.workspace.getConfiguration('supersurfer').get('session');
  const endpoint=process.env.SUPERSURFER_EDITOR_ENDPOINT,token=process.env.SUPERSURFER_EDITOR_TOKEN;
  require('./spelling.cjs').activateSpelling(vscode,context);
  if(!session||!endpoint||!token)return;
  const documents=new Map(),reviews=new Map(),openingReviews=new Set(),documentChanges=new vscode.EventEmitter(),lensChanges=new vscode.EventEmitter();let sequence=0,ack=[],folderRepair=false,registeredFolder,purposeReady=false,activeEvents=Promise.resolve();
  const request=fields=>new Promise((resolve,reject)=>{
    const bytes=Buffer.from(JSON.stringify({session,...fields}));
    const req=http.request(endpoint,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json','Content-Length':bytes.length}},response=>{
      let data='';response.on('data',chunk=>{data+=chunk;if(data.length>20*1024*1024)req.destroy(new Error('Editor response too large'));});
      response.on('end',()=>{try{const result=JSON.parse(data);if(response.statusCode!==200)throw new Error(result.error||'Editor bridge failed');resolve(result);}catch(error){reject(error);}});
    });req.setTimeout(10000,()=>req.destroy(new Error('Editor bridge timed out')));req.on('error',reject);req.end(bytes);
  });
  const drafts=require('./draft-review.js').activateDraftReview(vscode,context,{request,getFolder:()=>registeredFolder});
  function virtual(name,text){const uri=vscode.Uri.parse('supersurfer-diff:/'+(++sequence)+'/'+encodeURIComponent(name));documents.set(uri.toString(),text);return uri;}
  context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider('supersurfer-diff',{onDidChange:documentChanges.event,provideTextDocumentContent:uri=>documents.get(uri.toString())||''}));
  const notifyState=()=>request({operation:'state',trusted:vscode.workspace.isTrusted,dirty:vscode.workspace.textDocuments.some(doc=>doc.isDirty)}).catch(()=>{});
  context.subscriptions.push(vscode.workspace.onDidChangeTextDocument(notifyState));
  context.subscriptions.push(vscode.workspace.onDidCloseTextDocument(doc=>{const uri=doc.uri.toString();if(openingReviews.has(uri)||vscode.workspace.textDocuments.some(other=>other!==doc&&other.uri.toString()===uri))return;documents.delete(uri);reviews.delete(uri);}));
  context.subscriptions.push(vscode.languages.registerCodeLensProvider({scheme:'supersurfer-diff'},{onDidChangeCodeLenses:lensChanges.event,provideCodeLenses(document){
    const review=reviews.get(document.uri.toString());if(!review)return [];
    return (review.data.review?.chunks||[]).flatMap(chunk=>{
      const range=new vscode.Range(Math.max(0,chunk.patch_line-1),0,Math.max(0,chunk.patch_line-1),0);
      if(chunk.state)return [new vscode.CodeLens(range,{title:chunk.state==='accepted'?'Accepted':'Rejected',command:''})];
      return ['accept',...(chunk.can_reject?['reject']:[])].map(decision=>new vscode.CodeLens(range,{title:decision==='accept'?'Accept':'Reject',command:'supersurfer.decideChunk',arguments:[document.uri.toString(),chunk.index,decision]}));
    });
  }}));
  context.subscriptions.push(vscode.commands.registerCommand('supersurfer.decideChunk',async(reviewUri,hunk,decision)=>{
    const review=reviews.get(reviewUri);if(!review)return;
    if(!registeredFolder){vscode.window.showErrorMessage('Reconnect this project editor before reviewing its changes.');return;}
    try{await request({operation:'chunk_decision',scope:review.scope,change_id:review.data.id,path:path.join(registeredFolder,review.data.path),hunk,decision,revision:review.data.review.revision});}
    catch(error){vscode.window.showErrorMessage(error.message);}
  }));
  async function selection(){
    const editor=vscode.window.activeTextEditor;if(!editor)return;
    const doc=editor.document;if(doc.uri.scheme!=='file'){vscode.window.showInformationMessage('Select text in a project source file to add it to chat.');return;}
    const range=editor.selection,text=doc.getText(range),lines=range.isEmpty?'':` · L${range.start.line+1}–${range.end.line+1}`;
    await request({operation:'selection',path:doc.uri.fsPath,label:path.basename(doc.uri.fsPath)+lines,
      text:(doc.isDirty?'Selection from unsaved editor changes.\n':'Selection from saved source.\n')+(text||'File reference: '+doc.uri.fsPath)});
  }
  context.subscriptions.push(vscode.commands.registerCommand('supersurfer.askAgent',()=>selection().catch(error=>vscode.window.showErrorMessage(error.message))));
  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(doc=>{if(doc.uri.scheme==='file')request({operation:'saved',path:doc.uri.fsPath}).catch(()=>{});}));
  context.subscriptions.push(vscode.window.registerCustomEditorProvider('supersurfer.pdf',{async openCustomDocument(uri){return {uri,dispose(){}};},async resolveCustomEditor(document,panel){panel.webview.html='<!doctype html><html><body>Opening SuperSurfer PDF viewer…</body></html>';panel.onDidChangeViewState(event=>{if(event.webviewPanel.active)request({operation:'open_pdf',path:document.uri.fsPath}).catch(()=>{});});await request({operation:'open_pdf',path:document.uri.fsPath});}},{supportsMultipleEditorsPerDocument:false}));
  context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(editor=>{
    if(!editor)return;const uri=editor.document.uri,review=reviews.get(uri.toString());
    const fields=uri.scheme==='file'?{operation:'open_source',path:uri.fsPath}:review?{operation:'review_active',scope:review.scope,change_id:review.data.id}:null;
    if(fields)activeEvents=activeEvents.catch(()=>{}).then(()=>request(fields)).catch(()=>{});
  }));
  async function command(item){
    if(item.kind==='changes')return vscode.commands.executeCommand('workbench.action.closeSidebar');
    if(item.kind==='files')return vscode.commands.executeCommand('workbench.view.explorer');
    if(item.kind==='selection')return selection();
    if(item.kind==='save')return drafts.save();
    if(item.kind==='trust')return vscode.commands.executeCommand('workbench.trust.manage');
    if(item.kind==='terminal'){
      const terminal=vscode.window.activeTerminal||vscode.window.createTerminal({name:'Terminal',cwd:vscode.workspace.workspaceFolders?.[0]?.uri});
      terminal.show();return;
    }
    if(item.kind==='ports')return vscode.commands.executeCommand('~remote.forwardedPorts.focus');
    if(item.kind==='extensions')return vscode.commands.executeCommand('workbench.view.extensions');
    if(item.kind==='settings')return vscode.commands.executeCommand('workbench.action.openSettings','@ext:'+item.extension_id);
    if(item.kind==='theme')return vscode.commands.executeCommand('workbench.action.selectTheme');
    if(item.kind==='file'){
      const doc=await vscode.workspace.openTextDocument(vscode.Uri.file(item.path));const editor=await vscode.window.showTextDocument(doc,{preview:false});
      if(item.range){const r=item.range,start=new vscode.Position(Math.max(0,(r.line||1)-1),Math.max(0,(r.column||1)-1)),end=new vscode.Position(Math.max(0,(r.endLine||r.line||1)-1),Math.max(0,(r.endColumn||r.column||1)-1));editor.selection=new vscode.Selection(start,end);editor.revealRange(editor.selection,vscode.TextEditorRevealType.InCenter);}await (activeEvents=activeEvents.catch(()=>{}).then(()=>request({operation:'open_source',path:item.path})));return;
    }
    if(item.kind==='agent_diff'){
      const row=item.data;if(typeof row.original==='string'&&typeof row.modified==='string')return vscode.commands.executeCommand('vscode.diff',virtual('Before-'+row.path,row.original),virtual('After-'+row.path,row.modified),item.title+' · '+row.path,{preview:false});const uri=vscode.Uri.parse('supersurfer-diff:/review/'+encodeURIComponent(item.scope)+'/'+encodeURIComponent(row.id)+'/'+encodeURIComponent(row.path+'.patch')),key=uri.toString();openingReviews.add(key);try{documents.set(key,row.patch||row.diff||'No patch recorded.');const doc=await vscode.workspace.openTextDocument(uri),typed=doc.languageId==='diff'?doc:await vscode.languages.setTextDocumentLanguage(doc,'diff');reviews.set(key,{data:row,scope:item.scope});documentChanges.fire(uri);lensChanges.fire();return await vscode.window.showTextDocument(typed,{preview:false});}finally{openingReviews.delete(key);}
    }
    if(item.kind==='comparison'){
      let data=item.data;
      if(!data.path){const selected=await vscode.window.showQuickPick(data.files.map(file=>({label:file.path,description:file.status})),{title:item.title,placeHolder:'Choose a changed file'});if(!selected)return;data=await request({operation:'comparison',base:data.base,head:data.head,path:selected.label});}
      if(data.binary||data.too_large)throw new Error('This comparison contains a binary or oversized file.');
      return vscode.commands.executeCommand('vscode.diff',virtual('Before-'+data.path,data.original||''),virtual('After-'+data.path,data.modified||''),item.title+' · '+data.path,{preview:false});
    }
  }
  async function poll(){
    if(stopped)return;
    try{const received=await request({operation:'poll',wait:2,folders:(vscode.workspace.workspaceFolders||[]).map(folder=>folder.uri.fsPath),trusted:vscode.workspace.isTrusted,dirty:vscode.workspace.textDocuments.some(doc=>doc.isDirty),ack});ack=[];if(typeof received.workspace_folder==='string'&&path.isAbsolute(received.workspace_folder))registeredFolder=received.workspace_folder;
      if(!folderRepair&&!vscode.workspace.workspaceFolders?.length&&typeof received.workspace_folder==='string'&&path.isAbsolute(received.workspace_folder)){folderRepair=true;const accepted=vscode.workspace.updateWorkspaceFolders(0,0,{uri:vscode.Uri.file(received.workspace_folder)});if(!accepted)await request({operation:'error',error:'The native editor could not attach its registered project folder. Reopen this panel.'});return;}
      if(!purposeReady&&['terminal','ports'].includes(received.view_kind)&&vscode.workspace.workspaceFolders?.length){purposeReady=true;setTimeout(()=>{if(!stopped)command({kind:received.view_kind}).catch(error=>request({operation:'error',error:error.message}).catch(()=>{}));},300);}
      for(const item of received.commands){try{await command(item);}catch(error){await request({operation:'error',error:error.message}).catch(()=>{});}ack.push(item.id);}
    }catch{}finally{if(!stopped)timer=setTimeout(poll,30);}
  }
  if(vscode.workspace.getConfiguration('supersurfer').get('editorOnly'))for(const command of ['workbench.action.closeSidebar','workbench.action.closeAuxiliaryBar'])vscode.commands.executeCommand(command).catch(()=>{});else vscode.commands.executeCommand('workbench.view.explorer').catch(()=>{});
  stopped=false;poll();context.subscriptions.push({dispose(){stopped=true;clearTimeout(timer);}});
}
function deactivate(){stopped=true;clearTimeout(timer);}
module.exports={activate,deactivate};
