const providers={codex:'ChatGPT / Codex',cursor:'Cursor',claude:'Claude Code'};
const installUrls={codex:'https://developers.openai.com/codex/cli/',cursor:'https://cursor.com/docs/cli/installation',claude:'https://code.claude.com/docs/en/setup'};
export function createWorkspaceAccounts({api,action,gate,readOnly,onError}){
 const records=new Map(),busy=new Set(),inflight=new Map(),revisions=new Map();let root=null;
 const markup=()=>`<div class="workspace-accounts">${Object.entries(providers).map(([id,label])=>`<div class="workspace-account-row" data-provider-account="${id}"><div><strong>${label}</strong><small class="provider-account-status" role="status">Checking…</small></div><a class="provider-install" href="${installUrls[id]}" target="_blank" rel="noopener noreferrer" hidden>Install CLI</a><button type="button" class="button small-button" data-account-login="${id}">Sign in</button><button type="button" class="button small-button" data-account-logout="${id}" hidden>Sign out</button><button type="button" class="icon-button" data-account-refresh="${id}" title="Refresh ${label} status" aria-label="Refresh ${label} status">↻</button></div>`).join('')}</div>`;
 function paint(){if(!root?.isConnected)return;for(const [id,label] of Object.entries(providers)){
  const row=root.querySelector(`[data-provider-account="${id}"]`),record=records.get(id),value=record?.value,connected=!!value?.account&&!value.error&&!value.login_required&&value.account.type===(id==='codex'?'chatgpt':id);
  if(!row)continue;const working=busy.has(id),loading=inflight.has(id),active=value?.active_turns>0;
  row.querySelector('.provider-account-status').textContent=working?'Signing out…':!value?'Checking…':value.error||value.note||(connected?['Signed in',value.account.email||value.account.authMethod,active?value.active_turns+' active turn'+(value.active_turns===1?'':'s'):''].filter(Boolean).join(' · '):'Signed out');
  row.querySelector('.provider-install').hidden=value?.installed!==false;
  const login=row.querySelector('[data-account-login]'),logout=row.querySelector('[data-account-logout]');login.hidden=connected;logout.hidden=!connected;
  login.disabled=readOnly()||working||loading||value?.installed===false;logout.disabled=readOnly()||working||active;logout.title=active?'Finish or stop this provider’s active turns before signing out.':'Sign out on this machine';row.querySelector('[data-account-refresh]').disabled=working||loading;
 }}
 function observe(value){records.set(value.backend||'codex',{value,at:Date.now()});paint();}
 async function refresh(id,force=false){
  if(inflight.has(id))return inflight.get(id);if(!force&&records.has(id)&&Date.now()-records.get(id).at<30000)return;
  const revision=revisions.get(id)||0;const task=(async()=>{try{let value=await api(id==='codex'?'account':'account?backend='+id);if(revision!==(revisions.get(id)||0))return;if(value.backend&&value.backend!==id)throw new Error('This machine returned a different provider account. Refresh the workspace.');value={...value,backend:id};observe(value);gate.observe(value);}catch(error){if(revision===(revisions.get(id)||0))observe({backend:id,login_required:true,error:error.message});}finally{inflight.delete(id);paint();}})();inflight.set(id,task);paint();return task;
 }
 async function logout(id){
  if(readOnly()||busy.has(id))return;revisions.set(id,(revisions.get(id)||0)+1);busy.add(id);paint();
  try{const value=await action('account.logout',{backend:id});observe(value);gate.signedOut(value);}
  catch(error){onError(error.message);}
  finally{busy.delete(id);paint();}
 }
 function mount(element){root=element;if(!root)return;if(!root.querySelector('[data-provider-account]'))root.innerHTML=markup();root.onclick=event=>{const button=event.target.closest('button');if(!button||button.disabled)return;const id=button.dataset.accountLogin||button.dataset.accountLogout||button.dataset.accountRefresh;if(!id)return;event.preventDefault();if(button.dataset.accountLogin)void gate.open(id);else if(button.dataset.accountLogout)void logout(id);else void refresh(id,true);};paint();void Promise.allSettled(Object.keys(providers).map(id=>refresh(id)));}
 return {mount,observe,refresh:()=>Promise.allSettled(Object.keys(providers).map(id=>refresh(id)))};
}
