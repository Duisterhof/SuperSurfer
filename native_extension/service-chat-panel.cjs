"use strict";
const crypto = require("node:crypto");

function chatPanel({ vscode, context, binding, agents, split, openBoard, splitAgent, panels, onChange, output }) {
  const scope = binding.scope;
  if (panels.has(scope)) { panels.get(scope).reveal(split ? vscode.ViewColumn.Beside : undefined); return; }
  const panel = vscode.window.createWebviewPanel("supersurferNative.chat", binding.name || binding.title,
    split ? vscode.ViewColumn.Beside : vscode.ViewColumn.Active,
    { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, "media")] });
  panels.set(scope, panel);
  const uri = file => panel.webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, "media", file));
  const nonce = crypto.randomBytes(18).toString("base64");
  panel.webview.html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${panel.webview.cspSource}; script-src 'nonce-${nonce}';"><link rel="stylesheet" href="${uri("chat.css")}"></head><body><div id="app"></div><script nonce="${nonce}" src="${uri("chat.js")}"></script></body></html>`;
  let closed = false, polling = false, limit = 150, acting = false;
  async function refresh() {
    if (closed || polling || !panel.visible) return;
    polling = true;
    try { await panel.webview.postMessage({ type: "chat", chat: await agents.chat(scope, limit), binding }); }
    catch (e) { if (!closed) await panel.webview.postMessage({ type: "connectionError", message: e.message }); }
    finally { polling = false; }
  }
  const timer = setInterval(refresh, 2000);
  panel.onDidDispose(() => { closed = true; clearInterval(timer); panels.delete(scope); });
  panel.onDidChangeViewState(() => refresh());
  panel.webview.onDidReceiveMessage(async message => {
    try {
      if (message.op === "ready") {
        await panel.webview.postMessage({ type: "restore", draft: context.workspaceState.get("chat-draft:" + scope, "") });
        return refresh();
      }
      if (message.op === "draft") {
        if (typeof message.text !== "string" || message.text.length > 100000) throw new Error("Draft is too long");
        return context.workspaceState.update("chat-draft:" + scope, message.text);
      }
      if (message.op === "refresh") return refresh();
      if (message.op === "earlier") { limit = Math.min(limit + 150, 100000); return refresh(); }
      if (message.op === "board" && binding.project_id) return openBoard();
      if (message.op === "split") return splitAgent();
      if (message.op === "link") {
        const url = new URL(message.url);
        if (!["https:", "http:"].includes(url.protocol)) throw new Error("Only web links can be opened from this view.");
        return vscode.env.openExternal(vscode.Uri.parse(url.href));
      }
      if (acting) throw new Error("Wait for the current request to finish.");
      acting = true;
      try {
        await agents.action(scope, message.op, message.args);
        await panel.webview.postMessage({ type: "result", op: message.op, text: message.args?.text });
        await refresh();
        onChange().catch(e => output.appendLine(e.message));
      } finally { acting = false; }
    } catch (e) {
      await panel.webview.postMessage({ type: "actionError", op: message.op, message: e.message + " Check the conversation before retrying; requests are never automatically replayed." });
    }
  });
  return panel;
}
module.exports = { chatPanel };
