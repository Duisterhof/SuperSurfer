"use strict";
const { test } = require("node:test"),
  assert = require("node:assert/strict");
const fs = require("node:fs"),
  os = require("node:os"),
  path = require("node:path"),
  http = require("node:http");
const { WebSocketServer } = require("ws");
const { Host, atomic, privateJSON } = require("../native_extension/host.cjs");

test("native host connects over an authenticated Unix socket and observes action receipts", async (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-native-host-"));
  const socket = path.join(dir, "host.sock"),
    endpoint = path.join(dir, "endpoint.json");
  const server = http.createServer(),
    wss = new WebSocketServer({ server });
  let requestPath;
  wss.on("connection", (ws, req) => {
    requestPath = req.url;
    ws.on("message", (raw) => {
      const msg = JSON.parse(raw);
      if (msg.method === "initialize")
        ws.send(
          JSON.stringify({
            jsonrpc: "2.0",
            id: msg.id,
            result: { protocolVersion: "0.9.0" },
          }),
        );
      if (msg.method === "dispatchAction")
        ws.send(
          JSON.stringify({
            jsonrpc: "2.0",
            method: "action",
            params: {
              channel: msg.params.channel,
              origin: {
                clientId: host.clientId,
                clientSeq: msg.params.clientSeq,
              },
              action: msg.params.action,
              ...(msg.params.action.reject
                ? { rejectionReason: "Not allowed" }
                : {}),
            },
          }),
        );
    });
  });
  await new Promise((r) => server.listen(socket, r));
  atomic(endpoint, {
    instanceId: "fixture",
    type: "editor",
    connectionToken: "fixture-only",
    endpoint: { type: "socket", path: socket },
  });
  const host = new Host(endpoint);
  t.after(async () => {
    host.close();
    for (const ws of wss.clients) ws.terminate();
    await new Promise((r) => server.close(r));
    fs.rmSync(dir, { recursive: true, force: true });
  });
  await host.connect();
  assert.equal(requestPath, "/?tkn=fixture-only");
  assert.equal(host.hostType, "editor");
  await host.dispatch("codex:/same", { type: "fixture" });
  await assert.rejects(
    host.dispatch("codex:/same", { type: "fixture", reject: true }),
    /Not allowed/,
  );
});

test("endpoint permissions and non-loopback connections are rejected", async (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-native-host-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const file = path.join(dir, "endpoint.json");
  atomic(file, {
    connectionToken: "fixture-only",
    endpoint: { type: "tcp", host: "example.com", port: 1234 },
  });
  await assert.rejects(new Host(file).connect(), /SSH/);
  fs.chmodSync(file, 0o644);
  assert.throws(() => privateJSON(file), /owner-only/);
});
