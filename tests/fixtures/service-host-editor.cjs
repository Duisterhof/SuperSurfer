"use strict";
// Runs only in the isolated VS Code extension-test process.
const vscode = require("vscode"), fs = require("node:fs"), path = require("node:path");
exports.run = async () => {
  const root = process.env.SS_SERVICE_HOST_QA;
  if (!root) throw new Error("An isolated QA directory is required.");
  try {
    const info = JSON.parse(fs.readFileSync(path.join(root, "fixture.json")));
    await vscode.workspace.getConfiguration("supersurferNative").update("stateDirectory", info.state, vscode.ConfigurationTarget.Global);
    const extension = vscode.extensions.getExtension("supersurfer.native-workflows");
    await extension.activate();
    await vscode.window.showTextDocument(vscode.Uri.file(path.join(info.binding.repo, "README.md")));
    await vscode.commands.executeCommand("workbench.view.extension.supersurferNative");
    await vscode.commands.executeCommand("supersurferNative.openChat", info.binding);
    let processing = false;
    setInterval(async () => {
      const file = path.join(root, "command.json");
      if (processing || !fs.existsSync(file)) return;
      processing = true;
      try {
        const value = JSON.parse(fs.readFileSync(file)); fs.unlinkSync(file);
        await vscode.commands.executeCommand(value.command, ...(value.args || []));
        fs.writeFileSync(path.join(root, "command-result.json"), JSON.stringify({ ok: true }));
      } catch (e) { fs.writeFileSync(path.join(root, "command-result.json"), JSON.stringify({ error: e.message })); }
      finally { processing = false; }
    }, 100);
    fs.writeFileSync(path.join(root, "ready.json"), JSON.stringify({ commands: (await vscode.commands.getCommands(true)).filter(c => c.includes("supersurfer") || c.includes("remote-")) }));
    // Keep the test host open for native UI interaction and reconnect checks.
    await new Promise(() => {});
  } catch (e) { fs.writeFileSync(path.join(root, "error.txt"), e.stack); throw e; }
};
