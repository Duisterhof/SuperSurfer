// Injected into opted-in report documents. Only declared, read-only data is sent.
(()=>{
 const listeners=new Set(),instance=Array.from(crypto.getRandomValues(new Uint32Array(4))).join('-');let state={loading:true,sources:[],error:null};
 const request=type=>parent.postMessage({type,instance},'*');
 window.SuperSurferResults=Object.freeze({subscribe(callback){listeners.add(callback);callback(state);return()=>listeners.delete(callback);},refresh(){request('supersurfer:results:refresh');}});
 window.addEventListener('message',event=>{
  if(event.source!==parent||event.data?.type!=='supersurfer:results:data'||event.data.instance!==instance)return;
  state=event.data.data;for(const listener of listeners){try{listener(state);}catch(error){console.error('Result renderer failed',error);}}
 });
 request('supersurfer:results:subscribe');
})();
