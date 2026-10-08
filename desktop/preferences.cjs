'use strict';

function workspacePreference(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid workspace preference.');
  return {
    view: ['workspace','compute','settings'].includes(value.view) ? value.view : 'workspace',
    tab: ['overview','runs','results','compute','surfboard','artifacts','activity','editor','chat','documents','preview'].includes(value.tab) || /^page:page_[a-f0-9]+$/.test(value.tab || '') ? value.tab : 'overview',
    projectId: typeof value.projectId === 'string' ? value.projectId.slice(0,200) : null,
    experimentId: typeof value.experimentId === 'string' ? value.experimentId.slice(0,200) : null,
    chatVisible: value.chatVisible !== false,
    chatWidth: Number.isFinite(value.chatWidth) ? Math.max(280, Math.min(760, value.chatWidth)) : 390,
    chatMaximized: value.chatMaximized === true,
  };
}

module.exports = { workspacePreference };
