"use strict";
const { test } = require("node:test"), assert = require("node:assert/strict"), fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const { ServiceHost } = require("../native_extension/service-host.cjs");
const { Host, atomic } = require("../native_extension/host.cjs");
const { resource, chatResource } = require("../native_extension/service-session.cjs");
function fixture(t) {
  const storage = fs.mkdtempSync(path.join(os.tmpdir(), "ss-service-host-")), scope = "experiment:existing", sent = [];
  const chat = { scope, backend: "codex", thread_id: "original-provider-thread", agent: { name: "Existing agent", model: "saved-model" }, busy: false, status: "completed", message_count: 2,
    messages: [{ id: "old-user", role: "user", text: "Original assignment", created: 100 }, { id: "old-answer", role: "assistant", text: "Saved answer", created: 101 }] };
  const service = {
    request: async route => {
      if (route === "/api/state") return { projects: [{ id: "p", name: "Research", repo: storage }] };
      if (route.startsWith("/api/project-agents")) return { agents: [{ scope, name: "Existing agent", owner: "supersurfer", experiment_id: "existing" }] };
      if (route.startsWith("/api/chat")) return structuredClone(chat);
      throw Error(route);
    },
    action: async (op, args) => {
      sent.push({ op, args });
      if (op === "chat.send") { chat.busy = true; chat.status = "working"; chat.messages.push({ id: "new-user", role: "user", text: args.text, created: 200 }); chat.message_count++; return { accepted: true, message_id: "new-user" }; }
      if (op === "chat.stop") { chat.busy = false; chat.status = "interrupted"; }
      return { accepted: true };
    },
  };
  const config = { storage, secret: "fixture-token", stateDirectory: storage }, host = new ServiceHost(config, service);
  t.after(async () => { await host.close(); fs.rmSync(storage, { recursive: true, force: true }); });
  async function connect() {
    const port = host.server?.address().port || await host.listen(), file = path.join(storage, "endpoint.json");
    atomic(file, { instanceId: "fixture", type: "standalone", connectionToken: config.secret, endpoint: { type: "tcp", host: "127.0.0.1", port } });
    const client = new Host(file); await client.connect(); await client.snapshot(resource(scope)); await client.snapshot(chatResource(scope)); t.after(() => client.close()); return client;
  }
  return { host, chat, scope, storage, sent, service, config, connect };
}
test("native discovery and history preserve provider, model, folder and thread without a write", async t => {
  const f = fixture(t), c = await f.connect(), sessions = await c.sessions();
  assert.ok(sessions.some(s => s.resource === resource(f.scope)));
  const session = await c.snapshot(resource(f.scope)), chat = await c.snapshot(chatResource(f.scope));
  assert.equal(session.config.values.model, "saved-model"); assert.equal(session._meta.supersurfer.threadId, "original-provider-thread");
  assert.equal(chat.turns[0].responseParts[0].content, "Saved answer"); assert.equal(f.sent.length, 0);
});
test("two native clients share one send and see work finish after both disconnect", async t => {
  const f = fixture(t), a = await f.connect(), b = await f.connect();
  const action = { type: "chat/turnStarted", turnId: "native-turn", startedAt: new Date().toISOString(), message: { text: "Continue", origin: { kind: "user" } } };
  await a.dispatch(chatResource(f.scope), action); await b.dispatch(chatResource(f.scope), action);
  assert.equal(f.sent.length, 1); assert.equal(f.sent[0].args.scope, f.scope);
  assert.equal((await b.snapshot(chatResource(f.scope))).activeTurn.id, "native-turn");
  a.close(); b.close();
  f.chat.messages.push({ id: "later-answer", role: "assistant", text: "Finished while disconnected", created: 201 }); f.chat.busy = false; f.chat.status = "completed";
  const back = await f.connect(), view = await back.snapshot(chatResource(f.scope));
  assert.equal(view.turns.at(-1).responseParts[0].content, "Finished while disconnected"); assert.equal(f.chat.thread_id, "original-provider-thread");
});
test("uncertain send survives bridge restart and is never replayed", async t => {
  const f = fixture(t), c = await f.connect();
  f.service.action = async () => { f.sent.push("attempt"); throw Error("Connection lost"); };
  const action = { type: "chat/turnStarted", turnId: "uncertain-turn", message: { text: "Do this once", origin: { kind: "user" } } };
  await assert.rejects(c.dispatch(chatResource(f.scope), action), /Connection lost/);
  const resumed = new ServiceHost(f.config, f.service); await resumed.catalog();
  await assert.rejects(resumed.send(f.scope, action), /uncertain/); assert.equal(f.sent.length, 1);
});
test("questions and approvals require explicit decisions and stay in the original conversation", async t => {
  const f = fixture(t); f.chat.busy = true;
  f.chat.questions = [{ id: "q", status: "pending", can_answer: true, questions: [{ id: "choice", question: "Which result?", options: [{ label: "Latest" }] }] }];
  f.chat.approvals = [{ id: "permission", status: "pending", can_approve: true, kind: "command", command: "test-command" }];
  const c = await f.connect(), view = await c.snapshot(chatResource(f.scope));
  assert.equal(view.status, 24); assert.equal(f.sent.length, 0);
  await c.dispatch(chatResource(f.scope), { type: "chat/inputCompleted", requestId: "q", response: "accept", answers: { choice: { state: "submitted", value: { kind: "selected", value: "Latest" } } } });
  await c.dispatch(chatResource(f.scope), { type: "chat/toolCallConfirmed", turnId: view.activeTurn.id, toolCallId: "permission", selectedOptionId: "deny", approved: false, confirmed: "user-action" });
  assert.deepEqual(f.sent, [{ op: "chat.answer", args: { scope: f.scope, question_id: "q", answers: { choice: ["Latest"] } } }, { op: "chat.approve", args: { scope: f.scope, approval_id: "permission", decision: "deny" } }]);
});
test("drafts persist and opening a chat does not submit them", async t => {
  const f = fixture(t), c = await f.connect(), draft = { text: "Unsent draft", origin: { kind: "user" } };
  await c.dispatch(chatResource(f.scope), { type: "chat/draftChanged", draft });
  const resumed = new ServiceHost(f.config, f.service); await resumed.catalog();
  const view = await resumed.snapshot(chatResource(f.scope));
  assert.equal(view.state.draft.text, draft.text); assert.equal(f.sent.length, 0);
});
test("native view does not silently change models, send automation, or discard attachments", async t => {
  const f = fixture(t), c = await f.connect();
  for (const message of [
    { text: "x", origin: { kind: "automation" } },
    { text: "x", origin: { kind: "user" }, model: { id: "another" } },
    { text: "x", origin: { kind: "user" }, attachments: [{ type: "embeddedResource", contentType: "image/png", data: "AA==" }] },
  ]) await assert.rejects(c.dispatch(chatResource(f.scope), { type: "chat/turnStarted", turnId: crypto.randomUUID(), message }));
  assert.equal(f.sent.length, 0);
});

