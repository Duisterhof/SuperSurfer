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
 // Remember visibility by plot and measured series, not Plotly's array index.
 // Indices change when a report adds a curve, reorders plots or enables smoothing.
 let hidden=new Set(),legendChanged=false;
 const charts=new Map();
 function connectLegends(){
  const node=document.getElementById('training-spec');if(!node)return;
  let spec;try{spec=JSON.parse(node.textContent);}catch{return;}
  function attach(){
   for(const [index,plot] of spec.plots.entries()){
    const chart=document.getElementById('training-chart-'+index);
    if(!chart?.on||charts.has(chart))continue;
    const keys=new Map(plot.traces.map(trace=>[
     trace.source+':'+trace.metric+':'+trace.split,
     JSON.stringify([plot.title,plot.x_label,plot.y_label,spec.sources.find(s=>s.id===trace.source)?.url,trace.metric,trace.split,trace.x,trace.where?.key??null,trace.where?.equals??null])
    ]));
    const key=trace=>keys.get(trace.uid)||keys.get(trace.uid?.replace(/:raw$/,''));
    let restoring=false,timer;
    function restore(){
     timer=null;if(restoring||!chart.data)return;
     const indices=[],visible=[];
     chart.data.forEach((trace,index)=>{
      if(!key(trace))return;
      const value=hidden.has(key(trace))?'legendonly':true;
      if((trace.visible??true)!==value){indices.push(index);visible.push(value);}
     });
     if(!indices.length)return;
     restoring=true;
     Promise.resolve(Plotly.restyle(chart,{visible},indices)).catch(error=>console.warn('Could not restore Results legend',error)).finally(()=>{restoring=false;});
    }
    // Plotly emits afterplot before restyle. Wait until its legend operation has
    // finished before restoring; otherwise a click would undo itself.
    const schedule=()=>{clearTimeout(timer);timer=setTimeout(restore,0);};
    charts.set(chart,schedule);
    chart.on('plotly_afterplot',schedule);
    chart.on('plotly_restyle',([update])=>{
     if(restoring||!Object.hasOwn(update,'visible'))return;
     for(const trace of chart.data){
      if(!keys.has(trace.uid))continue; // Raw companions follow their main curve.
      if(trace.visible==='legendonly'||trace.visible===false)hidden.add(key(trace));else hidden.delete(key(trace));
     }
     legendChanged=true;
     parent.postMessage({type:'supersurfer:results:legend:set',instance,hidden:[...hidden]},'*');
     schedule();
    });
    schedule();
   }
   if(charts.size===spec.plots.length)observer.disconnect();
  }
  const observer=new MutationObserver(attach);
  observer.observe(document.body,{childList:true,subtree:true});attach();
 }
 document.addEventListener('DOMContentLoaded',connectLegends,{once:true});
 window.SuperSurferResults=Object.freeze({subscribe(callback){listeners.add(callback);callback(state);return()=>listeners.delete(callback);},refresh(){request('supersurfer:results:refresh');}});
 window.addEventListener('message',event=>{
  if(event.source!==parent||event.data?.instance!==instance)return;
  if(event.data.type==='supersurfer:results:scale'){
   savedScale=event.data.scale;restoreScale();return;
  }
  if(event.data.type==='supersurfer:results:legend'){
   if(!legendChanged&&Array.isArray(event.data.hidden)){
    hidden=new Set(event.data.hidden);for(const schedule of charts.values())schedule();
   }
   return;
  }
  if(event.data.type!=='supersurfer:results:data')return;
  state=event.data.data;for(const listener of listeners){try{listener(state);}catch(error){console.error('Result renderer failed',error);}}
 });
 request('supersurfer:results:subscribe');
})();
