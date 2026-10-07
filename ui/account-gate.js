// Sign-in belongs to the workspace host, never to a window or SSH connection.
export function createAccountGate({api, action, onAccount, readOnly}) {
  const dialog=document.createElement('dialog');dialog.className='modal account-gate';dialog.id='account-gate';
  dialog.setAttribute('aria-labelledby','account-gate-title');
  dialog.innerHTML=`<div class="modal-body"><div class="page-eyebrow">Workspace account</div><h2 id="account-gate-title">Connect ChatGPT</h2><p>Sign in on this workspace host to use its agents. Each host keeps its own login; reconnecting to a signed-in host skips this step.</p><p id="account-gate-status" role="status"></p><div id="account-gate-code" hidden><code></code><a class="button primary" target="_blank" rel="noopener noreferrer">Open verification page</a></div><div class="modal-footer"><button class="button" id="account-check">Check again</button><button class="button primary" id="account-sign-in">Sign in with ChatGPT</button><button class="button" id="account-return" hidden>Return to workspace</button></div></div>`;
  document.body.append(dialog);
  const status=dialog.querySelector('#account-gate-status'),code=dialog.querySelector('#account-gate-code'),signIn=dialog.querySelector('#account-sign-in'),check=dialog.querySelector('#account-check'),back=dialog.querySelector('#account-return');
  let connected=false,checking=false,starting=false,pending=null,timer,forced=false,account=null;
  const ready=()=>connected||readOnly();
  function render(){
    back.hidden=!ready();signIn.disabled=starting||!!pending;check.disabled=checking;
    code.hidden=!pending;
    if(pending){code.querySelector('code').textContent=pending.userCode;code.querySelector('a').href=pending.verificationUrl;}
    else {code.querySelector('code').textContent='';code.querySelector('a').removeAttribute('href');}
    status.textContent=starting?'Requesting a secure sign-in code…':pending?'Enter this code in your browser. This screen will continue automatically when sign-in is confirmed.':checking?'Checking ChatGPT login on this host…':account?.error||account?.login?.error||(connected?'ChatGPT is connected on this host.':'ChatGPT sign-in is required before agent work can start.');
    if(ready()&&!forced){if(dialog.open)dialog.close();}
    else if(!dialog.open)dialog.showModal();
  }
  function schedule(){clearTimeout(timer);timer=setTimeout(refresh,pending?2000:ready()?60000:10000);}
  async function refresh(){
    if(checking)return;checking=true;render();
    try{
      account=await api('account');
      connected=account.account?.type==='chatgpt'&&account.login_required!==true&&!account.error;
      if(pending&&account.login?.loginId===pending.loginId&&['completed','failed'].includes(account.login.status)){
        if(account.login.status==='failed'||connected)pending=null;
      }
      if(connected&&!starting&&!pending)forced=false;
    }catch(error){connected=false;account={error:error.message};}
    finally{checking=false;onAccount(account);render();schedule();}
  }
  async function login(){
    if(starting||pending)return;forced=true;starting=true;render();
    try{
      const result=await action('account.login');
      const url=new URL(result.verificationUrl);
      if(url.protocol!=='https:'||url.hostname!=='auth.openai.com'||!result.userCode||!result.loginId)throw new Error('The workspace did not return a valid ChatGPT sign-in code. Try again.');
      pending=result;
    }catch(error){account={...account,error:error.message};}
    finally{starting=false;render();schedule();}
  }
  dialog.addEventListener('cancel',event=>{event.preventDefault();if(ready()){forced=false;dialog.close();}});
  back.onclick=()=>{forced=false;dialog.close();};signIn.onclick=login;check.onclick=refresh;
  window.addEventListener('focus',()=>{if(!starting)void refresh();});
  render();
  return {ready,refresh,open:()=>{forced=true;render();void login();}};
}
