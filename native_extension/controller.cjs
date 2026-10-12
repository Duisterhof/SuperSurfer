"use strict";
// The companion outlives the editor. Only this process contributes workflow
// tools; closing an extension host cannot strand an in-flight tool call.
const fs = require("node:fs"),
  path = require("node:path"),
  http = require("node:http"),
  crypto = require("node:crypto");
const { fileURLToPath } = require("node:url");
const { Host, atomic } = require("./host.cjs"),
  { Service } = require("./service.cjs");
const finish = {
  name: "finish_workflow",
  title: "Finish workflow",
  description:
    "Complete the attached user task with evidence. Required Surfboard checks must pass for the current source. Call when the requested work is actually finished; this stops automatic continuation.",
  inputSchema: {
    type: "object",
    properties: { summary: { type: "string" } },
    required: ["summary"],
  },
};
class Controller {
  constructor(config) {
    this.config = config;
    this.service = new Service(config.stateDirectory);
    this.file = path.join(config.storage, "bindings.json");
    try {
      this.bindings = JSON.parse(fs.readFileSync(this.file));
    } catch (e) {
      if (e.code !== "ENOENT") throw e;
      this.bindings = {};
    }
    this.busy = new Set();
    this.executing = new Set();
    this.error = null;
    this.closed = false;
    this.refreshTimer = null;
  }
  save() {
    atomic(this.file, this.bindings);
  }
  async connect() {
    if (this.closed) return;
    this.host = new Host(this.config.endpointFile);
    this.host.on("disconnect", () => {
      this.error = "Native host disconnected. Work has not been replayed.";
      if (!this.closed)
        this.reconnect = setTimeout(() => {
          this.reconnect = null;
          this.connect().catch(() => {});
        }, 3000);
    });
    this.host.on("event", (msg) => {
      if (
        msg.method === "action" &&
        msg.params?.action?.type === "chat/turnCancelled"
      ) {
        for (const b of Object.values(this.bindings))
          if (b.chat === msg.params.channel) {
            b.paused = true;
            b.note = "Stopped in native chat. Resume persistence explicitly.";
            this.save();
          }
      }
      this.schedule();
    });
    try {
      await this.host.connect();
      this.error = null;
      for (const b of Object.values(this.bindings)) {
        if (b.host_id === this.host.identity) await this.contribute(b);
      }
      this.schedule();
    } catch (e) {
      this.error = e.message;
      if (!this.closed && !this.reconnect)
        this.reconnect = setTimeout(() => {
          this.reconnect = null;
          this.connect().catch(() => {});
        }, 5000);
    }
  }
  schedule() {
    if (!this.refreshTimer && !this.closed)
      this.refreshTimer = setTimeout(() => {
        this.refreshTimer = null;
        this.refresh().catch((e) => {
          this.error = e.message;
        });
      }, 250);
  }
  async contribute(b) {
    await this.host.snapshot(b.session);
    const catalog = await this.service.native("tools", { scope: b.scope });
    await this.host.dispatch(b.session, {
      type: "session/activeClientSet",
      activeClient: {
        clientId: this.host.clientId,
        displayName: "SuperSurfer",
        tools: [...catalog.tools, finish],
      },
    });
  }
  async refresh() {
    if (!this.host?.connected) return;
    for (const b of Object.values(this.bindings)) {
      if (b.host_id !== this.host.identity || this.busy.has(b.scope)) continue;
      this.busy.add(b.scope);
      try {
        await this.observe(b);
      } catch (e) {
        b.note = e.message;
      } finally {
        this.busy.delete(b.scope);
      }
    }
  }
  async observe(b) {
    const state = await this.host.snapshot(b.chat);
    if (
      b.pendingUserMessage &&
      [state.activeTurn, ...(state.turns || [])].some(
        (t) => t?.id === b.pendingUserMessage.turnId,
      )
    )
      b.pendingUserMessage.status = "observed";
    b.status = state.status;
    b.activity = state.activity || "";
    const turn = state.activeTurn;
    let origin = turn?.message?.origin?.kind || null;
    if (turn?.id === b.continuation?.turnId) origin = "continuation";
    if (turn && origin === "user" && b.userTurn !== turn.id) {
      b.userTurn = turn.id;
      b.continuations = 0;
      b.complete = false;
      b.note = "";
      b.continuation = null;
      this.save();
    }
    const result = await this.service.native("observe", {
      scope: b.scope,
      turn_id: turn?.id || null,
      origin,
    });
    b.complete = result.complete;
    if (turn) {
      for (const part of turn.responseParts || []) {
        const call = part.toolCall;
        if (
          part.kind !== "toolCall" ||
          call?.status !== "running" ||
          call.contributor?.clientId !== this.host.clientId
        )
          continue;
        await this.tool(b, turn, call);
      }
    } else if (
      b.persistent &&
      !b.paused &&
      !b.complete &&
      b.userTurn &&
      b.userTurn !== b.configurationTurn
    ) {
      const last = state.turns?.at(-1);
      // Never continue an error/cancellation or a human question. No replay
      // after uncertain delivery: the pending turn must be observed by ID.
      if (
        !last ||
        (last.state !== "complete" &&
          last.status !== "completed" &&
          last.status !== "complete")
      ) {
        b.note = "Waiting for a successful native turn.";
        return;
      }
      if (b.continuation && b.continuation.status === "uncertain") {
        if (state.turns.some((t) => t.id === b.continuation.turnId))
          b.continuation.status = "observed";
        else {
          b.paused = true;
          b.note =
            "Continuation delivery is uncertain. Inspect the native chat before resuming.";
          this.save();
          return;
        }
      }
      if (b.lastCompleted === last.id) return;
      b.lastCompleted = last.id;
      if ((b.continuations || 0) >= 3) {
        b.paused = true;
        b.note =
          "Three continuation attempts used. Review the chat to continue.";
        this.save();
        return;
      }
      const text =
        "Continue the user-requested task attached to this SuperSurfer workflow. Read read_surfboard for the current graph. Use run_board_action for required checks, then finish_workflow with evidence when the requested work is complete. Do not start unrelated work or GPU runs. If you need the user, ask using the native question tool and wait. Preserve the latest user instructions.";
      b.continuations = (b.continuations || 0) + 1;
      const turnId = crypto.randomUUID();
      b.continuation = { turnId, status: "uncertain" };
      this.save();
      try {
        await this.host.dispatch(b.chat, {
          type: "chat/turnStarted",
          turnId,
          startedAt: new Date().toISOString(),
          message: { text, origin: { kind: "automation" } },
        });
        b.continuation.status = "accepted";
        this.save();
      } catch (e) {
        b.paused = true;
        b.note = e.message;
        this.save();
      }
    }
  }
  async tool(b, turn, call) {
    const identity = b.scope + ":" + turn.id + ":" + call.toolCallId;
    if (this.executing.has(identity)) return;
    this.executing.add(identity);
    try {
      let result;
      try {
        if (typeof call.toolInput !== "string")
          throw new Error(
            "Referenced tool input is not supported; retry with inline arguments.",
          );
        const args = JSON.parse(call.toolInput || "{}");
        const value = await this.service.native("tool", {
          scope: b.scope,
          name: call.toolName,
          arguments: args,
          request_id: crypto
            .createHash("sha256")
            .update(identity)
            .digest("hex"),
        });
        result = {
          success: true,
          pastTenseMessage: "Updated SuperSurfer workflow",
          content: [{ type: "text", text: JSON.stringify(value) }],
        };
      } catch (e) {
        result = {
          success: false,
          pastTenseMessage: "SuperSurfer needs attention",
          error: { message: e.message },
          content: [{ type: "text", text: e.message }],
        };
      }
      await this.host.dispatch(b.chat, {
        type: "chat/toolCallComplete",
        turnId: turn.id,
        toolCallId: call.toolCallId,
        result,
      });
    } finally {
      this.executing.delete(identity);
    }
  }
  async handle(op, args = {}) {
    if (op === "status")
      return {
        connected: !!this.host?.connected,
        error: this.error,
        hostType: this.host?.hostType,
        bindings: Object.values(this.bindings).map((b) => ({
          ...b,
          connected: !!this.host?.connected && b.host_id === this.host.identity,
        })),
      };
    if (op === "snapshot") return this.host.snapshot(args.channel);
    if (op === "sessions") {
      if (!this.host?.connected)
        throw new Error(this.error || "Native host is connecting.");
      return { sessions: await this.host.sessions() };
    }
    if (op === "state") return this.service.request("/api/state");
    if (op === "attach") {
      if (!this.host?.connected)
        throw new Error("Connect the native host first.");
      const session = await this.host.snapshot(args.session);
      const chat = args.chat || session.defaultChat;
      if (!chat || !session.chats?.some((c) => c.resource === chat))
        throw new Error("Choose an interactive chat in this native session.");
      if (chat !== session.defaultChat)
        throw new Error(
          "This preview attaches the main conversation of each native session.",
        );
      const c = await this.host.snapshot(chat);
      if (c.interactivity && c.interactivity !== "full")
        throw new Error("This native chat is not interactive.");
      const roots = c.workingDirectories ?? session.workingDirectories ?? [];
      const cwd = roots
        .map((uri) => {
          try {
            return fileURLToPath(uri);
          } catch {
            return null;
          }
        })
        .find((dir) => dir && path.resolve(dir) === path.resolve(args.repo));
      if (!cwd)
        throw new Error(
          "The native chat must work in the selected project repository.",
        );
      const b = await this.service.native("attach", {
        host_id: this.host.identity,
        session: args.session,
        chat,
        project_id: args.project_id,
        experiment_id: args.experiment_id || null,
        cwd,
        title: session.title,
      });
      b.provider = session.provider;
      b.persistent = this.host.hostType === "standalone" && b.role === "worker";
      b.paused = false;
      this.bindings[b.scope] = b;
      this.save();
      try {
        await this.contribute(b);
      } catch (error) {
        b.paused = true;
        b.note =
          "Workflow tools could not be attached. Reattach before continuing: " +
          error.message;
        this.save();
        throw error;
      }
      return b;
    }
    const b = this.bindings[args.scope];
    if (!b && op !== "queue" && op !== "queueAction")
      throw new Error("Select an attached native chat.");
    if (
      ["ask", "pause"].includes(op) &&
      (!this.host?.connected || b.host_id !== this.host.identity)
    )
      throw new Error(
        "This conversation's host is disconnected. Reattach to its host before continuing.",
      );
    if (op === "board") return this.service.board(b);
    if (op === "save" || op === "apply" || op === "discard") {
      const fields = { ...args };
      delete fields.scope;
      return this.service.action(
        "surfboard." +
          { save: "draft", apply: "apply", discard: "discard" }[op],
        {
          ...fields,
          project_id: b.project_id,
          ...(b.experiment_id ? { experiment_id: b.experiment_id } : {}),
        },
      );
    }
    if (op === "pause") {
      if (
        args.paused === false &&
        (this.host.hostType !== "standalone" || !b.persistent)
      )
        throw new Error(
          "Persistence requires a task attached to a standalone Agent Host.",
        );
      b.paused = args.paused !== false;
      b.note = b.paused
        ? "Automatic continuation paused. The native chat remains available."
        : "";
      if (!b.paused) {
        b.continuations = 0;
        b.continuation = null;
        b.lastCompleted = null;
      }
      this.save();
      return b;
    }
    if (op === "detach") {
      if (this.host?.connected && b.host_id === this.host.identity)
        await this.host.dispatch(b.session, {
          type: "session/activeClientSet",
          activeClient: {
            clientId: this.host.clientId,
            displayName: "SuperSurfer",
            tools: [],
          },
        });
      await this.service.native("detach", { scope: b.scope });
      delete this.bindings[b.scope];
      this.save();
      return { detached: true };
    }
    if (op === "ask") {
      if (
        typeof args.text !== "string" ||
        !args.text.trim() ||
        args.text.length > 20000
      )
        throw new Error("Describe the requested workflow edit.");
      const current = await this.host.snapshot(b.chat);
      if (b.pendingUserMessage?.status === "uncertain")
        throw new Error(
          "Previous message delivery is uncertain. Inspect the native chat before sending again.",
        );
      if (current.activeTurn)
        throw new Error(
          "This agent is working. Send a follow-up in its native chat.",
        );
      const turnId = crypto.randomUUID();
      b.configurationTurn = args.purpose === "edit" ? turnId : null;
      b.pendingUserMessage = { turnId, text: args.text, status: "uncertain" };
      this.save();
      await this.host.dispatch(b.chat, {
        type: "chat/turnStarted",
        turnId,
        startedAt: new Date().toISOString(),
        message: { text: args.text, origin: { kind: "user" } },
      });
      b.pendingUserMessage.status = "accepted";
      this.save();
      return { accepted: true };
    }
    if (op === "queue") {
      const s = await this.service.request("/api/state");
      return {
        queue: s.queue,
        runs: s.runs,
        hosts: s.hosts,
        updated_at: s.updated_at,
        connected: s.connected,
      };
    }
    if (op === "queueAction") {
      if (
        !["queue.pause", "queue.resume", "run.move", "run.cancel"].includes(
          args.action,
        )
      )
        throw new Error("Unsupported queue action.");
      return this.service.action(args.action, args.params || {});
    }
    throw new Error("Unknown SuperSurfer command.");
  }
  close() {
    this.closed = true;
    clearTimeout(this.reconnect);
    clearTimeout(this.refreshTimer);
    clearInterval(this.tick);
    this.host?.close();
  }
}
async function main(file) {
  const config = JSON.parse(fs.readFileSync(file));
  const c = new Controller(config);
  const server = http.createServer((req, res) => {
    let raw = "";
    req.on("data", (data) => {
      raw += data;
      if (raw.length > 2 * 1024 * 1024) req.destroy();
    });
    req.on("end", async () => {
      try {
        if (
          req.method !== "POST" ||
          req.headers.authorization !== "Bearer " + config.secret
        )
          throw new Error("Unauthorized companion request");
        const { op, args } = JSON.parse(raw);
        const result = await c.handle(op, args);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
  });
  server.on("error", (e) => {
    if (e.code === "EADDRINUSE") process.exit(0);
    else throw e;
  });
  server.listen(config.socket, () => {
    fs.chmodSync(config.socket, 0o600);
    c.connect().catch(() => {});
    c.tick = setInterval(
      () =>
        c.refresh().catch((e) => {
          c.error = e.message;
        }),
      5000,
    );
  });
  const close = () => {
    c.close();
    server.close();
    try {
      fs.unlinkSync(config.socket);
    } catch {}
    process.exit();
  };
  process.on("SIGTERM", close);
  process.on("SIGINT", close);
}
if (require.main === module)
  main(process.argv[2]).catch((e) => {
    console.error(e.message);
    process.exit(1);
  });
module.exports = { Controller };
