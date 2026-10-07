'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {workspacePreference} = require('../desktop/preferences.cjs');
test('custom experiment tabs survive native preference round trips',()=>{
 const value={view:'workspace',tab:'page:page_a123bc',projectId:'p1',experimentId:'e1',chatWidth:520,chatMaximized:true};
 const restored=workspacePreference(JSON.parse(JSON.stringify(workspacePreference(value))));
 assert.equal(restored.tab,value.tab);assert.equal(restored.chatWidth,520);assert.equal(restored.chatMaximized,true);
 for(const tab of ['page:../../secret','page:page_','javascript:alert(1)',{}])assert.equal(workspacePreference({...value,tab}).tab,'overview');
 for(const value of [null,[],42])assert.throws(()=>workspacePreference(value));
});
