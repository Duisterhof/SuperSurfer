'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { validateConfig } = require('./connection.cjs');
const { workspacePreference } = require('./preferences.cjs');

function readJSON(file) { try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return null; } }
function configKey(config) { return JSON.stringify(validateConfig(config)); }
function windowLabel(record) { return record.config ? record.config.mode === 'local' ? 'This machine' : record.config.target : 'New workspace'; }
function boundsPreference(value) {
  if (!value || !['x','y','width','height'].every(key => Number.isFinite(value[key]))) return null;
  return { x: Math.max(-100000,Math.min(100000,Math.round(value.x))), y: Math.max(-100000,Math.min(100000,Math.round(value.y))),
    width: Math.max(1000,Math.min(4000,Math.round(value.width))), height: Math.max(680,Math.min(3000,Math.round(value.height))) };
}

class WindowStore {
  constructor(directory) {
    this.directory = directory;
    this.file = path.join(directory, 'windows.json');
    this.records = [];
    const saved = readJSON(this.file);
    for (const item of Array.isArray(saved?.windows) ? saved.windows.slice(0,50) : []) {
      try {
        if (!item || !/^[a-f0-9-]{36}$/.test(item.id) || this.records.some(row => row.id === item.id)) continue;
        this.records.push({ id:item.id, config:item.config ? validateConfig(item.config) : null, workspace:item.workspace ? workspacePreference(item.workspace) : null,
          bounds:boundsPreference(item.bounds), maximized:item.maximized === true, open:item.open === true, updated:Number.isFinite(item.updated) ? item.updated : 0 });
      } catch {}
    }
    if (!this.records.length && !fs.existsSync(this.file)) {
      const config = readJSON(path.join(directory, 'connection.json'));
      try {
        const record = this.create(config ? validateConfig(config) : null);
        const workspace = readJSON(path.join(directory, 'workspace.json'));
        if (workspace) { try { record.workspace = workspacePreference(workspace); } catch {} }
      } catch { this.records = []; }
    }
  }
  create(config = null) {
    const record = {id:randomUUID(), config:config ? validateConfig(config) : null, workspace:null, bounds:null, maximized:false, open:true, updated:Date.now()};
    this.records.push(record);return record;
  }
  restore() {
    const open = this.records.filter(row => row.open);
    if (open.length) return open;
    const last = [...this.records].filter(row => row.config).sort((a,b) => b.updated-a.updated)[0];
    return [last || this.create()];
  }
  recent() {
    const seen = new Set();
    return [...this.records].filter(row => row.config).sort((a,b) => b.updated-a.updated).filter(row => {
      const key = configKey(row.config);if (seen.has(key)) return false;seen.add(key);return true;
    }).slice(0,10);
  }
  connected(record, config) {
    const next = validateConfig(config);
    if (record.config && configKey(record.config) !== configKey(next)) {
      // Keep the old association in Open Recent, including its navigation.
      this.records.push({...record, id:randomUUID(), open:false});record.workspace=null;
    }
    record.config=next;record.updated=Date.now();this.save();
  }
  save() {
    const open = this.records.filter(row => row.open);
    const closed = this.records.filter(row => !row.open).sort((a,b) => b.updated-a.updated).slice(0,Math.max(0,50-open.length));
    this.records=[...open,...closed];
    fs.mkdirSync(this.directory,{recursive:true});
    const temporary=this.file+'.tmp';
    fs.writeFileSync(temporary,JSON.stringify({version:1,windows:this.records}),{mode:0o600});fs.renameSync(temporary,this.file);
  }
}
module.exports={WindowStore,configKey,windowLabel,boundsPreference};
