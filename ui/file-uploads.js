// Finder/File-picker drops upload bytes to the connected workspace, never a local path.
export function createFileUploads({capture,onUploaded,onBusy,onError,notice}){
 const pending=new Map();let hover=null,activeUploads=0;
 const input=document.createElement('input');input.type='file';input.multiple=true;input.hidden=true;input.setAttribute('aria-label','Upload files from this computer');document.body.append(input);
 const status=document.createElement('div');status.className='upload-status';status.role='status';status.hidden=true;document.body.append(status);
 let selected=null;
 function busy(scope,amount){if(scope)pending.set(scope,Math.max(0,(pending.get(scope)||0)+amount));onBusy?.();}
 function destination(element){if(element.closest('#chat-panel'))return 'chat';if(element.closest('.code-editor,.code-tile-root,[data-tile-kind=pdf],.file-viewer-page'))return 'editor';if(element.closest('[data-tile-kind=artifacts],[data-kind=artifacts],.artifact-list,.artifact-breadcrumb,#main'))return 'editor';return null;}
 function resetHover(){hover?.classList.remove('file-drop-target');hover=null;}
 async function upload(files,context){
  if(!context)return;files=Array.from(files);if(!files.length)return;
  if(context.target==='chat'&&files.length+(context.attachmentCount||0)>8)throw new Error('A chat message can contain up to eight attachments. Remove an attachment before uploading more.');
  if(files.length>8)throw new Error('Drop up to eight files at a time.');
  if(files.some(file=>file.size>32*1024*1024))throw new Error('Each upload must be 32 MiB or smaller.');
  if(files.some(file=>file.webkitRelativePath))throw new Error('Drop individual files; folder uploads are not supported.');
  busy(context.scope,1);activeUploads++;status.hidden=false;let completed=0;
  try{for(const file of files){
   status.textContent='Uploading '+file.name+' to '+context.projectName+'…';
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),120000);
   let response;try{response=await fetch('/api/upload?'+new URLSearchParams({project_id:context.projectId,name:file.name,upload_id:crypto.randomUUID().replaceAll('-','')}),{method:'POST',headers:{'Content-Type':'application/octet-stream',...(sessionStorage.getItem('supersurfer-token')?{Authorization:'Bearer '+sessionStorage.getItem('supersurfer-token')}:{})},body:file,signal:controller.signal});}catch(error){throw new Error('Upload was not confirmed for '+file.name+'. Check Project files before retrying.');}finally{clearTimeout(timer);}
   const result=await response.json();if(!response.ok)throw new Error(result.error||'Upload failed.');completed++;
   await onUploaded(result,context);
  }notice?.(completed+' file'+(completed===1?'':'s')+' uploaded to '+context.projectName+(context.target==='chat'?'. Attached to the original chat draft.':'.'));
  }catch(error){throw new Error((completed?completed+' file(s) were uploaded. ':'')+error.message);}finally{busy(context.scope,-1);activeUploads--;status.hidden=activeUploads===0;}
 }
 input.onchange=()=>{const context=selected,files=[...input.files];input.value='';void upload(files,context).catch(onError);};
 document.addEventListener('dragover',event=>{if(!Array.from(event.dataTransfer?.types||[]).includes('Files'))return;event.preventDefault();const target=destination(event.target);event.dataTransfer.dropEffect=target?'copy':'none';resetHover();if(target){hover=event.target.closest(target==='chat'?'#chat-panel':'.code-editor,.code-tile-root,[data-tile-kind=pdf],#main');hover?.classList.add('file-drop-target');}},true);
 document.addEventListener('dragleave',event=>{if(!event.relatedTarget)resetHover();});
 document.addEventListener('drop',event=>{if(!Array.from(event.dataTransfer?.types||[]).includes('Files'))return;event.preventDefault();event.stopImmediatePropagation();resetHover();const target=destination(event.target);if(!target){onError(new Error('Drop files onto a file viewer or an agent chat.'));return;}const items=[...event.dataTransfer.items];if(items.some(item=>item.webkitGetAsEntry?.()?.isDirectory)){onError(new Error('Drop individual files; folder uploads are not supported.'));return;}try{void upload(event.dataTransfer.files,capture(target)).catch(onError);}catch(error){onError(error);}},true);
 return {pending:scope=>(pending.get(scope)||0)>0,pick(target='editor'){try{selected=capture(target);input.click();}catch(error){onError(error);}}};
}
