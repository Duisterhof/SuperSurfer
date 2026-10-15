// The opaque sandbox can access only its selected report's data and scale choice.
export function connectLiveResults({api, selection, frame}) {
 let current=null;
 const cache=new Map();
 const scaleKey=entry=>entry.experimentId+'/'+entry.id;
 const storageKey=entry=>'supersurfer-result-scale:'+scaleKey(entry);
 const validScale=scale=>scale==='linear'||scale==='log';
 function active(entry){const page=selection();return current===entry&&frame()?.contentWindow===entry.window&&page?.id===entry.id&&page?.experimentId===entry.experimentId&&page?.sha256===entry.sha256&&page?.preview_url===entry.previewUrl;}
 function post(entry,data){if(active(entry))entry.window.postMessage({type:'supersurfer:results:data',instance:entry.instance,data},'*');}
 async function restoreScale(entry){
  let scale=null;
  try{scale=localStorage.getItem(storageKey(entry));}catch{}
  try{const saved=await window.superSurferDesktop?.getResultScale?.(scaleKey(entry));if(validScale(saved))scale=saved;}catch{}
  if(active(entry)&&!entry.scaleChanged&&validScale(scale))entry.window.postMessage({type:'supersurfer:results:scale',instance:entry.instance,scale},'*');
 }
 function saveScale(entry,scale){
  entry.scaleChanged=true;
  try{localStorage.setItem(storageKey(entry),scale);}catch{}
  window.superSurferDesktop?.setResultScale?.(scaleKey(entry),scale).catch(error=>console.warn('Could not save Results scale',error));
 }
 async function refresh(){
  const entry=current;if(!entry||!active(entry)||entry.loading)return;
  entry.loading=true;post(entry,{...cache.get(entry.key),loading:true,error:null});
  try{
   const path='result-data?experiment_id='+encodeURIComponent(entry.experimentId)+'&result_id='+encodeURIComponent(entry.id)+'&background=1'+(entry.revision!=null?'&revision='+encodeURIComponent(entry.revision):'');
   let first=true;
   do {
    if(!active(entry))return;
    const data=await api(path+(first?'&refresh=1':''));first=false;
    if(!active(entry))return;
    if(cache.size>=100&&!cache.has(entry.key))cache.delete(cache.keys().next().value);
    cache.set(entry.key,data);post(entry,{...data,loading:!!data.loading,error:null});
    if(!data.loading)break;
    await new Promise(resolve=>setTimeout(resolve,400));
   }while(active(entry));
  }catch(error){post(entry,{...cache.get(entry.key),loading:false,error:error.message,stale:true});}
  finally{entry.loading=false;entry.lastChecked=Date.now();}
 }
 const onMessage=event=>{
  const page=selection(),message=event.data;
  if(!page?.wandb_sources?.length||event.source!==frame()?.contentWindow||event.origin!=='null'||!message||!['supersurfer:results:subscribe','supersurfer:results:refresh','supersurfer:results:scale:set'].includes(message.type)||typeof message.instance!=='string'||message.instance.length>100)return;
  if(message.type==='supersurfer:results:scale:set'){
   if(current&&active(current)&&current.instance===message.instance&&validScale(message.scale))saveScale(current,message.scale);
   return;
  }
  if(!current||current.window!==event.source||current.instance!==message.instance||current.id!==page.id||current.experimentId!==page.experimentId||current.sha256!==page.sha256||current.previewUrl!==page.preview_url){
   current={id:page.id,experimentId:page.experimentId,sha256:page.sha256,previewUrl:page.preview_url,revision:page.updated,key:page.experimentId+':'+page.id+':'+page.preview_url,window:event.source,instance:message.instance,loading:false,lastChecked:0};void restoreScale(current);void refresh();
  }else if(message.type==='supersurfer:results:refresh'&&Date.now()-current.lastChecked>1000)void refresh();
 };
 window.addEventListener('message',onMessage);
 return {refresh,dispose(){current=null;cache.clear();window.removeEventListener('message',onMessage);}};
}
