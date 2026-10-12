"use strict";
const vscode = require("vscode");
const fs = require("node:fs"),
  path = require("node:path"),
  os = require("node:os");
const crypto = require("node:crypto"),
  { spawn } = require("node:child_process");
const { endpointFiles, privateJSON, atomic } = require("./host.cjs");
const { call } = require("./client.cjs");
const { Service } = require("./service.cjs");
const { ServiceAgents, sessionFolder } = require("./service-agents.cjs");
const { NativeServiceChats } = require("./service-host-client.cjs");

function activate(context) {
  let config,
    starting,
    selected,
    status = { bindings: [] }, projects = [], serviceError, serviceAgents, nativeChats;
  const panels = new Map(),
    changed = new vscode.EventEmitter();
  const output = vscode.window.createOutputChannel("SuperSurfer");
  const settings = () => vscode.workspace.getConfiguration("supersurferNative");
  const agents = () => serviceAgents ||= new ServiceAgents(new Service(settings().get("stateDirectory")));
  const manager = { scope: "manager", title: "Workspace manager", name: "Workspace manager", service: true };
  const fail = (e) => {
    output.appendLine(e.message);
    vscode.window.showErrorMessage("SuperSurfer: " + e.message);
  };

  async function ensure() {
    if (config) {
      try {
        await call(config, "status");
        return config;
      } catch {
        config = undefined;
      }
    }
    if (starting) return starting;
    starting = (async () => {
      if (!vscode.workspace.isTrusted)
        throw new Error("Trust this workspace before attaching an agent.");
      if (process.platform === "win32")
        throw new Error(
          "Connect to your Linux host with Remote SSH to use persistent workflows.",
        );
      let endpointFile = settings().get("endpointFile");
      const endpoints = endpointFiles(endpointFile);
      if (!endpoints.length)
        throw new Error(
          "No native Agent Host found. Connect to your host in VS Code Chat first, or select its endpoint file in SuperSurfer settings.",
        );
      endpointFile = endpoints[0];
      if (endpoints.length > 1) {
        const picked = await vscode.window.showQuickPick(
          endpoints.map((file) => {
            const e = privateJSON(file);
            return {
              label:
                e.type === "standalone" ? "Persistent host" : "Editor host",
              description: e.instanceId,
              file,
            };
          }),
          { title: "Choose the host that owns your native chats" },
        );
        if (!picked) throw new Error("No host selected.");
        endpointFile = picked.file;
        await settings().update(
          "endpointFile",
          endpointFile,
          vscode.ConfigurationTarget.Global,
        );
      }
      const storage = context.globalStorageUri.fsPath;
      fs.mkdirSync(storage, { recursive: true, mode: 0o700 });
      const configFile = path.join(storage, "companion.json");
      let existing;
      try {
        existing = privateJSON(configFile);
      } catch (e) {
        if (e.code !== "ENOENT") throw e;
      }
      const stateDirectory = settings().get("stateDirectory") || "";
      if (existing) {
        try {
          await call(existing, "status");
          if (
            existing.endpointFile !== endpointFile ||
            existing.stateDirectory !== stateDirectory
          )
            throw new Error(
              "A companion is already connected to another host. Detach its workflows and stop that companion before changing connection settings.",
            );
          return (config = existing);
        } catch (e) {
          if (!["ENOENT", "ECONNREFUSED"].includes(e.code)) throw e;
        }
      }
      const socket = path.join(
        os.tmpdir(),
        "supersurfer-" +
          crypto
            .createHash("sha256")
            .update(storage)
            .digest("hex")
            .slice(0, 16) +
          ".sock",
      );
      if (fs.existsSync(socket)) {
        const st = fs.lstatSync(socket);
        if (!st.isSocket() || st.uid !== process.getuid())
          throw new Error("Unexpected companion socket owner.");
        fs.unlinkSync(socket);
      }
      config = {
        storage,
        stateDirectory,
        endpointFile,
        socket,
        secret: crypto.randomBytes(32).toString("hex"),
      };
      atomic(configFile, config);
      const log = fs.openSync(path.join(storage, "companion.log"), "a", 0o600);
      const child = spawn(
        process.execPath,
        [path.join(__dirname, "controller.cjs"), configFile],
        {
          detached: true,
          stdio: ["ignore", log, log],
          env: { ...process.env, ELECTRON_RUN_AS_NODE: "1" },
        },
      );
      child.unref();
      fs.closeSync(log);
      for (let attempt = 0; attempt < 30; attempt++) {
        try {
          await call(config, "status");
          return config;
        } catch {
          await new Promise((r) => setTimeout(r, 100));
        }
      }
      config = undefined;
      throw new Error(
        "The host companion could not start. Check its log in the extension storage directory.",
      );
    })().finally(() => {
      starting = undefined;
    });
    return starting;
  }
  async function request(op, args) {
    return call(await ensure(), op, args);
  }
  async function refresh() {
    try { projects = await agents().list(); nativeChats?.provider.update(projects); serviceError = null; }
    catch (e) { serviceError = e.message; }
    if (config) {
      try { status = await call(config, "status"); }
      catch (e) { status = { ...status, connected: false, error: e.message }; }
    }
    changed.fire();
    for (const [key, panel] of panels)
      if (panel.visible) await update(panel, key);
  }
  const tree = {
    onDidChangeTreeData: changed.event,
    getChildren: (parent) => parent?.kind === "project" ? parent.agents : parent?.kind === "native" ? status.bindings : [
      ...(serviceError ? [{ kind: "error", name: serviceError }] : [manager, ...projects]),
      ...(status.bindings.length ? [{ kind: "native", name: "Attached VS Code chats" }] : []),
      { newChat: true }, { empty: true },
    ],
    getTreeItem: (b) => {
      if (b.kind) {
        const folder = b.kind === "project" || b.kind === "native";
        const item = new vscode.TreeItem(b.name, folder ? vscode.TreeItemCollapsibleState.Expanded : vscode.TreeItemCollapsibleState.None);
        item.id = b.kind + ":" + (b.id || b.name);
        item.iconPath = new vscode.ThemeIcon(folder ? "folder" : "warning");
        if (b.kind === "project") {
          const working = b.agents.filter(a => a.busy).length;
          item.description = working ? `${working} working` : `${b.agents.length} agents`;
          item.tooltip = b.repo;
        }
        return item;
      }
      const item = new vscode.TreeItem(
        b.newChat ? "New SuperSurfer Chat…" : b.empty ? "Attach a VS Code chat…" : b.title || "Native agent",
      );
      if (b.newChat) { item.iconPath = new vscode.ThemeIcon("add"); item.command = { command: "supersurferNative.newChat", title: "New SuperSurfer Chat" }; return item; }
      if (b.service) {
        item.id = b.scope;
        item.description = b.busy ? "Working" : b.status === "awaiting_input" ? "Needs your input" : b.status || "Ready";
        item.tooltip = `${b.projectName || "SuperSurfer"} · ${b.name}\nExisting conversation on this host`;
        item.iconPath = new vscode.ThemeIcon(b.busy ? "sync~spin" : "comment-discussion");
        item.command = { command: "supersurferNative.openChat", title: "Open conversation", arguments: [b] };
        item.contextValue = b.project_id ? "serviceAgent" : "serviceManager";
        return item;
      }
      item.description = b.empty
        ? ""
        : b.connected === false
          ? "Disconnected"
          : b.complete
            ? "Finished"
            : b.paused
              ? "Paused"
              : b.status & 8
                ? "Working"
                : "Ready";
      item.iconPath = new vscode.ThemeIcon(
        b.empty
          ? "add"
          : b.complete
            ? "pass"
            : b.status & 8
              ? "sync~spin"
              : "comment-discussion",
      );
      item.command = {
        command: b.empty
          ? "supersurferNative.attach"
          : "supersurferNative.open",
        title: "Open workflow",
        arguments: [b],
      };
      item.contextValue = b.empty ? "empty" : "agent";
      return item;
    },
  };
  async function choose(value) {
    if (value?.scope) return (selected = value);
    await refresh();
    if (!status.bindings.length) return attach();
    const picked = await vscode.window.showQuickPick(
      status.bindings.map((b) => ({
        label: b.title || b.session,
        description: b.complete ? "Finished" : "Attached",
        b,
      })),
      { title: "Choose an agent" },
    );
    if (picked) return (selected = picked.b);
  }
  async function chooseService() {
    if (!projects.length) await refresh();
    if (serviceError) throw new Error(serviceError);
    const picked = await vscode.window.showQuickPick([manager, ...projects.flatMap(p => p.agents)].map(b => ({
      label: b.name, description: [b.projectName, b.busy ? "Working" : b.status].filter(Boolean).join(" · "), b,
    })), { title: "Open an existing SuperSurfer agent" });
    return picked?.b;
  }
  let creatingChat = false;
  async function newChat() {
    if (creatingChat) return;
    if (!vscode.workspace.isTrusted) throw new Error("Trust this workspace before starting an agent.");
    let folders = vscode.workspace.workspaceFolders || [], folder;
    const active = vscode.window.activeTextEditor?.document.uri;
    if (active) folder = vscode.workspace.getWorkspaceFolder(active);
    if (!folder && folders.length === 1) folder = folders[0];
    if (!folder && folders.length > 1) {
      const picked = await vscode.window.showQuickPick(folders.map(f => ({ label: f.name, description: f.uri.fsPath, folder: f })), { title: "Which folder should this chat work in?" });
      if (!picked) return; folder = picked.folder;
    }
    if (!folder) {
      const picked = await vscode.window.showOpenDialog({ canSelectFiles: false, canSelectFolders: true, canSelectMany: false, openLabel: "Start chat here" });
      if (!picked?.length) return; folder = { uri: picked[0] };
    }
    creatingChat = true;
    try { const b = await agents().newChat(folder.uri.fsPath); await refresh(); return openChat(b); }
    finally { creatingChat = false; }
  }
  async function attach() {
    const { sessions } = await request("sessions");
    const choices = sessions.filter(s => sessionFolder(s).length);
    if (!choices.length)
      throw new Error(
        "No VS Code chats with a local project folder were found on this host. Use New SuperSurfer Chat to start here, or select an existing research agent in the sidebar.",
      );
    const session = await vscode.window.showQuickPick(
      choices.map((s) => ({
        label: s.title || "Untitled native chat",
        description: sessionFolder(s).join(", "),
        s,
      })),
      { title: "Attach the same chat you already use" },
    );
    if (!session) return;
    const roots = sessionFolder(session.s);
    const directory = roots.length === 1 ? roots[0] : await vscode.window.showQuickPick(roots, { title: "Choose this chat’s project folder" });
    if (!directory) return;
    const project = await agents().projectForFolder(directory);
    const state = await agents().service.request("/api/state");
    const tasks = (state.experiments || []).filter(e => e.project_id === project.id && !e.archived);
    const task = tasks.length ? await vscode.window.showQuickPick([
      { label: "Project workflow", id: null }, ...tasks.map(e => ({ label: e.name, id: e.id })),
    ], { title: "Choose a Surfboard" }) : { id: null };
    if (!task) return;
    const resource = session.s.resource || session.s.session;
    const snapshot = await request("snapshot", { channel: resource });
    const chat = snapshot.defaultChat;
    selected = await request("attach", {
      session: resource,
      chat,
      repo: project.repo,
      project_id: project.id,
      experiment_id: task.id,
    });
    await refresh();
    await show(selected);
    return selected;
  }
  async function openChat(b, split = false) {
    b = b?.scope ? b : await chooseService();
    if (!b) return;
    if (b.service) {
      nativeChats ||= new NativeServiceChats(vscode, context, agents().service);
      return nativeChats.open(b, split);
    }
    const row = privateJSON((await ensure()).endpointFile);
    const configured =
      vscode.workspace.getConfiguration("chat").get("remoteAgentHosts") || [];
    const address =
      row.endpoint?.type === "tcp"
        ? `${row.endpoint.host}:${row.endpoint.port}`
        : null;
    const host = configured.find(
      (h) =>
        h.sshInstanceId === row.instanceId ||
        (address && h.address?.replace(/^ws:\/\//, "") === address),
    );
    let type;
    if (host) {
      const value = host.address.replace(/^ws:\/\//, "");
      const authority =
        value === "local"
          ? "remote_local"
          : /^[a-z0-9.:\-]+$/.test(value) && !value.startsWith("hex-")
            ? value.replaceAll(":", "__")
            : "hex-" + Buffer.from(value).toString("hex");
      type = `remote-${authority}-${b.provider}`;
    } else if (row.type === "editor") type = "agent-host-" + b.provider;
    else {
      const prefix = "workbench.action.chat.openSessionWithPrompt.";
      const types = (await vscode.commands.getCommands(true))
        .filter(
          (c) =>
            c.startsWith(prefix + "remote-") && c.endsWith("-" + b.provider),
        )
        .map((c) => c.slice(prefix.length));
      if (types.length === 1) type = types[0];
      else
        throw new Error(
          "Connect this persistent host in VS Code Chat first. SuperSurfer will then open its existing conversation.",
        );
    }
    const uri = vscode.Uri.from({
      scheme: type,
      path: vscode.Uri.parse(b.session).path,
    });
    if (row.type === "standalone") {
      await vscode.commands.executeCommand(
        "workbench.action.chat.openSessionInAgentsWindow",
        { sessionResource: uri },
      );
    } else
      await vscode.commands.executeCommand(
        split
          ? "workbench.action.chat.openSessionInNewEditorGroup"
          : "workbench.action.chat.openSessionInEditorGroup",
        { resource: uri },
      );
  }
  async function update(panel, key) {
    try {
      const binding = panel.serviceBinding || status.bindings.find(b => b.scope === key);
      const data =
        key === "queue"
          ? await agents().service.request("/api/state")
          : binding?.service ? await agents().board(binding) : await request("board", { scope: key });
      await panel.webview.postMessage({
        type: "state",
        data,
        binding: binding?.service ? { ...binding, status: projects.flatMap(p => p.agents).find(a => a.scope === key)?.busy ? 8 : 0 } : binding,
        hostType: binding?.service ? "service" : status.hostType,
      });
    } catch (e) {
      await panel.webview.postMessage({ type: "error", message: e.message });
    }
  }
  async function show(b, mode = "board") {
    if (mode !== "queue") {
      b = b?.scope ? b : await choose();
      if (!b) return;
    }
    const key = mode === "queue" ? "queue" : b.scope;
    if (panels.has(key)) {
      panels.get(key).reveal();
      return;
    }
    const panel = vscode.window.createWebviewPanel(
      "supersurferNative.board",
      mode === "queue" ? "GPU queue" : "Surfboard",
      vscode.ViewColumn.Active,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.joinPath(context.extensionUri, "media"),
        ],
      },
    );
    panels.set(key, panel);
    if (b?.service) panel.serviceBinding = b;
    panel.onDidDispose(() => panels.delete(key));
    const uri = (file) =>
      panel.webview.asWebviewUri(
        vscode.Uri.joinPath(context.extensionUri, "media", file),
      );
    const nonce = crypto.randomBytes(18).toString("base64");
    panel.webview.html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${panel.webview.cspSource}; script-src 'nonce-${nonce}'; img-src ${panel.webview.cspSource} data:;"><link rel="stylesheet" href="${uri("board.css")}"></head><body data-mode="${mode}"><main id="app"><p>Connecting to your host…</p></main><script nonce="${nonce}" src="${uri("board.js")}"></script></body></html>`;
    panel.webview.onDidReceiveMessage(async (message) => {
      try {
        if (message.op === "ready") {
          await panel.webview.postMessage({
            type: "restore",
            saved: context.workspaceState.get("draft:" + key),
          });
          return update(panel, key);
        }
        if (message.op === "retainDraft" && mode !== "queue") {
          if (JSON.stringify(message.args).length > 1024 * 1024)
            throw new Error("Local draft is too large.");
          return context.workspaceState.update("draft:" + key, message.args);
        }
        if (message.op === "reload" && mode !== "queue") {
          await context.workspaceState.update("draft:" + key, undefined);
          await panel.webview.postMessage({ type: "reset" });
          return update(panel, key);
        }
        if (message.op === "openChat") return openChat(b);
        if (message.op === "splitChat") return openChat(b, true);
        const allowed =
          mode === "queue"
            ? ["queueAction"]
            : ["save", "apply", "discard", "ask", "pause"];
        if (!allowed.includes(message.op))
          throw new Error("Unsupported panel action");
        if (
          message.op === "queueAction" &&
          message.args?.action === "run.cancel"
        ) {
          if (
            (await vscode.window.showWarningMessage(
              "Cancel this queued or running job?",
              { modal: true },
              "Cancel job",
            )) !== "Cancel job"
          )
            return;
        }
        let result;
        if (mode === "queue") {
          const { action, ...args } = message.args || {};
          if (!["run.cancel", "run.move", "queue.pause", "queue.resume"].includes(action)) throw new Error("Unsupported queue action");
          result = await agents().service.action(action, args);
        } else if (b?.service) result = await agents().boardAction(b, message.op, message.args);
        else result = await request(message.op, { ...message.args, scope: key });
        await panel.webview.postMessage({
          type: "result",
          op: message.op,
          result,
        });
        await refresh();
      } catch (e) {
        await panel.webview.postMessage({ type: "error", message: e.message });
      }
    });
  }
  const register = (name, fn) =>
    context.subscriptions.push(
      vscode.commands.registerCommand("supersurferNative." + name, (...args) =>
        Promise.resolve(fn(...args)).catch(fail),
      ),
    );
  register("open", async b => { b = b?.scope ? b : await chooseService(); if (b?.project_id || !b?.service && b) return show(b); });
  register("newChat", newChat);
  register("attach", attach);
  register("queue", () => show(null, "queue"));
  register("refresh", refresh);
  register("openChat", openChat);
  register("openChatBeside", b => openChat(b, true));
  register("detach", async (b) => {
    b = await choose(b);
    if (b) {
      await request("detach", { scope: b.scope });
      panels.get(b.scope)?.dispose();
      await refresh();
    }
  });
  context.subscriptions.push(
    output,
    changed,
    vscode.window.registerTreeDataProvider("supersurferNative.sessions", tree),
  );
  let polling = false;
  const timer = setInterval(async () => {
    if (polling) return;
    polling = true;
    try {
      await refresh();
    } catch (e) {
      output.appendLine(e.message);
    } finally {
      polling = false;
    }
  }, 3000);
  context.subscriptions.push({
    dispose() {
      clearInterval(timer);
      for (const panel of panels.values()) panel.dispose();
    },
  });
  // Service agents are available without a native Agent Host or an attachment.
  refresh().catch(e => output.appendLine(e.message));
  try { nativeChats = new NativeServiceChats(vscode, context, agents().service); }
  catch (e) { output.appendLine(e.message); }
  if (
    fs.existsSync(path.join(context.globalStorageUri.fsPath, "companion.json"))
  )
    ensure().then(() => refresh()).catch((e) => output.appendLine(e.message));
  return { request, show, refresh };
}
module.exports = { activate };
