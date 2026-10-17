// Read-only navigation from a known, opaque reusable block in the same project.
export function connectBlockNavigation({frames,experiment,projectId,open,listen=window}){
 const handler=event=>{
  const packet=event.data;
  if(event.origin!=='null'||!packet||!['supersurfer:block:capabilities','supersurfer:block:open-results'].includes(packet.type)||typeof packet.request_id!=='string'||packet.request_id.length>100)return;
  const frame=frames().find(frame=>frame.contentWindow===event.source);
  if(!frame||frame.dataset.blockProject!==projectId())return;
  const reply=error=>event.source.postMessage({type:'supersurfer:block:navigation',request_id:packet.request_id,supported:true,...(error?{error}: {})},'*');
  if(packet.type==='supersurfer:block:capabilities'){reply();return;}
  if(Object.keys(packet).some(key=>!['type','request_id','experiment_id','result_id'].includes(key))||typeof packet.experiment_id!=='string'||packet.experiment_id.length>200||(packet.result_id!==undefined&&(typeof packet.result_id!=='string'||packet.result_id.length>100))){reply('Invalid Results navigation request');return;}
  const item=experiment(packet.experiment_id);
  if(!item||item.project_id!==projectId()){reply('Results navigation is limited to this project');return;}
  reply();Promise.resolve(open(item,packet.result_id)).catch(error=>reply(error.message));
 };
 listen.addEventListener('message',handler);return()=>listen.removeEventListener('message',handler);
}
