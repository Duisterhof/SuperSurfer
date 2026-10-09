const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function agentReviewControls(change,scope,{readOnly=false,busy=false}={}){
 const state=change.review_decision?.state;if(['accepted','rejected','mixed'].includes(state))return `<span class="agent-review-result">${state==='mixed'?'Reviewed':state==='accepted'?'Accepted':'Rejected'}</span>`;
 const disabled=readOnly||busy,fields=`data-agent-change="${esc(change.id)}" data-agent-scope="${esc(scope)}"`;
 return `<button type="button" class="button small-button" data-agent-decision="accept" ${fields}${disabled||change.review?.can_accept===false?' disabled':''}>Accept all</button><button type="button" class="button small-button" data-agent-decision="reject" ${fields}${disabled||change.review?.can_reject===false?' disabled':''} title="${esc(change.review?.reason||'Undo the recorded edit, preserving unrelated source changes')}">Reject all</button>${change.review?.reason?`<span class="agent-review-reason">${esc(change.review.reason)}</span>`:''}`;
}
export async function decideAgentEdit({api,action,projectId,scope,changeId,decision,hunk,change,hasUnsaved,isCurrent}){
 if(decision==='reject'&&await hasUnsaved?.())throw new Error('Save your open editor changes before rejecting an agent edit.');
 const data=change||await api('code/agent-diff?'+new URLSearchParams({project_id:projectId,scope,change_id:changeId}));
 if(isCurrent&&!isCurrent())throw new Error('Return to the original editor before deciding this change.');
 return action('code.decide',{project_id:projectId,scope,change_id:changeId,decision,revision:data.review?.revision??null,...(hunk===undefined?{}:{hunk})});
}

export function agentChunkControls(change,scope,chunk,{readOnly=false}={}){
 if(chunk.state)return `<span class="agent-review-result">${chunk.state==='accepted'?'Accepted':'Rejected'}</span>`;
 const fields=`data-agent-change="${esc(change.id)}" data-agent-scope="${esc(scope)}" data-agent-hunk="${chunk.index}"`;
 return `<button type="button" data-agent-decision="accept" ${fields}${readOnly?' disabled':''}>Accept</button><button type="button" data-agent-decision="reject" ${fields}${readOnly||!chunk.can_reject?' disabled':''} title="${esc(chunk.reason||'Undo only this chunk')}">Reject</button>`;
}
export function addAgentChunkZones(editor,change,scope,options={}){
 editor.changeViewZones(accessor=>{for(const chunk of change.review?.chunks||[]){
  const node=document.createElement('div');node.className='agent-chunk-controls';node.innerHTML=`<span>Lines ${chunk.new_start}–${Math.max(chunk.new_start,chunk.new_start+chunk.new_count-1)}</span>`+agentChunkControls(change,scope,chunk,options);
  accessor.addZone({afterLineNumber:Math.max(0,chunk.patch_line-1),heightInPx:30,domNode:node,suppressMouseDown:false});
 }});
}
