'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {loginCommand,openProviderLogin}=require('../desktop/provider-login.cjs');
test('login command is fixed and bound to validated workspace host',()=>{
 const remote=loginCommand({mode:'remote',target:'research@tulip'},'claude');
 assert.match(remote,/ssh -t/);assert.match(remote,/StrictHostKeyChecking=yes/);assert.match(remote,/ClearAllForwardings=yes/);assert.match(remote,/'research@tulip'/);assert.match(remote,/claude auth login/);
 assert.throws(()=>loginCommand({mode:'remote',target:'host; steal-token'},'claude'));assert.throws(()=>loginCommand({mode:'local'},'claude; anything'));
 assert.equal(loginCommand({mode:'local'},'cursor').includes('ssh'),false);
});
test('macOS terminal is launched without capturing provider output or accepting shell input',async()=>{
 let call;const result=await openProviderLogin({mode:'remote',target:'tulip'},'cursor',{platform:'darwin',run:(...args)=>{call=args;args.at(-1)(null);}});
 assert.equal(result.opened,true);assert.equal(call[0],'/usr/bin/osascript');assert.match(call[1].join(' '),/tell application "Terminal"/);assert.match(call[1].join(' '),/agent login/);assert.equal(call[2].timeout,15000);
});
test('other platforms return an explicit command without launching a shell',async()=>{
 const result=await openProviderLogin({mode:'remote',target:'tulip'},'claude',{platform:'linux',run:()=>assert.fail('Must not run')});assert.equal(result.opened,false);assert.match(result.command,/claude auth login/);
});
test('remote Cursor login prints a browser link and resolves both CLI names',()=>{
 const command=loginCommand({mode:'remote',target:'research'},'cursor');
 assert.match(command,/NO_OPEN_BROWSER=1/);assert.match(command,/elif command -v cursor-agent/);
 assert.doesNotMatch(loginCommand({mode:'local'},'cursor'),/NO_OPEN_BROWSER/);
});
test('Cursor installation is an explicit fixed host-bound action',async()=>{
 const command=loginCommand({mode:'remote',target:'research'},'cursor','install');
 assert.match(command,/'research'/);assert.match(command,/curl https:\/\/cursor.com\/install -fsS \| bash/);
 assert.throws(()=>loginCommand({mode:'local'},'claude','install'));
 assert.throws(()=>loginCommand({mode:'local'},'cursor','install; anything'));
 const result=await openProviderLogin({mode:'remote',target:'research'},'cursor',{platform:'darwin',run:(...args)=>args.at(-1)(new Error('Terminal unavailable'))});
 assert.equal(result.opened,false);assert.match(result.command,/ssh -t/);assert.match(result.error,/displayed command/);
});
