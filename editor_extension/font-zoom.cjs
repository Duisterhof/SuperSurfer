'use strict';

function fontZoom(vscode) {
  let baseline, changed = false;
  return async (kind, target) => {
    if (target !== 'terminal') return vscode.commands.executeCommand({
      'zoom-in': 'editor.action.fontZoomIn',
      'zoom-out': 'editor.action.fontZoomOut',
      'zoom-reset': 'editor.action.fontZoomReset',
    }[kind]);
    // Each pane has its own generated workspace. Avoid the native terminal zoom
    // commands, which can write shared user settings and resize other panes.
    const config = vscode.workspace.getConfiguration('terminal.integrated');
    if (kind === 'zoom-reset') {
      if (changed) await config.update('fontSize', baseline, vscode.ConfigurationTarget.Workspace);
      changed = false;
      return;
    }
    if (!changed) baseline = config.inspect('fontSize')?.workspaceValue;
    const size = config.get('fontSize', 14);
    await config.update('fontSize', Math.max(6, Math.min(100, size + (kind === 'zoom-in' ? 1 : -1))), vscode.ConfigurationTarget.Workspace);
    changed = true;
  };
}
module.exports = {fontZoom};
