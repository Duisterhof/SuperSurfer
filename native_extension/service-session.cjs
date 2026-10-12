"use strict";
// A view of the service's conversation, not a second provider session.
const { pathToFileURL } = require("node:url");
const encode = value => Buffer.from(value).toString("base64url");
const resource = scope => "supersurfer:/" + encode(scope);
const chatResource = (scope, session = resource(scope)) => "ahp-chat://default/" + encode(session);
const iso = seconds => new Date((Number(seconds) || 0) * 1000).toISOString();
const partKey = part => part.id || part.toolCall?.toolCallId || part.request?.id;
function inputRequest(question) {
  return { id: question.id, questions: question.questions.map(q => ({
    id: q.id, title: q.header || "Question", message: q.question, required: true,
    ...(q.options?.length ? { kind: "single-select", allowFreeformInput: q.isOther !== false,
      options: q.options.map(o => ({ id: o.label, label: o.label, description: o.description })) } : { kind: "text" }),
  })) };
}
function approvalPart(approval) {
  return { kind: "toolCall", toolCall: {
    toolCallId: approval.id, toolName: approval.kind || "approval", displayName: "Permission requested",
    invocationMessage: approval.reason || approval.command || "The agent needs your permission to continue.",
    toolInput: approval.command || JSON.stringify(approval.paths || []), status: "pending-confirmation",
    options: [{ id: "approve", label: "Approve once", kind: "approve" }, { id: "deny", label: "Deny", kind: "deny" }],
  } };
}
function sessionView(binding, chat, saved = {}) {
  const turns = [], ids = saved.turnIds || {}, scope = binding.scope;
  const sessionURI = saved.resource || resource(scope), chatURI = chatResource(scope, sessionURI);
  let current;
  for (const m of chat.messages || []) {
    if ((m.role === "user" || m.role === "system") && !m.steering) {
      current = { id: ids[m.id] || m.id, startedAt: iso(m.created), state: "complete",
        message: { text: m.text || "", origin: { kind: m.role === "user" ? "user" : "automation" } }, responseParts: [] };
      turns.push(current);
    } else if (current && m.text) {
      current.responseParts.push({ kind: "markdown", id: m.id, content: m.steering ? "**Your direction:** " + m.text : m.text });
    }
  }
  const last = turns.at(-1);
  if (last) {
    if (chat.error) last.responseParts.push({ kind: "markdown", id: "service-error", content: "**Agent needs attention:** " + chat.error });
    if (["failed", "error"].includes(chat.status)) last.state = "error";
    if (["interrupted", "stopped"].includes(chat.status)) last.state = "cancelled";
    const lastTime = Date.parse(last.startedAt) / 1000;
    for (const event of chat.activity || []) {
      if (!event.text || event.created < lastTime || ["reasoning", "thinking"].includes(event.type)) continue;
      const running = chat.busy && ["running", "inProgress", "started"].includes(event.status);
      last.responseParts.push({ kind: "toolCall", toolCall: {
        toolCallId: "activity-" + event.id, toolName: event.type || "activity", displayName: event.type || "Activity",
        invocationMessage: event.text.split("\n")[0], toolInput: "", confirmed: "not-needed",
        status: running ? "running" : "completed", ...(running ? {} : { success: event.status !== "failed", pastTenseMessage: event.text.split("\n")[0] }),
        content: [{ type: "text", text: event.text }],
      } });
    }
  }
  const questions = (chat.questions || []).filter(q => q.status === "pending" && q.can_answer !== false);
  const approvals = (chat.approvals || []).filter(a => a.status === "pending" && a.can_approve !== false);
  // A pending human question can outlive a provider turn; keep its native input usable.
  const active = !!(last && (chat.busy || questions.length || approvals.length));
  if (active) {
    for (const q of questions) last.responseParts.push({ kind: "inputRequest", request: inputRequest(q) });
    for (const a of approvals) last.responseParts.push(approvalPart(a));
  }
  const status = questions.length || approvals.length ? 24 : chat.busy ? 8 : chat.status === "failed" ? 2 : 1;
  const title = chat.agent?.name || binding.name || "SuperSurfer agent";
  const workingDirectories = binding.repo ? [pathToFileURL(binding.repo).href] : [];
  const modifiedAt = iso(Math.max(binding.updated_at || 0, ...((chat.messages || []).map(m => m.created || 0))));
  const summary = { provider: "supersurfer", resource: sessionURI, title, status,
    createdAt: iso(chat.created_at || binding.created_at), modifiedAt, workingDirectories,
    ...(binding.repo ? { project: { uri: workingDirectories[0], displayName: binding.projectName || title } } : {}),
    _meta: { supersurfer: { scope, backend: chat.backend, threadId: chat.thread_id }, isArchived: !!chat.archived },
  };
  const chatSummary = { resource: chatURI, title, status, modifiedAt, workingDirectories, interactivity: chat.read_only ? "read-only" : "full" };
  const state = { ...chatSummary, turns: active ? turns.slice(0, -1) : turns,
    ...(active ? { activeTurn: { ...last, state: undefined } } : {}),
    ...(saved.draft ? { draft: saved.draft } : {}),
    ...(saved.queue?.length ? { queuedMessages: saved.queue } : {}),
  };
  const backend = chat.backend || chat.agent?.backend || "codex";
  const model = chat.preferences?.effective?.model || chat.agent?.model;
  const session = { ...summary, lifecycle: "ready", activeClients: [], chats: [chatSummary], defaultChat: chatURI,
    serverTools: [], customizations: [], changesets: [],
    config: { schema: { type: "object", properties: {
      backend: { type: "string", title: "Provider", readOnly: true },
      model: { type: "string", title: "Model", readOnly: true },
    } }, values: { backend, model: model || "Provider default" } },
    inputNeeded: active ? [
      ...questions.map(q => ({ id: q.id, chat: chatURI, kind: "chatInput", request: inputRequest(q) })),
      ...approvals.map(a => ({ id: a.id, chat: chatURI, kind: "toolConfirmation", turnId: last.id, toolCall: approvalPart(a).toolCall })),
    ] : [],
  };
  return { summary, session, chat: state };
}
module.exports = { resource, chatResource, sessionView, partKey };