test("all history pages load once without losing earlier messages during tail polling", async t => {
  const f = fixture(t), request = f.service.request;
  const messages = Array.from({ length: 302 }, (_, i) => ({ id: "history-" + i, role: i % 2 ? "assistant" : "user", text: "Message " + i, created: i + 1 }));
  f.service.request = async route => route.startsWith("/api/chat") ? { ...f.chat, message_count: messages.length, messages: messages.slice(-Number(new URL(route, "http://local").searchParams.get("limit"))) } : request(route);
  const c = await f.connect(); let view = await c.snapshot(chatResource(f.scope));
  assert.equal(view.turns.length, 75);
  while (view.turnsNextCursor) { await c.request("fetchTurns", { channel: chatResource(f.scope), cursor: view.turnsNextCursor }); view = await c.snapshot(chatResource(f.scope)); }
  assert.equal(view.turns.length, 151); assert.equal(view.turns[0].message.text, "Message 0");
  assert.equal((await c.snapshot(chatResource(f.scope))).turns.length, 151); assert.equal(f.sent.length, 0);
});
test("explicit Stop targets this conversation and an old turn cannot stop newer work", async t => {
  const f = fixture(t), c = await f.connect(); f.chat.busy = true;
  const view = await c.snapshot(chatResource(f.scope));
  await assert.rejects(c.dispatch(chatResource(f.scope), { type: "chat/turnCancelled", turnId: "other-turn" }), /changed/);
  assert.equal(f.sent.length, 0);
  await c.dispatch(chatResource(f.scope), { type: "chat/turnCancelled", turnId: view.activeTurn.id });
  assert.deepEqual(f.sent, [{ op: "chat.stop", args: { scope: f.scope } }]);
});
test("read-only service and unknown conversations reject native writes", async t => {
  const f = fixture(t), request = f.service.request;
  f.service.request = async route => route === "/api/state" ? { ...(await request(route)), read_only: true } : request(route);
  const c = await f.connect();
  await assert.rejects(c.snapshot(resource("experiment:unknown")), /unavailable/);
  await assert.rejects(c.dispatch(chatResource(f.scope), { type: "chat/turnStarted", turnId: "no-write", message: { text: "x", origin: { kind: "user" } } }), /read-only/);
  assert.equal(f.sent.length, 0);
});
test("text context is delivered with its label and a conflicting retry cannot send again", async t => {
  const f = fixture(t), c = await f.connect();
  const action = { type: "chat/turnStarted", turnId: "context-turn", message: { text: "Review this", origin: { kind: "user" }, attachments: [{ type: "simple", label: "selected.py", modelRepresentation: "print(1)" }] } };
  await c.dispatch(chatResource(f.scope), action);
  assert.match(f.sent[0].args.text, /User-selected context: selected.py/); assert.match(f.sent[0].args.text, /print\(1\)/);
  await assert.rejects(c.dispatch(chatResource(f.scope), { ...action, message: { ...action.message, text: "Changed request" } }), /different input/);
  assert.equal(f.sent.length, 1);
});
