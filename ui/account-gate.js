// Official CLI authentication stays on the workspace host, never in agent chat.
const labels={codex:'ChatGPT / Codex',cursor:'Cursor',claude:'Claude Code',opencode:'OpenCode'};
const titles={codex:'ChatGPT',cursor:'Cursor',claude:'Claude',opencode:'OpenCode'};
const installUrls={codex:'https://developers.openai.com/codex/cli/',cursor:'https://cursor.com/docs/cli/installation',claude:'https://code.claude.com/docs/en/setup',opencode:'https://opencode.ai/docs'};
export function createAccountGate({api,action,onAccount,readOnly,getBackend=()=> 'codex',getSetupRequired=()=>false,onChoose=()=>{}}){
 const dialog=document.createElement('dialog');dialog.className='modal account-gate';dialog.id='account-gate';dialog.setAttribute('aria-labelledby','account-gate-title');
 dialog.innerHTML=`<div class="modal-body"><div class="page-eyebrow">Accounts on this machine</div><h2 id="account-gate-title">Connect your provider</h2><label class="field"><span>Provider</span><select id="account-provider" aria-label="Account provider"><option value="" disabled>Choose a provider…</option>${Object.entries(labels).map(([key,label])=>`<option value="${key}">${label}</option>`).join('')}</select></label><p id="account-description">You only need one provider. Sign-in stays on this workspace machine.</p><p id="account-gate-status" role="status"></p><div id="account-install-help" hidden><p>SuperSurfer uses the provider’s command-line app on your workspace computer. The Cursor desktop app and CLI are separate; the CLI must be available on this workspace computer.</p><button type="button" class="button" id="account-install-cursor" hidden>Install Cursor CLI in Terminal</button> <a id="account-install" target="_blank" rel="noopener noreferrer">Installation guide</a></div><div id="account-gate-code" hidden><code></code><a class="button primary" target="_blank" rel="noopener noreferrer">Open verification page</a></div><pre id="account-terminal-command" hidden></pre><div class="modal-footer"><button class="button" id="account-check">Check again</button><button class="button primary" id="account-sign-in">Sign in</button><button class="button primary" id="account-use" hidden>Use this provider</button><button class="button" id="account-return">Return to workspace</button></div></div>`;
 document.body.append(dialog);
 const status=dialog.querySelector('#account-gate-status'),code=dialog.querySelector('#account-gate-code'),signIn=dialog.querySelector('#account-sign-in'),check=dialog.querySelector('#account-check'),title=dialog.querySelector('h2'),select=dialog.querySelector('select'),command=dialog.querySelector('pre'),use=dialog.querySelector('#account-use'),install=dialog.querySelector('#account-install'),installHelp=dialog.querySelector('#account-install-help'),installCursor=dialog.querySelector('#account-install-cursor');
 const accounts=new Map(),checks=new Map(),graceMs=15000;let checking=false,checkingBackend=null,checkingEpoch=-1,starting=false,pending=null,timer,forced=false,dismissed=false,selected=getBackend(),waitingSince=Date.now(),generation=0,terminalCommand='',setupMode=false,actionError='';
 const desired=()=>labels[getBackend()]?getBackend():'codex';
 const connected=backend=>{const account=accounts.get(backend);return !!account?.account&&!account.error&&account.login_required!==true&&account.account.type===(backend==='codex'?'chatgpt':backend);};
 const ready=()=>readOnly()||!getSetupRequired()&&connected(desired());
 const waiting=()=>!ready()&&waitingSince!==null&&Date.now()-waitingSince<graceMs;
 const hint=()=>ready()?'':getSetupRequired()?'Choose a provider for this machine.':accounts.get(desired())?.error||`Connect ${titles[desired()]} to send messages.`;
 const current=()=>setupMode?selected:forced?selected:desired();
 function render(){
  if(setupMode&&!getSetupRequired()){setupMode=false;forced=false;pending=null;terminalCommand='';}
  if(getSetupRequired()&&!setupMode&&!forced&&!dismissed&&!waiting()&&!readOnly()){setupMode=true;selected='';generation++;}
  const backend=current(),account=accounts.get(backend),label=titles[backend]||'your provider',reconnect=!!account?.transport_error&&!forced&&!pending&&!setupMode;
  select.value=backend;title.textContent=setupMode?'Choose a provider for this machine':reconnect?`Reconnecting to ${label}`:`Connect ${label}`;
  signIn.hidden=reconnect||setupMode&&connected(backend);signIn.textContent=backend==='codex'?'Sign in with ChatGPT':`Sign in with ${label} in Terminal`;
  signIn.disabled=starting||checking||!!pending||!labels[backend]||account?.installed===false;check.disabled=checking||!labels[backend];select.disabled=starting;
  use.hidden=!setupMode;use.disabled=starting||!connected(backend);use.textContent='Use '+(labels[backend]||'this provider');
  code.hidden=!pending;code.querySelector('code').textContent=pending?.userCode||'';if(pending)code.querySelector('a').href=pending.verificationUrl;else code.querySelector('a').removeAttribute('href');
  command.hidden=!terminalCommand;command.textContent=terminalCommand;installHelp.hidden=account?.installed!==false;installCursor.hidden=backend!=='cursor'||!window.superSurferDesktop?.installCursor;installCursor.disabled=starting;install.href=installUrls[backend]||installUrls.codex;
  status.textContent=actionError||(!labels[backend]?'Choose Codex, Cursor, Claude or OpenCode. You can connect more accounts later in Settings.':starting?'Opening official sign-in…':pending?'Enter this code on the official verification page. Sign-in is confirmed automatically.':checking?`Checking ${label} on this machine…`:reconnect?(waiting()?`Retrying the ${label} connection…`:account?.error||`Could not verify ${label}. Check the connection and try again.`):account?.error||(connected(backend)?`${label} is signed in on this machine.`:terminalCommand?'Complete sign-in in your terminal, then check again. Never paste passwords, codes or tokens into chat.':`Sign in on this machine to use ${label}.`));
  const show=!readOnly()&&(setupMode||forced||!!pending||!dismissed&&!ready()&&!waiting()&&account!==undefined);
  if(show&&!dialog.open)dialog.showModal();else if(!show&&dialog.open)dialog.close();
 }
 function schedule(){clearTimeout(timer);timer=setTimeout(refresh,pending||forced||setupMode||waiting()?2000:ready()?60000:10000);}
 function observe(account){const backend=account.backend||'codex';accounts.set(backend,account);onAccount(account);if(ready())waitingSince=null;else if(waitingSince===null)waitingSince=Date.now();render();}
 async function refresh(force=false){
  render();const backend=current(),epoch=generation;if(!labels[backend]){schedule();return;}if(checking&&checkingBackend===backend&&checkingEpoch===epoch)return;checking=true;checkingBackend=backend;checkingEpoch=epoch;render();
  try{
   let task=checks.get(backend);if(!task){const query=new URLSearchParams();if(backend!=='codex')query.set('backend',backend);if(force||pending||terminalCommand)query.set('refresh','1');task=api('account'+(query.size?'?'+query:''));checks.set(backend,task);task.finally(()=>{if(checks.get(backend)===task)checks.delete(backend);}).catch(()=>{});}const account=await task;if(epoch!==generation)return;
   observe(account);
   if(pending&&account.login?.loginId===pending.loginId&&account.login.status==='failed'){
    actionError=typeof account.login.error==='string'?account.login.error.slice(0,2000):'Sign-in did not complete. Try again.';pending=null;
   }
   if(connected(backend)){pending=null;if(!starting&&!setupMode){forced=false;terminalCommand='';}}
  }catch(error){if(epoch===generation)observe({backend,login_required:true,transport_error:true,error:error.message});}
  finally{if(ready())waitingSince=null;else if(waitingSince===null)waitingSince=Date.now();if(epoch===generation){checking=false;checkingBackend=null;render();schedule();}}
 }
 async function login(){
  if(starting||pending||!labels[selected]||readOnly())return;actionError='';forced=true;starting=true;const backend=selected,epoch=generation;render();
  try{
   const result=await action('account.login',{backend});if(epoch!==generation)return;
   if(backend==='codex'){
    const url=new URL(result.verificationUrl);if(url.protocol!=='https:'||url.hostname!=='auth.openai.com'||!result.userCode||!result.loginId)throw new Error('The host did not return a valid ChatGPT sign-in code.');pending=result;
   }else{
    if(result.type!=='terminal'||result.backend!==backend)throw new Error('The host did not return a supported sign-in flow.');
    terminalCommand='On the workspace computer, run: '+result.command;
    if(window.superSurferDesktop?.openProviderLogin){const opened=await window.superSurferDesktop.openProviderLogin(backend);if(opened.command)terminalCommand=opened.command;if(opened.error)actionError=opened.error;}
   }
  }catch(error){actionError=error.message;}
  finally{starting=false;render();schedule();}
 }
 async function choose(){
  if(starting||!connected(selected))return;actionError='';starting=true;render();
  try{const result=await action('account.choose',{backend:selected});await onChoose(result);setupMode=false;forced=false;pending=null;terminalCommand='';dismissed=false;await refresh();}
  catch(error){actionError=error.message;await refresh();}
  finally{starting=false;render();schedule();}
 }
 installCursor.onclick=async()=>{if(starting||readOnly())return;starting=true;actionError='';render();try{const result=await window.superSurferDesktop.installCursor();terminalCommand=result.command||'';actionError=result.error||'Complete installation in Terminal, then choose Check again.';}catch(error){actionError=error.message;}finally{starting=false;render();schedule();}};
 const dismiss=()=>{forced=false;setupMode=false;dismissed=true;pending=null;terminalCommand='';generation++;render();schedule();};
 dialog.addEventListener('cancel',event=>{event.preventDefault();dismiss();});dialog.querySelector('#account-return').onclick=dismiss;
 select.onchange=()=>{actionError='';generation++;selected=select.value;forced=true;pending=null;terminalCommand='';void refresh();};signIn.onclick=login;check.onclick=()=>{actionError='';void refresh(true);};use.onclick=choose;
 window.addEventListener('focus',()=>{if(!starting)void refresh(true);});render();
 return {ready,hint,refresh,observe,signedOut:account=>{if(current()===(account.backend||'codex')){generation++;pending=null;terminalCommand='';forced=false;setupMode=false;dismissed=true;}observe(account);schedule();},open:async(backend=desired())=>{if(readOnly())return;generation++;selected=labels[backend]?backend:desired();setupMode=getSetupRequired();forced=true;dismissed=false;pending=null;terminalCommand='';render();await refresh(true);if(accounts.get(selected)?.installed!==false&&!connected(selected))await login();}};
}
