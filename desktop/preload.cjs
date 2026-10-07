'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('superSurferDesktop', {
  configuration: () => ipcRenderer.invoke('configuration'),
  connectionReady: () => ipcRenderer.invoke('connection:ready'),
  cancelConnection: () => ipcRenderer.invoke('connection:cancel'),
  connect: config => ipcRenderer.invoke('connect', config),
  listHosts: () => ipcRenderer.invoke('hosts:list'),
  listThemes: () => ipcRenderer.invoke('themes:list'),
  importTheme: () => ipcRenderer.invoke('themes:import'),
  getTheme: () => ipcRenderer.invoke('appearance:get'),
  setTheme: value => ipcRenderer.invoke('appearance:set', value),
  getWorkspace: () => ipcRenderer.invoke('workspace:get'),
  setWorkspace: value => ipcRenderer.invoke('workspace:set', value),
  onStatus: callback => { const listener = (_, message) => callback(message); ipcRenderer.on('connection-status', listener); return () => ipcRenderer.removeListener('connection-status', listener); },
});
