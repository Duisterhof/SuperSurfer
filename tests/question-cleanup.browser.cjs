'use strict';
// Run with: node tests/question-cleanup.browser.cjs (Playwright + Chromium).
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

(async () => {
  const executablePath = process.env.SUPERSURFER_CHROME || (fs.existsSync('/opt/google/chrome/chrome') ? '/opt/google/chrome/chrome' : undefined);
  const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage({ viewport: { width: 1400, height: 1000 }, timezoneId: 'America/New_York' });
    page.setDefaultTimeout(10000);
    const errors = [], calls = [], scope = 'project:p1', other = 'project:p2', storage = 'supersurfer-question-drafts';
    page.on('pageerror', error => errors.push(error.message));
    const question = id => ({ id, status: 'pending', can_answer: true, questions: [
      { id: 'direction', question: 'Which evidence should we inspect?', options: [] },
      { id: 'secret', question: 'Private detail?', isSecret: true, options: [] },
    ] });
    let questions = [{ ...question('old'), status: 'unavailable', can_answer: false }], busy = false, disconnected = false;
    const data = { connected: true, read_only: false, projects: [{ id: 'p1', name: 'VLA', repo: '/tmp/vla', initialized: true }],
      experiments: [], runs: [], hosts: [], agents: [], queue: { paused: false, run_ids: [] }, monitoring: {},
      settings: { models: { manager: '', lead: '', worker: '' }, reasoning: { manager: 'medium', lead: 'medium', worker: 'medium' }, approval_mode: 'ask', timezone: 'America/New_York' } };
    await page.addInitScript(({ scope, other, storage }) => {
      if (localStorage.getItem('question-fixture-initialized')) return;
      localStorage.setItem('question-fixture-initialized', 'yes');
      localStorage.setItem(storage, JSON.stringify([[JSON.stringify([scope, 'old']), { updated: Date.now(), answers: { direction: { text: 'Old draft' } } }],
        [JSON.stringify([other, 'unrelated']), { updated: Date.now(), answers: { direction: { text: 'Another chat draft' } } }]]));
    }, { scope, other, storage });
    await page.route('http://questions.test/**', async route => {
      const request = route.request(), url = new URL(request.url());
      let body = {};
      if (url.pathname === '/api/account') body = {account:{type:'chatgpt'}};
      else if (url.pathname === '/api/state') body = data;
      else if (url.pathname === '/api/project-agents') body = { project_id: 'p1', agents: [{ scope, name: 'VLA lead', owner: 'supersurfer', status: busy ? 'working' : 'idle', busy }] };
      else if (url.pathname === '/api/chat') {
        if (disconnected) return route.abort('connectionfailed');
        body = { busy, steerable: busy && !questions.some(q => q.status === 'pending'), questions, approvals: [],
          messages: [{ id: 'history', role: 'assistant', text: 'Existing conversation history.', created: 1 }],
          preferences: { editable: true, defaults: { model: '', reasoning: 'medium', approval_mode: 'ask' }, overrides: {},
            effective: { model: 'fixture', reasoning: 'medium', approval_mode: 'ask' }, supported_reasoning: ['medium'] } };
      } else if (url.pathname === '/api/models') body = { models: [{ id: 'fixture', displayName: 'Fixture', supportedReasoningEfforts: [{ reasoningEffort: 'medium' }] }] };
      else if (url.pathname === '/api/action') {
        const call = request.postDataJSON(); calls.push(call);
        if (call.op === 'settings.save') Object.assign(data.settings, call.params);
        else if (call.op === 'chat.answer') {
          questions = questions.map(q => ({ ...q, status: 'unavailable', can_answer: false })); busy = false;
          return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: 'The original agent connection ended.' }) });
        } else throw new Error('Unexpected action: ' + call.op);
      } else if (!url.pathname.startsWith('/api/')) {
        const file = path.join(root, 'ui', url.pathname === '/' ? 'index.html' : url.pathname.slice(1));
        return route.fulfill({ contentType: { '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' }[path.extname(file)] || 'text/html', body: fs.readFileSync(file) });
      }
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    });
    const drafts = () => page.evaluate(storage => JSON.parse(localStorage.getItem(storage) || '[]'), storage);
    const refresh = async () => { await page.getByRole('button', { name: 'Refresh connection', exact: true }).click(); };
    const noCard = async () => { await page.waitForFunction(() => document.querySelector('#chat-questions').hidden && !document.querySelector('.question-card')); };
    await page.goto('http://questions.test/');
    await page.getByText('Existing conversation history.', { exact: true }).waitFor();
    await noCard(); assert.equal(await page.locator('#chat-send').isEnabled(), true);
    assert.deepEqual((await drafts()).map(([key]) => JSON.parse(key)), [[other, 'unrelated']]);
    console.log('PASS expired question disappears on first load; composer/history/unrelated draft preserved');

    questions = [question('live')]; busy = true; await refresh();
    await page.getByRole('textbox', { name: 'Which evidence should we inspect?' }).fill('Keep my current answer');
    await page.getByLabel('Private detail?', { exact: true }).fill('SECRET-FIXTURE-DRAFT');
    assert.ok(!JSON.stringify(await drafts()).includes('SECRET-FIXTURE-DRAFT'));
    disconnected = true; await refresh();
    await page.waitForFunction(() => document.querySelector('.chat-error'));
    assert.ok(JSON.stringify(await drafts()).includes('Keep my current answer'));
    disconnected = false; await page.reload();
    await page.getByRole('textbox', { name: 'Which evidence should we inspect?' }).waitFor();
    assert.equal(await page.getByRole('textbox', { name: 'Which evidence should we inspect?' }).inputValue(), 'Keep my current answer');
    assert.equal(await page.getByLabel('Private detail?', { exact: true }).inputValue(), '');
    console.log('PASS a client disconnect/reload preserves a live remote question and ordinary draft');

    for (const ending of ['unavailable', 'cancelled', 'answered', 'removed']) {
      questions = [question(ending)]; busy = true; await refresh();
      await page.getByRole('textbox', { name: 'Which evidence should we inspect?' }).fill('Draft for ' + ending);
      questions = ending === 'removed' ? [] : questions.map(q => ({ ...q, status: ending, can_answer: false })); busy = false;
      await refresh(); await noCard();
      assert.equal(await page.locator('#chat-send').isEnabled(), true);
      assert.deepEqual((await drafts()).map(([key]) => JSON.parse(key)), [[other, 'unrelated']]);
    }
    console.log('PASS disconnect/stop/answer/removal clear the card and scoped drafts without blocking new messages');

    questions = [question('answer-race')]; busy = true; await refresh();
    await page.getByRole('textbox', { name: 'Which evidence should we inspect?' }).fill('Evidence');
    await page.getByLabel('Private detail?', { exact: true }).fill('Private');
    await page.getByRole('button', { name: 'Answer & continue', exact: true }).click();
    await noCard(); assert.equal(calls.filter(call => call.op === 'chat.answer').length, 1);
    assert.deepEqual((await drafts()).map(([key]) => JSON.parse(key)), [[other, 'unrelated']]);
    questions = [question('fresh-turn')]; busy = true; await refresh();
    await page.getByRole('textbox', { name: 'Which evidence should we inspect?' }).waitFor();
    assert.equal(await page.getByRole('textbox', { name: 'Which evidence should we inspect?' }).inputValue(), '');
    assert.equal(await page.locator('.question-error:visible').count(), 0);
    assert.deepEqual(errors, []);
    console.log('PASS expired answer is not replayed; a new turn gets a clean question with no JS errors');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
