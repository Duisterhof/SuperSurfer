// Provider sign-in belongs to the workspace host. No pasted credentials are accepted.
const labels={codex:'ChatGPT',cursor:'Cursor',claude:'Claude'};
export function createAccountGate({api,action,onAccount,readOnly,getBackend=()=> 'codex'}){
 const dialog=document.createElement('dialog');dialog.className='modal account-gate';dialog.id='account-gate';dialog.setAttribute('aria-labelledby','account-gate-title');
 dialog.innerHTML=`<div class="modal-body"><div class="page-eyebrow">Workspace accounts</div><h2 id="account-gate-title">Connect ChatGPT</h2><label class="field"><span>Account</span><select id="account-provider" aria-label="Account provider"><option value="codex">ChatGPT / Codex</option><option value="cursor">Cursor</option><option value="claude">Claude Code</option></select></label><p id="account-description">Each workspace host keeps its own login. Credentials stay with the official CLI.</p><p id="account-gate-status" role="status"></p><div id="account-gate-code" hidden><code></code><a class="button primary" target="_blank" rel="noopener noreferrer">Open verification page</a></div><pre id="account-terminal-command" hidden></pre><div class="modal-footer"><button class="button" id="account-check">Check again</button><button class="button primary" id="account-sign-in">Sign in with ChatGPT</button><button class="button" id="account-return">Return to workspace</button></div></div>`;
 document.body.append(dialog);
 const status=dialog.querySelector('#account-gate-status'),code=dialog.querySelector('#account-gate-code'),signIn=dialog.querySelector('#account-sign-in'),check=dialog.querySelector('#account-check'),title=dialog.querySelector('h2'),select=dialog.querySelector('select'),command=dialog.querySelector('pre');
 const accounts=new Map(),graceMs=15000;let checking=false,starting=false,pending=null,timer,forced=false,dismissed=false,selected=getBackend(),waitingSince=Date.now(),generation=0,terminalCommand='';
 const desired=()=>labels[getBackend()]?getBackend():'codex';
 const isConnected=(backend)=>{const account=accounts.get(backend);return !!account?.account&&!account.error&&account.login_required!==true&&account.account.type===(backend==='codex'?'chatgpt':backend);};
 const ready=()=>readOnly()||isConnected(desired());
 const waiting=()=>!ready()&&waitingSince!==null&&Date.now()-waitingSince<graceMs;
 const hint=()=>ready()?'':accounts.get(desired())?.error||`Connect ${labels[desired()]} to send messages.`;
 function render(){
  const backend=forced?selected:desired(),account=accounts.get(backend),label=labels[backend];select.value=backend;
  const reconnect=!!account?.transport_error&&!forced&&!pending;
  title.textContent=reconnect?`Reconnecting to ${label}`:`Connect ${label}`;signIn.hidden=reconnect;signIn.textContent=backend==='codex'?'Sign in with ChatGPT':`Sign in with ${label} in Terminal`;
  signIn.disabled=starting||!!pending;check.disabled=checking;select.disabled=starting;
  code.hidden=!pending;code.querySelector('code').textContent=pending?.userCode||'';if(pending)code.querySelector('a').href=pending.verificationUrl;else code.querySelector('a').removeAttribute('href');
  command.hidden=!terminalCommand;command.textContent=terminalCommand;
  status.textContent=starting?'Opening official sign-in…':pending?'Enter this code on the official verification page. Sign-in is confirmed automatically.':checking?`Checking ${label} on this host…`:reconnect?`Retrying the ${label} connection on this host…`:account?.error||(isConnected(backend)?`${label} is connected on this host.`:terminalCommand?'Complete the provider’s sign-in in your own terminal. Never paste passwords, codes or tokens into agent chat.':`Sign in on this workspace host to use ${label}. You can browse the workspace and choose your backend in Settings.`);
  const show=forced||!!pending||(!dismissed&&!ready()&&!waiting()&&account!==undefined);
  if(show&&!dialog.open)dialog.showModal();else if(!show&&dialog.open)dialog.close();
 }
 function schedule(){clearTimeout(timer);timer=setTimeout(refresh,pending||forced||waiting()?2000:ready()?60000:10000);}
 async function refresh(){
  if(checking)return;checking=true;const backend=forced?selected:desired(),epoch=generation;render();
  try{
   const account=await api(backend==='codex'?'account':'account?backend='+backend);if(epoch!==generation)return;
   accounts.set(backend,account);onAccount(account);
   if(pending&&account.login?.loginId===pending.loginId&&['completed','failed'].includes(account.login.status)&&account.login.status==='failed')pending=null;
   if(isConnected(backend)){pending=null;if(!starting){forced=false;terminalCommand='';}}
  }catch(error){if(epoch===generation){const account={backend,login_required:true,transport_error:true,error:error.message};accounts.set(backend,account);onAccount(account);}}
  finally{if(ready())waitingSince=null;else if(waitingSince===null)waitingSince=Date.now();checking=false;render();schedule();}
 }
 async function login(){
  if(starting||pending)return;forced=true;starting=true;const backend=selected,epoch=generation;render();
  try{
   const result=await action('account.login',{backend});if(epoch!==generation)return;
   if(backend==='codex'){
    const url=new URL(result.verificationUrl);if(url.protocol!=='https:'||url.hostname!=='auth.openai.com'||!result.userCode||!result.loginId)throw new Error('The host did not return a valid ChatGPT sign-in code.');pending=result;
   }else{
    if(result.type!=='terminal'||result.backend!==backend)throw new Error('The host did not return a supported sign-in flow.');
    terminalCommand=`On this workspace host, run: ${backend==='cursor'?'agent login':'claude auth login'}`;
    if(window.superSurferDesktop?.openProviderLogin){const opened=await window.superSurferDesktop.openProviderLogin(backend);if(opened.command)terminalCommand=opened.command;}
   }
  }catch(error){accounts.set(backend,{...accounts.get(backend),login_required:true,error:error.message});}
  finally{starting=false;render();schedule();}
 }
 const dismiss=()=>{forced=false;dismissed=true;pending=null;terminalCommand='';render();schedule();};
 dialog.addEventListener('cancel',event=>{event.preventDefault();dismiss();});dialog.querySelector('#account-return').onclick=dismiss;
 select.onchange=()=>{generation++;selected=select.value;forced=true;pending=null;terminalCommand='';void refresh();};signIn.onclick=login;check.onclick=refresh;
 window.addEventListener('focus',()=>{if(!starting)void refresh();});render();
 return {ready,hint,refresh,open:(backend=desired())=>{generation++;selected=labels[backend]?backend:desired();forced=true;pending=null;terminalCommand='';render();void login();}};
}
