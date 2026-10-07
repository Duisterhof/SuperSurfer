'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { validateConfig, shellQuote, parseSetupResponse, SSH_OPTIONS } = require('../desktop/connection.cjs');
test('SSH option injection and relative paths are rejected', () => {
  for (const target of ['-oProxyCommand=touch bad', 'tulip; echo bad', 'tulip\nwhoami', '']) assert.throws(() => validateConfig({ target }));
  assert.throws(() => validateConfig({ target: 'tulip', remoteRoot: '../something' }));
  assert.throws(() => validateConfig({ target: 'tulip', remotePort: 22 }));
  assert.equal(validateConfig({ target: 'bart@tulip' }).remoteRoot, '~/.local/share/supersurfer');
});
test('SSH banners and trailing messages do not hide successful setup', () => {
  const ready = { token: 'test-session-token-1234567890', port: 8765, version: '0.1.1' };
  const output = 'Welcome to Tulip\r\n' + JSON.stringify(ready) + '\r\nWarning: a separate forwarding port is already in use\n';
  assert.deepEqual(parseSetupResponse(output), ready);
  assert.throws(() => parseSetupResponse('Connected\n{"token":"too-short","port":8765}'));
  assert.throws(() => parseSetupResponse(JSON.stringify({ ...ready, port: 99999 })));
});
test('remote shell arguments preserve literal code and whitespace', () => {
  const { execFileSync } = require('node:child_process');
  const value = "some ' $(touch never) `echo no` folder\nnext";
  const output = execFileSync('/bin/sh', ['-c', `printf %s ${shellQuote(value)}`], { encoding: 'utf8' });
  assert.equal(output, value);
  assert.ok(SSH_OPTIONS.includes('StrictHostKeyChecking=yes'));
});
