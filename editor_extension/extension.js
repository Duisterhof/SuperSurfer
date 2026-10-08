'use strict';
const vscode = require('vscode'), http = require('node:http'), path = require('node:path');
let timer, stopped=false;
function activate(context) {
  const session=vscode.workspace.getConfiguration('supersurfer').get('session');
  const endpoint=process.env.SUPERSURFER_EDITOR_ENDPOINT,token=process.env.SUPERSURFER_EDITOR_TOKEN;
  require('./spelling.cjs').activateSpelling(vscode,context);
  if(!session||!endpoint||!token)return;
  const documents=new Map();let sequence=0,ack=[];
  const request=fields=>new Promise((resolve,reject)=>{
    const bytes=Buffer.from(JSON.stringify({session,...fields}));
    const req=http.request(endpoint,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json','Content-Length':bytes.length}},response=>{
      let data='';response.on('data',chunk=>{data+=chunk;if(data.length>20*1024*1024)req.destroy(new Error('Editor response too large'));});
      response.on('end',()=>{try{const result=JSON.parse(data);if(response.statusCode!==200)throw new Error(result.error||'Editor bridge failed');resolve(result);}catch(error){reject(error);}});
    });req.setTimeout(10000,()=>req.destroy(new Error('Editor bridge timed out')));req.on('error',reject);req.end(bytes);
  });
  function virtual(name,text){const uri=vscode.Uri.parse('supersurfer-diff:/'+(++sequence)+'/'+encodeURIComponent(name));documents.set(uri.toString(),text);return uri;}
  context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider('supersurfer-diff',{provideTextDocumentContent:uri=>documents.get(uri.toString())||''}));
  context.subscriptions.push(vscode.workspace.onDidCloseTextDocument(doc=>documents.delete(doc.uri.toString())));
  async function selection(){
    const editor=vscode.window.activeTextEditor;if(!editor)return;
    const doc=editor.document;if(doc.uri.scheme!=='file'){vscode.window.showInformationMessage('Select text in a project source file to add it to chat.');return;}
    const range=editor.selection,text=doc.getText(range),lines=range.isEmpty?'':` · L${range.start.line+1}–${range.end.line+1}`;
    await request({operation:'selection',path:doc.uri.fsPath,label:path.basename(doc.uri.fsPath)+lines,
      text:(doc.isDirty?'Selection from unsaved editor changes.\n':'Selection from saved source.\n')+(text||'File reference: '+doc.uri.fsPath)});
  }
  context.subscriptions.push(vscode.commands.registerCommand('supersurfer.askAgent',()=>selection().catch(error=>vscode.window.showErrorMessage(error.message))));
  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(doc=>{if(doc.uri.scheme==='file')request({operation:'saved',path:doc.uri.fsPath}).catch(()=>{});}));
  async function command(item){
    if(item.kind==='selection')return selection();
    if(item.kind==='terminal'){
      const terminal=vscode.window.activeTerminal||vscode.window.createTerminal({name:'Terminal',cwd:vscode.workspace.workspaceFolders?.[0]?.uri});
      terminal.show();return;
    }
    if(item.kind==='ports')return vscode.commands.executeCommand('remoteExplorer.toggleForwardedPortsView');
    if(item.kind==='extensions')return vscode.commands.executeCommand('workbench.view.extensions');
    if(item.kind==='settings')return vscode.commands.executeCommand('workbench.action.openSettings','@ext:'+item.extension_id);
    if(item.kind==='theme')return vscode.commands.executeCommand('workbench.action.selectTheme');
    if(item.kind==='file'){
      const doc=await vscode.workspace.openTextDocument(vscode.Uri.file(item.path));const editor=await vscode.window.showTextDocument(doc,{preview:false});
      if(item.range){const r=item.range,start=new vscode.Position(Math.max(0,(r.line||1)-1),Math.max(0,(r.column||1)-1)),end=new vscode.Position(Math.max(0,(r.endLine||r.line||1)-1),Math.max(0,(r.endColumn||r.column||1)-1));editor.selection=new vscode.Selection(start,end);editor.revealRange(editor.selection,vscode.TextEditorRevealType.InCenter);}return;
    }
    if(item.kind==='agent_diff'){
      const row=item.data,uri=virtual(row.path+'.patch',row.patch||row.diff||'No patch recorded.');const doc=await vscode.workspace.openTextDocument(uri);await vscode.languages.setTextDocumentLanguage(doc,'diff');return vscode.window.showTextDocument(doc,{preview:false});
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
    try{const received=await request({operation:'poll',dirty:vscode.workspace.textDocuments.some(doc=>doc.isDirty),ack});ack=[];
      for(const item of received.commands){try{await command(item);}catch(error){await request({operation:'error',error:error.message}).catch(()=>{});}ack.push(item.id);}
    }catch{}finally{if(!stopped)timer=setTimeout(poll,800);}
  }
  stopped=false;poll();context.subscriptions.push({dispose(){stopped=true;clearTimeout(timer);}});
}
function deactivate(){stopped=true;clearTimeout(timer);}
module.exports={activate,deactivate};
