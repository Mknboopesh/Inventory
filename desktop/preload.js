const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("inventoryDesktop", {
  platform: process.platform,
  version: "1.0.0"
});
