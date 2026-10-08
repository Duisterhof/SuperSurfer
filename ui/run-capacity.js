// Counts match the scheduler's owned/reserved states, including uncertain jobs.
const reserved=new Set(['starting','running','cancelling','unreachable','orphaned','launching','stopping']);
export function projectCapacity(project,runs){
 const owned=runs.filter(run=>run.project_id===project.id&&reserved.has(run.status));
 return {runs:owned.length,gpus:owned.reduce((sum,run)=>sum+(Number.isFinite(Number(run.gpu_count))?Math.max(0,Number(run.gpu_count)):0),0),gpuLimit:displayLimit(project.gpu_limit),runLimit:displayLimit(project.run_limit)};
}
export function displayLimit(value){return value==='unlimited'||Number.isSafeInteger(value)&&value>=Number.MAX_SAFE_INTEGER?'Unlimited':Number.isInteger(value)&&value>=0?String(value):'Unknown';}
export function capacityWaitReason(run,projects,runs){
 let reason=run.waiting_reason||run.error||'';const project=projects.find(row=>row.id===run.project_id);if(!project)return reason;
 const use=projectCapacity(project,runs);
 reason=reason.replace(/Project concurrent run limit reached/gi,`Concurrent run limit reached (${use.runs} / ${use.runLimit})`).replace(/Project GPU limit reached/gi,`GPU allocation limit reached (${use.gpus} / ${use.gpuLimit})`);
 return reason;
}
