'use strict';
// Opt in because this starts an isolated loopback sshd. No user SSH files are read
// or written. Run: SUPERSURFER_SSHD_TEST=1 node --test tests/ssh.integration.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const http = require('node:http');
const { setTimeout: delay } = require('node:timers/promises');
const { startTunnel, SSH_OPTIONS } = require('../desktop/connection.cjs');

const enabled = process.env.SUPERSURFER_SSHD_TEST === '1';
const sshd = ['/usr/sbin/sshd', '/usr/local/sbin/sshd'].find(file => fs.existsSync(file));
const skip = !enabled ? 'Set SUPERSURFER_SSHD_TEST=1 to run the localhost SSH regression.' : !sshd ? 'Local sshd is unavailable.' : false;

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return server.address().port;
}
async function unusedPort() {
  const server = net.createServer();
  const port = await listen(server);
  await new Promise(resolve => server.close(resolve));
  return port;
}
async function isListening(port) {
  return new Promise(resolve => {
    const socket = net.connect({ host: '127.0.0.1', port });
    let done = false;
    const finish = result => { if (!done) { done = true; socket.destroy(); resolve(result); } };
    socket.once('connect', () => finish(true));
    socket.once('error', () => finish(false));
    socket.setTimeout(500, () => finish(false));
  });
}
async function terminate(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  const exited = once(child, 'exit').catch(() => {});
  child.kill('SIGTERM');
  await Promise.race([exited, delay(2000)]);
  if (child.exitCode === null && child.signalCode === null) {
    child.kill('SIGKILL');
    await exited;
  }
}
async function closeServer(server) {
  if (!server.listening) return;
  const closed = new Promise(resolve => server.close(resolve));
  server.closeAllConnections?.();
  await closed;
}
async function fixture(t) {
  // Short path also exercises the same Unix-domain socket limits as macOS.
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ss-test-'));
  const servers = [], children = [];
  t.after(async () => {
    for (const child of children.reverse()) await terminate(child);
    for (const server of servers.reverse()) await closeServer(server);
    fs.rmSync(directory, { recursive: true, force: true });
  });
  const hostKey = path.join(directory, 'host_key');
  const clientKey = path.join(directory, 'client_key');
  for (const key of [hostKey, clientKey]) execFileSync('/usr/bin/ssh-keygen', ['-q', '-t', 'ed25519', '-N', '', '-f', key]);
  const token = 'isolated-super-surfer-test-token-123456';
  const received = [];
  const remote = http.createServer((request, response) => {
    received.push({ url: request.url, authorization: request.headers.authorization });
    response.setHeader('Content-Type', 'application/json');
    if (request.url === '/api/health') return response.end(JSON.stringify({ ok: true }));
    if (request.url === '/api/session' && request.headers.authorization === `Bearer ${token}`) return response.end(JSON.stringify({ ok: true }));
    if (request.url === '/probe' && request.headers.authorization === `Bearer ${token}`) return response.end(JSON.stringify({ fixture: 'isolated-sshd' }));
    response.statusCode = 401;
    response.end(JSON.stringify({ error: 'Unauthorized fixture request' }));
  });
  servers.push(remote);
  const remotePort = await listen(remote);
  const occupied = net.createServer(socket => {
    socket.on('error', () => {}); // Port probes deliberately close immediately.
    socket.end('original listener');
  });
  servers.push(occupied);
  const occupiedPort = await listen(occupied);
  const unwantedPort = await unusedPort();
  const sshPort = await unusedPort();
  const daemonConfig = path.join(directory, 'sshd_config');
  fs.writeFileSync(daemonConfig, [
    `Port ${sshPort}`, 'ListenAddress 127.0.0.1', `HostKey ${hostKey}`,
    `PidFile ${path.join(directory, 'sshd.pid')}`, `AuthorizedKeysFile ${clientKey}.pub`,
    'StrictModes no', 'PasswordAuthentication no', 'KbdInteractiveAuthentication no',
    'PubkeyAuthentication yes', 'AuthenticationMethods publickey', 'UsePAM no',
    'PermitRootLogin yes', 'AllowTcpForwarding local', 'GatewayPorts no',
    `PermitOpen 127.0.0.1:${remotePort}`, 'LogLevel ERROR',
    `AllowUsers ${os.userInfo().username}`, '',
  ].join('\n'), { mode: 0o600 });
  let daemonError = '';
  const daemon = spawn(sshd, ['-D', '-e', '-f', daemonConfig], { stdio: ['ignore', 'ignore', 'pipe'] });
  children.push(daemon);
  daemon.stderr.on('data', chunk => { daemonError = (daemonError + chunk).slice(-5000); });
  let spawnError;
  daemon.on('error', error => { spawnError = error; });
  for (let i = 0; i < 60; i++) {
    if (spawnError) throw spawnError;
    if (daemon.exitCode !== null) throw new Error(`Isolated sshd exited: ${daemonError}`);
    if (await isListening(sshPort)) break;
    await delay(50);
  }
  assert.equal(await isListening(sshPort), true, `Isolated sshd did not listen: ${daemonError}`);
  const knownHosts = path.join(directory, 'known_hosts');
  const publicHost = fs.readFileSync(hostKey + '.pub', 'utf8').trim().split(/\s+/).slice(0, 2).join(' ');
  fs.writeFileSync(knownHosts, `[127.0.0.1]:${sshPort} ${publicHost}\n`, { mode: 0o600 });
  const clientConfig = path.join(directory, 'ssh_config');
  fs.writeFileSync(clientConfig, [
    'Host supersurfer-regression.invalid', '  HostName 127.0.0.1', `  Port ${sshPort}`,
    `  User ${os.userInfo().username}`, `  IdentityFile ${clientKey}`, '  IdentitiesOnly yes',
    `  UserKnownHostsFile ${knownHosts}`, '  GlobalKnownHostsFile /dev/null',
    '  StrictHostKeyChecking yes', '  ControlMaster auto', '  ControlPersist 600',
    `  ControlPath ${path.join(directory, 'user-master')}`, '  ForkAfterAuthentication yes',
    `  LocalForward 127.0.0.1:${occupiedPort} 127.0.0.1:${remotePort}`,
    `  LocalForward 127.0.0.1:${unwantedPort} 127.0.0.1:${remotePort}`, '',
  ].join('\n'), { mode: 0o600 });
  return { directory, children, occupiedPort, unwantedPort, received, token,
    config: { target: 'supersurfer-regression.invalid', remotePort },
    ready: { port: remotePort, token }, sshOptions: ['-F', clientConfig, ...SSH_OPTIONS] };
}

