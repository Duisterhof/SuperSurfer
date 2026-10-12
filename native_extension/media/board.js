/* The webview only sends scoped requests. Host tokens never enter this page. */
"use strict";
const api = acquireVsCodeApi();
const app = document.getElementById("app");
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const send = (op, args = {}) => api.postMessage({ op, args });
let state,
  board,
  binding,
  selected,
  dirty = false,
  busy = false,
  applyAfterSave = false,
  hostType;
let saved = api.getState();
let questionDraft = saved?.questionDraft || "";
const group = (kind) =>
  kind === "agent"
    ? "agent"
    : ["check", "approval", "condition"].includes(kind)
      ? "condition"
      : ["code", "compute", "experiment", "timer", "latex"].includes(kind)
        ? "action"
        : "view";
const clone = (value) => JSON.parse(JSON.stringify(value));
const draftVersion = (value) => value?.draft?.draft_version || 0;
function persist() {
  const value = {
    board,
    dirty,
    version: state.version,
    draftVersion: draftVersion(state),
    selected,
    questionDraft,
  };
  api.setState(value);
  send("retainDraft", value);
}
function notice(text, error = false) {
  const element = document.getElementById("notice");
  if (element) {
    element.textContent = text;
    element.classList.toggle("error", error);
  }
}
function changed() {
  dirty = true;
  persist();
  document.getElementById("save").disabled = false;
  notice("Unsaved edits · your changes stay here until you save or apply.");
}
function render() {
  if (document.body.dataset.mode === "queue") return renderQueue();
  const status =
    binding?.connected === false
      ? "Disconnected"
      : binding?.complete
        ? "Finished"
        : binding?.paused
          ? "Persistence paused"
          : binding?.status & 8
            ? "Agent working"
            : "Ready";
  app.innerHTML = `<header class="top"><div><h1>${esc(board.name || "Surfboard")}</h1><span class="muted">${esc(binding?.title || "Native agent")} · ${hostType === "standalone" ? "Persistent host" : "Editor host"}</span></div><div class="actions"><span class="badge" id="status">${status}</span><button id="open">${hostType === "standalone" ? "Open in Agents" : "Open chat"}</button>${hostType === "standalone" ? "" : '<button id="split">Split chat</button>'}</div></header>
    <div class="toolbar"><div class="legend"><span class="agent">Agent</span><span class="condition">Check / condition</span><span class="action">Action</span><span class="view">View / context</span></div><div class="actions"><button id="reload">Use saved version</button><button id="add">+ Block</button><button id="save" ${!dirty ? "disabled" : ""}>Save draft</button><button class="primary" id="apply">Apply workflow</button></div></div>
    <div class="workspace"><div class="graph"><svg id="graph" role="img" aria-label="Editable workflow. Select a block to edit its settings."></svg></div><aside class="inspector" id="inspector"></aside></div>
    <div class="notice" id="notice" role="status"></div>
    <section class="ask"><label for="question">Edit with this agent</label><div class="ask-row"><textarea id="question" placeholder="Add a test before preview, and retry if it fails…"></textarea><button class="primary" id="ask">Send</button>${hostType === "standalone" && binding?.persistent ? `<button id="pause">${binding?.paused ? "Resume" : "Pause"} persistence</button>` : ""}</div><small>Your message goes to the same native chat. Changes appear here live.</small></section>`;
  document.getElementById("open").onclick = () => send("openChat");
  document.getElementById("question").value = questionDraft;
  document.getElementById("question").oninput = (event) => {
    questionDraft = event.target.value;
    persist();
  };
  if (document.getElementById("split"))
    document.getElementById("split").onclick = () => send("splitChat");
  if (document.getElementById("pause"))
    document.getElementById("pause").onclick = () =>
      send("pause", { paused: !binding?.paused });
  document.getElementById("ask").onclick = () => {
    const text = document.getElementById("question").value.trim();
    if (text && !busy) {
      busy = true;
      send("ask", {
        purpose: "edit",
        text:
          "Edit the attached Surfboard as requested. Read read_surfboard, preserve unrelated changes, then propose_surfboard and apply_surfboard with the current versions. Applying the graph does not start its actions. Request: " +
          text,
      });
      notice("Sending to this agent…");
    }
  };
  document.getElementById("save").onclick = () => save(false);
  document.getElementById("apply").onclick = () => save(true);
  document.getElementById("add").onclick = addBlock;
  document.getElementById("reload").onclick = () => send("reload");
  draw();
  inspect();
  notice(
    dirty
      ? "Unsaved edits retained."
      : state.draft
        ? "Draft saved · apply to activate these changes."
        : `Applied workflow · version ${state.version}. Select a block to edit; drag to rearrange.`,
  );
}
function save(apply) {
  if (busy) return;
  busy = true;
  applyAfterSave = apply;
  if (dirty)
    send("save", {
      board,
      expected_version: state.version,
      expected_draft_version: draftVersion(state),
    });
  else if (apply && state.draft)
    send("apply", {
      expected_version: state.version,
      expected_draft_version: draftVersion(state),
    });
  else {
    busy = false;
    notice("This workflow is already applied.");
  }
}
function draw() {
  const svg = document.getElementById("graph");
  const nodes = board.nodes,
    maxX = Math.max(650, ...nodes.map((n) => n.x + 240)),
    maxY = Math.max(400, ...nodes.map((n) => n.y + 100));
  svg.setAttribute("viewBox", `0 0 ${maxX + 40} ${maxY + 30}`);
  svg.innerHTML =
    `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="currentColor"/></marker></defs>` +
    board.edges
      .map((e) => {
        const a = nodes.find((n) => n.id === e.source),
          b = nodes.find((n) => n.id === e.target);
        if (!a || !b) return "";
        const down = Math.abs(b.y - a.y) > Math.abs(b.x - a.x),
          forward = down ? b.y >= a.y : b.x >= a.x;
        const ax = a.x + (down ? 100 : forward ? 200 : 0),
          ay = a.y + (down ? (forward ? 66 : 0) : 33);
        const bx = b.x + (down ? 100 : forward ? 0 : 200),
          by = b.y + (down ? (forward ? 0 : 66) : 33);
        return `<path class="edge" marker-end="url(#arrow)" d="M${ax} ${ay}L${bx} ${by}"/><text class="edge-label" text-anchor="middle" x="${(ax + bx) / 2}" y="${(ay + by) / 2 - 7}">${esc(e.relation)}</text>`;
      })
      .join("") +
    nodes
      .map(
        (n) =>
          `<g class="node ${group(n.kind)} ${selected === n.id ? "selected" : ""}" data-id="${esc(n.id)}" transform="translate(${n.x},${n.y})" tabindex="0" role="button" aria-label="Edit ${esc(n.label)}"><rect width="200" height="66" rx="8"/><rect class="stripe" x="0" y="10" width="4" height="46" rx="2"/><text class="kind" x="16" y="23">${esc(n.kind)}</text><text x="16" y="46" font-size="15">${esc(n.label.length > 23 ? n.label.slice(0, 22) + "…" : n.label)}</text></g>`,
      )
      .join("");
  svg.querySelectorAll(".node").forEach((element) => {
    const choose = () => {
      selected = element.dataset.id;
      persist();
      inspect();
      svg
        .querySelectorAll(".node")
        .forEach((n) =>
          n.classList.toggle("selected", n.dataset.id === selected),
        );
    };
    element.onkeydown = (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        choose();
      }
    };
    element.onpointerdown = (event) => {
      choose();
      const node = nodes.find((n) => n.id === selected),
        start = point(event),
        old = { x: node.x, y: node.y };
      let moved = false;
      svg.setPointerCapture(event.pointerId);
      svg.onpointermove = (e) => {
        const p = point(e);
        if (Math.abs(p.x - start.x) + Math.abs(p.y - start.y) < 4 && !moved)
          return;
        moved = true;
        node.x = Math.max(10, Math.round(old.x + p.x - start.x));
        node.y = Math.max(10, Math.round(old.y + p.y - start.y));
        draw();
      };
      svg.onpointerup = () => {
        svg.onpointermove = null;
        svg.onpointerup = null;
        if (moved) changed();
      };
    };
  });
  function point(event) {
    const p = svg.createSVGPoint();
    p.x = event.clientX;
    p.y = event.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }
}
function inspect() {
  const el = document.getElementById("inspector"),
    node = board.nodes.find((n) => n.id === selected);
  if (!node) {
    el.innerHTML =
      '<h2>Your workflow</h2><p>Select a colored block to edit its instructions or settings.</p><p class="muted">Arrows show ownership, data flow and required checks.</p><p class="muted">You can also describe a change to your agent below.</p>';
    return;
  }
  const spec = state.catalog.find((c) => c.kind === node.kind);
  el.innerHTML = `<h2>${esc(spec?.label || node.kind)}</h2><small>${esc(spec?.description)}</small><label for="label">Name</label><input id="label" value="${esc(node.label)}"><div id="fields"></div><h2 class="connections">Connections</h2><div id="edges"></div><label for="relation">Relationship</label><select id="relation">${(spec?.relations || []).map((r) => `<option value="${esc(r.relation)}">${esc(r.label)}</option>`).join("")}</select><label for="target">Connect to</label><select id="target"></select><button id="connect">Add connection</button><br><button id="remove">Remove block</button>`;
  el.querySelector("#label").oninput = (e) => {
    node.label = e.target.value;
    changed();
    draw();
  };
  const fields = el.querySelector("#fields");
  for (const [name, field] of Object.entries(spec?.config_fields || {})) {
    const wrapper = document.createElement("div"),
      label = document.createElement("label"),
      input = document.createElement(
        field.enum || field.type === "boolean"
          ? "select"
          : field.type === "array" ||
              ["instructions", "description"].includes(name)
            ? "textarea"
            : "input",
      );
    label.textContent = name.replaceAll("_", " ");
    label.htmlFor = "field-" + name;
    input.id = label.htmlFor;
    if (input.tagName === "SELECT")
      for (const value of field.enum || ["true", "false"]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        input.append(option);
      }
    const value = node.config[name] ?? field.default ?? "";
    input.value =
      field.type === "array"
        ? Array.isArray(value)
          ? value.join("\n")
          : ""
        : value;
    if (field.type === "integer" || field.type === "number") {
      input.type = "number";
      if (field.minimum !== undefined) input.min = field.minimum;
      if (field.maximum !== undefined) input.max = field.maximum;
    }
    input.onchange = () => {
      let value = input.value;
      if (field.type === "array") value = value.split("\n").filter(Boolean);
      else if (field.type === "boolean") value = value === "true";
      else if (["integer", "number"].includes(field.type)) {
        if (!input.checkValidity()) {
          input.reportValidity();
          return;
        }
        value = Number(value);
      }
      node.config[name] = value;
      changed();
    };
    wrapper.append(label, input);
    if (field.type === "array") {
      const hint = document.createElement("small");
      hint.textContent =
        name === "argv"
          ? "One command argument per line."
          : "One value per line.";
      wrapper.append(hint);
    }
    fields.append(wrapper);
  }
  el.querySelector("#edges").innerHTML = board.edges
    .filter((e) => e.source === node.id)
    .map(
      (e) =>
        `<div class="edge-row"><span>${esc(e.relation)} → ${esc(board.nodes.find((n) => n.id === e.target)?.label)}</span><button data-edge="${esc(e.id)}" aria-label="Remove connection">×</button></div>`,
    )
    .join("");
  el.querySelectorAll("[data-edge]").forEach(
    (button) =>
      (button.onclick = () => {
        board.edges = board.edges.filter((e) => e.id !== button.dataset.edge);
        changed();
        draw();
        inspect();
      }),
  );
  const targets = () => {
    const relation = spec?.relations.find(
      (r) => r.relation === el.querySelector("#relation").value,
    );
    el.querySelector("#target").innerHTML = board.nodes
      .filter((n) => n.id !== node.id && relation?.targets.includes(n.kind))
      .map((n) => `<option value="${esc(n.id)}">${esc(n.label)}</option>`)
      .join("");
  };
  el.querySelector("#relation").onchange = targets;
  targets();
  el.querySelector("#connect").onclick = () => {
    const target = el.querySelector("#target").value,
      relation = el.querySelector("#relation").value;
    if (!target || !relation) return;
    if (
      board.edges.some(
        (e) =>
          e.source === node.id &&
          e.target === target &&
          e.relation === relation,
      )
    )
      return;
    board.edges.push({
      id: "edge-" + crypto.randomUUID().slice(0, 8),
      source: node.id,
      target,
      relation,
      description: "",
    });
    changed();
    draw();
    inspect();
  };
  el.querySelector("#remove").onclick = () => {
    board.nodes = board.nodes.filter((n) => n !== node);
    board.edges = board.edges.filter(
      (e) => e.source !== node.id && e.target !== node.id,
    );
    selected = undefined;
    changed();
    draw();
    inspect();
  };
}
function addBlock() {
  const el = document.getElementById("inspector");
  el.innerHTML =
    '<h2>Add a block</h2><p class="muted">Choose its role in your workflow.</p>' +
    state.catalog
      .map(
        (c) => `<button data-kind="${esc(c.kind)}">${esc(c.label)}</button> `,
      )
      .join("");
  el.querySelectorAll("[data-kind]").forEach(
    (button) =>
      (button.onclick = () => {
        const kind = button.dataset.kind,
          spec = state.catalog.find((c) => c.kind === kind);
        selected = kind + "-" + crypto.randomUUID().slice(0, 8);
        board.nodes.push({
          id: selected,
          kind,
          label: spec.label,
          x: 60 + (board.nodes.length % 3) * 250,
          y: Math.max(20, ...board.nodes.map((n) => n.y)) + 120,
          config: Object.fromEntries(
            Object.entries(spec.config_fields)
              .filter(([, f]) => f.default !== undefined)
              .map(([k, f]) => [k, clone(f.default)]),
          ),
        });
        changed();
        draw();
        inspect();
      }),
  );
}
function renderQueue() {
  const runs = (state.runs || [])
    .filter(
      (r) =>
        !["completed", "cancelled", "failed", "succeeded", "canceled"].includes(
          r.status,
        ),
    )
    .sort((a, b) => (a.queue_order || 0) - (b.queue_order || 0));
  app.innerHTML = `<header class="top"><div><h1>GPU queue</h1><span class="muted">Shared with SuperSurfer on this host</span></div><button id="queue-toggle">${state.queue?.paused ? "Resume" : "Pause"} queue</button></header><section class="queue">${runs.length ? runs.map((r, i) => `<article class="job"><span class="badge">${esc(r.status)}</span><div class="details"><strong>${esc(r.name || r.id)}</strong><small>${esc(r.host_id || "Awaiting host")} · ${esc(r.gpu_count ?? r.config?.gpu_count ?? "?")} GPU(s)</small></div><button data-up="${esc(r.id)}" ${r.status !== "queued" || !runs.slice(0, i).some((x) => x.status === "queued") ? "disabled" : ""}>Move up</button><button data-cancel="${esc(r.id)}">Cancel</button></article>`).join("") : '<div class="empty"><h2>No active jobs</h2><p class="muted">Queued and running jobs appear here.</p></div>'}</section><div id="notice" class="notice" role="status"></div>`;
  document.getElementById("queue-toggle").onclick = () =>
    send("queueAction", {
      action: state.queue?.paused ? "queue.resume" : "queue.pause",
      params: {},
    });
  app.querySelectorAll("[data-cancel]").forEach(
    (b) =>
      (b.onclick = () =>
        send("queueAction", {
          action: "run.cancel",
          params: { run_id: b.dataset.cancel },
        })),
  );
  app.querySelectorAll("[data-up]").forEach(
    (b) =>
      (b.onclick = () =>
        send("queueAction", {
          action: "run.move",
          params: {
            run_id: b.dataset.up,
            before_id: runs
              .slice(
                0,
                runs.findIndex((r) => r.id === b.dataset.up),
              )
              .filter((r) => r.status === "queued")
              .at(-1)?.id,
          },
        })),
  );
}
window.addEventListener("message", (event) => {
  const message = event.data;
  if (message.type === "reset") {
    state = undefined;
    board = undefined;
    dirty = false;
    saved = null;
    api.setState(undefined);
    return;
  }
  if (message.type === "restore") {
    if (!board && message.saved) {
      saved = message.saved;
      questionDraft = saved.questionDraft || questionDraft;
    }
    return;
  }
  if (message.type === "error") {
    busy = false;
    applyAfterSave = false;
    notice(message.message, true);
    return;
  }
  if (message.type === "result") {
    busy = false;
    if (message.op === "ask") {
      questionDraft = "";
      document.getElementById("question").value = "";
      persist();
      notice("Sent. Follow the conversation in native chat.");
    }
    if (["save", "apply", "discard"].includes(message.op)) {
      state = { ...state, ...message.result };
      dirty = false;
      board = clone(state.draft?.board || state.board);
      persist();
      if (message.op === "save" && applyAfterSave) {
        applyAfterSave = false;
        busy = true;
        send("apply", {
          expected_version: state.version,
          expected_draft_version: draftVersion(state),
        });
      }
      render();
    }
    return;
  }
  if (message.type !== "state") return;
  binding = message.binding;
  hostType = message.hostType;
  if (document.body.dataset.mode === "queue") {
    state = message.data;
    render();
    return;
  }
  if (
    dirty &&
    state &&
    (state.version !== message.data.version ||
      draftVersion(state) !== draftVersion(message.data))
  ) {
    notice(
      "The agent changed this workflow. Your local edits are retained; save will report a conflict. Use saved version to load the latest graph and discard your local edits.",
      true,
    );
    return;
  }
  const before = state;
  state = message.data;
  if (!board && saved?.dirty) {
    board = saved.board;
    dirty = true;
    selected = saved.selected;
    state = {
      ...state,
      version: saved.version,
      draft: { ...state.draft, draft_version: saved.draftVersion },
    };
    saved = null;
  } else if (!dirty) board = clone(state.draft?.board || state.board);
  if (
    !before ||
    before.version !== state.version ||
    draftVersion(before) !== draftVersion(state)
  )
    render();
  else {
    const badge = document.getElementById("status");
    if (badge)
      badge.textContent =
        binding?.connected === false
          ? "Disconnected"
          : binding?.complete
            ? "Finished"
            : binding?.paused
              ? "Persistence paused"
              : binding?.status & 8
                ? "Agent working"
                : "Ready";
    const pause = document.getElementById("pause");
    if (pause)
      pause.textContent =
        (binding?.paused ? "Resume" : "Pause") + " persistence";
    if (binding?.note && !dirty) notice(binding.note);
  }
});
send("ready");
