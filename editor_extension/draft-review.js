'use strict';
const path=require('node:path'),crypto=require('node:crypto');
// Incoming edits are applied to the existing draft, never implicitly saved.
function activateDraftReview(vscode,context,{request,getFolder}){
 const records=new Map(),lenses=new vscode.EventEmitter(),decoration=vscode.window.createTextEditorDecorationType({isWholeLine:true,backgroundColor:new vscode.ThemeColor('diffEditor.insertedLineBackground'),overviewRulerColor:new vscode.ThemeColor('editorOverviewRuler.addedForeground')});
 let stopped=false,timer,busy=false;
 const key=doc=>'supersurfer-draft:'+doc.uri.toString();
 const ordinary=doc=>doc?.uri.scheme==='file'&&getFolder()&&doc.uri.fsPath.startsWith(getFolder()+path.sep);
 function persist(doc,row){void context.workspaceState.update(key(doc),doc.isDirty||row.chunks.length?{base:row.base,revision:row.revision,chunks:row.chunks,draft:doc.getText(),rebased:row.rebased}:undefined);}
 function range(doc,chunk){return new vscode.Range(doc.positionAt(chunk.start),doc.positionAt(chunk.end));}
 function redraw(){lenses.fire();for(const editor of vscode.window.visibleTextEditors){const row=records.get(editor.document.uri.toString());editor.setDecorations(decoration,(row?.chunks||[]).map(chunk=>({range:range(editor.document,chunk),hoverMessage:chunk.conflict?'Concurrent edit: choose Use incoming or Keep mine.\n\nIncoming:\n'+chunk.after.slice(0,4000):'Incoming edit · Accept keeps it in your draft; Reject restores the previous text. Neither saves the file.'})));}}
 function rowFor(doc){return records.get(doc.uri.toString());}
 async function attach(doc){
  if(!ordinary(doc)||records.has(doc.uri.toString())||doc.getText().length>2*1024*1024)return;
  const initial=doc.getText(),wasDirty=doc.isDirty,saved=context.workspaceState.get(key(doc)),row={base:saved?.base,revision:saved?.revision,chunks:saved?.chunks||[],rebased:saved?.rebased===true,loading:true};records.set(doc.uri.toString(),row);
  try{const disk=await request({operation:'buffer_read',path:doc.uri.fsPath});if(typeof row.base!=='string'){row.base=wasDirty?disk.content:initial;row.revision=row.base===disk.content?disk.revision:null;if(wasDirty&&doc.getText()!==disk.content){row.rebased=true;row.chunks.push({id:crypto.randomUUID(),start:0,end:doc.getText().length,before:doc.getText(),after:disk.content,conflict:true});}}else if(saved.draft!==doc.getText()){for(const chunk of row.chunks)chunk.edited=true;}row.loading=false;persist(doc,row);redraw();}
  catch(error){records.delete(doc.uri.toString());}
 }
 async function reconcile(doc){
  const row=rowFor(doc);if(!row||row.loading||row.saving||doc.isClosed)return;
  const version=doc.version,text=doc.getText(),disk=await request({operation:'buffer_read',path:doc.uri.fsPath});
  if(disk.revision===row.revision)return;
  const result=await request({operation:'buffer_merge',path:doc.uri.fsPath,base:row.base,content:text,revision:disk.revision});
  if(doc.version!==version||row.saving||doc.isClosed)return;
  if(row.chunks.length+result.chunks.length>400)throw new Error('Review existing incoming chunks before merging more changes.');
  const chunks=result.chunks.map(chunk=>({...chunk,id:crypto.randomUUID()})),edits=chunks.filter(chunk=>!chunk.conflict&&!chunk.already_applied);
  if(edits.length){const edit=new vscode.WorkspaceEdit();for(const chunk of edits)edit.replace(doc.uri,range(doc,chunk),chunk.after);if(!await vscode.workspace.applyEdit(edit))return;}
  // applyEdit's change event maps already-pending chunks. New chunks use the
  // original draft coordinates plus offsets from the just-applied incoming edits.
  let shift=0;for(const chunk of chunks){const start=chunk.start+shift;if(!chunk.conflict&&!chunk.already_applied)shift+=chunk.after.length-(chunk.end-chunk.start);chunk.start=start;chunk.end=start+(chunk.conflict?chunk.before.length:chunk.after.length);row.chunks.push(chunk);}
  row.base=result.content;row.revision=result.revision;row.rebased=true;persist(doc,row);redraw();
 }
 async function check(){if(stopped||busy)return;busy=true;try{for(const doc of vscode.workspace.textDocuments.filter(doc=>doc.isDirty||rowFor(doc)?.chunks.length||vscode.window.visibleTextEditors.some(editor=>editor.document===doc)).slice(0,32)){await attach(doc);if(rowFor(doc))try{await reconcile(doc);}catch{/* Keep every draft on read/merge errors; the next save reports a conflict. */}}}finally{busy=false;if(!stopped)timer=setTimeout(check,2000);}}
 async function decide(uri,id,accept){
  const doc=vscode.workspace.textDocuments.find(doc=>doc.uri.toString()===uri),row=doc&&rowFor(doc),chunk=row?.chunks.find(chunk=>chunk.id===id);if(!chunk)return;
  if(chunk.edited){if(accept){row.chunks=row.chunks.filter(row=>row.id!==id);persist(doc,row);redraw();}else vscode.window.showWarningMessage('This chunk was edited after review. Your text is preserved; inspect it before deciding.');return;}
  const current=doc.getText(range(doc,chunk)),expected=chunk.conflict?chunk.before:chunk.after;
  if(current!==expected){chunk.edited=true;persist(doc,row);redraw();return;}
  const replacement=chunk.conflict?(accept?chunk.after:null):(!accept?chunk.before:null);
  if(replacement!==null){const edit=new vscode.WorkspaceEdit();edit.replace(doc.uri,range(doc,chunk),replacement);if(!await vscode.workspace.applyEdit(edit))return;}
  row.chunks=row.chunks.filter(row=>row.id!==id);persist(doc,row);redraw();
 }
 async function save(doc=vscode.window.activeTextEditor?.document){
  if(!ordinary(doc))return vscode.commands.executeCommand('workbench.action.files.save');
  await attach(doc);const row=rowFor(doc);if(!row||row.loading)throw new Error('Draft baseline is not available yet. Retry Save after the connection recovers.');if(row.saving){row.saveAgain=true;return;}
  await reconcile(doc);if(row.chunks.some(chunk=>chunk.conflict))throw new Error('Resolve overlapping incoming edits using Use incoming or Keep mine before saving.');
  row.saving=true;try{
   if(!row.rebased){const snapshot=doc.getText();if(!await doc.save())throw new Error('The disk file changed while saving. Your draft is preserved; review the incoming edits and retry.');const saved=await request({operation:'buffer_read',path:doc.uri.fsPath});if(doc.getText()===saved.content){row.base=saved.content;row.revision=saved.revision;}else{row.base=snapshot;row.revision=null;}persist(doc,row);redraw();return;}
   if(vscode.workspace.getConfiguration('editor',doc.uri).get('formatOnSave')&&vscode.window.activeTextEditor?.document===doc)await vscode.commands.executeCommand('editor.action.formatDocument');
   const content=doc.getText(),version=doc.version;persist(doc,row);
   const result=await request({operation:'buffer_save',path:doc.uri.fsPath,content,revision:row.revision});row.base=content;row.revision=result.revision;persist(doc,row);
   // Save only the captured draft. Typing while the write is in flight remains
   // dirty and is never replaced with an older save response.
   if(doc.version===version){const latest=await request({operation:'buffer_read',path:doc.uri.fsPath});if(latest.revision===result.revision&&doc.version===version){await vscode.commands.executeCommand('workbench.action.files.revert',doc.uri);if(doc.getText()===content)row.rebased=false;if(doc.getText()!==content&&!doc.isDirty){const edit=new vscode.WorkspaceEdit();edit.replace(doc.uri,new vscode.Range(doc.positionAt(0),doc.positionAt(doc.getText().length)),content);await vscode.workspace.applyEdit(edit);}}}
   await request({operation:'saved',path:doc.uri.fsPath});persist(doc,row);redraw();
  }finally{row.saving=false;if(row.saveAgain){row.saveAgain=false;void save(doc).catch(error=>vscode.window.showErrorMessage(error.message));}}
 }
 context.subscriptions.push(decoration,lenses,vscode.languages.registerCodeLensProvider({scheme:'file'},{onDidChangeCodeLenses:lenses.event,provideCodeLenses(doc){const row=rowFor(doc);return (row?.chunks||[]).flatMap(chunk=>{const at=new vscode.Range(doc.positionAt(chunk.start),doc.positionAt(chunk.start));if(chunk.edited)return [new vscode.CodeLens(at,{title:'Edited incoming chunk · Keep current',command:'supersurfer.reviewDraftChunk',arguments:[doc.uri.toString(),chunk.id,true]})];return [true,false].map(accept=>new vscode.CodeLens(at,{title:chunk.conflict?(accept?'Use incoming':'Keep mine'):(accept?'Accept':'Reject'),command:'supersurfer.reviewDraftChunk',arguments:[doc.uri.toString(),chunk.id,accept]}));});}}),
  vscode.commands.registerCommand('supersurfer.reviewDraftChunk',(uri,id,accept)=>decide(uri,id,accept).catch(error=>vscode.window.showErrorMessage(error.message))),
  vscode.commands.registerCommand('supersurfer.saveDraft',()=>save().catch(error=>vscode.window.showErrorMessage(error.message))),
  vscode.workspace.onDidOpenTextDocument(doc=>{void attach(doc);}),vscode.workspace.onDidCloseTextDocument(doc=>{records.delete(doc.uri.toString());redraw();}),vscode.window.onDidChangeVisibleTextEditors(redraw),
  vscode.workspace.onDidChangeTextDocument(event=>{const row=rowFor(event.document);if(!row)return;for(const change of [...event.contentChanges].sort((a,b)=>b.rangeOffset-a.rangeOffset)){const start=change.rangeOffset,end=start+change.rangeLength,shift=change.text.length-change.rangeLength;for(const chunk of row.chunks){if(end<=chunk.start){chunk.start+=shift;chunk.end+=shift;}else if(start>=chunk.end)continue;else{chunk.edited=true;chunk.end=Math.max(chunk.start,chunk.end+shift);}}}persist(event.document,row);redraw();}),
  {dispose(){stopped=true;clearTimeout(timer);}});
 timer=setTimeout(check,1000);
 return {save,attachOpenDocs(){for(const doc of vscode.workspace.textDocuments)void attach(doc);}};
}
module.exports={activateDraftReview};
