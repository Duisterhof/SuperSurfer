'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {workspacePreference} = require('../desktop/preferences.cjs');
test('custom experiment tabs survive native preference round trips',()=>{
 const value={view:'workspace',tab:'page:page_a123bc',projectId:'p1',experimentId:'e1',chatWidth:520,chatMaximized:true,filesHeight:315,projectTreeHeight:180};
 const restored=workspacePreference(JSON.parse(JSON.stringify(workspacePreference(value))));
 assert.equal(restored.tab,value.tab);assert.equal(restored.chatWidth,520);assert.equal(restored.chatMaximized,true);
 assert.equal(restored.filesHeight,315);assert.equal(restored.projectTreeHeight,180);
 for(const tab of ['editor','chat','documents','preview','view-analysis','CustomPage123'])assert.equal(workspacePreference({...value,tab}).tab,tab);
 for(const tab of ['page:../../secret','page:page_','javascript:alert(1)',{}])assert.equal(workspacePreference({...value,tab}).tab,'overview');
 for(const value of [null,[],42])assert.throws(()=>workspacePreference(value));
});

test('task tabs survive native persistence and reject foreign values',()=>{const value=workspacePreference({taskTabs:{'vla/E15':'results','vla/E12':'runs','vla/_project':'compute','../bad':'editor','vla/E17':{},'vla/E18':'javascript:alert(1)'}});assert.deepEqual(value.taskTabs,{'vla/E15':'results','vla/E12':'runs','vla/_project':'compute'});});
