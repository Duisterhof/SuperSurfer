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
