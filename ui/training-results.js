(()=>{
 'use strict';
 const spec=JSON.parse(document.getElementById('training-spec').textContent),byId=new Map(),panels=[],palette=['#2463de','#d47713','#26906c','#9860bb','#bd4d64','#378997'];
 const $=id=>document.getElementById(id),finite=v=>typeof v==='number'&&Number.isFinite(v),local=t=>finite(t)?new Date(t*1000).toLocaleString():'unknown';
 let latest={loading:true,sources:[]},seen=false,lastRendered='';
 spec.sources.forEach((source,index)=>{byId.set(source.id,{...source,color:palette[index]});const link=document.createElement('a');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=source.label+' ↗';$('source-links').append(link,document.createTextNode('  '));});
 $('provenance-note').textContent=(spec.provenance||'')+' Histories are sampled, with a separately fetched recent tail and sparse held-out observations. A refresh time is not a measurement time. Solid lines are training; dashed lines are validation; dotted lines are test. Smoothing applies only to training and retains faint raw values.';
 if(spec.missing_measurements?.length){$('gaps').hidden=false;$('gaps').textContent='Reported gaps at publication: '+spec.missing_measurements.join(' · ');}
 for(const [index,plot] of spec.plots.entries()){
  const panel=document.createElement('section');panel.className='panel';
  const header=document.createElement('div');header.className='panel-header';const title=document.createElement('h2');title.textContent=plot.title;const expand=document.createElement('button');expand.textContent='Expand';expand.setAttribute('aria-label','Expand '+plot.title);header.append(title,expand);
  const chart=document.createElement('div');chart.className='chart';chart.id='training-chart-'+index;chart.innerHTML='<p class="chart-wait">Waiting for measurements…</p>';
  const missing=document.createElement('div');missing.className='missing';const caption=document.createElement('div');caption.className='caption';caption.textContent=plot.caption||'';
  panel.append(header,chart,missing,caption);$(plot.secondary?'secondary-plots':'plots').append(panel);if(plot.secondary)$('secondary').hidden=false;
  const entry={plot,panel,chart,missing,index};panels.push(entry);
  expand.onclick=()=>{const open=!panel.classList.contains('expanded');for(const p of panels){p.panel.classList.remove('expanded');p.panel.querySelector('button').textContent='Expand';}panel.classList.toggle('expanded',open);expand.textContent=open?'Close':'Expand';if(chart.data)Plotly.Plots.resize(chart);};
  new ResizeObserver(()=>{if(chart.data)Plotly.Plots.resize(chart);}).observe(chart);
 }
 function traceData(trace){
  const source=byId.get(trace.source),rows=(source.rows||[]).filter(r=>(!trace.where||r[trace.where.key]===trace.where.equals)&&finite(r[trace.x])&&finite(r[trace.metric])).sort((a,b)=>a[trace.x]-b[trace.x]);
  const alpha=Number($('smoothing').value),raw=rows.map(r=>r[trace.metric]*(trace.y_scale||1));let previous;
  const values=raw.map(v=>previous=previous===undefined||trace.split!=='training'?v:alpha*previous+(1-alpha)*v);
  const label=source.label+' · '+(trace.label||trace.split),base={uid:trace.source+':'+trace.metric+':'+trace.split,name:label,type:'scatter',x:rows.map(r=>(r[trace.x]-(trace.x_offset||0))*(trace.x_scale||1)),y:values,
   mode:trace.split==='training'&&rows.length>1?'lines':'lines+markers',connectgaps:false,
   line:{color:source.color,width:1.8,dash:trace.split==='training'?'solid':trace.split==='validation'?'dash':'dot'},marker:{size:6},
   customdata:rows.map((r,index)=>[raw[index],local(r._timestamp)]),hovertemplate:'%{x}<br>Value %{y}<br>Raw %{customdata[0]}<br>%{customdata[1]}<extra></extra>'};
  // Do not turn a widely missing interval into an apparent observation.
  const differences=base.x.slice(1).map((x,i)=>x-base.x[i]).filter(x=>x>0).sort((a,b)=>a-b),gap=differences[Math.floor(differences.length/2)]*5;
  if(trace.split==='training'&&gap>0){for(let i=base.x.length-1;i>0;i--)if(base.x[i]-base.x[i-1]>gap){base.x.splice(i,0,null);base.y.splice(i,0,null);base.customdata.splice(i,0,[null,'Missing interval']);}}
  if(alpha&&trace.split==='training')return [{...base,uid:base.uid+':raw',y:base.customdata.map(v=>v[0]),opacity:.2,showlegend:false,hoverinfo:'skip'},base];
  return [base];
 }
 function draw(){
  const signature=JSON.stringify([$('scale').value,$('smoothing').value,[...byId.values()].map(s=>[s.id,s.fetched_at,s.error,s.rows?.length])]);
  if(signature===lastRendered)return;lastRendered=signature;
  for(const {plot,chart,missing,index} of panels){
   const traces=plot.traces.flatMap(traceData),measured=traces.flatMap(t=>t.y).filter(finite),positive=measured.filter(v=>v!==0).map(Math.abs),size=Math.max(...positive,0);
   const precision=size?Math.min(15,Math.max(0,4-Math.floor(Math.log10(size)))):3;
   missing.textContent=plot.traces.filter(t=>!traceData(t).some(trace=>trace.x.length)).map(t=>byId.get(t.source).label+' '+(t.label||t.split)+': no recorded measurements for '+t.metric).join(' · ');
   if(!chart.data)chart.replaceChildren();
   Plotly.react(chart,traces,{uirevision:index+':'+$('scale').value,margin:{l:78,r:20,t:35,b:68},paper_bgcolor:'white',plot_bgcolor:'white',font:{family:'system-ui',size:11,color:'#334155'},dragmode:'pan',hovermode:'x unified',legend:{orientation:'h',y:1.1,x:0},
    xaxis:{title:{text:plot.x_label,standoff:12},gridcolor:'#edf1f5',zeroline:false,tickformat:',.8~f',exponentformat:'none'},
    yaxis:{title:{text:plot.y_label,standoff:12},gridcolor:'#edf1f5',zeroline:false,type:$('scale').value,tickformat:',.'+precision+'~f',exponentformat:'none',showexponent:'none'},
    annotations:!measured.length?[{text:latest.loading?'Waiting for measurements…':'No measured values available',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}]:[]},
    {responsive:true,scrollZoom:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d'],toImageButtonOptions:{format:'svg',filename:'training-comparison'}}).catch(error=>{missing.textContent='Plot could not render: '+error.message;});
  }
 }
 function update(status){
  seen=true;latest=status;
  for(const source of status.sources||[]){const previous=byId.get(source.id);if(previous)byId.set(source.id,{...previous,...source,rows:source.fetched_at!=null?source.rows:previous.rows||[]});}
  const errors=[status.error,...[...byId.values()].map(s=>s.error?s.label+': '+s.error:null)].filter(Boolean),pending=(status.sources||[]).filter(s=>s.loading).map(s=>byId.get(s.id)?.label||s.id);
  $('freshness').textContent=(errors.length?'Some data is stale or unavailable: '+errors.join('; '):status.loading?'Updating from W&B'+(pending.length?' · waiting for '+pending.join(', '):''):'Updated directly from W&B')+' · '+[...byId.values()].map(s=>s.label+' sample '+local(s.observed_at)).join(' · ');
  $('provenance').textContent=JSON.stringify([...byId.values()].map(({id,url,label,fetched_at,observed_at,loading,stale,error,rows})=>({id,url,label,fetched_at:local(fetched_at),latest_sample:local(observed_at),loading:!!loading,stale:!!status.error||!!stale,error:status.error||error||null,samples:rows?.length||0})),null,2);
  draw();
 }
 $('refresh').onclick=()=>window.SuperSurferResults?.refresh();$('scale').onchange=draw;$('smoothing').oninput=()=>{$('smoothing-value').textContent=$('smoothing').value;draw();};
 $('columns').onchange=()=>{document.documentElement.style.setProperty('--columns',$('columns').value);};
 $('reset').onclick=()=>panels.forEach(({chart})=>{if(chart.data)Plotly.relayout(chart,{'xaxis.autorange':true,'yaxis.autorange':true});});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')for(const {panel} of panels){panel.classList.remove('expanded');panel.querySelector('button').textContent='Expand';}});
 if(window.SuperSurferResults)SuperSurferResults.subscribe(update);else $('freshness').textContent='The live-data connection is unavailable. Reload the SuperSurfer window to load its current interface.';
 setTimeout(()=>{if(!seen||!(latest.sources||[]).length)$('freshness').textContent='Still waiting for the live-data connection. Reload the SuperSurfer window, then reopen Results. Existing runs are unaffected.';},15000);
})();
