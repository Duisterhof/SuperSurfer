'use strict';
const { app, BrowserWindow, ipcMain, Menu, shell, session, nativeTheme, dialog, screen } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const { connect, validateConfig } = require('./connection.cjs');
const { knownHosts } = require('./hosts.cjs');
const { openProviderLogin } = require('./provider-login.cjs');
const themes = require('./themes.cjs');
const { workspacePreference } = require('./preferences.cjs');
const { WindowStore, configKey, windowLabel } = require('./windows.cjs');
const windows = new Map(), panelWindows = new Map();
const contexts=()=>[...windows.values(),...panelWindows.values()];
const releaseConnection=(connection)=>{if(connection&&!contexts().some(row=>row.connection===connection))connection.child?.kill();};
let store, shuttingDown = false;
const setupPath = path.join(__dirname, 'setup.html');
const setupUrl = pathToFileURL(setupPath).href;

function loadTheme() { try { const theme = JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), 'appearance.json'), 'utf8')).theme; return typeof theme === 'string' && (['light','dark','system'].includes(theme) || theme.startsWith('vscode:')) ? theme : 'system'; } catch { return 'system'; } }
function themeSource(value) { if (['light','dark','system'].includes(value)) return value; const theme = themes.listThemes(app.getPath('userData')).themes.find(t => t.id === value); return /light/i.test(theme?.type || '') ? 'light' : 'dark'; }
function ownWindow(event, setupOnly = false) {
  const context = contexts().find(item => item.window.webContents === event.sender);
  const message = setupOnly ? 'Connection settings are available only in the setup window.' : 'This action is available only in a trusted workspace window.';
  if (!context || event.senderFrame !== context.window.webContents.mainFrame) throw new Error(message);
  const url = event.senderFrame.url;
  if (url !== setupUrl && (setupOnly || !context.connection || new URL(url).origin !== context.connection.origin)) throw new Error(message);
  return context;
}
function openExternal(url) {
  try { const parsed = new URL(url); if (['https:', 'http:'].includes(parsed.protocol) && !['127.0.0.1','localhost','[::1]'].includes(parsed.hostname)) shell.openExternal(parsed.href); } catch {}
}
function focus(context) { if (context.window.isMinimized()) context.window.restore(); context.window.show(); context.window.focus(); }
function focused() { return [...windows.values()].find(item => item.window === BrowserWindow.getFocusedWindow()) || [...windows.values()].at(-1); }
function sendStatus(context, phase, message) {
  context.status = {phase,message};
  if (!context.window.isDestroyed()) context.window.webContents.send('connection-status', context.status);
}
function saveWindow(context) {
  if (context.window.isDestroyed()) return;
  context.record.bounds = context.window.getNormalBounds();
  context.record.maximized = context.window.isMaximized();
  store.save();
}
function cancelConnection(context) {
  const attempt = context.attempt;context.attempt = null;attempt?.abort();
  sendStatus(context, 'idle', 'Connection cancelled. Your saved workspace is still available.');
}
async function showSetup(context, restore = false) {
  const previous = {restoreRequested:context.restoreRequested,editing:context.editing};
  context.restoreRequested = restore;
  context.editing = !restore;
  try { await context.window.loadFile(setupPath); }
  catch (error) {
    if (context.window.isDestroyed()) return;
    if (context.window.webContents.getURL() !== setupUrl) Object.assign(context,previous);
    if (error.code !== 'ERR_ABORTED') sendStatus(context, 'error', error.message);
  }
}
async function connectWindow(context, raw) {
  if (context.attempt) return {error:'A connection is already in progress.'};
  const attempt = new AbortController();context.attempt = attempt;context.editing = false;
  let next;
  try {
    const config = validateConfig(raw);
    if(context.connection&&configKey(context.connection.config)!==configKey(config)&&[...panelWindows.values()].some(row=>row.parent===context))throw new Error('Close this workspace’s separate panels before changing its host, or use New Window for the other host.');
    sendStatus(context, 'connecting', `Connecting to ${config.mode === 'local' ? 'this machine' : config.target}…`);
    next = await connect(config, message => sendStatus(context, 'connecting', message), {signal:attempt.signal});
    if (attempt.signal.aborted || context.attempt !== attempt || context.window.isDestroyed()) { next.child?.kill();return {error:'Connection cancelled.'}; }
    const changedHost = context.record.config && configKey(context.record.config) !== configKey(next.config);
    if (changedHost) await context.window.webContents.session.clearStorageData();
    attempt.signal.throwIfAborted();
    store.connected(context.record, next.config);
    const previous = context.connection;context.connection = next;releaseConnection(previous);for(const panel of panelWindows.values())if((panel.parent===context||panel.parent.window.isDestroyed()&&panel.parent.record.id===context.record.id)&&configKey(panel.hostConfig)===configKey(next.config)){panel.parent=context;panel.connection=next;const url=new URL(panel.window.webContents.getURL());void panel.window.loadURL(next.origin+'/'+url.search);}releaseConnection(previous);
    context.window.setTitle(windowLabel(context.record) + ' — SuperSurfer');updateMenu();
    next.child?.once('exit', () => {
      for(const panel of panelWindows.values())if(panel.connection===next){panel.connection=null;sendStatus(panel,'error','Connection lost. The panel and remote work are preserved. Reopen the same host to reconnect.');}
      if (context.connection !== next || shuttingDown || context.window.isDestroyed()) return;
      context.connection = null;
      sendStatus(context, 'error', 'Connection lost. Your remote work is still running.');
      if (!context.editing) {
        if (context.attempt) context.restoreAfterAttempt=true;
        else void showSetup(context, true);
      }
    });
    sendStatus(context, 'connected', 'Workspace connected.');
    await context.window.loadURL(next.origin);
    return {ok:true};
  } catch (error) {
    next?.child?.kill();
    if (context.connection === next) context.connection = null;
    if (context.attempt === attempt && !context.window.isDestroyed()) {
      context.editing = true;
      sendStatus(context, 'error', error.message);
      if (context.window.webContents.getURL() !== setupUrl) await showSetup(context);
    }
    return attempt.signal.aborted ? {cancelled:true} : {error:error.message};
  } finally {
    if (context.attempt === attempt) context.attempt = null;
    if (context.restoreAfterAttempt && !context.attempt && !shuttingDown && !context.window.isDestroyed()) { context.restoreAfterAttempt=false;void showSetup(context,true); }
  }
}
function visibleBounds(bounds) {
  if (!bounds) return {};
  const displays = screen.getAllDisplays();
  const matched=displays.find(({workArea:r}) => Math.min(r.x+r.width,bounds.x+bounds.width)-Math.max(r.x,bounds.x)>100 && Math.min(r.y+r.height,bounds.y+bounds.height)-Math.max(r.y,bounds.y)>100);
  const r=(matched || screen.getPrimaryDisplay()).workArea;
  const width=Math.max(1000,Math.min(bounds.width,r.width)),height=Math.max(680,Math.min(bounds.height,r.height));
  return {width,height,x:Math.max(r.x,Math.min(bounds.x,r.x+r.width-width)),y:Math.max(r.y,Math.min(bounds.y,r.y+r.height-height))};
}
function makeWindow(record = store.create()) {
  const existing = windows.get(record.id);if (existing) { focus(existing);return existing; }
  record.open = true;store.save();
  const partition = session.fromPartition('persist:workspace-'+record.id);
  const window = new BrowserWindow({width:1480,height:940,...visibleBounds(record.bounds),minWidth:1000,minHeight:680,title:windowLabel(record)+' — SuperSurfer',backgroundColor:nativeTheme.shouldUseDarkColors?'#1c201c':'#f8f8f6',titleBarStyle:'hiddenInset',trafficLightPosition:{x:18,y:20},show:false,
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),session:partition,contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true}});
  const context = {window,record,connection:null,attempt:null,status:{phase:'idle',message:''},restoreRequested:false,editing:true};
  windows.set(record.id,context);
  partition.setPermissionRequestHandler((_contents,_permission,callback) => callback(false));
  partition.webRequest.onBeforeSendHeaders((details,callback) => {
    // Credentials belong to this window's main frame and exact loopback origin.
    const owner=contexts().find(row=>row.window.webContents.id===details.webContentsId),connection=owner?.connection;
    if(connection&&details.frame===owner.window.webContents.mainFrame&&details.frame.url.startsWith(connection.origin+'/')&&details.url.startsWith(connection.origin+'/api/'))details.requestHeaders.Authorization=`Bearer ${connection.token}`;
    callback({requestHeaders:details.requestHeaders});
  });
  window.once('ready-to-show', () => { if (record.maximized) window.maximize();window.show(); });
  window.webContents.on('page-title-updated', event => { event.preventDefault();window.setTitle(windowLabel(record)+' — SuperSurfer'); });
  window.webContents.setWindowOpenHandler(({url}) => { openExternal(url);return {action:'deny'}; });
  window.webContents.on('will-navigate', (event,url) => {
    try { if (url === setupUrl || context.connection && new URL(url).origin === context.connection.origin) return; } catch {}
    event.preventDefault();openExternal(url);
  });
  window.webContents.on('will-attach-webview', event => event.preventDefault());
  window.webContents.on('will-prevent-unload', event => {
    const choice = dialog.showMessageBoxSync(window, {type:'question',
      buttons:['Keep editing','Discard unsaved changes'],defaultId:0,cancelId:0,
      title:'Unsaved source files',message:'Discard unsaved editor changes?',
      detail:'Saved files and remote agent work are preserved.'});
    if (choice === 1) event.preventDefault();
    else shuttingDown = false;
  });
  let geometryTimer;
  for (const name of ['move','resize','maximize','unmaximize']) window.on(name, () => { clearTimeout(geometryTimer);geometryTimer=setTimeout(() => saveWindow(context),200); });
  window.on('focus', () => { record.updated=Date.now();store.save(); });
  window.on('close', () => { clearTimeout(geometryTimer);saveWindow(context); });
  window.on('closed', () => {
    if (!shuttingDown) { record.open=false;store.save(); }
    windows.delete(record.id);context.attempt?.abort();releaseConnection(context.connection);
    if(!contexts().some(row=>row.window.webContents.session===partition))partition.webRequest.onBeforeSendHeaders(null);if (!shuttingDown) updateMenu();
  });
  void showSetup(context, !!record.config);updateMenu();return context;
}
function openPanel(context,fields){
  if(!context.connection)throw new Error('Connect a workspace before opening a panel window.');
  if(!fields||typeof fields!=='object'||Object.keys(fields).some(key=>!['project','item','page','tile','title','path'].includes(key)))throw new Error('Choose a project panel.');
  const valid=value=>typeof value==='string'&&/^[A-Za-z0-9_:-]{1,128}$/.test(value);
  if(!['project','page','tile'].every(key=>valid(fields[key]))||fields.item&&!valid(fields.item))throw new Error('Choose a saved project page and panel.');
  if(typeof fields.title!=='string'||fields.title.length>100)throw new Error('Choose a short panel title.');
  if(fields.path!==undefined&&(typeof fields.path!=='string'||fields.path.length>2000||/[\x00-\x1f]/.test(fields.path)))throw new Error('Choose a valid source path.');
  const partition=context.window.webContents.session;const connection=context.connection,url=new URL('/',connection.origin);for(const key of ['project','item','page','tile','path'])url.searchParams.set('panel_'+key,fields[key]||'');
  const child=new BrowserWindow({width:940,height:760,minWidth:360,minHeight:260,title:fields.title+' — SuperSurfer',backgroundColor:nativeTheme.shouldUseDarkColors?'#1c201c':'#f8f8f6',titleBarStyle:'hiddenInset',trafficLightPosition:{x:14,y:14},webPreferences:{preload:path.join(__dirname,'preload.cjs'),session:context.window.webContents.session,contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true}});
  const childId=child.webContents.id;const panel={window:child,record:context.record,connection,hostConfig:connection.config,parent:context,parentPanel:true,fields:{...fields}};panelWindows.set(child.webContents.id,panel);
  child.webContents.setWindowOpenHandler(({url})=>{openExternal(url);return {action:'deny'};});
  child.webContents.on('will-navigate',(event,url)=>{try{if(new URL(url).origin===panel.connection.origin)return;}catch{}event.preventDefault();openExternal(url);});
  child.webContents.on('will-attach-webview',event=>event.preventDefault());
  child.webContents.on('will-prevent-unload',event=>{const choice=dialog.showMessageBoxSync(child,{type:'question',buttons:['Keep editing','Discard unsaved changes'],defaultId:0,cancelId:0,title:'Unsaved source files',message:'Discard unsaved editor changes?'});if(choice===1)event.preventDefault();else shuttingDown=false;});
  child.on('closed',()=>{if(!context.window.isDestroyed())context.window.webContents.send('panel-closed',{id:childId});panelWindows.delete(childId);releaseConnection(panel.connection);if(!contexts().some(row=>row.window.webContents.session===partition))partition.webRequest.onBeforeSendHeaders(null);});
  void child.loadURL(url.href);return {opened:true,id:childId};
}
async function openPort(context,fields){
  if(!fields||Object.keys(fields).sort().join(',')!=='port,project_id'||!Number.isInteger(fields.port))throw new Error('Choose a project and one localhost development port.');
  const connection=context.connection;if(!connection)throw new Error('Connect a workspace first.');
  const response=await fetch(connection.origin+'/api/action',{method:'POST',headers:{Authorization:'Bearer '+connection.token,'Content-Type':'application/json'},body:JSON.stringify({op:'editor.port.check',params:fields})});const checked=await response.json();if(!response.ok)throw new Error(checked.error||'This project port could not be opened.');
  const tunnel=await connection.openPort(fields.port);if(context.window.isDestroyed()||context.connection!==connection){await tunnel.close();throw new Error('The workspace changed before this preview opened.');}
  const preview=new BrowserWindow({width:1040,height:760,minWidth:360,minHeight:260,title:'localhost:'+fields.port+' — SuperSurfer',webPreferences:{partition:'port-preview-'+require('node:crypto').randomUUID(),contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true}});
  const origin=new URL(tunnel.url).origin;preview.webContents.setWindowOpenHandler(({url})=>{openExternal(url);return {action:'deny'};});preview.webContents.on('will-navigate',(event,url)=>{try{if(new URL(url).origin===origin)return;}catch{}event.preventDefault();openExternal(url);});preview.webContents.on('will-attach-webview',event=>event.preventDefault());
  const parentClosed=()=>{if(!preview.isDestroyed())preview.close();};context.window.once('closed',parentClosed);preview.on('closed',()=>{context.window.removeListener('closed',parentClosed);void tunnel.close();});await preview.loadURL(tunnel.url).catch(error=>{preview.close();throw error;});return {opened:true,port:fields.port};
}
function connectionSettings() {
  const context=focused();if (!context) { makeWindow();return; }
  if (context.attempt) cancelConnection(context);
  sendStatus(context,'idle','');void showSetup(context);
}
function workspaceCommand(command){const context=contexts().find(row=>row.window===BrowserWindow.getFocusedWindow())||focused();if(context?.connection&&context.window.webContents.getURL().startsWith(context.connection.origin+'/'))context.window.webContents.send('workspace-command',command);else if(command.startsWith('zoom-')){const win=BrowserWindow.getFocusedWindow();if(win)win.webContents.setZoomLevel(command==='zoom-reset'?0:Math.max(-3,Math.min(4,win.webContents.getZoomLevel()+(command==='zoom-in'?.5:-.5))));}}
function updateMenu() {
  const recent=store.recent().map(record => ({label:windowLabel(record)+(record.config.remoteRoot !== '~/.local/share/supersurfer' ? ' · '+record.config.remoteRoot : ''),click:() => makeWindow(record)}));
  if (app.dock) app.dock.setMenu(Menu.buildFromTemplate([{label:'New Window',click:() => makeWindow()}]));
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform === 'darwin' ? [{label:'SuperSurfer',submenu:[{role:'about'},{type:'separator'},{label:'Connection Settings…',accelerator:'CmdOrCtrl+,',click:connectionSettings},{type:'separator'},{role:'hide'},{role:'hideOthers'},{role:'unhide'},{type:'separator'},{role:'quit'}]}] : []),
    {label:'File',submenu:[{label:'New Window',accelerator:'CmdOrCtrl+Shift+N',click:() => makeWindow()},{label:'Open Recent',submenu:recent.length?recent:[{label:'No recent workspaces',enabled:false}]},{label:'Connection Settings…',click:connectionSettings},{type:'separator'},{role:'close'},...(process.platform === 'darwin' ? [] : [{role:'quit'}])]},
    {label:'Edit',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},
    {label:'Rearrange',submenu:[{label:'Rearrange current page…',accelerator:'CmdOrCtrl+Alt+Shift+R',click:()=>workspaceCommand('rearrange')},{label:'Toggle workspace sidebar',click:()=>workspaceCommand('sidebar')},{label:'Toggle agent panel',accelerator:'CmdOrCtrl+Shift+B',click:()=>workspaceCommand('chat')}]},
    {label:'View',submenu:[{role:'reload'},{role:'togglefullscreen'},{label:'Reset Zoom',accelerator:'CmdOrCtrl+0',click:()=>workspaceCommand('zoom-reset')},{label:'Zoom In',accelerator:'CmdOrCtrl+Plus',click:()=>workspaceCommand('zoom-in')},{label:'Zoom Out',accelerator:'CmdOrCtrl+-',click:()=>workspaceCommand('zoom-out')},{type:'separator'},{label:'Connection Settings…',click:connectionSettings}]},
    {label:'Window',submenu:[{role:'minimize'},{role:'zoom'},{type:'separator'},...[...windows.values()].map(context => ({label:windowLabel(context.record),click:() => focus(context)}))]},
  ]));
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { const context=focused();if (context) focus(context);else if (store) store.restore().forEach(makeWindow); });
  app.whenReady().then(() => {
    store=new WindowStore(app.getPath('userData'));nativeTheme.themeSource=themeSource(loadTheme());
    ipcMain.handle('provider:login',(event,backend)=>{const context=ownWindow(event);if(!context.connection)throw new Error('Connect a workspace first.');return openProviderLogin(context.connection.config,backend);});
    ipcMain.handle('provider:install-cursor',event=>{const context=ownWindow(event);if(!context.connection)throw new Error('Connect a workspace first.');return openProviderLogin(context.connection.config,'cursor',{operation:'install'});});
    ipcMain.handle('port:open',(event,fields)=>openPort(ownWindow(event),fields));
    ipcMain.handle('panel:open',(event,fields)=>openPanel(ownWindow(event),fields));
    ipcMain.handle('window:new',event => { ownWindow(event);makeWindow();return {opened:true}; });
    ipcMain.handle('configuration',event => ownWindow(event,true).record.config || {});
    ipcMain.handle('workspace:zoom',(event,delta)=>{const context=ownWindow(event);if(![-1,0,1].includes(delta))throw new Error('Invalid zoom direction');const wc=context.window.webContents;wc.setZoomLevel(delta===0?0:Math.max(-3,Math.min(5,wc.getZoomLevel()+delta*.5)));return wc.getZoomLevel();});
    ipcMain.handle('panel:list',event=>{const parent=ownWindow(event);return [...panelWindows.values()].filter(panel=>panel.parent===parent).map(panel=>({id:panel.window.webContents.id,...panel.fields}));});
    ipcMain.handle('hosts:list',event => { ownWindow(event,true);return knownHosts(); });
    ipcMain.handle('connection:ready',event => {
      const context=ownWindow(event,true);
      if (context.restoreRequested) { context.restoreRequested=false;void connectWindow(context,context.record.config); }
      return context.status;
    });
    ipcMain.handle('connection:cancel',event => { const context=ownWindow(event,true);cancelConnection(context);return context.status; });
    ipcMain.handle('themes:list',event => { ownWindow(event);return themes.listThemes(app.getPath('userData')); });
    ipcMain.handle('themes:import',async event => {
      const context=ownWindow(event);
      const result=await dialog.showOpenDialog(context.window,{title:'Import VS Code color theme',properties:['openFile'],filters:[{name:'VS Code theme',extensions:['json','jsonc','code-theme']}]});
      return result.canceled?null:themes.importTheme(result.filePaths[0],app.getPath('userData'));
    });
    ipcMain.handle('appearance:get',event => { ownWindow(event);return loadTheme(); });
    ipcMain.handle('appearance:set',(event,value) => {
      ownWindow(event);
      if (!(['light','dark','system'].includes(value) || themes.listThemes(app.getPath('userData')).themes.some(t=>t.id===value))) throw new Error('Invalid theme.');
      fs.mkdirSync(app.getPath('userData'),{recursive:true});fs.writeFileSync(path.join(app.getPath('userData'),'appearance.json'),JSON.stringify({theme:value}),{mode:0o600});
      nativeTheme.themeSource=themeSource(value);
      for (const context of windows.values()) context.window.setBackgroundColor(nativeTheme.shouldUseDarkColors?'#1c201c':'#f8f8f6');
      return value;
    });
    ipcMain.handle('workspace:get',event => ownWindow(event).record.workspace);
    ipcMain.handle('workspace:set',(event,value) => {
      const context=ownWindow(event);context.record.workspace=workspacePreference(value);store.save();return context.record.workspace;
    });
    ipcMain.handle('connect',(event,config) => connectWindow(ownWindow(event,true),config));
    store.restore().forEach(makeWindow);
    app.on('activate',() => { if (!windows.size) store.restore().forEach(makeWindow); });
  });
  app.on('before-quit',() => {
    shuttingDown=true;
    for (const context of windows.values()) { saveWindow(context);context.attempt?.abort();context.connection?.child?.kill(); }
  });
  app.on('window-all-closed',() => { if (process.platform !== 'darwin') app.quit(); });
}
