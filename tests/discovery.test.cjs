'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { knownHosts } = require('../desktop/hosts.cjs');
const { parseJSONC, themeFile, descriptor, extensionThemes, listThemes, importTheme } = require('../desktop/themes.cjs');
const { validateConfig } = require('../desktop/connection.cjs');

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'supersurfer-discovery-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}
function write(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, typeof value === 'string' ? value : JSON.stringify(value));
}

test('SSH discovery handles quoted aliases, includes and cycles without changing files', t => {
  const home = fixture(t), ssh = path.join(home, '.ssh');
  const config = path.join(ssh, 'config');
  write(config, 'Host "tulip" \'trinity-1\' * gpu-* !blocked # comment\nHost=direct\n  Include "config parts/*.conf"\nInclude ~/extra.conf\n');
  write(path.join(ssh, 'config parts', 'a.conf'), 'Host alpha "quoted-alias"\nInclude config\n');
  write(path.join(ssh, 'config parts', 'b.conf'), 'Host beta tulip\nInclude missing/*.conf\nHost !negated *.example ?x\n');
  write(path.join(home, 'extra.conf'), 'Host extra\n');
  const files = [config, path.join(ssh, 'config parts', 'a.conf'), path.join(ssh, 'config parts', 'b.conf'), path.join(home, 'extra.conf')];
  const original = files.map(file => ({ file, data: fs.readFileSync(file), modified: fs.statSync(file, { bigint: true }).mtimeNs }));
  const result = knownHosts({ home, files: [config] });
  assert.deepEqual(result.hosts.map(host => host.target), ['alpha', 'beta', 'direct', 'extra', 'quoted-alias', 'trinity-1', 'tulip']);
  assert.deepEqual(result.warnings, []);
  for (const saved of original) {
    assert.deepEqual(fs.readFileSync(saved.file), saved.data);
    assert.equal(fs.statSync(saved.file, { bigint: true }).mtimeNs, saved.modified);
  }
});

test('SSH discovery reads aliases only and handles duplicate real paths and absent config', t => {
  const home = fixture(t), ssh = path.join(home, '.ssh'), config = path.join(ssh, 'config');
  write(config, 'Host real\nHostName not-an-alias.example\nUser not-an-alias\nInclude loop\n');
  fs.symlinkSync(config, path.join(ssh, 'loop'));
  assert.deepEqual(knownHosts({ home, files: [config, path.join(ssh, 'loop')] }).hosts, [{ name: 'real', target: 'real' }]);
  assert.deepEqual(knownHosts({ home, files: [path.join(ssh, 'missing')] }), { hosts: [], warnings: [] });
});

test('local mode does not require an SSH target and retains validated workspace settings', () => {
  const local = validateConfig({ mode: 'local' });
  assert.equal(local.mode, 'local');
  assert.equal(local.target, '');
  assert.equal(local.amlHome, '~/.auto-ml');
  assert.equal(local.remotePort, 8765);
  assert.equal(validateConfig({ mode: 'local', target: 'ignored', remoteRoot: '/tmp/local workspace', remotePort: 9123 }).target, '');
  assert.throws(() => validateConfig({ mode: 'remote' }));
  assert.throws(() => validateConfig({ mode: 'local', remoteRoot: './relative' }));
});

test('JSONC supports comments after trailing commas without corrupting quoted content', () => {
  const source = String.raw`{
    // Comment before fields.
    "description": "url https://example.com/a//b and literal /* text */",
    "quoted": "text with \"quote\" and a backslash \\",
    "array": ["alpha", // final item
    ],
    "colors": {"editor.background": "#123", /* final color */ },
  }`;
  const parsed = parseJSONC('\uFEFF' + source);
  assert.equal(parsed.description, 'url https://example.com/a//b and literal /* text */');
  assert.equal(parsed.quoted, 'text with "quote" and a backslash \\');
  assert.deepEqual(parsed.array, ['alpha']);
  assert.deepEqual(parsed.colors, { 'editor.background': '#123' });
});

