const { app, BrowserWindow, dialog, shell } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const net = require('node:net');
const path = require('node:path');
const crypto = require('node:crypto');

let mainWindow = null;
let backendProcess = null;
let backendLog = null;
let backendPort = null;
let shutdownToken = null;
let quitting = false;

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = address && typeof address === 'object' ? address.port : null;
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

function launchBackend(port) {
  const env = {
    ...process.env,
    PRIMEPICK_DATA_DIR: app.getPath('userData'),
    PRIMEPICK_SHUTDOWN_TOKEN: shutdownToken,
  };
  const logPath = path.join(app.getPath('userData'), 'logs', 'backend.log');
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  backendLog = fs.createWriteStream(logPath, { flags: 'a' });

  if (app.isPackaged) {
    // PyInstaller --onedir writes <distpath>/PrimePickGoodsBackend/PrimePickGoodsBackend.exe
    const executable = path.join(process.resourcesPath, 'backend', 'PrimePickGoodsBackend', 'PrimePickGoodsBackend.exe');
    env.PLAYWRIGHT_BROWSERS_PATH = path.join(process.resourcesPath, 'playwright-browsers');
    backendProcess = spawn(executable, ['--host', '127.0.0.1', '--port', String(port)], {
      cwd: path.dirname(executable),
      env,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } else {
    const projectRoot = path.resolve(__dirname, '..');
    const backendDir = path.join(projectRoot, 'backend');
    const python = process.env.PYTHON_EXECUTABLE || (process.platform === 'win32' ? 'python' : 'python3');
    backendProcess = spawn(python, [path.join(backendDir, 'run_backend.py'), '--host', '127.0.0.1', '--port', String(port)], {
      cwd: backendDir,
      env: { ...env, PYTHONPATH: backendDir },
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  }
  backendProcess.stdout.pipe(backendLog, { end: false });
  backendProcess.stderr.pipe(backendLog, { end: false });

  backendProcess.once('error', (error) => {
    console.error('PrimePick backend did not start:', error.message);
  });
  backendProcess.once('exit', (code) => {
    if (backendLog) {
      backendLog.end();
      backendLog = null;
    }
    if (!quitting && code !== 0 && mainWindow && !mainWindow.isDestroyed()) {
      dialog.showMessageBox(mainWindow, {
        type: 'error',
        title: 'PrimePick Goods could not continue',
        message: 'The local app service stopped unexpectedly.',
        detail: 'Please close the app and open it again. Your saved listings remain on this computer.',
        buttons: ['Close app'],
      }).then(() => app.quit());
    }
  });
}

function waitForBackend(port, attempts = 100) {
  return new Promise((resolve, reject) => {
    let remaining = attempts;
    const check = () => {
      if (!backendProcess || backendProcess.exitCode !== null) {
        reject(new Error('Local app service stopped before it became ready.'));
        return;
      }
      const request = http.get({ hostname: '127.0.0.1', port, path: '/api/health', timeout: 700 }, (response) => {
        response.resume();
        if (response.statusCode === 200) {
          resolve();
          return;
        }
        retry();
      });
      request.on('error', retry);
      request.on('timeout', () => request.destroy());
    };
    const retry = () => {
      remaining -= 1;
      if (remaining <= 0) {
        reject(new Error('The local app service did not become ready in time.'));
        return;
      }
      setTimeout(check, 300);
    };
    check();
  });
}

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1390,
    height: 930,
    minWidth: 960,
    minHeight: 680,
    show: false,
    backgroundColor: '#f5f7f9',
    icon: path.join(__dirname, 'assets', 'primepick.ico'),
    title: 'PrimePick Goods Listing Generator',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://') || url.startsWith('http://')) shell.openExternal(url);
    return { action: 'deny' };
  });
  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.loadURL(`http://127.0.0.1:${port}`).then(() => mainWindow && mainWindow.show());
}

function waitForBackendExit(timeoutMs = 8000) {
  return new Promise((resolve) => {
    if (!backendProcess || backendProcess.exitCode !== null || backendProcess.signalCode !== null) {
      resolve();
      return;
    }
    const onExit = () => {
      clearTimeout(timer);
      resolve();
    };
    const timer = setTimeout(() => {
      backendProcess?.removeListener('exit', onExit);
      resolve();
    }, timeoutMs);
    backendProcess.once('exit', onExit);
  });
}

function requestBackendShutdown() {
  return new Promise((resolve) => {
    if (!backendProcess || backendProcess.exitCode !== null || !backendPort) {
      resolve();
      return;
    }
    const request = http.request({
      hostname: '127.0.0.1',
      port: backendPort,
      path: '/api/internal/shutdown',
      method: 'POST',
      headers: { 'x-primepick-shutdown-token': shutdownToken },
      timeout: 1200,
    }, (response) => {
      response.resume();
      response.on('end', () => resolve());
    });
    request.on('error', () => resolve());
    request.on('timeout', () => { request.destroy(); resolve(); });
    request.end();
    setTimeout(resolve, 1600);
  });
}

app.whenReady().then(async () => {
  try {
    backendPort = await findFreePort();
    shutdownToken = crypto.randomBytes(32).toString('hex');
    launchBackend(backendPort);
    await waitForBackend(backendPort);
    createWindow(backendPort);
  } catch {
    await dialog.showMessageBox({
      type: 'error',
      title: 'PrimePick Goods could not start',
      message: 'The local app service did not start.',
      detail: 'Try opening the app again. If this keeps happening, reinstall PrimePick Goods or contact your support person.',
      buttons: ['Close'],
    });
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0 && backendPort) createWindow(backendPort);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', (event) => {
  if (quitting) return;
  event.preventDefault();
  quitting = true;
  requestBackendShutdown().then(() => waitForBackendExit()).finally(() => {
    if (backendProcess && backendProcess.exitCode === null) backendProcess.kill();
    if (backendLog) {
      backendLog.end();
      backendLog = null;
    }
    app.exit(0);
  });
});
