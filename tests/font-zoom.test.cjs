const {test}=require('node:test'),assert=require('node:assert/strict');
const {fontZoom}=require('../editor_extension/font-zoom.cjs');
test('terminal zoom is pane-local and reset restores inherited or explicit size',async()=>{
 for(const initial of [undefined,18]){
  let workspaceValue=initial;const calls=[];
  const vscode={ConfigurationTarget:{Workspace:2},commands:{executeCommand:async id=>calls.push(id)},workspace:{getConfiguration:section=>{
   assert.equal(section,'terminal.integrated');return {
    get:()=>workspaceValue??14,inspect:()=>({workspaceValue}),
    update:async(key,value,target)=>{assert.equal(key,'fontSize');assert.equal(target,2);workspaceValue=value;},
   };
  }}};
  const zoom=fontZoom(vscode);await zoom('zoom-in','terminal');assert.equal(workspaceValue,(initial??14)+1);
  await zoom('zoom-out','terminal');assert.equal(workspaceValue,initial??14);
  await zoom('zoom-in','terminal');await zoom('zoom-reset','terminal');assert.equal(workspaceValue,initial);
  assert.deepEqual(calls,[]);
  await zoom('zoom-in','editor');assert.deepEqual(calls,['editor.action.fontZoomIn']);assert.equal(workspaceValue,initial);
 }
});
