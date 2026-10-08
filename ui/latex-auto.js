/* Save-triggered compilation also works when the PDF pane is on another page. */
export function createLatexAutoCompile(options){
 const pending=new Map(),terminal=new Set(['succeeded','failed','cancelled','timed_out','interrupted']);
 function enabled(key){try{return (localStorage.getItem('supersurfer-latex-auto:'+key)??String(options.editorSettings?.get().latex_auto_compile??true))==='true';}catch{return options.editorSettings?.get().latex_auto_compile!==false;}}
 async function drain(row){
  if(row.running)return;row.running=true;let deadline=Date.now()+10*60*1000;
  try{
   while(row.pending&&enabled(row.key)&&!options.readOnly?.()){
    if(options.hasUnsaved?.(row.projectId)){row.pending=false;return;}
    const status=await options.api('latex?'+new URLSearchParams({project_id:row.projectId,...(row.experimentId?{experiment_id:row.experimentId}:{})}));
    if(!status.blocks?.length||status.capabilities?.available===false){row.pending=false;return;}
    const block=status.blocks.find(block=>block.node_id===row.nodeId)||(status.blocks.length===1?status.blocks[0]:null);
    if(!block)throw new Error('Choose the LaTeX block in the PDF view before compiling on save.');
    if([status.build,...(status.builds||[])].some(build=>build&&!terminal.has(build.status))){if(Date.now()>deadline)throw new Error('A LaTeX build is still active. Compile the latest save from the PDF view when it finishes.');await new Promise(resolve=>setTimeout(resolve,1000));continue;}
    // Coalesce all saves received before launch into one build. A subsequent
    // save waits for this build and launches exactly one follow-up.
    row.pending=false;
    await options.action('latex.action',{project_id:row.projectId,...(row.experimentId?{experiment_id:row.experimentId}:{}),operation:'start',node_id:block.node_id,main_file:row.main||block.main_file||'main.tex',source_dir:row.sourceDir||'',request_id:'latex_'+crypto.randomUUID().replaceAll('-','')});
   }
  }finally{row.running=false;if(!row.pending)pending.delete(row.key);}
 }
 return {saved(record,choice={}){if(!/\.(tex|latex|bib|sty|cls)$/i.test(record.path||'')||record.path.startsWith('artifact:'))return;
  const key=record.projectId+':'+(record.experimentId||'');if(!enabled(key)||options.readOnly?.())return;
  let row=pending.get(key);if(!row){row={...record,...choice,key,pending:false,running:false};pending.set(key,row);}row.pending=true;return drain(row);
 }};
}
