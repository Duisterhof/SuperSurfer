"use strict";
const { test } = require("node:test"),
  assert = require("node:assert/strict");
const fs = require("node:fs"),
  os = require("node:os"),
  path = require("node:path");
const { Controller } = require("../native_extension/controller.cjs");
function fixture(t) {
  const directory = fs.mkdtempSync(
    path.join(os.tmpdir(), "ss-native-controller-"),
  );
  const c = new Controller({ storage: directory, stateDirectory: directory });
  const b = {
    scope: "native:fixture",
    host_id: "fixture",
    session: "codex:/same",
    chat: "ahp-chat://default/same",
    persistent: true,
    userTurn: "user-1",
    continuations: 0,
  };
  c.bindings[b.scope] = b;
  let state = { turns: [{ id: "user-1", state: "complete" }] };
  const sent = [];
  c.host = {
    connected: true,
    identity: "fixture",
    hostType: "standalone",
    snapshot: async () => state,
    dispatch: async (channel, action) => {
      sent.push({ channel, action });
    },
    close() {},
  };
  c.service = { native: async () => ({ complete: false }) };
  t.after(() => {
    c.close();
    fs.rmSync(directory, { recursive: true, force: true });
  });
  return {
    c,
    b,
    sent,
    set: (value) => {
      state = value;
    },
  };
}
test("continuation stays in the same chat without selecting a new provider or model", async (t) => {
  const f = fixture(t);
  await f.c.observe(f.b);
  assert.equal(f.sent.length, 1);
  assert.equal(f.sent[0].channel, f.b.chat);
  assert.equal(f.sent[0].action.message.origin.kind, "automation");
  assert.equal(f.sent[0].action.model, undefined);
  await f.c.observe(f.b);
  assert.equal(f.sent.length, 1);
});
test("failed or cancelled turns and paused work never continue", async (t) => {
  const f = fixture(t);
  for (const state of ["error", "cancelled"]) {
    f.set({ turns: [{ id: "user-1", state }] });
    await f.c.observe(f.b);
  }
  f.b.paused = true;
  f.set({ turns: [{ id: "user-1", state: "complete" }] });
  await f.c.observe(f.b);
  assert.equal(f.sent.length, 0);
});
test("manual pause remains paused when the user sends another message", async (t) => {
  const f = fixture(t);
  f.b.paused = true;
  f.set({
    activeTurn: {
      id: "new-user",
      message: { origin: { kind: "user" } },
      responseParts: [],
    },
  });
  await f.c.observe(f.b);
  assert.equal(f.b.paused, true);
});
test("uncertain dispatch is persisted and never replayed", async (t) => {
  const f = fixture(t);
  f.c.host.dispatch = async () => {
    throw new Error("Connection lost");
  };
  await f.c.observe(f.b);
  assert.equal(f.b.paused, true);
  const saved = JSON.parse(fs.readFileSync(f.c.file));
  assert.equal(saved[f.b.scope].continuation.status, "uncertain");
  f.b.paused = false;
  await f.c.observe(f.b);
  assert.equal(f.b.paused, true);
});
test("configuration-only messages do not start workflow actions afterward", async (t) => {
  const f = fixture(t);
  await f.c.handle("ask", {
    scope: f.b.scope,
    text: "Rename this block",
    purpose: "edit",
  });
  const id = f.sent[0].action.turnId;
  f.set({
    activeTurn: {
      id,
      message: { origin: { kind: "user" } },
      responseParts: [],
    },
  });
  await f.c.observe(f.b);
  f.set({ turns: [{ id, state: "complete" }] });
  await f.c.observe(f.b);
  assert.equal(f.sent.length, 1);
});
test("only this companion executes its own client tool calls", async (t) => {
  const f = fixture(t);
  f.c.host.clientId = "owner";
  let tools = 0;
  f.c.tool = async () => {
    tools++;
  };
  const call = (clientId) => ({
    kind: "toolCall",
    toolCall: { status: "running", contributor: { kind: "client", clientId } },
  });
  f.set({
    activeTurn: {
      id: "new-user",
      message: { origin: { kind: "user" } },
      responseParts: [call("foreign"), call("owner")],
    },
  });
  await f.c.observe(f.b);
  assert.equal(tools, 1);
});
test("persistence stops after three continuations and editor hosts cannot enable it", async (t) => {
  const f = fixture(t);
  f.b.continuations = 3;
  await f.c.observe(f.b);
  assert.equal(f.sent.length, 0);
  assert.equal(f.b.paused, true);
  f.c.host.hostType = "editor";
  await assert.rejects(
    f.c.handle("pause", { scope: f.b.scope, paused: false }),
    /standalone/,
  );
});
test("repeated tools use the same stable receipt", async (t) => {
  const f = fixture(t);
  const receipts = [];
  f.c.service.native = async (op, args) => {
    receipts.push(args.request_id);
    return { okay: true };
  };
  const call = {
    toolCallId: "call-1",
    toolName: "read_surfboard",
    toolInput: "{}",
  };
  await f.c.tool(f.b, { id: "turn-1" }, call);
  await f.c.tool(f.b, { id: "turn-1" }, call);
  assert.equal(receipts[0], receipts[1]);
  assert.equal(receipts[0].length, 64);
});

test("attachments reject secondary chats and pause if tool installation fails", async (t) => {
  const f = fixture(t);
  const repo = f.c.config.storage;
  const session = {
    provider: "codex",
    defaultChat: "ahp-chat://default/same",
    chats: [
      { resource: "ahp-chat://default/same" },
      { resource: "ahp-chat://secondary/same" },
    ],
    workingDirectories: [require("node:url").pathToFileURL(repo).href],
  };
  f.c.host.snapshot = async () => session;
  await assert.rejects(
    f.c.handle("attach", {
      session: "codex:/same",
      chat: "ahp-chat://secondary/same",
      repo,
    }),
    /main conversation/,
  );
  f.c.service.native = async () => ({
    scope: f.b.scope,
    host_id: "fixture",
    session: "codex:/same",
    chat: session.defaultChat,
  });
  f.c.contribute = async () => {
    throw new Error("host lost");
  };
  await assert.rejects(
    f.c.handle("attach", { session: "codex:/same", repo }),
    /host lost/,
  );
  assert.equal(f.c.bindings[f.b.scope].paused, true);
  assert.match(f.c.bindings[f.b.scope].note, /Reattach/);
});
