const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const PORT = 8000;
const HOST = "127.0.0.1";
const APP_URL = `http://${HOST}:${PORT}`;

let mongoProcess = null;
let backendProcess = null;
let mainWindow = null;

function appRoot() {
  return app.isPackaged ? process.resourcesPath : path.resolve(__dirname, "..");
}

function ensureDir(target) {
  fs.mkdirSync(target, { recursive: true });
}

function executable(root, relativePath) {
  return path.join(root, ...relativePath);
}

function startMongo(root, userDataDir) {
  const mongod = executable(root, ["mongodb-win32-x86_64-windows-7.0.14", "bin", process.platform === "win32" ? "mongod.exe" : "mongod"]);
  const dbPath = path.join(userDataDir, "mongo-db");
  const logPath = path.join(userDataDir, "mongod.log");
  ensureDir(dbPath);

  mongoProcess = spawn(mongod, ["--dbpath", dbPath, "--logpath", logPath, "--bind_ip", HOST, "--port", "27017"], {
    cwd: root,
    windowsHide: true,
    stdio: "ignore"
  });

  mongoProcess.on("exit", () => {
    mongoProcess = null;
  });
}

function startBackend(root, userDataDir) {
  const python = executable(root, ["venv", "Scripts", process.platform === "win32" ? "python.exe" : "python"]);
  const documentsDir = path.join(userDataDir, "generated-documents");
  ensureDir(documentsDir);

  backendProcess = spawn(python, ["-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", String(PORT)], {
    cwd: root,
    windowsHide: true,
    env: {
      ...process.env,
      MONGO_URI: "mongodb://127.0.0.1:27017",
      MONGO_DB: "inventory_management",
      DOCUMENTS_DIR: documentsDir,
      CORS_ORIGINS: APP_URL,
      SESSION_HOURS: "12"
    },
    stdio: "ignore"
  });

  backendProcess.on("exit", () => {
    backendProcess = null;
  });
}

function waitForServer(timeoutMs = 30000) {
  const start = Date.now();

  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(`${APP_URL}/health`, response => {
        response.resume();
        if (response.statusCode === 200) return resolve();
        retry();
      });

      request.on("error", retry);
      request.setTimeout(1500, () => {
        request.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error("The local Inventory server did not start in time."));
      } else {
        setTimeout(check, 700);
      }
    };

    check();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 1100,
    minHeight: 720,
    title: "Inventory Management",
    backgroundColor: "#f8fbff",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.removeMenu();
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.loadURL(APP_URL);
}

async function boot() {
  const root = appRoot();
  const userDataDir = app.getPath("userData");

  try {
    startMongo(root, userDataDir);
    startBackend(root, userDataDir);
    await waitForServer();
    createWindow();
  } catch (error) {
    dialog.showErrorBox("Inventory Management could not start", error.message);
    app.quit();
  }
}

function shutdown() {
  if (backendProcess) backendProcess.kill();
  if (mongoProcess) mongoProcess.kill();
}

app.whenReady().then(boot);

app.on("window-all-closed", () => {
  shutdown();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", shutdown);
