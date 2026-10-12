"use strict";
const fs = require("node:fs"), path = require("node:path"), os = require("node:os"), http = require("node:http"), assert = require("node:assert/strict");
const { spawn } = require("node:child_process"), { chromium } = require("playwright");
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const root = process.env.SS_SERVICE_HOST_QA || fs.mkdtempSync(path.join(os.tmpdir(), "ss-native-chat-"));
  fs.mkdirSync(root, { recursive: true });
  const state = path.join(root, "state"), repo = path.join(root, "project"), profile = path.join(root, "profile");
  for (const p of [state, repo, path.join(profile, "User")]) fs.mkdirSync(p, { recursive: true });
  fs.writeFileSync(path.join(repo, "README.md"), "# Research project\n\nNative chat integration fixture. No live agents or model inference.\n");
  fs.writeFileSync(path.join(state, "token"), "isolated-fixture-token", { mode: 0o600 });
  const binding = { scope: "experiment:fixture", name: "Evaluation agent", title: "Evaluation agent", owner: "supersurfer", service: true, project_id: "project", experiment_id: "fixture", repo, projectName: "Research project" };
  const chat = { ...binding, backend: "codex", thread_id: "original-fixture-thread", busy: false, status: "completed", agent: { name: binding.name, model: "Existing Codex model" }, questions: [], approvals: [], activity: [],
    messages: [{ id: "request", role: "user", text: "Check our saved evaluation results and tell me what to do next.", created: Date.now() / 1000 - 3600 },
      { id: "answer", role: "assistant", text: "The evaluation results are saved. **The current checkpoint is ready for review.**\n\nI can help inspect the results or update the Surfboard here. This is the same persistent conversation used by SuperSurfer.\n\n*Integration fixture — no model inference.*", created: Date.now() / 1000 - 3599 }] };
  const second = { ...binding, scope: "experiment:writing", name: "Writing agent", title: "Writing agent", experiment_id: "writing" };
  const secondChat = { ...structuredClone(chat), scope: second.scope, agent: { name: second.name, model: "Existing model" }, busy: true, status: "awaiting_input",
    messages: [{ id: "writing-user", role: "user", text: "Help revise the results section.", created: Date.now() / 1000 - 3600 }],
    questions: [{ id: "question", status: "pending", questions: [{ id: "source", header: "Results", question: "Which results should I use?", options: [{ label: "Latest results", description: "Use the latest saved evaluation." }, { label: "Earlier baseline", description: "Use the comparison run." }] }] }],
    approvals: [{ id: "approval", status: "pending", reason: "Update the draft results section?", kind: "command" }] };
  const calls = [];
  const server = http.createServer((req, res) => {
    let body = ""; req.on("data", data => { body += data; }); req.on("end", () => {
      let result;
      if (req.headers.authorization !== "Bearer isolated-fixture-token") { res.writeHead(401); res.end("{}"); return; }
      const url = new URL(req.url, "http://localhost");
      if (url.pathname === "/api/state") result = { projects: [{ id: "project", name: "Research project", repo }], experiments: [{ id: "fixture", project_id: "project", name: "Evaluation" }] };
      else if (url.pathname === "/api/project-agents") result = { agents: [binding, second] };
      else if (url.pathname === "/api/chat") { const selected = url.searchParams.get("scope") === second.scope ? secondChat : chat; result = { ...selected, message_count: selected.messages.length }; }
      else if (url.pathname === "/api/action") {
        const { op, params } = JSON.parse(body); const target = params.scope === second.scope ? secondChat : chat; calls.push({ op, params }); fs.writeFileSync(path.join(root, "calls.json"), JSON.stringify(calls));
        if (op === "chat.send") {
          const id = "message-" + calls.length; chat.busy = true; chat.status = "working";
          chat.messages.push({ id, role: "user", text: params.text, created: Date.now() / 1000 });
          result = { accepted: true, message_id: id };
          setTimeout(() => { chat.messages.push({ id: "response-" + id, role: "assistant", text: "The same agent finished this request on the host. Its original provider conversation is preserved.", created: Date.now() / 1000 }); chat.busy = false; chat.status = "completed"; }, 6000);
        } else if (op === "chat.answer") { target.questions[0].status = "answered"; result = {}; }
        else if (op === "chat.approve") { target.approvals[0].status = "answered"; target.busy = false; target.status = "completed"; target.messages.push({ id: "writing-answer", role: "assistant", text: "The requested draft update is saved. Integration fixture — no inference.", created: Date.now() / 1000 }); result = {}; }
        else if (op === "chat.stop") { chat.busy = false; chat.status = "interrupted"; result = {}; }
        else result = {};
      } else { res.writeHead(404); res.end(JSON.stringify({ error: req.url })); return; }
      res.writeHead(200, { "Content-Type": "application/json" }); res.end(JSON.stringify(result));
    });
  });
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  fs.writeFileSync(path.join(state, "service.json"), JSON.stringify({ port: server.address().port }));
  fs.writeFileSync(path.join(root, "fixture.json"), JSON.stringify({ state, binding }));
  fs.writeFileSync(path.join(profile, "User/settings.json"), JSON.stringify({
    "workbench.startupEditor": "none", "telemetry.telemetryLevel": "off", "security.workspace.trust.enabled": false,
    "chat.agentHost.allowSignedOutWhenUsable": true, "chat.remoteAgentHostsEnabled": true,
    "update.mode": "none", "extensions.autoUpdate": false, "supersurferNative.stateDirectory": state,
    "chat.agentHost.codexAgent.enabled": false, "chat.agentHost.claudeAgent.enabled": false,
  }));
  const binary = process.env.SS_VSCODE_BINARY || "/Applications/Visual Studio Code.app/Contents/MacOS/Code";
  const log = fs.openSync(path.join(root, "editor.log"), "a");
  const launch = () => spawn(binary, [repo, "--new-window", "--skip-welcome", "--skip-release-notes", "--disable-updates", "--disable-workspace-trust", "--enable-proposed-api=supersurfer.native-workflows", "--remote-debugging-port=9418", "--user-data-dir=" + profile,
    "--extensions-dir=" + path.join(root, "extensions"), "--extensionDevelopmentPath=" + path.resolve(__dirname, "../native_extension"), "--extensionTestsPath=" + path.join(__dirname, "fixtures/service-host-editor.cjs")],
    { env: { ...process.env, SS_SERVICE_HOST_QA: root }, stdio: ["ignore", log, log] });
  let child = launch();
  console.log("QA directory:", root);
  let browser;
  try {
    for (let i = 0; i < 100; i++) { try { browser = await chromium.connectOverCDP("http://127.0.0.1:9418"); break; } catch { await sleep(300); } }
    if (!browser) throw Error("The isolated VS Code window did not start.");
    for (let i = 0; i < 120; i++) { if (fs.existsSync(path.join(root, "ready.json")) || fs.existsSync(path.join(root, "error.txt"))) break; await sleep(500); }
    if (fs.existsSync(path.join(root, "error.txt"))) throw Error(fs.readFileSync(path.join(root, "error.txt"), "utf8"));
    let page = browser.contexts()[0].pages().find(p => p.url().includes("workbench"));
    if (!page) throw Error("No VS Code workbench found.");
    await sleep(1500);
    fs.writeFileSync(path.join(root, "rendered.txt"), await page.locator("body").innerText());
    await page.screenshot({ path: path.join(root, "native-chat.png") });
    assert.match(await page.locator("body").innerText(), /current checkpoint is ready for review/);
    assert.equal(calls.length, 0, "Opening history must not send an agent message");
    console.log("PASS: existing SuperSurfer history displayed by native VS Code Chat, without inference");
    const input = page.locator('.interactive-input-part .monaco-editor');
    await input.click(); await page.keyboard.type("Continue checking the evaluation results."); await page.keyboard.press("Enter");
    for (let i = 0; i < 40 && !calls.length; i++) await sleep(100);
    fs.writeFileSync(path.join(root, "after-send.txt"), await page.locator("body").innerText());
    await page.screenshot({ path: path.join(root, "after-send.png") });
    if (!calls.length) {  if (process.env.SS_SERVICE_HOST_KEEP === "1") await new Promise(() => {}); }
    assert.equal(calls.length, 1); assert.equal(calls[0].op, "chat.send"); assert.equal(calls[0].params.scope, binding.scope);
    assert.ok(chat.busy);
    await browser.close(); browser = undefined; child.kill("SIGTERM");
    await sleep(7000);
    assert.equal(chat.busy, false); assert.equal(calls.length, 1, "Closing VS Code must not stop the agent");
    fs.unlinkSync(path.join(root, "ready.json"));
    child = launch();
    for (let i = 0; i < 100; i++) { try { browser = await chromium.connectOverCDP("http://127.0.0.1:9418"); break; } catch { await sleep(300); } }
    for (let i = 0; i < 120 && !fs.existsSync(path.join(root, "ready.json")); i++) await sleep(500);
    page = browser.contexts()[0].pages().find(p => p.url().includes("workbench"));
    await page.getByText("The same agent finished this request on the host.", { exact: false }).waitFor({ timeout: 20000 });
    assert.equal(calls.length, 1, "Reopening must not replay the request");
    await page.screenshot({ path: path.join(root, "native-chat-reconnected.png") });
    console.log("PASS: native send, close while busy, finish on host and reopen same history without replay or Stop");
    fs.writeFileSync(path.join(root, "command.json"), JSON.stringify({ command: "supersurferNative.openChatBeside", args: [second] }));
    await page.getByText("Which results should I use?", { exact: true }).waitFor({ timeout: 20000 });
    await page.screenshot({ path: path.join(root, "native-chat-split.png") });
    fs.writeFileSync(path.join(root, "questions-ui.txt"), await page.locator("body").innerText());
    await page.getByRole("button", { name: "Answer question", exact: true }).click();
    await page.getByText("Latest results", { exact: true }).click();
    await page.getByRole("button", { name: "Approve once", exact: true }).waitFor();
    for (let i = 0; i < 40 && calls.at(-1).op !== "chat.answer"; i++) await sleep(100);
    assert.equal(calls.at(-1).op, "chat.answer");
    assert.deepEqual(calls.at(-1).params.answers, { source: ["Latest results"] });
    await page.getByRole("button", { name: "Approve once", exact: true }).click();
    await page.getByText("The requested draft update is saved.", { exact: false }).waitFor();
    assert.equal(calls.at(-1).op, "chat.approve"); assert.equal(calls.at(-1).params.scope, second.scope);
    await page.screenshot({ path: path.join(root, "native-chat-two-agents.png") });
    console.log("PASS: two native agent views, native question form and explicit permission decision");
    if (process.env.SS_SERVICE_HOST_KEEP === "1") await new Promise(() => {});
  } finally {
    if (browser) await browser.close(); child.kill("SIGTERM"); fs.closeSync(log); await new Promise(r => server.close(r));
    // Only this test's detached presentation adapter; it owns no real provider.
    const endpoint = path.join(profile, "User/globalStorage/supersurfer.native-workflows/service-host-endpoint.json");
    try { process.kill(JSON.parse(fs.readFileSync(endpoint)).pid, "SIGTERM"); } catch {}
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
