"use strict";
const vscode = acquireVsCodeApi();
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const send = (op, args) => vscode.postMessage({ op, args });
let chat, binding, busy = false, connected = false, first = true, decisionSignature = "", contentSignature = "";
const app = document.getElementById("app");
app.innerHTML = `<header><div><h1 id="title">Connecting…</h1><div class="meta" id="meta"></div><div class="status" id="status" role="status"></div></div><div class="buttons"><button id="board">Surfboard</button><button id="split">Split view</button><button id="refresh" aria-label="Refresh conversation">Refresh</button></div></header><main id="history"><div class="empty">Loading your existing conversation…</div></main><div id="decisions"></div><div id="notice" role="status"></div><form class="composer" id="composer"><textarea id="prompt" aria-label="Message this agent" maxlength="100000" placeholder="Message this agent…" rows="3"></textarea><footer><small id="ownership">Connected to SuperSurfer on this host</small><div class="buttons"><button type="button" id="stop" hidden>Stop</button><button class="primary" type="submit" id="send" disabled>Send</button></div></footer></form>`;
const el = id => document.getElementById(id);
function inline(text) {
  const tokens = [];
  const token = html => { tokens.push(html); return `\u0000${tokens.length-1}\u0000`; };
  let value = String(text).replace(/\u0000/g, "").replace(/`([^`]+)`/g, (_, s) => token(`<code>${esc(s)}</code>`));
  value = value.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => token(`<a href="#" data-url="${esc(url)}">${esc(label)}</a>`));
  return esc(value).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>").replace(/\u0000(\d+)\u0000/g, (_, n) => tokens[Number(n)] || "");
}
function markdown(text) {
  const lines = String(text || "").replace(/\r/g, "").split("\n");
  const out = []; let paragraph = [], list = null;
  const flush = () => { if (paragraph.length) out.push(`<p>${inline(paragraph.join("\n"))}</p>`); paragraph = []; if (list) out.push(`</${list}>`); list = null; };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*```/.test(line)) { flush(); const code=[]; while (++i < lines.length && !/^\s*```/.test(lines[i])) code.push(lines[i]); out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`); continue; }
    const heading = line.match(/^(#{1,4})\s+(.+)$/), bullet = line.match(/^\s*(?:([-*])|\d+\.)\s+(.+)$/);
    if (heading) { flush(); out.push(`<h${Math.max(2,heading[1].length)}>${inline(heading[2])}</h${Math.max(2,heading[1].length)}>`); }
    else if (bullet) { const kind=bullet[1]?"ul":"ol"; if (list!==kind) {flush();list=kind;out.push(`<${kind}>`);} out.push(`<li>${inline(bullet[2])}</li>`); }
    else if (!line.trim()) flush();
    else { if(list) flush(); paragraph.push(line); }
  }
  flush(); return out.join("");
}
function notice(text, error=false) { el("notice").textContent=text; el("notice").classList.toggle("error",error); }
function controls() {
  const locked = !connected || !chat || chat.read_only || chat.archived || chat.retired;
  const waiting = (chat?.questions||[]).some(q=>q.status==="pending") || (chat?.approvals||[]).some(q=>q.status==="pending");
  el("send").disabled = locked || busy || waiting || (chat?.busy && !chat?.steerable) || !el("prompt").value.trim();
  el("send").textContent = busy ? "Sending…" : chat?.busy && chat.steerable ? "Send direction" : "Send";
  el("stop").hidden = !chat?.busy || binding?.owner === "AutoML";
  el("stop").disabled = locked || busy;
  el("prompt").disabled = locked;
  el("ownership").textContent = chat?.retired || chat?.archived ? "This conversation is read-only" : chat?.read_only ? "Read-only workspace" : "Work continues on the host when you close this tab";
}
function renderHistory() {
  const messages = chat.messages || [], activity=chat.activity || [], tasks=chat.tasks || [];
  const signature=JSON.stringify([messages,activity,tasks,chat.message_count]);
  if(signature===contentSignature)return;contentSignature=signature;
  const area=el("history"), nearEnd=area.scrollHeight-area.scrollTop-area.clientHeight<100, oldHeight=area.scrollHeight, oldScroll=area.scrollTop;
  const expanded=new Set([...area.querySelectorAll("details[open]")].map(d=>d.dataset.key));
  const earlier=(chat.message_count||messages.length)-messages.length;
  area.innerHTML=(earlier?`<button id="earlier">Load earlier messages · ${earlier}</button>`:"")+messages.map(m=>`<article class="message ${["user","system"].includes(m.role)?m.role:"assistant"}"><div class="message-head"><strong>${esc(m.role==="user"?"You":m.role==="system"?m.agent_sender?.name||"System":chat.agent?.name||binding.name)}</strong>${m.created?`<time>${esc(new Date(m.created*1000).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"}))}</time>`:""}</div><div class="content">${markdown(m.text)}</div>${m.status&&!["sent","completed"].includes(m.status)?`<div class="delivery">${esc(m.status)}${m.error?": "+esc(m.error):""}</div>`:""}</article>`).join("")+(messages.length?"":'<div class="empty">This is the existing agent’s conversation. Send a message to begin.</div>')+
    (activity.length?`<details data-key="activity" ${expanded.has("activity")?"open":""}><summary>Activity · ${activity.length} events</summary>${activity.slice(-80).map((a,i)=>`<details class="event" data-key="event:${esc(a.id||i)}" ${expanded.has("event:"+(a.id||i))?"open":""}><summary>${esc(a.type||"Tool")} · ${esc(a.status||"")}</summary><pre>${esc(a.text||a.command||"")}</pre></details>`).join("")}</details>`:"")+
    (tasks.length?`<details data-key="tasks" ${expanded.has("tasks")?"open":""}><summary>Tasks · ${tasks.filter(t=>t.status==="completed").length}/${tasks.length} complete</summary>${tasks.map(t=>`<div class="task"><span>${esc(t.status)}</span>${esc(t.title)}</div>`).join("")}</details>`:"");
  if(el("earlier"))el("earlier").onclick=()=>{contentSignature="";send("earlier");};
  if(first||nearEnd)area.scrollTop=area.scrollHeight;
  else if(earlierLoading)area.scrollTop=oldScroll+area.scrollHeight-oldHeight;
  else area.scrollTop=oldScroll;
  first=false;earlierLoading=false;
}
let earlierLoading=false;
function decisions() {
  const questions=(chat.questions||[]).filter(q=>q.status==="pending"), approvals=(chat.approvals||[]).filter(q=>q.status==="pending");
  const signature=JSON.stringify([questions,approvals,chat.read_only,chat.retired,binding.owner]);
  if(signature===decisionSignature)return;decisionSignature=signature;
  const disabled=chat.read_only||chat.retired||chat.archived||binding.owner==="AutoML";
  el("decisions").innerHTML=approvals.map(a=>`<section class="decision"><h2>Approval requested · ${esc(a.kind||"Agent action")}</h2>${a.reason?`<p>${esc(a.reason)}</p>`:""}<pre>${esc(typeof a.command==="string"?a.command:JSON.stringify(a.command||a.tool_request||a.paths||a.permissions||{},null,2))}</pre>${a.cwd?`<small>${esc(a.cwd)}</small>`:""}<div class="buttons"><button data-approval="${esc(a.id)}" data-decision="deny" ${disabled?"disabled":""}>Deny</button><button class="primary" data-approval="${esc(a.id)}" data-decision="approve" ${disabled||a.can_approve===false?"disabled":""}>Approve once</button></div></section>`).join("")+questions.map(q=>`<form class="decision" data-question="${esc(q.id)}"><h2>Your input is needed</h2>${q.questions.map((item,i)=>`<fieldset data-index="${i}" ${disabled||q.can_answer===false?"disabled":""}><legend>${esc(item.question)}</legend>${(item.options||[]).map((o,j)=>`<label class="option"><input type="radio" name="q${i}" value="${j}" required> ${esc(o.label)}${o.description?`<small>${esc(o.description)}</small>`:""}</label>`).join("")}${item.options?.length&&item.isOther?`<label class="option"><input type="radio" name="q${i}" value="other" required> Write another answer</label>`:""}${!item.options?.length||item.isOther?`<input type="${item.isSecret?"password":"text"}" data-answer autocomplete="off" maxlength="16000" aria-label="${esc(item.question)}" ${!item.options?.length?"required":""}>`:""}</fieldset>`).join("")}<button class="primary" type="submit" ${disabled||q.can_answer===false?"disabled":""}>Answer & continue</button></form>`).join("");
  el("decisions").querySelectorAll("[data-approval]").forEach(button=>button.onclick=()=>act("chat.approve",{approval_id:button.dataset.approval,decision:button.dataset.decision}));
  el("decisions").querySelectorAll("form[data-question]").forEach(form=>form.onsubmit=event=>{
    event.preventDefault();const q=questions.find(q=>String(q.id)===form.dataset.question),answers=Object.create(null);
    for(const [i,item] of q.questions.entries()) {
      const field=form.querySelector(`[data-index="${i}"]`),choice=field.querySelector("input:checked")?.value;
      const value=!item.options?.length||choice==="other"?field.querySelector("[data-answer]")?.value:item.options[Number(choice)]?.label;
      if(!value?.trim())return notice("Answer each question before continuing.",true);answers[item.id]=[value];
    }
    act("chat.answer",{question_id:q.id,answers});
  });
}
function act(op,args={}){if(busy)return;busy=true;notice("");controls();send(op,args);}
el("prompt").oninput=()=>{vscode.postMessage({op:"draft",text:el("prompt").value});controls();};
el("composer").onsubmit=event=>{event.preventDefault();if(el("send").disabled)return;act(chat.busy?"chat.steer":"chat.send",{text:el("prompt").value.trim()});};
el("prompt").onkeydown=event=>{if(event.key==="Enter"&&(event.metaKey||event.ctrlKey)){event.preventDefault();el("composer").requestSubmit();}};
el("stop").onclick=()=>act("chat.stop");el("board").onclick=()=>send("board");el("split").onclick=()=>send("split");el("refresh").onclick=()=>send("refresh");
app.addEventListener("click",event=>{const link=event.target.closest("[data-url]");if(link){event.preventDefault();vscode.postMessage({op:"link",url:link.dataset.url});}if(event.target.id==="earlier")earlierLoading=true;});
window.addEventListener("message",event=>{
  const m=event.data;
  if(m.type==="restore"){if(!el("prompt").value)el("prompt").value=m.draft||"";controls();return;}
  if(m.type==="connectionError"){connected=false;notice(m.message+" Reconnecting…",true);controls();return;}
  if(m.type==="actionError"){busy=false;notice(m.message,true);controls();return;}
  if(m.type==="result"){
    busy=false;
    if(["chat.send","chat.steer"].includes(m.op)&&el("prompt").value.trim()===m.text){el("prompt").value="";vscode.postMessage({op:"draft",text:""});}
    notice(m.op==="chat.stop"?"Stop requested.":"Saved.");controls();return;
  }
  if(m.type!=="chat")return;
  const reconnected=!connected;connected=true;chat=m.chat;binding=m.binding;
  if(reconnected)notice("");
  el("title").textContent=chat.agent?.name||binding.name;
  const model=chat.agent?.model||chat.preferences?.effective?.model||"";
  el("meta").textContent=[binding.projectName,model].filter(Boolean).join(" · ");
  const waiting=(chat.questions||[]).some(q=>q.status==="pending")||(chat.approvals||[]).some(q=>q.status==="pending");
  el("status").classList.toggle("working",!!chat.busy&&!waiting);
  el("status").innerHTML=`<span class="dot"></span><small>${esc(waiting?"Needs your input":chat.busy?"Working on host":chat.status==="completed"?"Finished":chat.status||"Ready")}</small>`;
  el("board").hidden=!binding.project_id;
  renderHistory();decisions();controls();
});
send("ready");
