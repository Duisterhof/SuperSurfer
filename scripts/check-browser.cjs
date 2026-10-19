'use strict';
// These tests own temporary projects; no real provider, SSH account or GPU is used.
const {execFileSync}=require('node:child_process');
const {chromium}=require('playwright');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const env={...process.env,CHROME_PATH:process.env.CHROME_PATH||chromium.executablePath()};
for(const test of ['workflow042','folder-speed042','detached-resize','large-pdf','backend-settings','opencode-provider']) {
  console.log(`Checking ${test}…`);
  execFileSync(process.execPath,[`tests/${test}.browser.cjs`],{cwd:root,env,stdio:'inherit',timeout:180000});
}
