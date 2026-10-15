'use strict';

function resultScaleKey(key) {
  return typeof key === 'string' && /^[A-Za-z0-9_:-]{1,200}\/[A-Za-z0-9_:-]{1,200}$/.test(key);
}
function resultScales(value) {
  return Object.fromEntries(Object.entries(value && typeof value === 'object' && !Array.isArray(value) ? value : {})
    .filter(([key, scale]) => resultScaleKey(key) && ['linear', 'log'].includes(scale)).slice(-512));
}
function validResultLegend(value) {
  return Array.isArray(value) && value.length <= 256 && value.every(key => typeof key === 'string' && key.length <= 1024);
}
function resultLegends(value) {
  const entries=Object.entries(value && typeof value === 'object' && !Array.isArray(value) ? value : {})
    .filter(([key, hidden]) => resultScaleKey(key) && validResultLegend(hidden)).slice(-512);
  // Drop oldest report preferences if a very large history would bloat windows.json.
  let size=0;
  return Object.fromEntries(entries.reverse().filter(entry => (size+=JSON.stringify(entry).length)<=1024*1024).reverse());
}

function workspacePreference(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid workspace preference.');
  return {
    resultScales: resultScales(value.resultScales),
    resultLegends: resultLegends(value.resultLegends),
    taskTabs: Object.fromEntries(Object.entries(value.taskTabs&&typeof value.taskTabs==='object'&&!Array.isArray(value.taskTabs)?value.taskTabs:{}).filter(([key,tab])=>/^[A-Za-z0-9_:-]{1,200}\/[A-Za-z0-9_:-]{1,200}$/.test(key)&&typeof tab==='string'&&/^(?:page:page_[a-f0-9]+|[A-Za-z0-9_][A-Za-z0-9_-]{0,63})$/.test(tab)).slice(-512)),
    view: ['workspace','compute','settings'].includes(value.view) ? value.view : 'workspace',
    tab: ['_files','_todos','overview','runs','results','compute','surfboard','artifacts','activity','editor','chat','documents','preview'].includes(value.tab) || /^(?:page:page_[a-f0-9]+|[A-Za-z0-9][A-Za-z0-9_-]{0,63})$/.test(value.tab || '') ? value.tab : 'overview',
    projectId: typeof value.projectId === 'string' ? value.projectId.slice(0,200) : null,
    experimentId: typeof value.experimentId === 'string' ? value.experimentId.slice(0,200) : null,
    chatVisible: value.chatVisible !== false,
    chatWidth: Number.isFinite(value.chatWidth) ? Math.max(280, Math.min(760, value.chatWidth)) : 390,
    sidebarCollapsed: value.sidebarCollapsed === true,
    sidebarWidth: Number.isFinite(value.sidebarWidth) ? Math.max(160, Math.min(600, value.sidebarWidth)) : null,
    projectTreeHeight: Number.isFinite(value.projectTreeHeight) ? Math.max(60, Math.min(1200, value.projectTreeHeight)) : null,
    filesHeight: Number.isFinite(value.filesHeight) ? Math.max(60, Math.min(1200, value.filesHeight)) : null,
    chatMaximized: value.chatMaximized === true,
    pinnedAgent: value.pinnedAgent && typeof value.pinnedAgent.scope === 'string' && /^(manager|(?:project|experiment|conversation|surfboard):[A-Za-z0-9_:-]+)$/.test(value.pinnedAgent.scope) ? {
      scope:value.pinnedAgent.scope.slice(0,256), name:String(value.pinnedAgent.name||'Agent').slice(0,160),
      projectId:typeof value.pinnedAgent.projectId==='string'?value.pinnedAgent.projectId.slice(0,200):null,
      experimentId:typeof value.pinnedAgent.experimentId==='string'?value.pinnedAgent.experimentId.slice(0,200):null, owner:'supersurfer'
    }:null,
  };
}

module.exports = { workspacePreference, resultScaleKey, resultScales, validResultLegend, resultLegends };
