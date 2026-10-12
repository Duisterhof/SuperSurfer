"use strict";
const fs = require("node:fs"),
  os = require("node:os"),
  path = require("node:path"),
  crypto = require("node:crypto");
const { EventEmitter } = require("node:events");
const WebSocket = require("ws");
const ROOT = "ahp-root://";
const VERSIONS = ["0.10.0", "0.9.0"];
function privateJSON(file) {
  const st = fs.lstatSync(file);
  if (
    !st.isFile() ||
    st.isSymbolicLink() ||
    (process.getuid && st.uid !== process.getuid()) ||
    (process.platform !== "win32" && st.mode & 0o077)
  )
    throw new Error("Agent Host endpoint must be an owner-only regular file.");
  return JSON.parse(fs.readFileSync(file, "utf8"));
}
function endpointFiles(extra) {
  if (extra) return [path.resolve(extra)];
  const homes = [
    path.join(os.homedir(), ".config", "Code"),
    path.join(os.homedir(), "Library", "Application Support", "Code"),
    path.join(os.homedir(), ".vscode-server", "data"),
  ];
  return homes
    .flatMap((home) => {
      const dir = path.join(home, "agent-host", "local-endpoint", "entries");
      try {
        return fs
          .readdirSync(dir)
          .filter((f) => f.endsWith(".json"))
          .map((f) => path.join(dir, f));
      } catch {
        return [];
      }
    })
    .filter((file) => {
      try {
        const row = privateJSON(file);
        process.kill(row.pid, 0);
        return true;
      } catch {
        return false;
      }
    });
}
class Host extends EventEmitter {
  constructor(file) {
    super();
    this.file = file;
    this.pending = new Map();
    this.seq = 0;
    this.clientSeq = 0;
    this.clientId = "supersurfer-" + crypto.randomUUID();
    this.connected = false;
    this.acks = new Map();
  }
  async connect() {
    const row = privateJSON(this.file),
      e = row.endpoint;
    if (!row.connectionToken || typeof row.connectionToken !== "string")
      throw new Error("Agent Host endpoint has no connection token.");
    this.identity = row.instanceId;
    this.hostType = row.type;
    const options = {
      maxPayload: 16 * 1024 * 1024,
      handshakeTimeout: 5000,
      perMessageDeflate: false,
    };
    let url;
    if (e?.type === "socket" && path.isAbsolute(e.path)) {
      if (e.path.includes(":"))
        throw new Error("Unsupported native socket path.");
      url =
        "ws+unix://" +
        e.path +
        ":/?tkn=" +
        encodeURIComponent(row.connectionToken);
    } else if (
      e?.type === "tcp" &&
      ["localhost", "127.0.0.1", "::1"].includes(e.host) &&
      Number.isInteger(e.port) &&
      e.port > 0 &&
      e.port < 65536
    )
      url = `ws://${e.host === "::1" ? "[::1]" : e.host}:${e.port}/?tkn=${encodeURIComponent(row.connectionToken)}`;
    else
      throw new Error(
        "Connect to an Agent Host on this machine; remote endpoints must use SSH.",
      );
    this.ws = new WebSocket(url, options);
    this.ws.on("message", (data) => {
      let msg;
      try {
        msg = JSON.parse(data.toString());
      } catch {
        return this.ws.close();
      }
      if (msg.id !== undefined) {
        const p = this.pending.get(msg.id);
        if (p) {
          clearTimeout(p.timer);
          this.pending.delete(msg.id);
          msg.error
            ? p.reject(new Error(msg.error.message))
            : p.resolve(msg.result);
        } else if (msg.method)
          this.ws.send(
            JSON.stringify({
              jsonrpc: "2.0",
              id: msg.id,
              error: {
                code: -32601,
                message: "Client resource requests are unavailable",
              },
            }),
          );
      }
      if (
        msg.method === "action" &&
        msg.params?.origin?.clientId === this.clientId
      ) {
        const p = this.acks.get(msg.params.origin.clientSeq);
        if (p) {
          clearTimeout(p.timer);
          this.acks.delete(msg.params.origin.clientSeq);
          msg.params.rejectionReason
            ? p.reject(new Error(msg.params.rejectionReason))
            : p.resolve(msg.params);
        }
      }
      if (msg.method) this.emit("event", msg);
    });
    this.ws.on("error", () => {});
    this.ws.on("close", () => {
      this.connected = false;
      for (const p of [...this.pending.values(), ...this.acks.values()]) {
        clearTimeout(p.timer);
        p.reject(
          new Error("Native host disconnected; outcome may be uncertain."),
        );
      }
      this.pending.clear();
      this.acks.clear();
      this.emit("disconnect");
    });
    await new Promise((resolve, reject) => {
      this.ws.once("open", resolve);
      this.ws.once("error", () =>
        reject(new Error("Cannot connect to the selected native Agent Host.")),
      );
    });
    this.connected = true;
    try {
      this.init = await this.request("initialize", {
        channel: ROOT,
        protocolVersions: VERSIONS,
        clientId: this.clientId,
        clientInfo: {
          name: "supersurfer",
          version: "0.1.43",
          title: "SuperSurfer workflows",
        },
        initialSubscriptions: [ROOT],
      });
    } catch (e) {
      this.close();
      throw e;
    }
    if (!VERSIONS.includes(this.init.protocolVersion)) {
      this.close();
      throw new Error(
        "Unsupported native host protocol; update the editor and host together.",
      );
    }
    return this.init;
  }
  request(method, params) {
    if (!this.connected)
      return Promise.reject(new Error("Native host is disconnected."));
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("Native host request timed out."));
      }, 15000);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
    });
  }
  dispatch(channel, action) {
    if (!this.connected)
      return Promise.reject(new Error("Native host is disconnected."));
    const clientSeq = ++this.clientSeq;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.acks.delete(clientSeq);
        reject(
          new Error(
            "Native host did not confirm the action; inspect the chat before retrying.",
          ),
        );
      }, 15000);
      this.acks.set(clientSeq, { resolve, reject, timer });
      this.ws.send(
        JSON.stringify({
          jsonrpc: "2.0",
          method: "dispatchAction",
          params: { channel, clientSeq, action },
        }),
      );
    });
  }
  async snapshot(channel) {
    const result = await this.request("subscribe", { channel });
    if (!result?.snapshot?.state)
      throw new Error("Native host returned no session state.");
    return result.snapshot.state;
  }
  async sessions() {
    const items = [];
    let cursor;
    const seen = new Set();
    do {
      const page = await this.request("listSessions", {
        channel: ROOT,
        limit: 100,
        ...(cursor ? { cursor } : {}),
      });
      items.push(...(page.items || []));
      cursor = page.nextCursor;
      if (cursor && seen.has(cursor))
        throw new Error("Native host repeated its session cursor.");
      seen.add(cursor);
    } while (cursor && items.length < 1000);
    return items;
  }
  close() {
    this.ws?.close();
  }
}
function atomic(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const temp = file + "." + crypto.randomUUID() + ".tmp";
  fs.writeFileSync(temp, JSON.stringify(value, null, 2) + "\n", {
    mode: 0o600,
  });
  fs.renameSync(temp, file);
}
module.exports = { Host, ROOT, endpointFiles, privateJSON, atomic };