test('private SSH master ignores inherited forwards and cleans up only its own tunnel', { skip, timeout: 45000 }, async t => {
  const f = await fixture(t);
  const result = await startTunnel(f.config, f.ready, { sshOptions: f.sshOptions });
  f.children.push(result.child);
  assert.equal(result.token, f.token);
  assert.equal(result.child.exitCode, null, 'Master must remain the owned foreground process');
  assert.equal(await isListening(f.occupiedPort), true, 'Original colliding listener must survive');
  assert.equal(await isListening(f.unwantedPort), false, 'Unused inherited LocalForward must not appear');
  const response = await fetch(result.origin + '/probe', { headers: { Authorization: `Bearer ${result.token}` } });
  assert.deepEqual(await response.json(), { fixture: 'isolated-sshd' });
  assert.ok(f.received.some(r => r.url === '/api/session' && r.authorization === `Bearer ${f.token}`), 'Tunnel health must authenticate the remote session');
  assert.equal(fs.existsSync(path.join(f.directory, 'user-master')), false, 'The user-configured master socket must remain unused');
  const socketIndex = result.child.spawnargs.indexOf('-S');
  assert.ok(socketIndex > -1, 'Dedicated master must have an explicit private control socket');
  const socketPath = result.child.spawnargs[socketIndex + 1];
  assert.ok(fs.existsSync(socketPath));
  await terminate(result.child);
  const localPort = Number(new URL(result.origin).port);
  for (let i = 0; i < 30 && fs.existsSync(path.dirname(socketPath)); i++) await delay(50);
  assert.equal(await isListening(localPort), false, 'Own forwarded port must close');
  assert.equal(fs.existsSync(path.dirname(socketPath)), false, 'Own temporary socket directory must be removed');
  assert.equal(await isListening(f.occupiedPort), true, 'Disconnect must preserve unrelated listeners');
  assert.equal(await isListening(f.unwantedPort), false);
});

test('rejected session credentials close the dedicated master and private socket', { skip, timeout: 45000 }, async t => {
  const f = await fixture(t);
  // Keep this call's temporary master directory inside the fixture, so cleanup
  // can be asserted without inspecting or affecting another app's temp files.
  const originalTmpdir = os.tmpdir;
  os.tmpdir = () => f.directory;
  try {
    await assert.rejects(
      startTunnel(f.config, { ...f.ready, token: 'incorrect-test-token' }, { sshOptions: f.sshOptions }),
      /remote rejected the workspace credentials/,
    );
  } finally {
    os.tmpdir = originalTmpdir;
  }
  const ownDirectories = () => fs.readdirSync(f.directory).filter(name => name.startsWith('ss-'));
  for (let i = 0; i < 40 && ownDirectories().length; i++) await delay(50);
  assert.deepEqual(ownDirectories(), [], 'Failed connection must clean its owned master socket directory');
  assert.ok(f.received.some(r => r.url === '/api/session' && r.authorization === 'Bearer incorrect-test-token'));
  assert.equal(await isListening(f.occupiedPort), true, 'Failed connection must preserve unrelated listeners');
  assert.equal(await isListening(f.unwantedPort), false);
  assert.equal(fs.existsSync(path.join(f.directory, 'user-master')), false);
});
