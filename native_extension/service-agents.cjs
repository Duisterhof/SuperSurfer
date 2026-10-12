"use strict";
const fs = require("node:fs"), path = require("node:path");
const { fileURLToPath } = require("node:url");
function canonical(directory) { return fs.realpathSync(directory); }
function sameFolder(a, b) {
  try { return canonical(a) === canonical(b); } catch { return false; }
}
function sessionFolder(session) {
  return (session.workingDirectories || []).map(uri => {
    try { return canonical(fileURLToPath(uri)); } catch { return null; }
  }).filter(Boolean);
}
// Existing conversations remain owned by the running SuperSurfer service.
// Listing/opening them never starts a provider or sends a turn.
class ServiceAgents {
  constructor(service) { this.service = service; }
  async projectForFolder(directory) {
    const repo = canonical(directory);
    const state = await this.service.request("/api/state");
    let project = state.projects.find(p => sameFolder(p.repo, repo));
    if (!project) {
      const result = await this.service.action("project.add", {
        name: state.projects.some(p => p.name === path.basename(repo)) ? `${path.basename(repo)} (${path.basename(path.dirname(repo))})` : path.basename(repo),
        repo, surfboard_template: "software",
      });
      project = result.project || result;
      if (!project.id) throw new Error("Project registration was not confirmed. Refresh before trying again.");
      if (result.initialized === false) throw new Error(result.warning || "Project setup needs attention. Refresh before trying again.");
    }
    return project;
  }
  async newChat(directory) {
    const project = await this.projectForFolder(directory);
    const task = await this.service.action("experiment.create", { project_id: project.id, name: "New chat" });
    if (!task.id) throw new Error("Chat creation was not confirmed. Refresh before trying again.");
    return { service: true, scope: "experiment:" + task.id, name: "New chat", title: "New chat", owner: "supersurfer",
      project_id: project.id, projectName: project.name, repo: project.repo, experiment_id: task.id };
  }
  async list() {
    const state = await this.service.request("/api/state");
    this.readOnly = !!state.read_only;
    const projects = await Promise.all((state.projects || []).map(async (project) => {
      const listing = await this.service.request("/api/project-agents?project_id=" + encodeURIComponent(project.id));
      const agents = listing.agents.filter(a => !a.archived && !a.retired).map(a => ({
        ...a, service: true, project_id: project.id, projectName: project.name,
        title: a.name, repo: project.repo,
      })).sort((a, b) => Number(!!b.busy) - Number(!!a.busy) || (b.updated_at || 0) - (a.updated_at || 0));
      return { ...project, kind: "project", agents };
    }));
    return projects.sort((a, b) => Number(b.agents.some(x => x.busy)) - Number(a.agents.some(x => x.busy)) || a.name.localeCompare(b.name));
  }
  async chat(scope, limit = 150) {
    if (!Number.isInteger(limit) || limit < 1 || limit > 100000) throw new Error("Invalid history size");
    const chat = await this.service.request("/api/chat?scope=" + encodeURIComponent(scope) + "&limit=" + limit);
    return { ...chat, read_only: this.readOnly };
  }
  action(scope, op, args = {}) {
    const fields = {
      "chat.send": ["text"], "chat.steer": ["text"], "chat.stop": [],
      "chat.approve": ["approval_id", "decision"], "chat.answer": ["question_id", "answers"],
    }[op];
    if (!fields || Object.keys(args).some(k => !fields.includes(k))) throw new Error("Unsupported conversation action");
    return this.service.action(op, { ...args, scope });
  }
  board(binding) {
    const query = new URLSearchParams({ project_id: binding.project_id });
    if (binding.experiment_id) query.set("experiment_id", binding.experiment_id);
    return this.service.request("/api/surfboard?" + query);
  }
  async boardAction(binding, op, args = {}) {
    if (op === "ask") {
      const chat = await this.chat(binding.scope, 1);
      if (chat.busy && !chat.steerable) throw new Error("This agent is working. Wait for its turn to finish before sending this edit.");
      return this.action(binding.scope, chat.busy ? "chat.steer" : "chat.send", {
        text: "Surfboard editing request: " + args.text + "\nUpdate the workflow configuration only; this message does not request execution of the workflow. Preserve the existing task and all other user instructions.",
      });
    }
    if (!["save", "apply", "discard"].includes(op)) throw new Error("Unsupported Surfboard action");
    const { scope, project_id, experiment_id, ...fields } = args;
    return this.service.action("surfboard." + { save: "draft", apply: "apply", discard: "discard" }[op], {
      ...fields, project_id: binding.project_id,
      ...(binding.experiment_id ? { experiment_id: binding.experiment_id } : {}),
    });
  }
}
module.exports = { ServiceAgents, sameFolder, sessionFolder };
