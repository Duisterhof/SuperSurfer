'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { validateConfig, shellQuote, parseSetupResponse, SSH_OPTIONS, BOOTSTRAP_SSH_OPTIONS,collect } = require('../desktop/connection.cjs');
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

test('bootstrap transport cannot inherit a shared master, null stdin or tunnel-only session',()=>{
 for(const option of ['ControlMaster=no','ControlPath=none','ControlPersist=no','StdinNull=no','SessionType=default','RemoteCommand=none','StrictHostKeyChecking=yes','ClearAllForwardings=yes'])assert.ok(BOOTSTRAP_SSH_OPTIONS.includes(option));
});
test('setup progress handles fragmented lines and ordinary SSH banners',async()=>{
 const script=`process.stderr.write('Welcome to the host\\nSUPERSURFER_PRO');setTimeout(()=>{process.stderr.write('GRESS: '+JSON.stringify({message:'Uploading the workspace…'})+'\\n');process.stdout.write('ready');},30);`;
 const status=[];assert.equal(await collect(process.execPath,['-e',script],undefined,1000,undefined,message=>status.push(message)),'ready');assert.deepEqual(status,['Uploading the workspace…']);
});
test('a timed-out setup kills only its owned child even if SIGTERM is ignored',async t=>{
 const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{setTimeout:delay}=require('node:timers/promises');
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'ss-setup-timeout-')),file=path.join(directory,'child.pid');t.after(()=>fs.rmSync(directory,{recursive:true,force:true}));
 const script=`require('node:fs').writeFileSync(process.argv[1],String(process.pid));process.on('SIGTERM',()=>{});setInterval(()=>{},1000);`;
 await assert.rejects(collect(process.execPath,['-e',script,file],undefined,150),/Workspace connection timed out/);
 const pid=Number(fs.readFileSync(file,'utf8'));let live=true;for(let i=0;i<30;i++){try{process.kill(pid,0);}catch{live=false;break;}await delay(50);}assert.equal(live,false);
});

test('port previews accept one explicit development port and exclude workspace management ports',()=>{const {previewPort}=require('../desktop/connection.cjs');assert.equal(previewPort(8000),8000);for(const value of [true,'8000',0,22,8765,9876,9877,9880,65536,8000.5])assert.throws(()=>previewPort(value));assert.throws(()=>previewPort(9000,[9000]));});
