'use strict';
const form = document.querySelector('#connect-form');
const button = document.querySelector('#connect-button');
const cancel = document.querySelector('#cancel-connect');
const status = document.querySelector('#status');
const mode = document.querySelector('#mode');
const hosts = document.querySelector('#host');
const target = document.querySelector('#target');
let ready = false, connecting = false, requestId = 0;
button.disabled = true;
function updateMode() {
  const local = mode.value === 'local';
  document.querySelector('#remote-fields').hidden = local;
  target.required = !local && hosts.value === '__custom';
  target.disabled = local || hosts.value !== '__custom';
  document.querySelector('#custom-host').hidden = hosts.value !== '__custom';
  document.querySelector('#connection-explanation').textContent = local ? 'Agents keep working here while this computer stays on.' : 'Your agents keep working on the remote computer when you close this app.';
}
function setBusy(value) {
  connecting=value;button.disabled=!ready||value;
  form.setAttribute('aria-busy',String(value));
  for (const field of form.querySelectorAll('input,select')) field.disabled=value;
  if (!value) updateMode();
  cancel.hidden=!value||!window.superSurferDesktop?.cancelConnection;
}
function showStatus(value) {
  const state=typeof value==='string'?{message:value}:value||{};
  if (state.phase) setBusy(state.phase==='connecting');
  status.className=state.phase==='error'?'error':'';status.textContent=state.message||'';
}
async function initialize() {
  if (!window.superSurferDesktop) { status.textContent = 'Open this screen in the SuperSurfer desktop app.'; return; }
  const [saved, discovery] = await Promise.allSettled([
    window.superSurferDesktop.configuration(), window.superSurferDesktop.listHosts()
  ]);
  const config = saved.status === 'fulfilled' && saved.value && typeof saved.value === 'object' && !Array.isArray(saved.value) ? saved.value : {};
  // Accept only the documented configuration fields, never arbitrary DOM properties.
  for (const key of ['remoteRoot','amlHome','remotePort','target']) {
    if (typeof config[key] === 'string' || typeof config[key] === 'number') form.elements[key].value = config[key];
  }
  mode.value = ['local','remote'].includes(config.mode) ? config.mode : config.target ? 'remote' : 'local';
  const known = discovery.status === 'fulfilled' && discovery.value ? discovery.value : {};
  const options = (Array.isArray(known.hosts) ? known.hosts : []).filter(host => host && typeof host.target === 'string' && typeof host.name === 'string');
  if (typeof config.target === 'string' && config.target && !options.some(host => host.target === config.target)) options.unshift({name:config.target,target:config.target});
  for (const host of options) hosts.add(new Option(host.name, host.target));
  hosts.add(new Option('Enter another host…', '__custom'));
  hosts.value = config.target || options[0]?.target || '__custom';
  updateMode();
  const warnings=[];
  if (saved.status === 'rejected') warnings.push('Saved connection could not be loaded. You can connect again below.');
  if (discovery.status === 'rejected' || (Array.isArray(known.warnings) && known.warnings.length)) warnings.push('Some SSH hosts could not be read. You can still enter a host or use this machine.');
  status.textContent = warnings.join('\n');
  window.superSurferDesktop.onStatus(showStatus);
  ready = true;setBusy(false);
  if (window.superSurferDesktop.connectionReady) {
    const current=await window.superSurferDesktop.connectionReady();
    if (current?.phase !== 'idle' || current.message) showStatus(current);
  }
}
mode.addEventListener('change', updateMode);
hosts.addEventListener('change', updateMode);
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!ready || connecting || !form.reportValidity()) return;
  const currentRequest=++requestId;
  const config = Object.fromEntries(new FormData(form));
  config.target = mode.value === 'local' ? '' : hosts.value === '__custom' ? target.value : hosts.value;
  delete config.host;
  setBusy(true);
  status.className = '';status.textContent = 'Connecting…';
  try {
    const result = await window.superSurferDesktop.connect(config);
    if (currentRequest===requestId&&result?.error) { status.className = 'error';status.textContent = result.error; }
  } catch (error) { if(currentRequest===requestId){status.className = 'error';status.textContent = error.message;} }
  finally { if(currentRequest===requestId)setBusy(false); }
});
cancel.addEventListener('click',async()=>{requestId++;try{showStatus(await window.superSurferDesktop.cancelConnection());}catch(error){showStatus({phase:'error',message:error.message});}});
initialize().catch(error => { status.className = 'error';status.textContent = error.message; });
