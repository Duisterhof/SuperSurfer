'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
function parseJSONC(text) {
  let clean = '', quoted = false, escaped = false;
  text = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) { clean += c; if (escaped) escaped = false; else if (c === '\\') escaped = true; else if (c === '"') quoted = false; continue; }
    if (c === '"') { quoted = true; clean += c; continue; }
    if (c === '/' && text[i + 1] === '/') { while (i < text.length && text[i] !== '\n') i++; clean += '\n'; continue; }
    if (c === '/' && text[i + 1] === '*') { i += 2; while (i < text.length && !(text[i] === '*' && text[i + 1] === '/')) i++; i++; clean += ' '; continue; }
    clean += c;
  }
  let normalized = ''; quoted = false; escaped = false;
  for (let i = 0; i < clean.length; i++) {
    const c = clean[i];
    if (quoted) { normalized += c; if (escaped) escaped = false; else if (c === '\\') escaped = true; else if (c === '"') quoted = false; continue; }
    if (c === '"') quoted = true;
    if (c === ',' && /^\s*[}\]]/.test(clean.slice(i + 1))) continue;
    normalized += c;
  }
  return JSON.parse(normalized);
}
function readJSON(file) { if (fs.statSync(file).size > 5 * 1024 * 1024) throw new Error('Theme file is too large.'); return parseJSONC(fs.readFileSync(file, 'utf8')); }
function themeFile(file, { root = path.dirname(file), depth = 0, seen = new Set() } = {}) {
  file = fs.realpathSync(file); root = fs.realpathSync(root);
  if (depth > 12 || seen.has(file)) throw new Error('Theme include cycle or excessive nesting.');
  if (file !== root && !file.startsWith(root + path.sep)) throw new Error('Theme includes must stay inside the theme folder.');
  seen.add(file);
  const data = readJSON(file);
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Choose a VS Code color-theme JSON file.');
  const base = data.include ? themeFile(path.resolve(path.dirname(file), data.include), { root, depth: depth + 1, seen }) : {};
  const colors = { ...base.colors };
  for (const [key, value] of Object.entries(data.colors || {})) if (typeof value === 'string' && /^#(?:[a-f0-9]{3,4}|[a-f0-9]{6}|[a-f0-9]{8})$/i.test(value)) colors[key] = value;
  return { name: data.name || base.name, type: data.type || base.type || 'dark', colors };
}
function descriptor(file, meta = {}) {
  const data = themeFile(file, { root: meta.root || path.dirname(file) });
  const id = meta.id || 'vscode:import-' + crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex').slice(0, 16);
  return { id, name: meta.name || data.name || path.basename(file, path.extname(file)), type: meta.type || data.type, colors: data.colors };
}
function extensionThemes(extension, prefix = 'installed') {
  const pkg = readJSON(path.join(extension, 'package.json'));
  let labels = {}; try { labels = readJSON(path.join(extension, 'package.nls.json')); } catch {}
  return (pkg.contributes?.themes || []).flatMap((theme, index) => {
    try {
      const label = String(theme.label || theme.id || pkg.displayName || pkg.name);
      const name = label.startsWith('%') ? labels[label.slice(1, -1)] || pkg.name : label;
      return [descriptor(path.resolve(extension, theme.path), { root: extension, name, type: { vs: 'light', 'vs-dark': 'dark', 'hc-black': 'hcDark', 'hc-light': 'hcLight' }[theme.uiTheme] || 'dark', id: `vscode:${prefix}-${pkg.publisher || 'vscode'}-${pkg.name}-${index}` })];
    } catch { return []; }
  });
}
function listThemes(userData, { home = os.homedir(), extensionRoots = null } = {}) {
  const themes = new Map();
  for (const theme of readJSON(path.join(__dirname, '../ui/themes.json')).themes || []) themes.set(theme.id, theme);
  try { for (const theme of readJSON(path.join(userData, 'imported-themes.json'))) themes.set(theme.id, theme); } catch {}
  const roots = extensionRoots || [path.join(home, '.vscode/extensions'), path.join(home, '.vscode-insiders/extensions'), path.join(home, '.vscode-oss/extensions'), path.join(home, '.cursor/extensions')];
  for (const root of roots) {
    let entries; try { entries = fs.readdirSync(root, { withFileTypes: true }); } catch { continue; }
    for (const entry of entries.slice(0, 1000)) if (entry.isDirectory()) {
      try { for (const theme of extensionThemes(path.join(root, entry.name))) themes.set(theme.id, theme); } catch {}
    }
  }
  return { themes: [...themes.values()].sort((a, b) => a.name.localeCompare(b.name)) };
}
function importTheme(file, userData) {
  const theme = descriptor(file);
  if (!Object.keys(theme.colors).length) throw new Error('This theme has no workbench colors. Choose a VS Code color-theme JSON file with a colors section.');
  let saved = []; try { saved = readJSON(path.join(userData, 'imported-themes.json')); } catch {}
  saved = saved.filter(item => item.id !== theme.id); saved.push(theme);
  fs.mkdirSync(userData, { recursive: true });
  fs.writeFileSync(path.join(userData, 'imported-themes.json'), JSON.stringify(saved), { mode: 0o600 });
  return theme;
}
module.exports = { parseJSONC, themeFile, descriptor, extensionThemes, listThemes, importTheme };
