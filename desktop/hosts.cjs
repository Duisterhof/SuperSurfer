'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

function words(line) {
  const result = []; let value = '', quote = null, escape = false;
  for (const ch of line) {
    if (escape) { value += ch; escape = false; continue; }
    if (ch === '\\') { escape = true; continue; }
    if (quote) { if (ch === quote) quote = null; else value += ch; continue; }
    if (ch === '"' || ch === "'") { quote = ch; continue; }
    if (ch === '#') break;
    if (/\s/.test(ch)) { if (value) { result.push(value); value = ''; } }
    else value += ch;
  }
  if (value) result.push(value);
  return result;
}
function knownHosts({ home = os.homedir(), files = null } = {}) {
  const hosts = new Set(), seen = new Set(), warnings = [];
  function read(file, base, depth = 0) {
    if (depth > 12 || seen.size > 500) return;
    try {
      file = fs.realpathSync(file);
      if (seen.has(file) || !fs.statSync(file).isFile() || fs.statSync(file).size > 2 * 1024 * 1024) return;
      seen.add(file);
      for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
        const tokens = words(line.replace(/^\s*(Host|Include)\s*=\s*/i, '$1 '));
        const keyword = tokens.shift()?.toLowerCase();
        if (keyword === 'host') for (const target of tokens) if (/^[a-zA-Z0-9][a-zA-Z0-9_.@:-]{0,199}$/.test(target)) hosts.add(target);
        if (keyword === 'include') for (let pattern of tokens) {
          if (pattern.startsWith('~/')) pattern = path.join(home, pattern.slice(2));
          if (!path.isAbsolute(pattern)) pattern = path.join(base, pattern);
          for (const included of fs.globSync(pattern)) read(included, base, depth + 1);
        }
      }
    } catch (error) { if (error.code !== 'ENOENT') warnings.push('Could not read SSH configuration: ' + path.basename(file)); }
  }
  const userBase = path.join(home, '.ssh');
  for (const file of files || [path.join(userBase, 'config'), '/etc/ssh/ssh_config']) read(file, file.startsWith('/etc/') ? '/etc/ssh' : userBase);
  return { hosts: [...hosts].sort((a, b) => a.localeCompare(b)).map(target => ({ name: target, target })), warnings };
}
module.exports = { knownHosts, words };
