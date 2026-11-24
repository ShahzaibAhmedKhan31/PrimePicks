const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('primepickDesktop', {
  version: process.env.npm_package_version || '0.1.0',
  isDesktop: true,
  // Built-in AliExpress browser panel (see desktop/main.cjs).
  productBrowser: {
    open: (url, bounds) => ipcRenderer.invoke('product-browser:open', { url, bounds }),
    show: (bounds, visible = true) => ipcRenderer.invoke('product-browser:show', { bounds, visible }),
    back: () => ipcRenderer.invoke('product-browser:navigate', 'back'),
    reload: () => ipcRenderer.invoke('product-browser:navigate', 'reload'),
    getPage: () => ipcRenderer.invoke('product-browser:get-page'),
    close: () => ipcRenderer.invoke('product-browser:close'),
    onState: (callback) => {
      const listener = (_event, state) => callback(state);
      ipcRenderer.on('product-browser:state', listener);
      return () => ipcRenderer.removeListener('product-browser:state', listener);
    },
  },
});
