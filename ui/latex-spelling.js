/* One offline dictionary worker. Only .tex/.latex documents enter this pipeline. */
let worker,serial=0;const pending=new Map();
function check(text,dictionary){
 if(!worker){worker=new Worker('/vendor/spelling/worker.js',{type:'module'});worker.onmessage=({data})=>{const resolve=pending.get(data.id);pending.delete(data.id);resolve?.(data);};worker.onerror=()=>{for(const resolve of pending.values())resolve({error:'Spelling dictionary could not load'});pending.clear();worker.terminate();worker=null;};}
 return new Promise(resolve=>{const id=++serial;pending.set(id,resolve);worker.postMessage({id,text,dictionary});});
}
export function createLatexSpelling(monaco,settings,saveWord){
 const records=new Map();let disposed=false;
 const provider=monaco.languages.registerCodeActionProvider('latex',{providedCodeActionKinds:['quickfix'],provideCodeActions(model,range,context){
  const row=records.get(model);if(!row)return {actions:[],dispose(){}};
  const actions=[];for(const marker of context.markers.filter(marker=>marker.source==='Spelling')){
   const item=row.errors?.find(item=>item.startLineNumber===marker.startLineNumber&&item.startColumn===marker.startColumn);if(!item)continue;
   for(const suggestion of item.suggestions)actions.push({title:'Change to “'+suggestion+'”',kind:'quickfix',diagnostics:[marker],edit:{edits:[{resource:model.uri,versionId:model.getVersionId(),textEdit:{range:marker,text:suggestion}}]}});
   actions.push({title:'Add “'+item.word+'” to workspace dictionary',kind:'quickfix',diagnostics:[marker],command:{id:'supersurfer.spelling.ignore',title:'Add to dictionary',arguments:[item.word]}});
  }return {actions,dispose(){}};
 }});
 const command=monaco.editor.registerCommand('supersurfer.spelling.ignore',(_accessor,word)=>saveWord(word));
 async function run(model,row){const version=model.getVersionId();if(disposed||model.isDisposed())return;if(!settings().latex_spellcheck){monaco.editor.setModelMarkers(model,'latex-spelling',[]);return;}
  const data=await check(model.getValue(),settings().dictionary);if(disposed||model.isDisposed()||version!==model.getVersionId()||!settings().latex_spellcheck)return;
  row.errors=(data.errors||[]).map(item=>{const start=model.getPositionAt(item.offset),end=model.getPositionAt(item.offset+item.length);return {...item,startLineNumber:start.lineNumber,startColumn:start.column,endLineNumber:end.lineNumber,endColumn:end.column};});
  monaco.editor.setModelMarkers(model,'latex-spelling',row.errors.map(item=>({...item,message:'Unknown word: '+item.word,source:'Spelling',severity:monaco.MarkerSeverity.Info})));
 }
 function schedule(model,row){clearTimeout(row.timer);row.timer=setTimeout(()=>run(model,row),450);}
 return {watch(model,path){if(!/\.(tex|latex)$/i.test(path)||records.has(model))return;const row={};records.set(model,row);row.listener=model.onDidChangeContent(()=>schedule(model,row));schedule(model,row);},refresh(){for(const [model,row]of records)schedule(model,row);},dispose(){disposed=true;provider.dispose();command.dispose();for(const [model,row]of records){clearTimeout(row.timer);row.listener.dispose();if(!model.isDisposed())monaco.editor.setModelMarkers(model,'latex-spelling',[]);}records.clear();}};
}
