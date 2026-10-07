'use strict';
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const os = require('node:os');

const SSH_OPTIONS = ['-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ClearAllForwardings=yes', '-o', 'ForkAfterAuthentication=no', '-o', 'ConnectTimeout=12', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3'];
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
function collect(command, args, input, timeout = 90000) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['pipe', 'pipe', 'pipe'] });
    const output = [], errors = []; let size = 0;
    const timer = setTimeout(() => { child.kill('SIGTERM'); reject(new Error('SSH connection timed out. Check that the remote host is reachable.')); }, timeout);
    child.stdout.on('data', chunk => { size += chunk.length; if (size > 2 * 1024 * 1024) child.kill(); else output.push(chunk); });
    child.stderr.on('data', chunk => { if (errors.reduce((n, x) => n + x.length, 0) < 100000) errors.push(chunk); });
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.on('close', code => {
      clearTimeout(timer);
      if (code !== 0) reject(new Error(Buffer.concat(errors).toString().trim() || `SSH exited with code ${code}.`));
      else resolve(Buffer.concat(output).toString());
    });
    child.stdin.on('error', () => {});
    child.stdin.end(input);
  });
}
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
async function startTunnel(config, ready, { sshOptions = SSH_OPTIONS } = {}) {
  // ClearAllForwardings clears command-line -L as well as inherited forwards.
  // Connect a private master first; then add only our listener over its socket.
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ss-'));
  const control = path.join(directory, 's');
  const cleanup = () => fs.rmSync(directory, { recursive: true, force: true });
  const child = spawn('/usr/bin/ssh', [...sshOptions, '-M', '-S', control, '-N', '-o', 'ControlPersist=no', config.target], { stdio: ['ignore', 'ignore', 'pipe'] });
  let failure = ''; let exited = false;
  child.stderr.on('data', chunk => { failure = (failure + chunk.toString()).slice(-10000); });
  child.on('error', error => { failure = error.message; exited = true; });
  child.on('exit', () => { exited = true; });
  child.once('close', cleanup);
  const controlArgs = ['-F', '/dev/null', '-S', control];
  try {
    let connected = false;
    for (let attempt = 0; attempt < 150; attempt++) {
      if (exited) throw new Error(failure.trim() || 'SSH tunnel closed.');
      if (fs.existsSync(control)) {
        await collect('/usr/bin/ssh', [...controlArgs, '-O', 'check', config.target], undefined, 5000);
        connected = true;
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    if (!connected) throw new Error('SSH did not establish the workspace connection in time.');
    const port = await freePort();
    await collect('/usr/bin/ssh', [...controlArgs, '-O', 'forward', '-o', 'ExitOnForwardFailure=yes', '-L', `127.0.0.1:${port}:127.0.0.1:${ready.port}`, config.target], undefined, 5000);
    const origin = `http://127.0.0.1:${port}`;
    for (let attempt = 0; attempt < 25; attempt++) {
      if (exited) throw new Error(failure.trim() || 'SSH tunnel closed.');
      try {
        const response = await fetch(origin + '/api/session', { headers: { Authorization: `Bearer ${ready.token}` }, signal: AbortSignal.timeout(1500) });
        if (response.ok && (await response.json()).ok) return { config, origin, token: ready.token, child };
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
async function connect(raw, onStatus = () => {}) {
  const config = validateConfig(raw);
  onStatus(config.mode === 'local' ? 'Starting your workspace on this machine…' : 'Connecting securely over SSH…');
  const script = fs.readFileSync(path.join(__dirname, 'bootstrap.py'), 'utf8');
  const bundle = fs.readFileSync(path.join(__dirname, 'remote.tar.gz'));
  const remoteCommand = `python3 -c ${shellQuote(script)} ${shellQuote(JSON.stringify(config))}`;
  let result;
  if (config.mode === 'local') {
    try { result = await collect(process.env.SUPERSURFER_PYTHON || 'python3', ['-c', script, JSON.stringify(config)], bundle); }
    catch (error) { if (error.code === 'ENOENT') throw new Error('This machine needs Python 3.10+ to run a local workspace. Install Python, then reopen SuperSurfer.'); throw error; }
  } else result = await collect('/usr/bin/ssh', [...SSH_OPTIONS, config.target, remoteCommand], bundle);
  const ready = parseSetupResponse(result);
  if (config.mode === 'local') {
    const origin = `http://127.0.0.1:${ready.port}`;
    const response = await fetch(origin + '/api/session', { headers: { Authorization: `Bearer ${ready.token}` }, signal: AbortSignal.timeout(5000) });
    if (!response.ok || !(await response.json()).ok) throw new Error('The local workspace did not pass its connection check.');
    return { config, origin, token: ready.token, child: null };
  }
  onStatus('Remote workspace is ready. Opening the connection…');
  return startTunnel(config, ready);
}
module.exports = { connect, startTunnel, validateConfig, shellQuote, parseSetupResponse, SSH_OPTIONS };
