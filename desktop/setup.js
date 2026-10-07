'use strict';
const form = document.querySelector('#connect-form');
const button = document.querySelector('#connect-button');
const status = document.querySelector('#status');
const mode = document.querySelector('#mode');
const hosts = document.querySelector('#host');
const target = document.querySelector('#target');
function updateMode() {
  const local = mode.value === 'local';
  document.querySelector('#remote-fields').hidden = local;
  target.required = !local && hosts.value === '__custom';
  target.disabled = local || hosts.value !== '__custom';
  document.querySelector('#custom-host').hidden = hosts.value !== '__custom';
  document.querySelector('#connection-explanation').textContent = local ? 'Runs the workspace service on this computer. Agents and jobs continue when you close the app, while this machine stays on.' : 'Connects using your existing SSH configuration. Agents and jobs continue on the remote computer when you close the app.';
}
async function initialize() {
  if (!window.superSurferDesktop) { status.textContent = 'Open this screen in the SuperSurfer desktop app.'; button.disabled = true; return; }
  const [config, known] = await Promise.all([window.superSurferDesktop.configuration(), window.superSurferDesktop.listHosts()]);
  for (const [key, value] of Object.entries(config)) { if (form.elements[key]) form.elements[key].value = value; }
  mode.value = config.mode || (config.target ? 'remote' : 'local');
  const options = known.hosts || [];
  if (config.target && !options.some(h => h.target === config.target)) options.unshift({name:config.target,target:config.target});
  for (const host of options) hosts.add(new Option(host.name, host.target));
  hosts.add(new Option('Enter another host…', '__custom'));
  hosts.value = config.target || options[0]?.target || '__custom';
  updateMode();
  window.superSurferDesktop.onStatus(message => { status.className = ''; status.textContent = message; });
}
mode.addEventListener('change', updateMode);
hosts.addEventListener('change', updateMode);
form.addEventListener('submit', async event => {
  event.preventDefault(); button.disabled = true; status.className = ''; status.textContent = 'Connecting…';
  try {
    const config = Object.fromEntries(new FormData(form));
    config.target = mode.value === 'local' ? '' : hosts.value === '__custom' ? target.value : hosts.value;
    delete config.host;
    const result = await window.superSurferDesktop.connect(config);
    if (result?.error) { status.className = 'error'; status.textContent = result.error; }
  } catch (error) { status.className = 'error'; status.textContent = error.message; }
  finally { button.disabled = false; }
});
initialize().catch(error => { status.className = 'error'; status.textContent = error.message; });
