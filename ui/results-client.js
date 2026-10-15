// Injected into opted-in report documents. Only declared, read-only data is sent.
(()=>{
 const listeners=new Set(),instance=Array.from(crypto.getRandomValues(new Uint32Array(4))).join('-');let state={loading:true,sources:[],error:null};
 const request=type=>parent.postMessage({type,instance},'*');
 // This bridge is injected at view time, so already-published reports benefit
 // without rewriting their reviewed HTML. The opaque frame cannot use storage.
 let savedScale=null,scaleChanged=false,restoringScale=false;
 function restoreScale(){
  const control=document.querySelector('#training-spec')&&document.querySelector('select#scale');
  if(!control||scaleChanged||!['linear','log'].includes(savedScale)||control.value===savedScale)return;
  restoringScale=true;
  try{control.value=savedScale;control.dispatchEvent(new Event('change',{bubbles:true}));}finally{restoringScale=false;}
 }
 document.addEventListener('change',event=>{
  if(restoringScale||!document.getElementById('training-spec')||!event.target.matches('select#scale')||!['linear','log'].includes(event.target.value))return;
  scaleChanged=true;parent.postMessage({type:'supersurfer:results:scale:set',instance,scale:event.target.value},'*');
 });
 document.addEventListener('DOMContentLoaded',restoreScale,{once:true});
 window.SuperSurferResults=Object.freeze({subscribe(callback){listeners.add(callback);callback(state);return()=>listeners.delete(callback);},refresh(){request('supersurfer:results:refresh');}});
 window.addEventListener('message',event=>{
  if(event.source!==parent||event.data?.instance!==instance)return;
  if(event.data.type==='supersurfer:results:scale'){
   savedScale=event.data.scale;restoreScale();return;
  }
  if(event.data.type!=='supersurfer:results:data')return;
  state=event.data.data;for(const listener of listeners){try{listener(state);}catch(error){console.error('Result renderer failed',error);}}
 });
 request('supersurfer:results:subscribe');
})();
