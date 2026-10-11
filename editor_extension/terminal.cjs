'use strict';
// Each editor session owns its project terminal; never adopt an unrelated active one.
function projectTerminal(vscode) {
  let terminal;
  return folder => {
    if (typeof folder !== 'string' || !folder.startsWith('/') || /[\0\r\n]/.test(folder)) throw new Error('Reconnect this project before opening its terminal.');
    if (!terminal || !vscode.window.terminals.includes(terminal)) {
      terminal = vscode.window.createTerminal({name:'Project terminal', cwd:folder});
      // A login profile may cd elsewhere during startup. Queue the project cd once,
      // after that startup, without moving a terminal the user has already used.
      terminal.sendText("cd -- '" + folder.replaceAll("'", "'\\''") + "'", true);
    }
    terminal.show();
    return terminal;
  };
}
module.exports = {projectTerminal};
