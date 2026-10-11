const {test}=require('node:test'),assert=require('node:assert/strict');
const {projectTerminal}=require('../editor_extension/terminal.cjs');
test('project terminal sets absolute cwd, quotes shell paths and reuses only its own terminal',()=>{
 const calls=[],unrelated={name:'Other project'},window={terminals:[unrelated],activeTerminal:unrelated,createTerminal(options){calls.push(options);const t={sendText:(...args)=>calls.push(args),show:()=>{}};this.terminals.push(t);return t;}};
 const open=projectTerminal({window}),folder="/data/My project's $(secret) `notes`";
 const first=open(folder);assert.equal(calls[0].cwd,folder);assert.deepEqual(calls[1],["cd -- '/data/My project'\\''s $(secret) `notes`'",true]);
 assert.equal(open(folder),first);assert.equal(calls.length,2);
 window.terminals=[unrelated];assert.notEqual(open(folder),first);assert.equal(calls.length,4);
 assert.throws(()=>open('relative'));assert.throws(()=>open('/tmp/a\ncommand'));
});