test('theme includes merge colors and filter nonhex CSS values', t => {
  const root = fixture(t), base = path.join(root, 'base.json'), child = path.join(root, 'child.json');
  write(base, { name: 'Base', type: 'light', colors: { 'editor.background': '#fff', 'editor.foreground': '#123456', 'focusBorder': '#0f08' } });
  write(child, { name: 'Child', include: './base.json', colors: { 'editor.foreground': '#abcdef80', 'button.background': 'url(https://example.com/track)', 'bad.color': 'rgb(0 0 0)', 'also.bad': '#xyzzzz', 'another.bad': 123 } });
  assert.deepEqual(themeFile(child), { name: 'Child', type: 'light', colors: { 'editor.background': '#fff', 'editor.foreground': '#abcdef80', 'focusBorder': '#0f08' } });
  assert.equal(descriptor(child).name, 'Child');
  assert.equal(descriptor(child).type, 'light');
});

test('theme include cycles and directory or symlink escapes are rejected', t => {
  const root = fixture(t), folder = path.join(root, 'themes');
  write(path.join(folder, 'first.json'), { include: 'second.json', colors: {} });
  write(path.join(folder, 'second.json'), { include: 'first.json', colors: {} });
  assert.throws(() => themeFile(path.join(folder, 'first.json')), /cycle/);
  write(path.join(root, 'outside.json'), { colors: { 'editor.background': '#fff' } });
  write(path.join(folder, 'escape.json'), { include: '../outside.json' });
  assert.throws(() => themeFile(path.join(folder, 'escape.json')), /inside/);
  fs.symlinkSync(path.join(root, 'outside.json'), path.join(folder, 'linked.json'));
  assert.throws(() => themeFile(path.join(folder, 'linked.json')), /inside/);
});

test('imported themes persist as data, deduplicate and remain available without source file', t => {
  const root = fixture(t), source = path.join(root, 'palette.json'), userData = path.join(root, 'app');
  write(source, { name: 'Personal palette', type: 'dark', colors: { 'editor.background': '#112233', 'editor.foreground': '#eee' } });
  const imported = importTheme(source, userData);
  assert.match(imported.id, /^vscode:import-/);
  assert.deepEqual(importTheme(source, userData), imported);
  const record = path.join(userData, 'imported-themes.json');
  assert.equal(JSON.parse(fs.readFileSync(record, 'utf8')).length, 1);
  assert.equal(fs.statSync(record).mode & 0o777, 0o600);
  fs.unlinkSync(source);
  const available = listThemes(userData, { home: root, extensionRoots: [] }).themes;
  assert.deepEqual(available.find(theme => theme.id === imported.id), imported);
  write(source, { colors: { 'editor.background': 'not-a-color' } });
  assert.throws(() => importTheme(source, userData), /no workbench colors/);
});

test('installed extensions contribute localized themes without executing extension code', t => {
  const root = fixture(t), extensions = path.join(root, 'extensions'), extension = path.join(extensions, 'example.palette-1.0');
  const sentinel = path.join(root, 'extension-was-executed');
  write(path.join(extension, 'package.json'), { name: 'palette', publisher: 'example', main: 'extension.js', contributes: { themes: [{ label: '%theme.label%', path: './themes/color.json', uiTheme: 'vs' }, { label: 'Escaped', path: '../outside.json', uiTheme: 'vs-dark' }] } });
  write(path.join(extension, 'package.nls.json'), { 'theme.label': 'Localized palette' });
  write(path.join(extension, 'extension.js'), `require('node:fs').writeFileSync(${JSON.stringify(sentinel)}, 'executed');`);
  write(path.join(extension, 'base.json'), { colors: { 'editor.background': '#123456' } });
  write(path.join(extension, 'themes/color.json'), { include: '../base.json', colors: { 'editor.foreground': '#def' } });
  write(path.join(extensions, 'outside.json'), { colors: { 'editor.background': '#ffffff' } });
  const themes = extensionThemes(extension);
  assert.equal(themes.length, 1);
  assert.equal(themes[0].name, 'Localized palette');
  assert.equal(themes[0].type, 'light');
  assert.equal(themes[0].colors['editor.background'], '#123456');
  assert.equal(fs.existsSync(sentinel), false);
  const installed = listThemes(path.join(root, 'app'), { home: root, extensionRoots: [extensions] }).themes;
  assert.deepEqual(installed.find(theme => theme.id === themes[0].id), themes[0]);
  assert.equal(fs.existsSync(sentinel), false);
});
