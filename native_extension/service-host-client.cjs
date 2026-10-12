"use strict";
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto"), { spawn } = require("node:child_process");
const { Host, privateJSON, atomic } = require("./host.cjs");
const { resource } = require("./service-session.cjs");
class NativeServiceChats {
  constructor(vscode, context, service) { this.vscode = vscode; this.context = context; this.service = service; this.provider = new (require("./service-provider.cjs").NativeSessionProvider)(vscode, context, this); }
  async ensure() {
    if (this.starting) return this.starting;
    this.starting = this.start().finally(() => { this.starting = undefined; });
    return this.starting;
  }
  async start() {
    const vscode = this.vscode;
    if (!vscode.workspace.isTrusted) throw new Error("Trust this workspace before connecting its agents.");
    const storage = this.context.globalStorageUri.fsPath;
    fs.mkdirSync(storage, { recursive: true, mode: 0o700 });
    const endpointFile = path.join(storage, "service-host-endpoint.json"), configFile = path.join(storage, "service-host.json");
    let endpoint;
    try {
      endpoint = privateJSON(endpointFile);
      const host = new Host(endpointFile);
      try { await host.connect(); } finally { host.close(); }
    } catch (error) {
      if (endpoint?.pid) {
        try { process.kill(endpoint.pid, 0); } catch { endpoint = undefined; }
        if (endpoint) throw new Error("The native chat bridge is running but cannot connect to SuperSurfer. Restore the service connection before retrying.");
      }
      const config = { storage, stateDirectory: this.service.directory, endpointFile, secret: crypto.randomBytes(32).toString("hex"), instanceId: "supersurfer-" + crypto.randomUUID() };
      const lockFile = path.join(storage, "service-host-start.lock");
      let lock;
      try { lock = fs.openSync(lockFile, "wx", 0o600); }
      catch (error) {
        if (error.code !== "EEXIST") throw error;
        const started = fs.statSync(lockFile).mtimeMs;
        if (Date.now() - started > 30000) { fs.unlinkSync(lockFile); return this.start(); }
        await new Promise(r => setTimeout(r, 200)); return this.start();
      }
      try {
      atomic(configFile, config);
      const log = fs.openSync(path.join(storage, "service-host.log"), "a", 0o600);
      const child = spawn(process.execPath, [path.join(__dirname, "service-host.cjs"), configFile], {
        detached: true, stdio: ["ignore", log, log], env: { ...process.env, ELECTRON_RUN_AS_NODE: "1" },
      });
      child.unref(); fs.closeSync(log);
      for (let i = 0; i < 50; i++) {
        try { const row = privateJSON(endpointFile); if (row.instanceId === config.instanceId) { endpoint = row; break; } } catch {}
        await new Promise(r => setTimeout(r, 100));
      }
      if (!endpoint || endpoint.instanceId !== config.instanceId) throw new Error("The native chat bridge could not start. See service-host.log in extension storage.");
      } finally { fs.closeSync(lock); fs.unlinkSync(lockFile); }
    }
    return { endpoint, endpointFile };
  }
  async connection() {
    if (this.host?.connected) return this.host;
    const { endpointFile } = await this.ensure();
    const host = new Host(endpointFile); await host.connect(); this.host = host; return host;
  }
  async open(binding, split = false) {
    const vscode = this.vscode;
    await this.provider.modelsReady;
    if (!this.provider.entries.has(binding.scope)) await this.provider.refresh();
    const uri = vscode.Uri.parse(resource(binding.scope));
    await vscode.commands.executeCommand(split ? "workbench.action.chat.openSessionInNewEditorGroup" : "workbench.action.chat.openSessionInEditorGroup", { resource: uri });
    if (!split) await vscode.commands.executeCommand("workbench.action.chat.openInSidebar");
  }
}
module.exports = { NativeServiceChats };
