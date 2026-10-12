"use strict";
// Render the actual extension webview with a VS Code message bridge shim. All
// board edits and agent requests go to the isolated real native companion.
const fs = require("node:fs"),
  path = require("node:path"),
  http = require("node:http");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");
const { call } = require("../native_extension/client.cjs");
const root = process.env.SS_NATIVE_QA_ROOT;
if (!root || !root.includes("supersurfer-native-qa"))
  throw new Error(
    "Select the isolated native QA root; never run against real conversations.",
  );
const config = JSON.parse(
  fs.readFileSync(
    path.join(
      root,
      process.env.SS_NATIVE_EDITOR_PROFILE || "editor3",
      "User/globalStorage/supersurfer.native-workflows/companion.json",
    ),
  ),
);
const binding = JSON.parse(
  fs.readFileSync(path.join(root, "editor-ready.json")),
);
const media = path.resolve(__dirname, "../native_extension/media");
const shots = process.env.SS_NATIVE_SHOTS || root;
fs.mkdirSync(shots, { recursive: true });
const html = `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/board.css"></head><body><main id="app"></main><script>
let fixtureSavedState;
const receive = data => window.dispatchEvent(new MessageEvent('message', {data}));
async function refresh(){const result=await fetch('/command',{method:'POST',body:JSON.stringify({op:'ready'})}).then(r=>r.json());receive(result)}
window.acquireVsCodeApi=()=>({getState:()=>fixtureSavedState,setState:value=>fixtureSavedState=value,postMessage:async message=>{if(message.op==='retainDraft')return;const result=await fetch('/command',{method:'POST',body:JSON.stringify(message)}).then(r=>r.json());receive(result);if(result.type==='result')await refresh();}});
setInterval(refresh,1000);
</script><script src="/board.js"></script></body></html>`;
const server = http.createServer((req, res) => {
  if (req.url === "/") {
    res.end(html);
    return;
  }
  if (req.url === "/board.js" || req.url === "/board.css") {
    res.setHeader(
      "Content-Type",
      req.url.endsWith(".css") ? "text/css" : "application/javascript",
    );
    res.end(fs.readFileSync(path.join(media, req.url.slice(1))));
    return;
  }
  if (req.url !== "/command" || req.method !== "POST") {
    res.writeHead(404);
    res.end();
    return;
  }
  let body = "";
  req.on("data", (c) => {
    body += c;
    if (body.length > 1024 * 1024) req.destroy();
  });
  req.on("end", async () => {
    try {
      const { op, args } = JSON.parse(body);
      if (op === "ready") {
        const status = await call(config, "status");
        res.end(
          JSON.stringify({
            type: "state",
            data: await call(config, "board", { scope: binding.scope }),
            binding: status.bindings.find((b) => b.scope === binding.scope),
            hostType: status.hostType,
          }),
        );
      } else if (["save", "apply", "ask", "pause"].includes(op))
        res.end(
          JSON.stringify({
            type: "result",
            op,
            result: await call(config, op, { ...args, scope: binding.scope }),
          }),
        );
      else
        res.end(
          JSON.stringify({
            type: "error",
            message: "Unsupported fixture action",
          }),
        );
    } catch (e) {
      res.end(JSON.stringify({ type: "error", message: e.message }));
    }
  });
});
(async () => {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.CHROME_PATH ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    args: ["--disable-gpu"],
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1180, height: 840 },
      deviceScaleFactor: 1,
    });
    page.setDefaultTimeout(12000);
    page.on("pageerror", (error) =>
      console.error("Webview error:", error.message),
    );
    await page.goto("http://127.0.0.1:" + server.address().port);
    await page.locator('.node[data-id="worker"]').click();
    await page.locator("#label").fill("Frontend builder");
    await page.locator("#apply").click();
    await page.waitForFunction(() =>
      document
        .querySelector("#notice")
        ?.textContent.includes("Applied workflow"),
    );
    assert.equal(
      (await call(config, "board", { scope: binding.scope })).board.nodes.find(
        (n) => n.id === "worker",
      ).label,
      "Frontend builder",
    );
    await page
      .locator("#question")
      .fill(
        "Rename the agent to Frontend developer. Keep tests required before preview.",
      );
    await page.screenshot({ path: path.join(shots, "surfboard-editor.png") });
    await page.locator("#ask").click();
    await page.waitForFunction(
      () =>
        document
          .querySelector('.node[data-id="worker"]')
          ?.textContent.includes("Frontend developer"),
      undefined,
      { timeout: 20000 },
    );
    let board;
    for (let attempt = 0; attempt < 40; attempt++) {
      board = await call(config, "board", { scope: binding.scope });
      if (
        !board.draft &&
        board.board.nodes.find((n) => n.id === "worker").label ===
          "Frontend developer"
      )
        break;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    assert.equal(
      board.board.nodes.find((n) => n.id === "worker").label,
      "Frontend developer",
    );
    assert.ok(
      board.board.edges.some(
        (e) =>
          e.source === "checks" &&
          e.target === "preview" &&
          e.relation === "requires",
      ),
    );
    await page.waitForFunction(
      () =>
        document
          .querySelector("#notice")
          ?.textContent.includes("Applied workflow") &&
        document.querySelector("#status")?.textContent === "Ready",
    );
    await page.screenshot({
      path: path.join(shots, "surfboard-agent-edit.png"),
    });
    console.log(
      "PASS: manual apply, same-native-agent edit, preserved condition, live graph refresh; screenshots captured.",
    );
  } finally {
    await browser.close();
    await new Promise((r) => server.close(r));
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
