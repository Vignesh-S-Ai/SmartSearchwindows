// Preload script - exposes safe APIs to renderer
const { contextBridge, ipcRenderer } = require('electron');


contextBridge.exposeInMainWorld('api', {
  search: (query) => ipcRenderer.invoke('search', query),
  getStatus: () => ipcRenderer.invoke('get-status'),
  startIndex: () => ipcRenderer.invoke('start-index'),
  openFile: (path) => ipcRenderer.invoke('open-file', path),
  showInFolder: (path) => ipcRenderer.invoke('show-in-folder', path),
  previewFile: (path) => ipcRenderer.invoke('preview-file', path),
  hideWindow: () => ipcRenderer.invoke('hide-window'),
  setAutoLaunch: (enable) => ipcRenderer.invoke('set-auto-launch', enable),
  onFocusSearch: (callback) => ipcRenderer.on('focus-search', callback)
});
