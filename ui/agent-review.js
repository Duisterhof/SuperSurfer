const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function agentReviewControls(change,scope,{readOnly=false,busy=false}={}){
 const state=change.review_decision?.state;if(['accepted','rejected'].includes(state))return `<span class="agent-review-result">${state==='accepted'?'Accepted':'Rejected'}</span>`;
 const disabled=readOnly||busy,fields=`data-agent-change="${esc(change.id)}" data-agent-scope="${esc(scope)}"`;
 return `<button type="button" class="button small-button" data-agent-decision="accept" ${fields}${disabled||change.review?.can_accept===false?' disabled':''}>Accept edit</button><button type="button" class="button small-button" data-agent-decision="reject" ${fields}${disabled||change.review?.can_reject===false?' disabled':''} title="${esc(change.review?.reason||'Undo the recorded edit, preserving unrelated source changes')}">Reject edit</button>${change.review?.reason?`<span class="agent-review-reason">${esc(change.review.reason)}</span>`:''}`;
}
export async function decideAgentEdit({api,action,projectId,scope,changeId,decision,change,hasUnsaved,isCurrent}){
 if(decision==='reject'&&await hasUnsaved?.())throw new Error('Save your open editor changes before rejecting an agent edit.');
 const data=change||await api('code/agent-diff?'+new URLSearchParams({project_id:projectId,scope,change_id:changeId}));
 if(isCurrent&&!isCurrent())throw new Error('Return to the original editor before deciding this change.');
 return action('code.decide',{project_id:projectId,scope,change_id:changeId,decision,revision:data.review?.revision??null});
}
