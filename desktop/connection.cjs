'use strict';
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const os = require('node:os');

const SSH_OPTIONS = ['-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ClearAllForwardings=yes', '-o', 'ForkAfterAuthentication=no', '-o', 'ConnectTimeout=12', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3'];
const BOOTSTRAP_SSH_OPTIONS = [...SSH_OPTIONS,'-o','ControlMaster=no','-o','ControlPath=none','-o','ControlPersist=no','-o','StdinNull=no','-o','SessionType=default','-o','RemoteCommand=none'];
function shellQuote(value) { return "'" + String(value).replaceAll("'", "'\\''") + "'"; }
function validateConfig(value) {
  if (!value || typeof value !== 'object') throw new Error('Choose a workspace connection.');
  const mode = value.mode === 'local' ? 'local' : 'remote';
  const target = String(value.target || '').trim();
  if (mode === 'remote' && !/^[a-zA-Z0-9][a-zA-Z0-9_.@:-]{0,199}$/.test(target)) throw new Error('Choose a computer from your SSH configuration.');
  const remoteRoot = String(value.remoteRoot || '~/.local/share/supersurfer').trim();
  const amlHome = String(value.amlHome || '~/.auto-ml').trim();
  for (const directory of [remoteRoot, amlHome]) {
    if ((!directory.startsWith('/') && !directory.startsWith('~/')) || /[\0\r\n]/.test(directory)) throw new Error('Workspace folders must start with / or ~/');
  }
  const remotePort = Number(value.remotePort || 8765);
  if (!Number.isInteger(remotePort) || remotePort < 1024 || remotePort > 65535) throw new Error('Workspace port must be between 1024 and 65535.');
  return { mode, target: mode === 'local' ? '' : target, remoteRoot, amlHome, remotePort };
}
function collect(command, args, input, timeout = 90000, signal, onProgress = () => {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['pipe', 'pipe', 'pipe'], signal });
    const output = [], errors = []; let size = 0,progressBuffer='';
    const terminate=()=>{child.kill('SIGTERM');const killer=setTimeout(()=>{if(child.exitCode===null&&child.signalCode===null)child.kill('SIGKILL');},500);killer.unref();};
    const timer = setTimeout(() => { terminate(); reject(new Error('Workspace connection timed out. Check the host and retry; remote work is preserved.')); }, timeout);
    child.stdout.on('data', chunk => { size += chunk.length; if (size > 2 * 1024 * 1024) child.kill(); else output.push(chunk); });
    child.stderr.on('data', chunk => { if (errors.reduce((n, x) => n + x.length, 0) < 100000) errors.push(chunk);progressBuffer+=chunk.toString();const lines=progressBuffer.split(/\r?\n/);progressBuffer=lines.pop().slice(-1000);for(const line of lines){if(!line.startsWith('SUPERSURFER_PROGRESS: '))continue;try{const data=JSON.parse(line.slice(22));if(typeof data.message==='string'&&data.message.length<=300)onProgress(data.message);}catch{}} });
    child.on('error', error => { clearTimeout(timer);if(error.name==='AbortError')terminate();reject(error); });
    child.on('close', code => {
      clearTimeout(timer);
      if (code !== 0) reject(new Error(Buffer.concat(errors).toString().trim() || `SSH exited with code ${code}.`));
      else resolve(Buffer.concat(output).toString());
    });
    child.stdin.on('error', () => {});
    child.stdin.end(input);
  });
}
function previewPort(value,reserved=[]){if(!Number.isInteger(value)||value<1024||value>65535||[8765,9876,9877,9880,...reserved].includes(value))throw new Error('Choose one localhost development port outside workspace management ports.');return value;}
function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer(); server.once('error', reject);
    server.listen(0, '127.0.0.1', () => { const port = server.address().port; server.close(() => resolve(port)); });
  });
}
function parseSetupResponse(output) {
  // Login scripts and SSH wrappers can print before or after our JSON response.
  for (const line of String(output).split(/\r?\n/).reverse()) {
    let value;
    try { value = JSON.parse(line.trim()); } catch { continue; }
    if (value && typeof value.token === 'string' && /^[A-Za-z0-9_-]{24,256}$/.test(value.token) && Number.isInteger(value.port) && value.port >= 1024 && value.port <= 65535) return value;
  }
  throw new Error('Remote setup did not return valid connection credentials. Check the remote service log.');
}
async function startTunnel(config, ready, { sshOptions = SSH_OPTIONS, signal } = {}) {
  // ClearAllForwardings clears command-line -L as well as inherited forwards.
  // Connect a private master first; then add only our listener over its socket.
  signal?.throwIfAborted();
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ss-'));
  const control = path.join(directory, 's');
  const cleanup = () => fs.rmSync(directory, { recursive: true, force: true });
  const child = spawn('/usr/bin/ssh', [...sshOptions, '-M', '-S', control, '-N', '-o', 'ControlPersist=no', config.target], { stdio: ['ignore', 'ignore', 'pipe'], signal });
  let failure = ''; let exited = false;
  child.stderr.on('data', chunk => { failure = (failure + chunk.toString()).slice(-10000); });
  child.on('error', error => { failure = error.message; exited = true; });
  child.on('exit', () => { exited = true; });
  child.once('close', cleanup);
  const controlArgs = ['-F', '/dev/null', '-S', control];
  try {
    let connected = false;
    for (let attempt = 0; attempt < 150; attempt++) {
      signal?.throwIfAborted();
      if (exited) throw new Error(failure.trim() || 'SSH tunnel closed.');
      if (fs.existsSync(control)) {
        await collect('/usr/bin/ssh', [...controlArgs, '-O', 'check', config.target], undefined, 5000, signal);
        connected = true;
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    if (!connected) throw new Error('SSH did not establish the workspace connection in time.');
    const port = await freePort();
    await collect('/usr/bin/ssh', [...controlArgs, '-O', 'forward', '-o', 'ExitOnForwardFailure=yes', '-L', `127.0.0.1:${port}:127.0.0.1:${ready.port}`, config.target], undefined, 5000, signal);
    const origin = `http://127.0.0.1:${port}`;
    for (let attempt = 0; attempt < 25; attempt++) {
      signal?.throwIfAborted();
      if (exited) throw new Error(failure.trim() || 'SSH tunnel closed.');
      try {
        const response = await fetch(origin + '/api/session', { headers: { Authorization: `Bearer ${ready.token}` }, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(1500)]) : AbortSignal.timeout(1500) });
        if (response.ok && (await response.json()).ok) return {config,origin,token:ready.token,child,async openPort(remotePort){previewPort(remotePort,[ready.port]);if(exited)throw new Error('Reconnect this workspace before opening a port.');const localPort=await freePort(),mapping=`127.0.0.1:${localPort}:127.0.0.1:${remotePort}`;await collect('/usr/bin/ssh',[...controlArgs,'-O','forward','-o','ExitOnForwardFailure=yes','-L',mapping,config.target],undefined,5000);let closed=false;return {url:'http://127.0.0.1:'+localPort,async close(){if(closed)return;closed=true;if(!exited)await collect('/usr/bin/ssh',[...controlArgs,'-O','cancel','-L',mapping,config.target],undefined,5000).catch(()=>{});}};}};
        if (response.status === 401 || response.status === 403) throw new Error('The remote rejected the workspace credentials. Reconnect to run setup again.');
      } catch (error) {
        if (error.message.startsWith('The remote rejected')) throw error;
      }
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    throw new Error('The SSH tunnel opened, but the workspace did not respond.');
  } catch (error) {
    child.kill();
    throw error;
  }
}
async function connect(raw, onStatus = () => {}, { signal } = {}) {
  signal?.throwIfAborted();
  const config = validateConfig(raw);
  onStatus(config.mode === 'local' ? 'Starting your workspace on this machine…' : 'Connecting securely over SSH…');
  const script = fs.readFileSync(path.join(__dirname, 'bootstrap.py'), 'utf8');
  const bundle = fs.readFileSync(path.join(__dirname, 'remote.tar.gz'));
  const setupConfig={...config,bundle_size:bundle.length};
  const remoteCommand = `python3 -c ${shellQuote(script)} ${shellQuote(JSON.stringify(setupConfig))}`;
  let result;
  if (config.mode === 'local') {
    try { result = await collect(process.env.SUPERSURFER_PYTHON || 'python3', ['-c', script, JSON.stringify(setupConfig)], bundle, 90000, signal, onStatus); }
    catch (error) { if (error.code === 'ENOENT') throw new Error('This machine needs Python 3.10+ to run a local workspace. Install Python, then reopen SuperSurfer.'); throw error; }
  } else result = await collect('/usr/bin/ssh', [...BOOTSTRAP_SSH_OPTIONS, config.target, remoteCommand], bundle, 90000, signal, onStatus);
  signal?.throwIfAborted();
  const ready = parseSetupResponse(result);
  if (config.mode === 'local') {
    const origin = `http://127.0.0.1:${ready.port}`;
    const response = await fetch(origin + '/api/session', { headers: { Authorization: `Bearer ${ready.token}` }, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000) });
    if (!response.ok || !(await response.json()).ok) throw new Error('The local workspace did not pass its connection check.');
    return {config,origin,token:ready.token,child:null,async openPort(port){previewPort(port,[ready.port]);return {url:'http://127.0.0.1:'+port,async close(){}};}};
  }
  onStatus('Remote workspace is ready. Opening the connection…');
  return startTunnel(config, ready, { signal });
}
module.exports = { previewPort, connect, startTunnel, validateConfig, shellQuote, parseSetupResponse, SSH_OPTIONS, BOOTSTRAP_SSH_OPTIONS, collect };
