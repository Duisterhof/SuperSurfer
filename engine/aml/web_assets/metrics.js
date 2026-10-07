/* Recorded curves stay independent of manager connectivity and queue controls. */
(() => {
  let recorded = null;
  const choices = new Map();
  const palette = ['#2166ac','#26847c','#db8737','#8865ab','#b54a52','#607845','#b779ad','#6e707b','#867a27','#2d99a1','#575dba','#a6542f'];
  const fmt = new Intl.NumberFormat(undefined,{maximumFractionDigits:4});
  function metricLabel(key) {
    return key.replaceAll('normalized_mse','MSE').replaceAll('eef_rmse_mm','EEF RMSE (mm)')
      .replaceAll('eef_mse_mm2','EEF MSE (mm²)').replaceAll('_',' ').replaceAll('/',' · ');
  }
  function family(key, evaluation) {
    if (evaluation) {
      if (key === 'success_rate') return 'Robot success (fraction)';
      if (key.endsWith('mae_deg')) return 'Joint-angle MAE (degrees)';
      if (key.endsWith('mae_m')) return 'Depth MAE (metres)';
      if (key.includes('visibility_accuracy')) return 'Visibility accuracy (fraction)';
      if (key.includes('epe')) return 'Track position error (pixels)';
      if (key.endsWith('eef_rmse_mm')) return 'End-effector RMSE (mm)';
      if (key.endsWith('eef_mse_mm2')) return 'End-effector squared error (mm²)';
      if (key.includes('action')) return 'Held-out action MSE';
      if (key.startsWith('reconstruction')) return 'Native reconstruction MSE';
      return 'Native forecast MSE';
    }
    if (key.startsWith('memory/')) return 'GPU memory (GiB)';
    if (key.startsWith('valid_examples/')) return 'Contributing examples';
    if (key==='clipped') return 'Gradient clipping (0/1)';
    if (key.includes('grad') || key.includes('encoder') || key.includes('decoder')) return 'Gradient norms';
    if (key === 'lr') return 'Learning rate';
    if (key.includes('per_second')) return 'Throughput (examples/stream/s)';
    if (key.includes('seconds')) return 'Duration (seconds)';
    if (key === 'objective') return 'Weighted training objective';
    if (key.includes('rec_') || key.includes('reconstruction')) return 'Reconstruction losses';
    if (key.includes('latent_')) return 'Latent forecast losses';
    return 'Forecast and action losses';
  }
  function chart(rows, keys, logarithmic, title, colorKeys) {
    const width=560,height=275,left=65,right=18,top=20,bottom=43;
    const values=rows.flatMap(row=>keys.map(k=>row.metrics[k]).filter(v=>Number.isFinite(v) && (!logarithmic || v>0)));
    if (!rows.length || !values.length) return el('p','No recorded values for this selection. Missing values are not zero.','empty');
    const xs=rows.map(r=>r.samples_per_stream/1e6);
    const minimum=values.reduce((a,b)=>Math.min(a,b),Infinity),maximum=values.reduce((a,b)=>Math.max(a,b),-Infinity);
    let lo=logarithmic?Math.log10(minimum):minimum,hi=logarithmic?Math.log10(maximum):maximum;
    const pad=(hi-lo||Math.max(Math.abs(hi),1))*.08;lo-=pad;hi+=pad;
    let xlo=xs.reduce((a,b)=>Math.min(a,b),Infinity),xhi=xs.reduce((a,b)=>Math.max(a,b),-Infinity);
    if(xlo===xhi)xlo=0;
    const x=v=>left+(v-xlo)/(xhi-xlo||1)*(width-left-right);
    const y=v=>height-bottom-((logarithmic?Math.log10(v):v)-lo)/(hi-lo)*(height-top-bottom);
    const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':title});
    for(let i=0;i<=4;i++) {
      const v=lo+(hi-lo)*i/4,yy=height-bottom-i*(height-top-bottom)/4;
      svg.append(svgNode('line',{x1:left,x2:width-right,y1:yy,y2:yy,class:'sr40-grid'}));
      const label=svgNode('text',{x:left-8,y:yy+4,'text-anchor':'end',class:'sr40-axis'});
      const number=logarithmic?10**v:v;label.textContent=Math.abs(number)<.001?number.toExponential(1):fmt.format(number);svg.append(label);
      const xx=left+i*(width-left-right)/4;
      const xt=svgNode('text',{x:xx,y:height-24,'text-anchor':'middle',class:'sr40-axis'});xt.textContent=fmt.format(xlo+(xhi-xlo)*i/4);svg.append(xt);
    }
    const axis=svgNode('text',{x:(left+width-right)/2,y:height-5,'text-anchor':'middle',class:'sr40-axis'});axis.textContent='Million examples per stream';svg.append(axis);
    keys.forEach(key=>{
      const index=colorKeys.indexOf(key);
      const valid=rows.filter(r=>Number.isFinite(r.metrics[key]) && (!logarithmic || r.metrics[key]>0));
      const path=svgNode('polyline',{points:valid.map(r=>`${x(r.samples_per_stream/1e6)},${y(r.metrics[key])}`).join(' '),fill:'none',stroke:palette[index%palette.length],'stroke-width':1.7});
      const description=svgNode('title');description.textContent=metricLabel(key);path.append(description);svg.append(path);
      if(valid.length) {
        const last=valid.at(-1),dot=svgNode('circle',{cx:x(last.samples_per_stream/1e6),cy:y(last.metrics[key]),r:3,fill:palette[index%palette.length]});
        const t=svgNode('title');t.textContent=`${metricLabel(key)}: ${fmt.format(last.metrics[key])} · update ${last.next_update} · ${time(last.observed_at)}`;dot.append(t);svg.append(dot);
      }
    });
    return svg;
  }
  function curvePanel(job, rows, evaluation) {
    const kind=evaluation?'evaluation':'training',stateKey=job.run_id+kind;
    const cohorts=[...new Set(rows.map(r=>r.cohort_id).filter(Boolean))];
    if(evaluation && cohorts.length>1){
      const panel=el('section',null,'panel curve-panel'),select=el('select'),holder=el('div');
      let chosen=choices.get(job.run_id+'cohort')||cohorts.at(-1);
      for(const id of cohorts){const row=rows.find(r=>r.cohort_id===id),option=el('option',row.kind==='sr40'?'Fixed40 · '+id.slice(-12):row.kind==='sr30_diagnostic'?'Diagnostic30 · '+id.slice(-12):`${row.episodes??'?'} episodes / ${row.windows??'?'} windows · ${id.slice(0,8)}`);option.value=id;option.selected=id===chosen;select.append(option);}
      select.setAttribute('aria-label','Evaluation cohort for '+job.label);
      function show(){chosen=select.value||chosen;choices.set(job.run_id+'cohort',chosen);holder.replaceChildren(curvePanel(job,rows.filter(r=>r.cohort_id===chosen),true));}
      select.addEventListener('change',show);panel.append(el('p','Choose one fixed cohort. Different cohorts are not connected.'),select,holder);show();return panel;
    }
    const groups=new Map();
    rows.forEach(r=>Object.keys(r.metrics||{}).forEach(key=>{
      const name=family(key,evaluation);if(!groups.has(name))groups.set(name,new Set());groups.get(name).add(key);
    }));
    const panel=el('section',null,'panel curve-panel');panel.append(el('h3',evaluation?'Evaluation curves':'Training curves'));
    if(!groups.size) {panel.append(el('p',evaluation?'No completed offline evaluation is available for this job.':'No mirrored training history is available yet.','empty'));return panel;}
    let state=choices.get(stateKey);
    if(!state || !groups.has(state.family)) {const first=evaluation&&groups.has('End-effector RMSE (mm)')?'End-effector RMSE (mm)':groups.has('Weighted training objective')?'Weighted training objective':groups.keys().next().value;state={family:first,log:first!=='Robot success (fraction)',selected:null};choices.set(stateKey,state);}
    const controls=el('div',null,'curve-controls'),select=el('select');select.setAttribute('aria-label',kind+' metric family for '+job.label);
    for(const name of groups.keys()) {const option=el('option',name);option.value=name;option.selected=name===state.family;select.append(option);}
    const logLabel=el('label',null,'small'),log=el('input');log.type='checkbox';log.checked=state.log;logLabel.append(log,document.createTextNode(' Log scale'));
    controls.append(select,logLabel);panel.append(controls);
    const legend=el('div',null,'curve-legend'),plot=el('div',null,'curve-plot');panel.append(legend,plot);
    function draw() {
      const all=[...groups.get(state.family)].sort();
      if(!state.selected)state.selected=new Set(all);
      legend.replaceChildren();
      all.forEach((key,index)=>{
        const label=el('label',null,'small'),check=el('input');check.type='checkbox';check.checked=state.selected.has(key);
        const name=el('span',metricLabel(key));name.style.color=palette[index%palette.length];label.append(check,name);legend.append(label);
        check.addEventListener('change',()=>{if(check.checked)state.selected.add(key);else state.selected.delete(key);draw();});
      });
      const selected=all.filter(k=>state.selected.has(k));
      plot.replaceChildren(chart(rows,selected,state.log,state.family,all));
    }
    select.addEventListener('change',()=>{state.family=select.value;state.selected=null;draw();});
    log.addEventListener('change',()=>{state.log=log.checked;draw();});draw();
    const diagnostic=job.kind==='sr30_diagnostic';
    panel.append(el('p',diagnostic?'Original 30 mapped scenes: 20 dynamics training, 1 validation and 9 outside those pools. No labelled-action overlap. This diagnostic is not fully held out and has no matched control.':evaluation?'Completed checkpoints only. Oracle uses true future fields. Different cohorts are separate measurements.':'Raw logged batches. Flow-time weighting makes training losses different from generated held-out errors. Zero values are omitted on log scale.','footnote'));
    return panel;
  }
  function table(rows) {
    const t=el('table',null,'budget-table'),body=el('tbody');rows.forEach(([k,v])=>{const row=el('tr');row.append(el('th',k),el('td',String(v)));body.append(row);});t.append(body);return t;
  }
  function context(job, group) {
    const details=el('details',null,'job-context');details.append(el('summary','Context · this job’s intervention and settings'));
    if(group==='e13') {
      if(job.kind==='sr30_diagnostic') {
        details.append(el('p','Closed-loop diagnostic on the stopped model’s coherent EMA checkpoint. The robot generates future tokens and actions from its current observations.'));
        details.append(table([['Cohort','Six trained tasks × five original mapped scenes = 30'],['Overlap','20 dynamics training; 1 dynamics validation; 9 outside those pools; 0 labelled-action overlap'],['Interpretation','Not fully held out; no matched control or E13 benefit established'],['Weights','One coherent EMA checkpoint; 16 current /256 whole-block future tokens'],['Source',job.source_revision]]));
        return details;
      }
      details.append(el('p','Fresh query model:16 current /256 whole-block future tokens. Reconstruction learns online encoders and decoders; future targets and native decoding use EMA. No E12 optimizer state was migrated.'));
      details.append(table([['Data','1250 dynamics /50 labelled action demonstrations per task; six tasks'],['Optimizer','AdamW1e-4; global128 examples/stream; two ranks; compute batch32'],['Teacher','EMA0.999 after each update; frozen parameters, predicted-token input gradients retained'],['Evaluation','60 held-out episodes /240 fixed windows; EMA; EEF RMSE in mm'],['Budget','Stopped by Bart; recorded results preserved. Original checkpoint/evaluation cadence: 250 updates']]));
    } else {
      const full=job.run_id==='run_1daa45c1af4b';
      const frozen=job.run_id==='run_fe860a3d0d84';
      const continuous=job.run_id==='run_d71f800a2ecd';
      const admission=job.run_id==='run_e01200177c90';
      let description='Amended E12 joint-codec continuation. Current 384 visual tokens retained; existing future channel maps learn jointly and pack to 256 tokens. This changes the earlier frozen-PCA objective.';
      if(full)description='Original full-field ModAR control. Current 384 visual tokens and 2304 future tokens. Native future/action prediction; no added joint-codec reconstruction objective.';
      if(frozen)description='Archived frozen compact training. Current 384 visual tokens retained; fixed PCA maps pack future fields into 256 tokens. These codec maps did not learn jointly. Later joint continuations use a different objective.';
      if(admission)description+=' This two-update run checks migration and recovery; it is not a trained-model comparison.';
      const computeBatch=frozen ? 32 : 16;
      let budget='Original 16.384M samples/stream endpoint; inherited progress included';
      if(continuous)budget='Continuous until explicit stop; inherited progress included';
      if(frozen)budget='Interrupted at update 89738; preserved archive, not an active job';
      if(admission)budget='Two validation updates from the sealed parent; no scientific score';
      details.append(el('p',description));
      details.append(table([['Data','Eight tasks; 400 action episodes nested in 3600 dynamics episodes'],['Optimizer','AdamW 1e-4; global 128 examples/stream; compute batch '+computeBatch],['Allocation',full?'Four GPUs on Trinity 3-3':frozen?'Original four-rank layout':'Eight GPUs on Trinity 3-13'],['Budget',budget],['Comparison','No completed matched final 400-scene comparison; current SR monitor is separate'],['Source',job.source_revision||'See immutable run record']]));
    }
    return details;
  }
  function jobCard(job, group, links) {
    const card=el('article',null,'panel study-job'),runtime=snapshot?.runs?.find(r=>r.id===job.run_id),status=job.latest_status||{};
    card.id=job.run_id;
    const heading=el('div',null,'section-heading');heading.append(el('h2',job.label),badge(runtime?.status||'Recorded metrics',runtime?.status==='running'?'good':'warning'));card.append(heading);
    const observation=status.utc||job.training.at(-1)?.observed_at;
    const count=status.samples_per_stream ?? job.training.at(-1)?.samples_per_stream;
    const diagnostic=job.kind==='sr30_diagnostic';
    card.append(el('p',diagnostic?'Diagnostic evaluation · source '+time(job.observed_at):(count!==undefined?examples(count)+' examples per stream · ':'')+'Last training record '+time(observation),'small freshness'));
    if(runtime?.status==='unreachable')card.append(el('p','Manager cannot currently reach the node. These are last observed metrics; this does not establish that training stopped.','warning-text'));
    if(job.error)card.append(el('p',job.error,'warning-text'));
    if(job.warnings?.length)card.append(el('p',job.warnings.join(' '),'warning-text'));
    const link=links?.find(r=>(r.aml_run_id||r.run_id)===job.run_id);
    if(link?.url && /^https:\/\/wandb\.ai\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/runs\/[A-Za-z0-9_.-]+$/.test(link.url)) {
      const anchor=el('a','W&B · all recorded metrics');anchor.href=link.url;anchor.target='_blank';anchor.rel='noopener noreferrer';card.append(anchor);
    } else card.append(el('p','W&B link pending synchronization','small muted'));
    const latest=job.evaluations.at(-1);
    if(latest) {
      const m=latest.metrics||{},tiles=el('div',null,'metric-tiles');
      const priority=k=>k.endsWith('eef_rmse_mm')?0:k==='success_rate'?0:k.includes('action')?1:2;
      const chosen=Object.keys(m).filter(k=>!k.includes('mm2')).sort((a,b)=>priority(a)-priority(b)).slice(0,12);
      chosen.forEach(key=>{const tile=el('div');tile.append(el('span',metricLabel(key),'small muted'),el('strong',Number.isFinite(m[key])?(key==='success_rate'?fmt.format(m[key]*100)+'%':fmt.format(m[key])):'Not measured'));tiles.append(tile);});card.append(tiles);
      const cohort=['sr40','sr30_diagnostic'].includes(latest.kind)?`${latest.successes} / ${latest.planned_trials} scenes`:`${latest.episodes??'?'} episodes / ${latest.windows??'?'} windows`;
      card.append(el('p',`Latest completed evaluation: update ${numeric.format(latest.next_update)} · ${cohort} · ${time(latest.observed_at)}`,'small freshness'));
    }
    const charts=el('div',null,'study-curve-grid');
    if(!diagnostic)charts.append(curvePanel(job,job.training,false));
    charts.append(curvePanel(job,job.evaluations.filter(e=>e.status==='completed'),true));card.append(charts,context(job,group));return card;
  }
  function renderGroup(group, container) {
    const value=recorded[group];
    if(!value?.runs?.length) {replace(container,[el('p',value?.error||'No metric history available yet.','empty')]);return;}
    const cards=value.runs.map(job=>jobCard(job,group,recorded.wandb?.runs));replace(container,cards);
    if(group==='e13' && !value.runs.some(job=>job.kind==='sr30_diagnostic'))container.append(el('p',value.sr30_error||'No verified closed-loop SR30 result has been published yet. Its original 30 scenes overlap dynamics training and validation; it is a separate diagnostic.','small muted'));
  }
  function renderContext(study) {
    replace('e13-overview',study.overview.map(text=>el('p',text)));
    replace('e13-losses',study.losses.map(([k,v])=>{const row=el('tr');row.append(el('th',k),el('td',v));return row;}));
    replace('e13-config',study.configuration.map(([k,v])=>{const row=el('tr');row.append(el('th',k),el('td',v));return row;}));
  }
  async function updateMetrics() {
    try {
      recorded=await request('/api/metrics');renderContext(recorded.e13.study);
      renderGroup('e12','e12-jobs');renderGroup('e13','e13-jobs');
      focusLinkedRun();
    } catch(error) {const target=e13View?'e13-jobs':'e12-jobs';if(!recorded)replace(target,[el('p','Recorded metrics unavailable: '+error.message,'warning-text')]);}
  }
  request('/api/study/e13').then(data=>renderContext(data.study)).catch(error=>notify(error.message,true));
  updateMetrics();setInterval(()=>{if(!document.hidden)updateMetrics();},60000);
  $('refresh').addEventListener('click',updateMetrics);
})();
