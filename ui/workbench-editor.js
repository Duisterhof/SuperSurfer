/* A real Code OSS workbench per task; parked panes retain their extension host and drafts. */
export function createWorkbenchEditor(options){
 const sessions=new Map();let client=sessionStorage.getItem('supersurfer-editor-window');if(!client){client=Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join('');sessionStorage.setItem('supersurfer-editor-window',client);}let root,context,current,timer,epoch=0;
 const parking=document.createElement('div');parking.hidden=true;parking.className='workbench-parking';document.body.append(parking);
 const move=(parent,node)=>{if(node.isConnected&&parent.isConnected)parent.moveBefore(node,null);else parent.append(node);};
 const key=ctx=>[ctx.projectId,ctx.experimentId||''].join(':');
 const hasUnsaved=projectId=>[...sessions.values()].some(row=>(!projectId||row.projectId===projectId)&&row.dirty);
 const report=text=>{const status=root?.querySelector('.workbench-status');if(status){status.textContent=text||'';status.hidden=!text;}};
 const call=(kind,fields={})=>options.action('editor.command',{id:current.id,kind,...fields});
 async function poll(){
  if(!root||!current)return;const target=current,token=epoch;
  try{const data=await options.api('editor/session?'+new URLSearchParams({id:target.id,after:target.after||0}));target.dirty=data.dirty;
   if(token!==epoch)return;report(data.connected?'':'Starting editor extensions…');
   const sourceContext={...context};for(const event of data.events){if(token!==epoch)break;target.after=event.sequence;try{if(event.kind==='selection')await options.onAskAgent?.({kind:'code',project_id:event.project_id,path:event.path,label:event.label,text:event.text});if(event.kind==='saved')await options.onSave?.({projectId:event.project_id,experimentId:sourceContext.experimentId,path:event.path});if(event.kind==='error')report(event.error);}catch(error){if(token===epoch)report(error.message);}}
  }catch(error){if(token===epoch)report(error.message);}finally{if(token===epoch)timer=setTimeout(poll,1000);}
 }
 async function mount(element,ctx){
  if(root===element&&context&&key(context)===key(ctx))return true;
  unmount();root=element;context={...ctx};const token=++epoch;root.classList.add('workbench-editor');if(!Element.prototype.moveBefore){root.textContent='The VS Code workbench needs a current browser. Use the SuperSurfer desktop app, update Chrome to 133 or later, or select the built-in editor in Settings.';return false;}
  const toolbar=document.createElement('div');toolbar.className='workbench-toolbar';
  for(const [kind,label]of [['extensions','Extensions'],['theme','Theme'],['selection','Ask agent']]){const button=document.createElement('button');button.type='button';button.textContent=label;button.onclick=()=>call(kind).catch(error=>report(error.message));toolbar.append(button);}
  const location=document.createElement('code');location.textContent=ctx.repo||'';location.title=ctx.repo||'';toolbar.prepend(location);root.append(toolbar);
  const status=document.createElement('div');status.className='workbench-status';status.textContent='Opening VS Code workbench…';root.append(status);
  const slot=document.createElement('div');slot.className='workbench-frame';root.append(slot);
  try{let session=sessions.get(key(ctx));if(!session){const data=await options.action('editor.open',{project_id:ctx.projectId,experiment_id:ctx.experimentId||null,client_id:client});
    const frame=document.createElement('iframe');frame.title='VS Code workbench';frame.setAttribute('allow','clipboard-read; clipboard-write');frame.referrerPolicy='no-referrer';frame.src=data.url;
    session={...data,frame,projectId:ctx.projectId,after:0};sessions.set(key(ctx),session);
   }
   if(token!==epoch)return false;current=session;move(slot,session.frame);poll();return true;
  }catch(error){if(token===epoch)report(error.message);return false;}
 }
 function unmount(){++epoch;clearTimeout(timer);if(current?.frame?.isConnected)move(parking,current.frame);if(root){root.replaceChildren();root.classList.remove('workbench-editor');}root=null;context=null;current=null;}
 const beforeUnload=event=>{if(hasUnsaved()){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',beforeUnload);
 return {mount,unmount,hasUnsaved,refresh:poll,openFile:(path,range)=>call('file',{path,range}),showComparison:data=>call('comparison',data),showAgentChange:(scope,change_id)=>call('agent_diff',{scope,change_id}),dispose(){unmount();parking.remove();window.removeEventListener('beforeunload',beforeUnload);}};
}
