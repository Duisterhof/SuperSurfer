"use strict";
// AHP presentation adapter. SuperSurfer remains the only provider owner.
const fs = require("node:fs"), path = require("node:path"), http = require("node:http"), crypto = require("node:crypto");
const { WebSocketServer } = require("ws");
const { atomic, privateJSON } = require("./host.cjs");
const { Service } = require("./service.cjs");
const { ServiceAgents } = require("./service-agents.cjs");
const { resource, chatResource, sessionView, partKey } = require("./service-session.cjs");
const ROOT = "ahp-root://", VERSION = "0.9.0";
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
class ServiceHost {
  constructor(config, service = new Service(config.stateDirectory)) {
    this.config = config; this.service = service; this.agents = new ServiceAgents(service);
    this.clients = new Set(); this.entries = new Map(); this.views = new Map(); this.raw = new Map(); this.seq = 0;
    this.serial = Promise.resolve(); this.catalogAt = 0;
    this.file = path.join(config.storage, "service-host-state.json");
    try { this.saved = privateJSON(this.file); } catch (e) { if (e.code !== "ENOENT") throw e; this.saved = { chats: {}, receipts: {}, aliases: {} }; }
  }
  save() { atomic(this.file, this.saved); }
  resource(scope) { return this.settings(scope).resource || resource(scope); }
  chatResource(scope) { return chatResource(scope, this.resource(scope)); }
  settings(scope) { return this.saved.chats[scope] ||= { turnIds: {}, queue: [] }; }
  root() { return { agents: [{ provider: "supersurfer", displayName: "SuperSurfer", description: "Your persistent agents, using their existing provider and account on this host.",
    models: [{ id: "current", provider: "supersurfer", name: "Agent's current model", supportsVision: false }], capabilities: {} }],
    activeSessions: [...this.entries.values()].filter(e => e.busy).length, terminals: [],
    config: { schema: { type: "object", properties: {} }, values: {} } }; }
  async catalog(force = false) {
    if (!force && Date.now() - this.catalogAt < 30000) return;
    const projects = await this.agents.list();
    const rows = projects.flatMap(p => p.agents).filter(a => a.owner === "supersurfer");
    rows.unshift({ scope: "manager", name: "Workspace manager", service: true });
    const next = new Map(rows.map(r => [r.scope, r]));
    for (const [scope, row] of next) {
      const previous = this.entries.get(scope);
      const summary = this.views.get(scope)?.summary || sessionView(row, {}).summary;
      if (!previous) this.notify("root/sessionAdded", { channel: ROOT, summary });
      else if (!same(previous, row)) this.notify("root/sessionSummaryChanged", { channel: ROOT, summary: { ...summary, title: row.name, status: row.busy ? 8 : summary.status } });
    }
    for (const scope of this.entries.keys()) if (!next.has(scope)) this.notify("root/sessionRemoved", { channel: ROOT, session: this.resource(scope) });
    this.entries = next; this.catalogAt = Date.now();
  }
  scope(channel) {
    const alias = this.saved.aliases[channel];
    if (alias && this.entries.has(alias)) return alias;
    for (const scope of this.entries.keys()) if (channel === this.resource(scope) || channel === this.chatResource(scope) || channel === resource(scope)) return scope;
    throw new Error("This conversation is unavailable. Refresh the SuperSurfer agent list.");
  }
  notify(method, params, only) {
    const message = JSON.stringify({ jsonrpc: "2.0", method, params });
    for (const client of only ? [only] : this.clients) if (client.ws.readyState === 1 && client.initialized && (!params.channel || client.subscriptions.has(params.channel))) client.ws.send(message);
  }
  action(channel, action, origin, rejectionReason) {
    this.notify("action", { channel, action, serverSeq: ++this.seq, ...(origin ? { origin } : {}), ...(rejectionReason ? { rejectionReason } : {}) });
  }
  async load(scope, limit = 150) {
    const latest = await this.agents.chat(scope, limit), old = this.raw.get(scope);
    const messages = new Map((old?.messages || []).map(m => [m.id, m]));
    for (const m of latest.messages || []) messages.set(m.id, m);
    latest.messages = [...messages.values()].sort((a, b) => (a.created || 0) - (b.created || 0));
    this.raw.set(scope, latest);
    const view = sessionView(this.entries.get(scope), latest, this.settings(scope));
    if (latest.message_count > latest.messages.length) view.chat.turnsNextCursor = String(latest.messages.length);
    this.publish(scope, this.views.get(scope), view); this.views.set(scope, view);
    return view;
  }
  publish(scope, before, after) {
    if (!before) return;
    const channel = this.chatResource(scope), previous = before.chat, next = after.chat;
    if (!same(before.summary, after.summary)) this.notify("root/sessionSummaryChanged", { channel: ROOT, summary: after.summary });
    if (!same(before.session.chats, after.session.chats)) this.action(this.resource(scope), { type: "session/chatUpdated", chat: channel, changes: after.session.chats[0] });
    for (const request of before.session.inputNeeded) if (!after.session.inputNeeded.some(x => x.id === request.id)) this.action(this.resource(scope), { type: "session/inputNeededRemoved", id: request.id });
    for (const request of after.session.inputNeeded) if (!before.session.inputNeeded.some(x => same(x, request))) this.action(this.resource(scope), { type: "session/inputNeededSet", request });
    const complete = (previous.activeTurn && next.turns.find(t => t.id === previous.activeTurn.id));
    if (previous.activeTurn && (complete || next.activeTurn?.id !== previous.activeTurn.id)) {
      if (complete) this.parts(channel, previous.activeTurn, complete);
      this.action(channel, { type: complete?.state === "cancelled" ? "chat/turnCancelled" : complete?.state === "error" ? "chat/error" : "chat/turnComplete",
        turnId: previous.activeTurn.id, duration: 0, ...(complete?.state === "error" ? { part: { kind: "error", error: { message: this.raw.get(scope)?.error || "The agent needs attention." } } } : {}) });
    }
    const known = new Set(previous.turns.map(t => t.id)); if (complete) known.add(complete.id);
    const missing = next.turns.filter(t => !known.has(t.id));
    // turnsLoaded prepends older pages. New completed turns are appended through normal turn actions.
    const older = missing.filter(t => !previous.turns.length || Date.parse(t.startedAt) < Date.parse(previous.turns[0].startedAt));
    if (older.length) this.action(channel, { type: "chat/turnsLoaded", turns: older, turnsNextCursor: next.turnsNextCursor });
    for (const turn of missing.filter(t => !older.includes(t))) {
      this.action(channel, { type: "chat/turnStarted", turnId: turn.id, startedAt: turn.startedAt, message: turn.message });
      this.parts(channel, { responseParts: [] }, turn);
      this.action(channel, { type: "chat/turnComplete", turnId: turn.id, duration: 0 });
    }
    if (next.activeTurn) {
      if (previous.activeTurn?.id !== next.activeTurn.id) this.action(channel, { type: "chat/turnStarted", turnId: next.activeTurn.id, startedAt: next.activeTurn.startedAt, message: next.activeTurn.message });
      this.parts(channel, previous.activeTurn?.id === next.activeTurn.id ? previous.activeTurn : { responseParts: [] }, next.activeTurn);
    }
  }
  parts(channel, before, after) {
    const old = new Map(before.responseParts.map(p => [partKey(p), p]));
    for (const part of after.responseParts) {
      const prior = old.get(partKey(part));
      if (same(prior, part)) continue;
      if (part.kind === "inputRequest") {
        if (!prior) this.action(channel, { type: "chat/inputRequested", request: part.request });
      } else if (part.kind === "toolCall") {
        const call = part.toolCall, base = { turnId: after.id, toolCallId: call.toolCallId };
        if (!prior) this.action(channel, { type: "chat/toolCallStart", ...base, toolName: call.toolName, displayName: call.displayName });
        if (!prior || prior.toolCall.status !== call.status) this.action(channel, { type: "chat/toolCallReady", ...base, invocationMessage: call.invocationMessage, toolInput: call.toolInput,
          ...(call.status === "pending-confirmation" ? { options: call.options } : { confirmed: call.confirmed }) });
        if (call.status === "completed") this.action(channel, { type: "chat/toolCallComplete", ...base, result: { success: call.success, pastTenseMessage: call.pastTenseMessage, content: call.content } });
        else if (call.content) this.action(channel, { type: "chat/toolCallContentChanged", ...base, content: call.content });
      } else if (!prior) this.action(channel, { type: "chat/responsePart", turnId: after.id, part });
      else if (part.kind === "markdown" && part.content.startsWith(prior.content)) this.action(channel, { type: "chat/delta", turnId: after.id, partId: part.id, content: part.content.slice(prior.content.length) });
    }
  }
  async snapshot(channel) {
    if (channel === ROOT) return { resource: ROOT, state: this.root(), fromSeq: this.seq };
    const scope = this.scope(channel), view = await this.load(scope);
    return { resource: channel, state: channel.startsWith("ahp-chat:") ? view.chat : view.session, fromSeq: this.seq };
  }
  async request(client, method, params = {}) {
    if (method === "initialize") {
      if (client.initialized) throw new Error("Already initialized");
      if (!params.protocolVersions?.includes(VERSION)) throw new Error("This SuperSurfer host requires Agent Host protocol 0.9.0.");
      if (typeof params.clientId !== "string" || params.clientId.length > 256) throw new Error("A client ID is required.");
      await this.catalog(); client.id = params.clientId; client.initialized = true;
      client.subscriptions = new Set(params.initialSubscriptions || [ROOT]);
      const snapshots = []; for (const c of client.subscriptions) snapshots.push(await this.snapshot(c));
      return { protocolVersion: VERSION, serverSeq: this.seq, serverInfo: { name: "supersurfer", version: "0.1.43" }, snapshots };
    }
    if (!client.initialized) throw new Error("Initialize the connection first.");
    if (method === "ping") return {};
    if (method === "reconnect") {
      client.subscriptions = new Set(params.subscriptions || [ROOT]);
      const snapshots = []; for (const c of client.subscriptions) snapshots.push(await this.snapshot(c));
      return { type: "snapshot", snapshots };
    }
    if (method === "subscribe") { const snapshot = await this.snapshot(params.channel); client.subscriptions.add(params.channel); return { snapshot }; }
    if (method === "unsubscribe") { client.subscriptions.delete(params.channel); return {}; }
    if (method === "listSessions") {
      await this.catalog(); const offset = Number(params.cursor || 0), limit = Math.min(params.limit || 100, 100);
      if (!Number.isInteger(offset) || offset < 0 || !Number.isInteger(limit) || limit < 1) throw new Error("Invalid session page.");
      const all = [...this.entries].map(([scope, row]) => this.views.get(scope)?.summary || sessionView(row, {}).summary);
      return { items: all.slice(offset, offset + limit), ...(offset + limit < all.length ? { nextCursor: String(offset + limit) } : {}) };
    }
    if (method === "resolveSessionConfig") return { schema: { type: "object", properties: {} }, values: {} };
    if (method === "sessionConfigCompletions" || method === "completions") return { items: [] };
    if (method === "fetchTurns") {
      const scope = this.scope(params.channel), prior = this.raw.get(scope);
      if (params.cursor && params.cursor !== String(prior?.messages?.length)) throw new Error("History changed. Reopen the conversation to load more.");
      await this.load(scope, Math.min((prior?.messages?.length || 150) + 150, 100000)); return {};
    }
    if (method === "dispatchAction") return this.dispatch(client, params);
    throw new Error("This operation is not available for SuperSurfer conversations: " + method);
  }
  async once(scope, key, value, fn) {
    const id = scope + ":" + key, fingerprint = crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex");
    const prior = this.saved.receipts[id];
    if (prior) {
      if (prior.fingerprint !== fingerprint) throw new Error("This request ID was already used for different input.");
      if (prior.status !== "complete") throw new Error("Delivery is uncertain. Inspect this conversation before sending a new request; it has not been replayed.");
      return prior.result;
    }
    this.saved.receipts[id] = { fingerprint, status: "uncertain" }; this.save();
    const result = await fn(); this.saved.receipts[id] = { fingerprint, status: "complete", result }; this.save(); return result;
  }
  async send(scope, action, steering = false) {
    const message = action.message;
    if (typeof message?.text !== "string" || !message.text.trim()) throw new Error("Enter a message.");
    if (typeof (action.turnId || action.id) !== "string" || (action.turnId || action.id).length > 256) throw new Error("A stable message ID is required.");
    if (message.origin?.kind !== "user") throw new Error("Only explicit user messages can start work through this interface.");
    let text = message.text;
    if (message.attachments?.length > 8) throw new Error("Attach up to eight context items.");
    for (const item of message.attachments || []) {
      if (item.type !== "simple" || typeof item.modelRepresentation !== "string" || item.modelRepresentation.length > 40000)
        throw new Error("This attachment cannot be sent. Use a text selection or project file path.");
      text += `\n\n[User-selected context: ${String(item.label).slice(0,4096)}]\n${item.modelRepresentation}`;
    }
    if (text.length > 100000) throw new Error("Message and attached context exceed 100,000 characters.");
    if (message.model?.id && message.model.id !== "current") throw new Error("This chat keeps its provider and model. Change them in SuperSurfer conversation settings.");
    const result = await this.once(scope, action.turnId || action.id, message, () => this.service.action(steering ? "chat.steer" : "chat.send", { scope, text }));
    if (result.message_id && !steering) { this.settings(scope).turnIds[result.message_id] = action.turnId; this.save(); }
    return result;
  }
  async dispatch(client, params) {
    const { channel, action, clientSeq } = params;
    const origin = { clientId: client.id, clientSeq };
    try {
      if (!Number.isInteger(clientSeq) || !action || typeof action.type !== "string") throw new Error("Invalid native action.");
      const scope = this.scope(channel), saved = this.settings(scope);
      const chat = await this.agents.chat(scope, 150);
      if (chat.read_only) throw new Error("This workspace is read-only.");
      switch (action.type) {
        case "chat/turnStarted":
          if (typeof action.turnId !== "string" || action.turnId.length > 256) throw new Error("A stable turn ID is required.");
          await this.send(scope, action); saved.draft = undefined; this.save(); break;
        case "chat/turnCancelled":
          if (this.views.get(scope)?.chat.activeTurn?.id !== action.turnId) throw new Error("The active turn has changed. Refresh before stopping it.");
          await this.service.action("chat.stop", { scope }); saved.queue = []; this.save(); break;
        case "chat/draftChanged": saved.draft = action.draft; this.save(); break;
        case "chat/pendingMessageSet":
          if (action.kind === "steering") { if (!chat.steerable) throw new Error("This provider cannot be steered while working. Wait for it to finish."); await this.send(scope, action, true); break; }
          throw new Error("Use Send to steer this agent, or wait for its turn to finish. Queued messages are not available yet.");
        case "chat/inputAnswerChanged":
          saved.answers ||= {}; saved.answers[action.requestId] ||= {}; saved.answers[action.requestId][action.questionId] = action.answer; this.save(); break;
        case "chat/inputCompleted": {
          if (action.response !== "accept") throw new Error("Answer this question, or use Stop to cancel the task.");
          const question = chat.questions?.find(q => q.id === action.requestId && q.status === "pending");
          if (!question) throw new Error("This question is no longer pending.");
          const answers = { ...(saved.answers?.[action.requestId] || {}), ...action.answers }, converted = {};
          for (const q of question.questions) {
            const a = answers[q.id]?.value;
            if (!a || !["text", "selected", "selected-many"].includes(a.kind)) throw new Error("Answer every question before continuing.");
            converted[q.id] = a.freeformValues?.length ? a.freeformValues : Array.isArray(a.value) ? a.value : [a.value];
          }
          await this.once(scope, "answer:" + action.requestId, converted, () => this.service.action("chat.answer", { scope, question_id: action.requestId, answers: converted })); break;
        }
        case "chat/toolCallConfirmed": {
          const approval = chat.approvals?.find(a => a.id === action.toolCallId && a.status === "pending");
          if (!approval) throw new Error("This approval is no longer pending.");
          if (action.editedToolInput !== undefined) throw new Error("Edited approval input is not supported. Deny the request and send the change to the agent.");
          const decision = action.selectedOptionId || (action.approved === true ? "approve" : action.approved === false ? "deny" : null);
          if (!["approve", "deny"].includes(decision)) throw new Error("Choose Approve once or Deny.");
          await this.once(scope, "approval:" + action.toolCallId, decision, () => this.service.action("chat.approve", { scope, approval_id: action.toolCallId, decision })); break;
        }
        case "session/titleChanged": await this.service.action("chat.rename", { scope, name: action.title }); break;
        case "session/isArchivedChanged": await this.service.action("chat.archive", { scope, archived: action.isArchived }); break;
        case "chat/isReadChanged": case "session/isReadChanged": case "session/activeClientSet": break;
        default: throw new Error("This native control is not available for SuperSurfer: " + action.type);
      }
      this.action(channel, action, origin);
      await this.load(scope);
    } catch (e) {
      this.action(channel, action, origin, e.message);
    }
    return {};
  }
  async poll() {
    await this.catalog();
    const scopes = new Set();
    for (const c of this.clients) for (const channel of c.subscriptions) if (channel !== ROOT) { try { scopes.add(this.scope(channel)); } catch {} }
    for (const scope of scopes) await this.load(scope);
  }
  enqueue(fn) { const result = this.serial.then(fn); this.serial = result.catch(() => {}); return result; }
  async listen() {
    this.server = http.createServer((_req, res) => { res.writeHead(404); res.end(); });
    this.wss = new WebSocketServer({ noServer: true, maxPayload: 2 * 1024 * 1024, perMessageDeflate: false });
    this.server.on("upgrade", (req, socket, head) => {
      const token = new URL(req.url, "http://localhost").searchParams.get("tkn") || "";
      if (Buffer.byteLength(token) !== Buffer.byteLength(this.config.secret) || !crypto.timingSafeEqual(Buffer.from(token), Buffer.from(this.config.secret))) { socket.destroy(); return; }
      this.wss.handleUpgrade(req, socket, head, ws => this.wss.emit("connection", ws));
    });
    this.wss.on("connection", ws => {
      const client = { ws, initialized: false, subscriptions: new Set() }; this.clients.add(client);
      ws.on("close", () => this.clients.delete(client)); ws.on("error", () => {});
      ws.on("message", raw => {
        let message; try { message = JSON.parse(raw); } catch { return ws.close(); }
        this.enqueue(async () => {
          try {
            const result = await this.request(client, message.method, message.params);
            if (message.id !== undefined && ws.readyState === 1) ws.send(JSON.stringify({ jsonrpc: "2.0", id: message.id, result }));
          } catch (e) { if (message.id !== undefined && ws.readyState === 1) ws.send(JSON.stringify({ jsonrpc: "2.0", id: message.id, error: { code: -32602, message: e.message } })); }
        });
      });
    });
    await new Promise((resolve, reject) => { this.server.once("error", reject); this.server.listen(this.config.port || 0, "127.0.0.1", resolve); });
    this.timer = setInterval(() => {
      if (!this.clients.size || this.polling) return;
      this.polling = true; this.enqueue(() => this.poll()).catch(() => {
        // Fail closed rather than presenting stale idle state after a service disconnect.
        for (const c of this.clients) c.ws.close(1011, "SuperSurfer service unavailable");
      }).finally(() => { this.polling = false; });
    }, 750);
    return this.server.address().port;
  }
  async close() { clearInterval(this.timer); for (const c of this.clients) c.ws.terminate(); if (this.server) await new Promise(r => this.server.close(r)); }
}
async function main(file) {
  const config = privateJSON(file), host = new ServiceHost(config), port = await host.listen();
  atomic(config.endpointFile, { type: "standalone", pid: process.pid, instanceId: config.instanceId, connectionToken: config.secret, endpoint: { type: "tcp", host: "127.0.0.1", port } });
  for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => host.close().then(() => process.exit()));
}
if (require.main === module) main(process.argv[2]).catch(e => { console.error(e.message); process.exitCode = 1; });
module.exports = { ServiceHost };
