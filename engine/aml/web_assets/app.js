"use strict";

const $ = (id) => document.getElementById(id);
const localTime = new Intl.DateTimeFormat(undefined, {month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit"});
const numeric = new Intl.NumberFormat(undefined, {maximumFractionDigits: 1});
const activeStates = new Set(["starting", "running", "unreachable", "orphaned", "cancelling"]);
let snapshot = null;
let busy = false;
let refreshing = false;
let draggedJobId = null;
let focusedRun = null;
function focusLinkedRun() {
  const id = window.location.hash?.slice(1);
  if (!/^(activity-)?run_[a-f0-9]+$/.test(id || "") || focusedRun === id) return;
  const target = $(id);
  if (!target) return;
  focusedRun = id;
  target.tabIndex = -1;
  target.scrollIntoView({block: "start"}); target.focus({preventScroll: true});
}
window.addEventListener("hashchange", () => { focusedRun = null; focusLinkedRun(); });

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function replace(id, nodes) { $(id).replaceChildren(...nodes); }
function clip(text, max = 240) { text = String(text || ""); return text.length > max ? text.slice(0, max).trim() + "…" : text; }
function time(value) {
  if (!value) return "No observation";
  const date = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isNaN(date.getTime()) ? "Unknown time" : localTime.format(date);
}
function badge(text, kind = "neutral") { return el("span", text, "badge " + kind); }
function button(text, action, className = "quiet") {
  const node = el("button", text, className);
  node.type = "button";
  node.disabled = busy;
  node.addEventListener("click", action);
  return node;
}
function notify(message, failed = false) {
  $("notice").hidden = !message;
  $("notice").textContent = message;
  $("notice").className = failed ? "notice error" : "notice";
}
async function request(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 18000);
  try {
    const options = {signal: controller.signal, cache: "no-store", credentials: "same-origin"};
    if (body !== undefined) Object.assign(options, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    const response = await fetch(window.location.origin + path, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed");
    return result;
  } finally { clearTimeout(timeout); }
}
async function mutate(action, body, message) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button, .priority-input").forEach(node => { node.disabled = true; });
  try {
    await request("/api/queue/" + action, body);
    notify(message);
  } catch (error) { notify(error.message + ". Refreshing current state.", true); }
  finally {
    busy = false;
    document.querySelectorAll("button, .priority-input").forEach(node => { node.disabled = false; });
    await refresh();
  }
}
function cancelJob(job) {
  if (window.confirm("Cancel “" + job.name + "”? Running work will be stopped; saved outputs remain."))
    mutate("cancel", {run: job.id}, "Cancellation requested for “" + job.name + "”.");
}
function jobLabel(job) { return job.config?.label || job.name; }
function jobStudy(job) {
  const name = String(job.config?.experiment || job.name || "").toLowerCase();
  if (name.startsWith("e13")) return "e13";
  if (name.startsWith("e12") || name.startsWith("sr-joint")) return "e12";
  return null;
}
const trainingCards = new Set(["run_1daa45c1af4b", "run_d71f800a2ecd", "run_575275f17844", "run_fe860a3d0d84", "run_095f3764b700", "run_e01200177c90"]);
function studyLink(job) {
  const study = jobStudy(job);
  if (!study || !/^run_[a-f0-9]+$/.test(job.id)) return null;
  const link = el("a", jobLabel(job));
  link.href = "/" + study + "#" + (trainingCards.has(job.id) ? job.id : "activity-" + job.id);
  return link;
}
function examples(value) {
  return value >= 1000000 ? new Intl.NumberFormat(undefined, {maximumFractionDigits: 3}).format(value / 1000000) + "M" : numeric.format(value);
}
function sampleBudget(job) {
  const budget = job.config?.budget;
  return typeof budget === "number" ? budget : typeof budget === "object" && budget ? budget.samples_per_stream || budget.samples : undefined;
}
function configLine(job) {
  const config = job.config || {};
  const budget = sampleBudget(job);
  return [config.phase, config.arm, budget ? examples(budget) + " examples / stream" : typeof config.budget === "string" ? config.budget : null].filter(Boolean).join(" · ");
}
function allocation(job) {
  const devices = job.gpus?.length ? job.gpus : (snapshot?.gpus || []).filter(gpu => gpu.run_id === job.id).map(gpu => gpu.gpu);
  const host = job.host_name || (snapshot?.gpus || []).find(gpu => gpu.run_id === job.id)?.host || "Host pending";
  if (devices.length) return host + " · GPUs " + devices.join(", ");
  if (job.allowed_host_names?.length > 1)
    return job.gpu_count + " GPUs · " + job.allowed_host_names.length + " allowed nodes";
  const pinned = job.config?.gpu_indices;
  return pinned?.length ? host + " · GPUs " + pinned.join(", ") + " planned" : host + " · " + (job.gpu_count || 0) + " GPU requested";
}
function placementDetails(job) {
  const candidates = job.candidate_hosts;
  if (!candidates?.length) return null;
  const details = el("details", null, "placement-details");
  details.append(el("summary", "Node checks · " + (job.placement_state || "checking")));
  const storage = job.config?.storage;
  if (storage?.min_free_gib !== undefined)
    details.append(el("p", "Needs " + numeric.format(storage.min_free_gib) + " GiB free scratch", "small"));
  for (const candidate of candidates) {
    const row = el("div", null, "candidate-row");
    row.append(el("strong", candidate.host_name), badge(candidate.state, candidate.state === "ready" ? "good" : "neutral"));
    if (candidate.wait_reason) row.append(el("p", clip(candidate.wait_reason, 300), "small muted"));
    if (candidate.staging) {
      const filename = candidate.staging.destination?.split("/").pop() || "input";
      row.append(el("p", "Copying " + filename + " · started " + time(candidate.staging.started_at), "small"));
    }
    details.append(row);
  }
  return details;
}
function reviewLinks(job) {
  const node = el("p", null, "small review-links");
  const url = job.config?.pr_url;
  if (!/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/pull\/[1-9][0-9]*$/.test(url || "")) {
    node.append(badge("PR required", "warning"));
    return node;
  }
  const pr = el("a", "PR #" + url.split("/").pop());
  pr.href = url; pr.target = "_blank"; pr.rel = "noopener noreferrer";
  node.append(pr);
  if (/^[a-f0-9]{40}$/.test(job.revision || "")) {
    const commit = el("a", job.revision.slice(0, 7));
    commit.href = url.replace(/\/pull\/[0-9]+$/, "/commit/" + job.revision);
    commit.target = "_blank"; commit.rel = "noopener noreferrer";
    node.append(el("span", " · "), commit);
  }
  return node;
}
function moveJob(job, delta) {
  const order = snapshot.queue.jobs.map(row => row.id);
  const index = order.indexOf(job.id);
  if (index + delta < 0 || index + delta >= order.length) return;
  [order[index], order[index + delta]] = [order[index + delta], order[index]];
  mutate("reorder", {order}, "Queue order updated.");
}
function renderSummary(data) {
  const running = data.runs.filter(job => activeStates.has(job.status));
  const ready = data.queue.jobs.filter(job => job.ready);
  const available = data.gpus.filter(gpu => gpu.status === "available" && !gpu.stale && gpu.allowed !== false && gpu.busy === false);
  const limit = data.projects.length === 1 ? data.projects[0].run_limit : null;
  const nodes = [[running.length + (limit ? " / " + limit : ""), "active jobs"], [ready.length, "ready / " + data.queue.jobs.length + " queued"],
    [available.length, "observed available GPUs"], [data.queue.paused ? "Paused" : "Open", "dispatch queue"]].map(([value, label]) => {
      const node = el("div", null, "summary-item"); node.append(el("strong", value), el("span", label)); return node;
    });
  replace("summary-strip", nodes);
}
function renderActivity(data) {
  const running = data.runs.filter(job => activeStates.has(job.status));
  const cards = running.map(job => {
    const card = el("article", null, "activity-card");
    const heading = el("div", null, "card-heading"); heading.append(badge(job.status, job.status === "running" ? "good" : "warning"), el("span", time(job.updated), "small muted"));
    const title = el("h3"); title.append(studyLink(job) || el("span", jobLabel(job)));
    card.append(heading, title, el("p", "Priority " + job.priority + " · " + allocation(job), "allocation"));
    card.append(reviewLinks(job));
    if (configLine(job)) card.append(el("p", configLine(job), "small muted"));
    const progress = job.config?.progress;
    if (typeof progress === "string") card.append(el("p", progress, "progress-text"));
    else if (progress && typeof progress === "object") {
      const samples = progress.samples_per_stream ?? progress.completed;
      const total = sampleBudget(job) || progress.total;
      if (typeof samples === "number") {
        card.append(el("p", examples(samples) + (total ? " / " + examples(total) : "") + " " + (progress.samples_per_stream !== undefined ? "examples / stream" : progress.unit || "units"), "progress-text"));
        if (total) { const meter = el("progress"); meter.max = total; meter.value = samples; meter.setAttribute("aria-label", "Training examples completed"); card.append(meter); }
      }
      const detail = [progress.step !== undefined ? "Step " + numeric.format(progress.step) : null, progress.phase, progress.utc || progress.observed_at ? "Observed " + time(progress.utc || progress.observed_at) : null].filter(Boolean).join(" · ");
      if (detail) card.append(el("p", detail, "small freshness"));
    }
    if (job.wait_reason || job.error) card.append(el("p", clip(job.wait_reason || job.error), "warning-text"));
    card.append(button("Cancel job", () => cancelJob(job), "quiet danger"));
    return card;
  });
  if (!cards.length) {
    const card = el("article", null, "activity-card idle-card");
    const next = data.queue.jobs.find(job => job.ready) || data.queue.jobs[0];
    card.append(badge("No running jobs"), el("h3", next ? "Next: " + jobLabel(next) : "E12 is in preparation"));
    card.append(el("p", next ? next.wait_reason || (data.queue.paused ? "Queue dispatch is paused." : "Job is held until marked ready.") : "Prepare the exact checkpoint, executable command and matched controls before marking a job ready.", "muted"));
    cards.push(card);
  }
  const blocked = data.tasks.filter(task => task.status === "blocked");
  if (blocked.length) {
    const card = el("article", null, "activity-card blocker-card");
    card.append(badge("Next blockers", "warning"));
    blocked.slice(0, 3).forEach(task => { card.append(el("h3", task.name), el("p", clip(task.findings) || "Preparation dependency requires attention.", "muted")); });
    cards.push(card);
  }
  const agents = data.agents.filter(agent => agent.status === "busy");
  if (agents.length) {
    const card = el("article", null, "activity-card");
    card.append(badge("Agent activity", "good"), el("h3", agents.length + " agent" + (agents.length === 1 ? "" : "s") + " working"), el("p", agents.map(agent => agent.name + (agent.task_name ? ": " + agent.task_name : "")).join("; "), "muted"));
    cards.push(card);
  }
  replace("current-activity", cards);
}
function renderQueue(data) {
  $("queue-count").textContent = data.queue.jobs.length;
  $("queue-toggle").textContent = data.queue.paused ? "Resume queue" : "Pause queue";
  $("queue-toggle").disabled = busy;
  $("queue-empty").hidden = data.queue.jobs.length > 0;
  const rows = data.queue.jobs.map((job, index) => {
    const row = el("tr");
    row.draggable = !busy;
    row.dataset.run = job.id;
    row.addEventListener("dragstart", event => {
      if (busy || event.target.closest("input") || event.target.closest("button:not(.drag-handle)")) { event.preventDefault(); return; }
      draggedJobId = job.id;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", job.id);
      row.classList.add("dragging");
    });
    row.addEventListener("dragover", event => {
      if (!draggedJobId || draggedJobId === job.id || busy) return;
      event.preventDefault(); event.dataTransfer.dropEffect = "move";
      row.classList.add("drop-target");
    });
    row.addEventListener("dragleave", event => { if (!row.contains(event.relatedTarget)) row.classList.remove("drop-target"); });
    row.addEventListener("drop", event => {
      event.preventDefault(); row.classList.remove("drop-target");
      if (!draggedJobId || draggedJobId === job.id || busy) return;
      const order = snapshot.queue.jobs.map(item => item.id);
      order.splice(order.indexOf(draggedJobId), 1);
      const bounds = row.getBoundingClientRect();
      order.splice(order.indexOf(job.id) + (event.clientY > bounds.top + bounds.height / 2 ? 1 : 0), 0, draggedJobId);
      draggedJobId = null;
      mutate("reorder", {order}, "Queue order updated.");
    });
    row.addEventListener("dragend", () => { draggedJobId = null; document.querySelectorAll(".dragging, .drop-target").forEach(node => node.classList.remove("dragging", "drop-target")); });
    const order = el("td");
    const handle = el("span", "⠿", "drag-handle"); handle.setAttribute("aria-hidden", "true"); handle.title = "Drag to reorder"; order.append(handle);
    order.append(el("span", String(index + 1).padStart(2, "0"), "order-number"));
    const form = el("form", null, "priority-form");
    const input = el("input", null, "priority-input"); input.type = "number"; input.step = "1"; input.value = job.priority;
    input.setAttribute("aria-label", "Priority for " + jobLabel(job)); input.disabled = busy;
    const apply = el("button", "Set", "quiet"); apply.type = "submit"; apply.disabled = busy;
    form.append(input, apply);
    form.addEventListener("submit", event => {
      event.preventDefault(); const priority = Number(input.value);
      if (!input.value || !Number.isSafeInteger(priority)) { notify("Enter a whole-number priority.", true); return; }
      mutate("priority", {run: job.id, priority}, "Priority updated; queue sorted by priority.");
    });
    order.append(form);
    const title = el("td"); title.append(el("strong", jobLabel(job)), el("p", configLine(job) || "E12", "small muted"), reviewLinks(job));
    const state = el("td"); state.append(badge(job.ready ? "Ready" : "Held", job.ready ? "good" : "neutral"));
    state.append(el("p", job.wait_reason || (job.ready ? "Waiting for dispatch" : "Not marked ready"), "small wait-reason"));
    const compute = el("td"); compute.append(el("span", allocation(job), "small"));
    const placement = placementDetails(job);
    if (placement) compute.append(placement);
    const controls = el("td", null, "queue-actions");
    controls.append(button(job.ready ? "Hold" : "Mark ready", () => mutate(job.ready ? "hold" : "ready", {run: job.id}, job.ready ? "Job held." : "Job marked ready."), "secondary compact"));
    const arrows = el("div", null, "order-actions");
    const up = button("↑", () => moveJob(job, -1)); up.setAttribute("aria-label", "Move " + jobLabel(job) + " up"); up.disabled = busy || index === 0;
    const down = button("↓", () => moveJob(job, 1)); down.setAttribute("aria-label", "Move " + jobLabel(job) + " down"); down.disabled = busy || index === data.queue.jobs.length - 1;
    arrows.append(up, down, button("Cancel", () => cancelJob(job), "quiet danger")); controls.append(arrows);
    row.append(order, title, state, compute, controls); return row;
  });
  replace("queue-jobs", rows);
}
function gpuObservation(gpu) {
  if (gpu.run_id || gpu.status === "reserved") return {kind: "reserved", label: "Reserved"};
  if (gpu.allowed === false) return {kind: "excluded", label: "Outside allocation"};
  if (!gpu.stale && gpu.status === "available" && gpu.busy === false && gpu.connectivity === "online")
    return {kind: "available", label: "Available · fresh"};
  const age = gpu.age_seconds ?? (gpu.sampled ? Date.now() / 1000 - gpu.sampled : Infinity);
  const recent = Number.isFinite(age) && age >= 0 && age <= 300 && gpu.connectivity === "online" && !gpu.error;
  const measured = [gpu.used_mib, gpu.free_mib, gpu.utilization].every(Number.isFinite);
  if (recent && measured) {
    if (gpu.used_mib <= 512 && gpu.free_mib >= 1024 && gpu.utilization <= 5)
      return {kind: "potential", label: "Observed empty · needs fresh check"};
    return {kind: "occupied", label: "Observed occupied"};
  }
  return {kind: "unknown", label: "Unknown · reading missing or old"};
}
function renderGPUs(data) {
  const hosts = new Map((data.hosts || []).map(host => [host.name, []]));
  for (const gpu of data.gpus) {
    const host = gpu.host || "Unknown host";
    if (!hosts.has(host)) hosts.set(host, []);
    hosts.get(host).push(gpu);
  }
  const cards = [...hosts].map(([host, gpus]) => {
    const card = el("details", null, "gpu-host");
    const summary = el("summary", null, "gpu-host-summary");
    const name = el("span", null, "gpu-host-name");
    const empty = gpus.filter(gpu => ["potential", "available"].includes(gpuObservation(gpu).kind)).length;
    name.append(el("strong", host), el("small", (empty ? empty + " observed empty · " : "") + (gpus[0]?.model || "Model unknown")));
    const chips = el("span", null, "gpu-chips");
    for (const gpu of gpus) {
      const state = gpuObservation(gpu), chip = el("span", gpu.gpu, "gpu-chip " + state.kind);
      chip.title = "GPU " + gpu.gpu + " · " + state.label + (gpu.run ? " · " + gpu.run : "") + " · observed " + time(gpu.sampled);
      chip.setAttribute("aria-label", chip.title); chips.append(chip);
    }
    if (!gpus.length) {
      const observation = data.hosts?.find(row => row.name === host);
      const label = observation?.status === "offline" ? "Unreachable · inventory unknown" : "Awaiting GPU inventory";
      const chip = el("span", label, "gpu-chip unknown");
      chip.title = observation?.error || "Registered host. The next scheduled manager check will observe physical devices.";
      chips.append(chip);
    }
    summary.append(name, chips); card.append(summary);
    const rows = gpus.map(gpu => {
      const row = el("div", null, "gpu-row");
      const heading = el("div", null, "gpu-heading");
      const state = gpuObservation(gpu);
      heading.append(el("strong", "GPU " + gpu.gpu), badge(state.label, state.kind === "available" ? "good" : state.kind === "potential" ? "warning" : "neutral"));
      row.append(heading);
      if (gpu.total_mib && gpu.used_mib !== null && gpu.used_mib !== undefined) {
        row.append(el("p", numeric.format(gpu.used_mib / 1024) + " / " + numeric.format(gpu.total_mib / 1024) + " GiB used · " + (gpu.utilization === null || gpu.utilization === undefined ? "utilization unknown" : gpu.utilization + "% utilization"), "small"));
      } else row.append(el("p", "Memory and utilization unknown", "small muted"));
      if (gpu.run) row.append(el("p", gpu.run, "small allocation"));
      if (gpu.allowed === false) row.append(el("p", "Outside managed allocation", "small muted"));
      row.append(el("p", "Observed " + time(gpu.sampled), "small freshness"));
      if (gpu.error) row.append(el("p", clip(gpu.error, 100), "small warning-text"));
      return row;
    });
    if (!rows.length) rows.push(el("p", "GPU count and availability are unknown until a scheduled observation succeeds.", "small muted"));
    const grid = el("div", null, "gpu-grid"); grid.append(...rows); card.append(grid); return card;
  });
  if (!cards.length) cards.push(el("p", "No GPU observations yet. Availability is unknown.", "empty"));
  replace("gpu-hosts", cards);
  const counts = {};
  for (const gpu of data.gpus) { const kind = gpuObservation(gpu).kind; counts[kind] = (counts[kind] || 0) + 1; }
  $("gpu-summary").textContent = data.gpus.length ? (counts.available || 0) + " fresh available · " + (counts.potential || 0) + " observed empty · " + (counts.reserved || 0) + " reserved" : "Unknown";
  const project = data.projects.length === 1 ? data.projects[0] : null;
  const active = data.runs.filter(job => activeStates.has(job.status));
  const ids = new Set(active.map(job => job.id));
  const reserved = data.gpus.filter(gpu => ids.has(gpu.run_id)).length;
  $("gpu-policy").textContent = (project ? "Project cap: " + reserved + " / " + project.gpu_limit + " GPUs reserved; " + active.length + " / " + project.run_limit + " active runs. " : "") + hosts.size + " registered hosts. Physical inventory and project caps are separate.";
  replace("gpu-legend", [["available", "Fresh available"], ["potential", "Observed empty; recheck needed"], ["reserved", "Reserved"], ["occupied", "Observed occupied"], ["unknown", "Unknown / old reading"], ["excluded", "Outside allocation"]].map(([kind, label]) => {
    const item = el("span", null, "gpu-legend-item"); item.append(el("i", null, "gpu-chip " + kind), el("span", label + " (" + (counts[kind] || 0) + ")")); return item;
  }));
}
function renderStudyActivity(data) {
  for (const study of ["e12", "e13"]) {
    const jobs = data.runs.filter(job => jobStudy(job) === study).sort((a, b) => Number(activeStates.has(b.status)) - Number(activeStates.has(a.status)) || b.updated - a.updated).slice(0, 12);
    replace(study + "-activity", jobs.map(job => {
      const row = el("article", null, "recent-row study-activity-row"); row.id = "activity-" + job.id;
      row.append(studyLink(job) || el("strong", jobLabel(job)), badge(job.status, job.status === "running" ? "good" : "neutral"), el("span", allocation(job), "small muted"), reviewLinks(job)); return row;
    }));
  }
  focusLinkedRun();
}
function renderTasks(data) {
  const tasks = data.tasks.filter(task => !["done", "failed"].includes(task.status));
  replace("planned-tasks", tasks.length ? tasks.map(task => {
    const card = el("article", null, "task-card");
    card.append(badge(task.status === "pending" ? "Planned" : task.status, task.status === "blocked" ? "warning" : "neutral"), el("h3", task.name), el("p", clip(task.findings, 380) || "Prepared task; awaiting its next recorded step.", "muted"));
    if (task.dependencies?.length) {
      const deps = task.dependencies.map(id => data.tasks.find(row => row.id === id)?.name || "prerequisite");
      card.append(el("p", "Depends on: " + deps.join(", "), "small"));
    }
    return card;
  }) : [el("p", "No preparation tasks recorded.", "empty")]);
  const recent = data.runs.filter(job => !activeStates.has(job.status) && job.status !== "queued").sort((a, b) => b.updated - a.updated).slice(0, 8);
  $("recent-count").textContent = "(" + recent.length + ")";
  replace("recent-jobs", recent.length ? recent.map(job => {
    const row = el("div", null, "recent-row"); row.append(el("strong", jobLabel(job)), badge(job.status), el("span", time(job.updated), "small muted")); return row;
  }) : [el("p", "No completed or canceled jobs in this workspace.", "empty")]);
}
function svgNode(tag, attributes, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes || {})) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function scorePolicy(point) {
  const arm = point.arm === "compact" ? "Compact" : point.arm === "full" ? "Full" : point.arm === "direct" ? "Direct" : point.arm || "Policy";
  const variant = point.variant || "Variant unknown";
  return variant.includes("joint") ? "Joint " + arm.toLowerCase() : variant.includes("frozen") ? "Frozen " + arm.toLowerCase() : arm;
}
function renderSR40(series, study) {
  series = series || {points: [], available: false};
  const points = series.points || [];
  const completed = points.filter(point => point.plot_ready);
  const groups = new Map();
  completed.forEach(point => {
    const key = [point.arm, point.variant, point.cohort_sha256].join("|");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(point);
  });
  $("sr40-updated").textContent = series.updated_at ? "Series checked " + time(series.updated_at) : "No series observation";
  const colors = ["#28624b", "#496e94", "#946325", "#8d6479"];
  const legend = [];
  if (!completed.length) {
    replace("sr40-chart", [el("p", series.error || (series.available ? "No complete fixed-40 score yet. Pending and failed evaluations are listed below." : "No series artifact yet. Checkpoint evaluations will appear here."), "empty")]);
  } else {
    const width = 900, height = 275, left = 58, right = 20, top = 18, bottom = 47;
    const maximum = Math.max(study.budgets.final.updates, ...completed.map(point => point.next_update));
    const x = value => left + value / maximum * (width - left - right);
    const y = value => height - bottom - value * (height - top - bottom);
    const svg = svgNode("svg", {viewBox: "0 0 " + width + " " + height, role: "img", "aria-labelledby": "sr40-title sr40-desc"});
    svg.append(svgNode("title", {id: "sr40-title"}, "Fixed-40 robot success by checkpoint training update"),
      svgNode("desc", {id: "sr40-desc"}, "Only validated complete forty-scene evaluations are plotted. Policy variants and cohorts use separate curves. Pending and failed evaluations appear in the table."));
    for (let i = 0; i <= 4; i++) {
      const rate = i / 4;
      svg.append(svgNode("line", {x1: left, x2: width - right, y1: y(rate), y2: y(rate), class: "sr40-grid"}),
        svgNode("text", {x: left - 10, y: y(rate) + 4, "text-anchor": "end"}, (rate * 100) + "%"));
      const update = Math.round(maximum * rate);
      svg.append(svgNode("text", {x: x(update), y: height - bottom + 21, "text-anchor": i === 4 ? "end" : "middle"}, numeric.format(update)));
    }
    svg.append(svgNode("text", {x: width / 2, y: height - 3, "text-anchor": "middle"}, "Total training update · inherited progress included"));
    let index = 0;
    for (const group of groups.values()) {
      group.sort((a, b) => a.next_update - b.next_update);
      const color = colors[index++ % colors.length];
      const line = svgNode("polyline", {points: group.map(point => x(point.next_update) + "," + y(point.success_rate)).join(" "), fill: "none", stroke: color, "stroke-width": 2});
      svg.append(line);
      for (const point of group) {
        const dot = svgNode("circle", {cx: x(point.next_update), cy: y(point.success_rate), r: 5, fill: color, class: "sr40-point", "data-checkpoint": point.checkpoint_sha256, tabindex: 0});
        dot.append(svgNode("title", {}, scorePolicy(point) + ": " + point.successes + "/40 (" + numeric.format(point.success_rate * 100) + "%) · update " + numeric.format(point.next_update) + " · checkpoint " + point.checkpoint_sha256 + " · " + time(point.observed_at)));
        svg.append(dot);
      }
      const item = el("span", null, "sr40-legend-item");
      const symbol = svgNode("svg", {width: 13, height: 13, "aria-hidden": "true"}); symbol.append(svgNode("circle", {cx: 6, cy: 6, r: 4, fill: color}));
      item.append(symbol, el("span", scorePolicy(group[0]) + " · " + group[0].variant)); legend.push(item);
    }
    replace("sr40-chart", [svg]);
  }
  replace("sr40-legend", legend);
  const recent = [...points].sort((a, b) => new Date(b.observed_at || 0) - new Date(a.observed_at || 0)).slice(0, 8);
  replace("sr40-points", recent.map(point => {
    const row = el("tr");
    const policy = el("td"); policy.append(el("strong", scorePolicy(point)), el("p", point.variant || "Variant unknown", "small muted"), el("p", point.checkpoint_sha256 ? "Checkpoint " + point.checkpoint_sha256.slice(0, 12) : "Checkpoint pending", "small muted"));
    const update = el("td", point.next_update === null ? "Pending" : numeric.format(point.next_update));
    const score = el("td", point.plot_ready ? point.successes + "/40 · " + numeric.format(point.success_rate * 100) + "%" : "—");
    const state = el("td"); state.append(badge(point.status || "pending", point.plot_ready ? "good" : ["failed", "invalid"].includes(point.status) ? "warning" : "neutral"));
    if (!point.plot_ready && typeof point.scored_trials === "number") state.append(el("p", point.scored_trials + "/40 scenes reported", "small muted"));
    if (point.run_status && !point.plot_ready) state.append(el("p", point.run_status, "small muted"));
    if (point.error) state.append(el("p", clip(point.error, 220), "small warning-text"));
    row.append(policy, update, score, state, el("td", time(point.observed_at), "small muted")); return row;
  }));
  if (points.length > 8) $("sr40-updated").textContent += " · latest 8 of " + points.length + " evaluations listed";
}
function renderStudy(study, evidence) {
  $("objective").textContent = "E12 retains384 current visual tokens. E13 learns16 current and256 future tokens. Each study has its own recorded curves and expandable Context.";
  replace("study-overview", study.overview.map(text => el("p", text)));
  const offline = study.archive.offline;
  const card = (value, title, detail) => {
    const node = el("article", null, "result-card"); node.append(el("p", title, "small muted"), el("strong", value), el("p", detail, "small")); return node;
  };
  replace("archive-results", [
    card(offline.compact_eef_rmse_mm.toFixed(3) + " mm", "Frozen compact offline EEF error", "Own direct: " + offline.direct_eef_rmse_mm.toFixed(3) + " mm · lower is better"),
    card("−0.621 to +2.888 mm", "Paired 95% interval, direct − compact", "80 episodes / 320 windows; includes zero"),
    card("28 / 40", "Predeclared balanced scene subset", "70% provisional; complete 400-scene and own-direct comparison pending"),
    card(offline.oracle_eef_rmse_mm.toFixed(4) + " mm", "Oracle future diagnostic", "Privileged recorded futures; unavailable during deployment")
  ]);
  $("archive-limits").textContent = study.archive.limitations + " Reviewed " + time(study.archive.observed_at) + ".";
  const table = el("table", null, "budget-table");
  const head = el("thead"); const header = el("tr"); ["", "Earlier frozen archive", "Original reference protocol"].forEach(text => header.append(el("th", text))); head.append(header); table.append(head);
  const body = el("tbody");
  const quick = study.budgets.quick, final = study.budgets.final;
  [["Examples per stream", "4.096M", "16.384M"], ["Optimizer updates", numeric.format(quick.updates), numeric.format(final.updates)],
    ["Checkpoint", quick.checkpoint, final.checkpoint], ["Required controls", quick.required_arms.join(" + "), final.required_arms.join(" + ")],
    ["Success cohort", "400 fixed scenes per arm", "400 fixed scenes per arm"],
    ["Compact inherited progress", "Archive endpoint only", numeric.format(study.continuation.parent_samples_per_stream) + " / stream at update " + numeric.format(study.continuation.parent_updates)],
    ["Joint current budget", "Historical evidence", "Continuous until explicit stop; original reference checkpoint preserved"]].forEach(values => {
      const row = el("tr"); row.append(el("th", values[0]), el("td", values[1]), el("td", values[2])); body.append(row);
    });
  table.append(body); const wrap = el("div", null, "table-wrap"); wrap.append(table); replace("study-budgets", [wrap]);
  replace("study-config", study.configuration.map(([label, text]) => { const row = el("tr"); row.append(el("th", label), el("td", text)); return row; }));
  const losses = []; for (const [label, text] of Object.entries(study.losses)) losses.push(el("dt", label.replaceAll("_", " ")), el("dd", text)); replace("study-losses", losses);
  replace("study-evidence", evidence.map(source => {
    const item = el("li");
    if (source.available) { const link = el("a", source.label); link.href = "/api/evidence/" + encodeURIComponent(source.id); link.target = "_blank"; link.rel = "noopener"; item.append(link); }
    else item.append(el("span", source.label), el("span", " · saved source unavailable on this host", "small muted"));
    return item;
  }));
}
function render(data) {
  snapshot = data;
  renderSummary(data); renderActivity(data); renderStudyActivity(data); renderQueue(data); renderGPUs(data); renderTasks(data);
  renderStudy(data.study, data.evidence);
  renderSR40(data.sr40_series, data.study);
  $("last-updated").textContent = "Manager checked " + time(data.observed_at);
  $("connection").textContent = "Manager connected";
  $("connection-dot").className = "dot connected";
}
async function refresh() {
  if (refreshing || busy) return;
  refreshing = true;
  try { render(await request("/api/status")); }
  catch (error) {
    $("connection").textContent = "Manager unavailable";
    $("connection-dot").className = "dot disconnected";
    $("last-updated").textContent = snapshot ? "Last confirmed " + time(snapshot.observed_at) + " · current state unknown" : "No manager observation";
    document.querySelectorAll(".queue-panel button, .priority-input, .activity-card button").forEach(node => { node.disabled = true; });
    $("gpu-summary").textContent = "Current availability unknown";
    if (!snapshot) {
      replace("current-activity", [el("p", "Manager unavailable. Current jobs and queue state are unknown.", "empty")]);
      replace("gpu-hosts", [el("p", "No current GPU observation.", "empty")]);
    }
    notify(error.message + ". Showing only the last confirmed observation, if available.", true);
  } finally { refreshing = false; }
}
const studyView = window.location.pathname === "/e12";
const e13View = window.location.pathname === "/e13";
$("home-view").hidden = studyView || e13View; $("study-view").hidden = !studyView; $("e13-view").hidden = !e13View;
$(e13View ? "nav-e13" : studyView ? "nav-study" : "nav-home").setAttribute("aria-current", "page");
$("timezone").textContent = "(" + Intl.DateTimeFormat().resolvedOptions().timeZone + ")";
$("refresh").addEventListener("click", refresh);
$("queue-toggle").addEventListener("click", () => {
  if (snapshot) mutate(snapshot.queue.paused ? "resume" : "pause", {}, snapshot.queue.paused ? "Queue resumed." : "Queue paused. Running work continues.");
});
request("/api/study").then(data => { renderStudy(data.study, data.evidence); renderSR40(data.sr40_series, data.study); }).catch(error => notify(error.message, true));
refresh();
setInterval(() => {
  if (!document.hidden && !draggedJobId && !document.activeElement?.matches("input")) refresh();
}, 10000);
