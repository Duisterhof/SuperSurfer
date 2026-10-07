'use strict';
const { app, BrowserWindow, ipcMain, Menu, shell, session, nativeTheme, dialog } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const { connect } = require('./connection.cjs');
const { knownHosts } = require('./hosts.cjs');
const themes = require('./themes.cjs');
let window, connection, connecting = false, shuttingDown = false;
const setupPath = path.join(__dirname, 'setup.html');
const setupUrl = pathToFileURL(setupPath).href;

function loadConfig() { try { return JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), 'connection.json'), 'utf8')); } catch { return {}; } }
function loadTheme() { try { const theme = JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), 'appearance.json'), 'utf8')).theme; return typeof theme === 'string' && (['light','dark','system'].includes(theme) || theme.startsWith('vscode:')) ? theme : 'system'; } catch { return 'system'; } }
function themeSource(value) { if (['light','dark','system'].includes(value)) return value; const theme = themes.listThemes(app.getPath('userData')).themes.find(t => t.id === value); return /light/i.test(theme?.type || '') ? 'light' : 'dark'; }
function sendStatus(message) { if (window && !window.isDestroyed()) window.webContents.send('connection-status', message); }
function assertSetup(event) {
  if (event.sender !== window?.webContents || event.senderFrame.url !== setupUrl) throw new Error('Connection settings are available only in the setup window.');
}
function openExternal(url) {
  try { const parsed = new URL(url); if (['https:', 'http:'].includes(parsed.protocol) && !['127.0.0.1','localhost','[::1]'].includes(parsed.hostname)) shell.openExternal(parsed.href); } catch {}
}
function showSetup() { window.loadFile(setupPath); }
function makeWindow() {
  window = new BrowserWindow({ width: 1480, height: 940, minWidth: 1000, minHeight: 680, title: 'SuperSurfer', backgroundColor: nativeTheme.shouldUseDarkColors ? '#1c201c' : '#f8f8f6', titleBarStyle: 'hiddenInset', trafficLightPosition: { x: 18, y: 20 }, show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, sandbox: true, nodeIntegration: false, webSecurity: true } });
  window.once('ready-to-show', () => window.show());
  window.webContents.setWindowOpenHandler(({ url }) => { openExternal(url); return { action: 'deny' }; });
  window.webContents.on('will-navigate', (event, url) => {
    if (url === setupUrl || (connection && new URL(url).origin === connection.origin)) return;
    event.preventDefault(); openExternal(url);
  });
  window.webContents.on('will-attach-webview', event => event.preventDefault());
  window.on('closed', () => { window = null; });
  showSetup();
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.focus(); } });
  app.whenReady().then(() => {
    nativeTheme.themeSource = themeSource(loadTheme());
    session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
    session.defaultSession.webRequest.onBeforeSendHeaders((details, callback) => {
      if (connection && details.url.startsWith(connection.origin + '/api/')) details.requestHeaders.Authorization = `Bearer ${connection.token}`;
      callback({ requestHeaders: details.requestHeaders });
    });
    ipcMain.handle('configuration', event => { assertSetup(event); return loadConfig(); });
    ipcMain.handle('hosts:list', event => { assertSetup(event); return knownHosts(); });
    ipcMain.handle('themes:list', event => { if (event.sender !== window?.webContents) throw new Error('Unknown window.'); return themes.listThemes(app.getPath('userData')); });
    ipcMain.handle('themes:import', async event => {
      if (event.sender !== window?.webContents) throw new Error('Unknown window.');
      const result = await dialog.showOpenDialog(window, { title: 'Import VS Code color theme', properties: ['openFile'], filters: [{ name: 'VS Code theme', extensions: ['json','jsonc','code-theme'] }] });
      return result.canceled ? null : themes.importTheme(result.filePaths[0], app.getPath('userData'));
    });
    ipcMain.handle('appearance:get', event => { if (event.sender !== window?.webContents) throw new Error('Unknown window.'); return loadTheme(); });
    ipcMain.handle('appearance:set', (event, value) => {
      if (event.sender !== window?.webContents || !(['light','dark','system'].includes(value) || themes.listThemes(app.getPath('userData')).themes.some(t => t.id === value))) throw new Error('Invalid theme.');
      fs.mkdirSync(app.getPath('userData'), { recursive: true });
      fs.writeFileSync(path.join(app.getPath('userData'), 'appearance.json'), JSON.stringify({theme:value}), {mode:0o600});
      nativeTheme.themeSource = themeSource(value);
      window.setBackgroundColor(nativeTheme.shouldUseDarkColors ? '#1c201c' : '#f8f8f6');
      return value;
    });
    ipcMain.handle('workspace:get', event => {
      if (event.sender !== window?.webContents) throw new Error('Unknown window.');
      try { return JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), 'workspace.json'), 'utf8')); } catch { return null; }
    });
    ipcMain.handle('workspace:set', (event, value) => {
      if (event.sender !== window?.webContents || !value || typeof value !== 'object') throw new Error('Invalid workspace preference.');
      const preference = {
        view: ['workspace','compute','settings'].includes(value.view) ? value.view : 'workspace',
        tab: ['overview','runs','results','compute'].includes(value.tab) ? value.tab : 'overview',
        projectId: typeof value.projectId === 'string' ? value.projectId.slice(0,200) : null,
        experimentId: typeof value.experimentId === 'string' ? value.experimentId.slice(0,200) : null,
        chatVisible: value.chatVisible !== false,
        chatWidth: Number.isFinite(value.chatWidth) ? Math.max(280, Math.min(760, value.chatWidth)) : 390,
        chatMaximized: value.chatMaximized === true,
      };
      fs.mkdirSync(app.getPath('userData'), { recursive: true });
      fs.writeFileSync(path.join(app.getPath('userData'), 'workspace.json'), JSON.stringify(preference), {mode:0o600});
      return preference;
    });
    ipcMain.handle('connect', async (event, config) => {
      assertSetup(event);
      if (connecting) return { error: 'A connection is already in progress.' };
      connecting = true;
      try {
        const next = await connect(config, sendStatus);
        connection?.child?.kill();
        connection = next;
        fs.mkdirSync(app.getPath('userData'), { recursive: true });
        fs.writeFileSync(path.join(app.getPath('userData'), 'connection.json'), JSON.stringify(next.config), { mode: 0o600 });
        next.child?.once('exit', () => {
          if (connection === next && !shuttingDown && window && !window.isDestroyed()) {
            connection = null;
            showSetup();
            window.webContents.once('did-finish-load', () => sendStatus('Connection lost. Your remote work is still running. Reconnect below.'));
          }
        });
        await window.loadURL(next.origin);
        return { ok: true };
      } catch (error) { return { error: error.message }; }
      finally { connecting = false; }
    });
    const template = [
      ...(process.platform === 'darwin' ? [{ label: 'SuperSurfer', submenu: [{ role: 'about' }, { type: 'separator' }, { label: 'Connection Settings…', accelerator: 'CmdOrCtrl+,', click: showSetup }, { type: 'separator' }, { role: 'hide' }, { role: 'hideOthers' }, { role: 'unhide' }, { type: 'separator' }, { role: 'quit' }] }] : []),
      { label: 'Edit', submenu: [{ role: 'undo' }, { role: 'redo' }, { type: 'separator' }, { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' }] },
      { label: 'View', submenu: [{ role: 'reload' }, { role: 'togglefullscreen' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { type: 'separator' }, { label: 'Connection Settings…', click: showSetup }] },
      { label: 'Window', submenu: [{ role: 'minimize' }, { role: 'zoom' }, { role: 'close' }] },
    ];
    Menu.setApplicationMenu(Menu.buildFromTemplate(template));
    makeWindow();
    app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) makeWindow(); });
  });
  app.on('before-quit', () => { shuttingDown = true; connection?.child?.kill(); });
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
}
