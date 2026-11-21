const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('primepickDesktop', {
  version: process.env.npm_package_version || '0.1.0',
  isDesktop: true,
});
