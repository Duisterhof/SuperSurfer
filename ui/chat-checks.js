// Collapse application-owned monitoring and agent coordination. Direct user
// messages always break a group; an agent steer must not hide a user-turn reply.
export function groupChatChecks(messages){
 const rows=[];let current=null;
 for(const message of messages){
  const automatic=!!message.background_check||(!message.origin&&message.assignment===true&&['user','system'].includes(message.role)&&message.text?.startsWith('Perform this worker check explicitly scheduled by the user.')&&message.text.includes('\n\nSaved task:\n')&&message.text.includes('\n\nWakeup evidence:\n'));
  const coordination=message.role==='system'&&!!message.agent_sender;
  const continuation=message.role==='system'&&(message.application_event==='continuation'||message.text?.startsWith('Application continuation:')||message.text==='Checking completed deliverables against the original assignment.');
  const category=coordination?'coordination':continuation?'activity':'monitoring';
  if((automatic||coordination||continuation)&&!['failed','uncertain','not_sent'].includes(message.status)){
   let group=rows.at(-1);if(group?.type!=='checks'||group.category!==category){group={type:'checks',category,id:message.id,checks:[]};rows.push(group);}
   current={id:message.id,messages:[message],turnId:message.turn_id||null,includeReply:!coordination||message.assignment===true&&!message.steering};group.checks.push(current);
  }else if(current?.includeReply&&message.role==='assistant'&&(!current.turnId||current.turnId===message.turn_id)){
   current.turnId??=message.turn_id;current.messages.push(message);
  }else {rows.push({type:'message',message});current=null;}
 }
 return rows;
}
export function renderChatTimeline(messages,{renderMessage,escape,date,expanded=new Set(),busy=false}){
 const rows=groupChatChecks(messages);
 const summary=check=>{if(check.messages.length===1&&check.messages[0].text?.startsWith('Application continuation:'))return 'Continuing the assigned work…';const last=[...check.messages].reverse().find(m=>m.role==='assistant'&&m.text?.trim())||(check.messages[0].role==='system'?check.messages[0]:null);return last?.text.trim().split(/\n\s*\n/)[0].replace(/[*_`]/g,'').slice(0,160)||'Waiting for the check result…';};
 return rows.map((row,index)=>{
  if(row.type==='message')return renderMessage(row.message);
  const id='group:'+row.id,open=expanded.has(id),latest=row.checks.at(-1),last=latest.messages.at(-1),working=busy&&index===rows.length-1;
  return `<details class="chat-checks" data-check-key="${escape(id)}" ${open?'open':''}><summary><span class="check-indicator ${working?'working':''}" aria-hidden="true">${working?'◌':'↻'}</span><strong>${row.category==='coordination'?'Agents':row.category==='activity'?'Activity':'Monitoring'} · ${row.checks.length} ${row.category!=='monitoring'?'update':'check'}${row.checks.length===1?'':'s'}</strong><time>${escape(date(last.created,true))}</time><span class="check-latest">${latest.messages[0].agent_sender?escape(latest.messages[0].agent_sender.name)+' · ':''}${escape(summary(latest))}</span></summary>${open?`<div class="chat-check-history">${row.checks.map(check=>{const key='check:'+check.id,show=expanded.has(key);return `<details class="chat-check" data-check-key="${escape(key)}" ${show?'open':''}><summary><time>${escape(date(check.messages[0].created,true))}</time> ${escape(summary(check))}</summary>${show?check.messages.map(m=>renderMessage(m===check.messages[0]?{...m,role:'system'}:m)).join(''):''}</details>`;}).join('')}</div>`:''}</details>`;
 }).join('');
}
