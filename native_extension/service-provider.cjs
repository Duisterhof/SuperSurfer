"use strict";
const crypto = require("node:crypto");
const { ServiceAgents } = require("./service-agents.cjs");
const { resource, chatResource } = require("./service-session.cjs");
const PARTICIPANT = "supersurfer";
class NativeSessionProvider {
  constructor(vscode, context, bridge) {
    this.vscode = vscode; this.context = context; this.bridge = bridge; this.entries = new Map();
    try { this.controller = vscode.chat.createChatSessionItemController("supersurfer", () => this.refresh()); }
    catch { throw new Error("Native Chat needs VS Code's preview API enabled for SuperSurfer. Run scripts/install-vscode.py with the VSIX, then restart VS Code."); }
    this.participant = vscode.chat.createChatParticipant(PARTICIPANT, async (request, context, stream, token) => {
      const uri = context.chatSessionContext?.chatSessionItem.resource || request.sessionResource;
      const session = await this.provideChatSessionContent(uri, token);
      return session.requestHandler(request, context, stream, token);
    });
    this.controller.getChatSessionInputState = async uri => {
      let name = "Agent’s saved provider";
      if (uri) {
        if (!this.entries.size) await this.refresh();
        const host = await bridge.connection(), view = await host.snapshot(resource(this.scope(uri)));
        name = `${view.config.values.backend} · ${view.config.values.model}`;
      }
      const selected = { id: "current", name, locked: true };
      return this.controller.createChatSessionInputState([{ id: "model", name: "Provider", items: [selected], selected }]);
    };
    this.controller.newChatSessionItemHandler = async () => {
      const folders = vscode.workspace.workspaceFolders || [];
      const folder = folders.length === 1 ? folders[0] : await vscode.window.showWorkspaceFolderPick({ placeHolder: "Choose the folder for this chat" });
      if (!folder) throw Error("Open or choose a project folder first.");
      const b = await new ServiceAgents(bridge.service).newChat(folder.uri.fsPath); await this.refresh(); return this.item(b);
    };
    context.subscriptions.push(this.controller, this.participant,
      // VS Code resolves a model before invoking a session request handler.
      // This session-scoped routing entry never performs inference itself.
      vscode.lm.registerLanguageModelChatProvider("supersurfer", {
        provideLanguageModelChatInformation: async () => [{ id: "current", name: "Agent’s saved model", family: "supersurfer", version: "1", maxInputTokens: 25000, maxOutputTokens: 25000, capabilities: { toolCalling: true }, targetChatSessionType: "supersurfer", isUserSelectable: true }],
        provideLanguageModelChatResponse: async () => { throw Error("Open a SuperSurfer conversation to talk to this agent."); },
        provideTokenCount: async (_model, text) => Math.ceil((typeof text === "string" ? text : JSON.stringify(text)).length / 4),
      }),
      vscode.chat.registerChatSessionContentProvider("supersurfer", this, this.participant, { supportsInterruptions: true }),
      vscode.commands.registerCommand("supersurferNative.stopAgent", async value => {
        if (!value) {
          const selected = await vscode.window.showQuickPick([...this.entries.values()].map(b => ({ label: b.name, description: b.projectName, scope: b.scope })), { title: "Stop which agent?" });
          if (!selected) return;
          value = selected.scope;
        }
        const scope = this.scope(value);
        await bridge.service.action("chat.stop", { scope }); await this.refresh();
      }),
      vscode.commands.registerCommand("supersurferNative.agentDecision", async (scope, kind, id, decision) => {
        if (!this.entries.has(scope) || kind !== "approval" || !["approve", "deny"].includes(decision)) throw Error("Invalid agent decision");
        const host = await bridge.connection(), view = await host.snapshot(chatResource(scope));
        await host.dispatch(chatResource(scope), { type: "chat/toolCallConfirmed", turnId: view.activeTurn?.id, toolCallId: id, approved: decision === "approve", confirmed: "user-action", selectedOptionId: decision });
      }),
      vscode.commands.registerCommand("supersurferNative.answerQuestion", async (scope, id) => {
        if (!this.entries.has(scope)) throw Error("Choose an existing SuperSurfer conversation.");
        const host = await bridge.connection(), view = await host.snapshot(chatResource(scope));
        const request = view.activeTurn?.responseParts.find(p => p.kind === "inputRequest" && p.request.id === id)?.request;
        if (!request) throw Error("This question is no longer pending.");
        const answers = {};
        for (const q of request.questions) {
          let value;
          if (q.options?.length) {
            const options = q.options.map(o => ({ label: o.label, description: o.description, value: o.id }));
            if (q.allowFreeformInput) options.push({ label: "Write an answer…", custom: true });
            const selected = await vscode.window.showQuickPick(options, { title: q.message || q.title, placeHolder: "Choose an answer" });
            if (!selected) return;
            if (!selected.custom) value = selected.value;
          }
          if (value === undefined) value = await vscode.window.showInputBox({ title: q.title, prompt: q.message, ignoreFocusOut: true });
          if (value === undefined) return;
          answers[q.id] = { state: "submitted", value: { kind: "text", value } };
        }
        await host.dispatch(chatResource(scope), { type: "chat/inputCompleted", requestId: id, response: "accept", answers });
      }),
      { dispose: () => { this.disposed = true; bridge.host?.close(); } });
    this.modelsReady = vscode.lm.selectChatModels({ vendor: "supersurfer" });
    this.modelsReady.catch(() => {});
    this.refresh().catch(() => {});
  }
  scope(value) {
    if (typeof value === "string" && this.entries.has(value)) return value;
    const uri = value?.resource || value;
    const row = [...this.entries.values()].find(b => resource(b.scope) === uri?.toString());
    if (!row) throw Error("Choose an existing SuperSurfer conversation.");
    return row.scope;
  }
  item(b) {
    const v = this.vscode, item = this.controller.createChatSessionItem(v.Uri.parse(resource(b.scope)), b.name || b.title);
    item.description = b.projectName || "On this host";
    item.tooltip = `${b.repo || "SuperSurfer"}\nSame persistent conversation`;
    item.status = b.busy ? v.ChatSessionStatus.InProgress : b.status === "awaiting_input" || b.status === "awaiting_approval" ? v.ChatSessionStatus.NeedsInput : b.status === "failed" ? v.ChatSessionStatus.Failed : v.ChatSessionStatus.Completed;
    item.timing = { created: (b.created_at || 0) * 1000, ...(b.updated_at ? { lastRequestStarted: b.updated_at * 1000, ...(!b.busy ? { lastRequestEnded: b.updated_at * 1000 } : {}) } : {}) };
    item.metadata = { workingDirectory: b.repo, projectName: b.projectName, scope: b.scope };
    return item;
  }
  update(projects) {
    const rows = projects.flatMap(p => p.agents).filter(a => a.owner === "supersurfer");
    rows.unshift({ scope: "manager", name: "Workspace manager", service: true });
    this.entries = new Map(rows.map(b => [b.scope, b]));
    this.controller.items.replace(rows.map(b => this.item(b)));
  }
  async refresh() {
    if (this.refreshing) return this.refreshing;
    this.refreshing = (async () => {
      const projects = await new ServiceAgents(this.bridge.service).list();
      this.update(projects);
    })().finally(() => { this.refreshing = undefined; });
    return this.refreshing;
  }
  parts(parts) {
    const v = this.vscode;
    return parts.filter(p => p.kind === "markdown" || p.kind === "toolCall" && p.toolCall.status !== "pending-confirmation").map(p => {
      if (p.kind === "markdown") return new v.ChatResponseMarkdownPart(p.content);
      const c = p.toolCall, part = new v.ChatToolInvocationPart(c.displayName, c.toolCallId);
      part.invocationMessage = c.invocationMessage; part.pastTenseMessage = c.pastTenseMessage;
      if (c.content?.length) part.toolSpecificData = { input: c.toolInput || "", output: c.content.filter(x => x.type === "text").map(x => x.text).join("\n") };
      part.isConfirmed = true; part.isComplete = c.status === "completed"; part.isError = c.success === false;
      return part;
    });
  }
  async provideChatSessionContent(uri, token) {
    if (!this.entries.size) await this.refresh();
    const scope = this.scope(uri), host = await this.bridge.connection();
    let view = await host.snapshot(chatResource(scope));
    const seen = new Set();
    while (view.turnsNextCursor) {
      if (seen.has(view.turnsNextCursor)) throw Error("The service could not load older history. Reopen the chat to retry.");
      seen.add(view.turnsNextCursor);
      await host.request("fetchTurns", { channel: chatResource(scope), cursor: view.turnsNextCursor });
      view = await host.snapshot(chatResource(scope));
    }
    const v = this.vscode, history = [];
    for (const turn of view.turns) {
      history.push(new v.ChatRequestTurn2(turn.message.text, undefined, [], PARTICIPANT, [], undefined, turn.id));
      history.push(new v.ChatResponseTurn2(this.parts(turn.responseParts), {}, PARTICIPANT));
    }
    if (view.activeTurn) history.push(new v.ChatRequestTurn2(view.activeTurn.message.text, undefined, [], PARTICIPANT, [], undefined, view.activeTurn.id));
    return { title: this.entries.get(scope).name, history,
      ...(view.activeTurn ? { activeResponseCallback: (stream, cancel) => this.stream(scope, stream, cancel, view.activeTurn.id, false) } : {}),
      requestHandler: async (request, _context, stream, cancel) => {
        const host = await this.bridge.connection();
        const current = await host.snapshot(chatResource(scope)), turnId = request.id || crypto.randomUUID();
        const attachments = [];
        for (const ref of request.references || []) {
          const value = ref.value;
          if (typeof value === "string") attachments.push({ type: "simple", label: ref.name || "Context", modelRepresentation: value });
          else if (value?.uri || value?.scheme) {
            const uri = value.uri || value;
            const doc = await v.workspace.openTextDocument(uri);
            attachments.push({ type: "simple", label: uri.fsPath, modelRepresentation: value.range ? doc.getText(value.range) : doc.getText() });
          } else throw Error("This context item cannot be attached. Include its file path instead.");
        }
        const message = { text: request.prompt, origin: { kind: "user" }, ...(attachments.length ? { attachments } : {}) };
        await host.dispatch(chatResource(scope), current.activeTurn ? { type: "chat/pendingMessageSet", kind: "steering", id: turnId, message } : { type: "chat/turnStarted", turnId, startedAt: new Date().toISOString(), message });
        await this.stream(scope, stream, cancel, current.activeTurn?.id || turnId); await this.refresh(); return {};
      } };
  }
  async stream(scope, stream, token, turnId, inlineQuestions = true) {
    const emitted = new Map(), decisions = new Set();
    stream.button({ command: "supersurferNative.stopAgent", title: "Stop agent", arguments: [scope] });
    while (!token.isCancellationRequested && !this.disposed) {
      const host = await this.bridge.connection();
      const view = await host.snapshot(chatResource(scope));
      const turn = view.activeTurn?.id === turnId ? view.activeTurn : view.turns.find(t => t.id === turnId);
      if (turn) for (const part of turn.responseParts) {
        if (part.kind === "markdown") {
          const previous = emitted.get(part.id) || "";
          if (part.content.startsWith(previous)) stream.markdown(part.content.slice(previous.length));
          emitted.set(part.id, part.content);
        } else if (part.kind === "toolCall") {
          const call = part.toolCall;
          if (call.status === "pending-confirmation") {
            if (!decisions.has(call.toolCallId)) {
              stream.markdown("\n\n**Permission requested:** " + call.invocationMessage + "\n\n");
              for (const decision of ["approve", "deny"]) stream.button({ command: "supersurferNative.agentDecision", title: decision === "approve" ? "Approve once" : "Deny", arguments: [scope, "approval", call.toolCallId, decision] });
              decisions.add(call.toolCallId);
            }
          } else if (emitted.get(call.toolCallId) !== JSON.stringify(call)) {
            const p = this.parts([part])[0]; p.enablePartialUpdate = emitted.has(call.toolCallId); stream.push(p); emitted.set(call.toolCallId, JSON.stringify(call));
          }
        } else if (part.kind === "inputRequest" && !decisions.has(part.request.id)) {
          decisions.add(part.request.id);
          if (!inlineQuestions) {
            // VS Code 1.139 does not route carousel replies back to restored
            // activeResponseCallback streams. Use its native picker after reconnect.
            stream.markdown("\n\n" + part.request.questions.map(q => q.message || q.title).join("\n\n"));
            stream.button({ command: "supersurferNative.answerQuestion", title: "Answer question", arguments: [scope, part.request.id] });
            continue;
          }
          const questions = part.request.questions.map(q => new this.vscode.ChatQuestion(q.id, q.kind === "text" ? 1 : 2, q.title, { message: q.message, allowFreeformInput: q.allowFreeformInput, options: q.options?.map(o => ({ id: o.id, label: o.label, value: o.id })) }));
          const answers = await stream.questionCarousel(questions, false);
          if (answers && !token.isCancellationRequested) {
            const converted = {};
            for (const q of part.request.questions) {
              const answer = answers[q.id];
              const value = typeof answer === "string" ? answer : answer?.freeformValue || answer?.selectedValue;
              if (typeof value !== "string") throw Error("The answer could not be read. Reopen this chat to answer the pending question.");
              converted[q.id] = { state: "submitted", value: { kind: "text", value } };
            }
            await host.dispatch(chatResource(scope), { type: "chat/inputCompleted", requestId: part.request.id, response: "accept", answers: converted });
          }
        }
      }
      if (!view.activeTurn || view.activeTurn.id !== turnId) return;
      await new Promise(r => setTimeout(r, 500));
    }
    // Disposing a native view cancels its stream too. Only the explicit Stop
    // agent action may stop the service; closing VS Code must never do so.
  }
}
module.exports = { NativeSessionProvider };
