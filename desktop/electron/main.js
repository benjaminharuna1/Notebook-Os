const { app, BrowserWindow, shell, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

let pythonProcess = null;
let mainWindow = null;
let splashWindow = null;
let backendStarted = false;
let serverReady = false;
let waitingForServer = false;
let backend_stderr = '';

const PYTHON_PORT = 8199;
const HEALTH_CHECK_URL = `http://127.0.0.1:${PYTHON_PORT}/health`;
const HEALTH_CHECK_RETRIES = 60;
const HEALTH_CHECK_DELAY = 1000;

function getDataDir() {
  if (app.isPackaged) {
    return path.join(app.getPath('userData'), 'data');
  }
  return path.join(__dirname, '..', '..', 'backend', 'data');
}

function getBackendPath() {
  if (app.isPackaged) {
    const exeName = process.platform === 'win32' ? 'notebook-backend.exe' : 'notebook-backend';
    return path.join(process.resourcesPath, 'backend', exeName);
  }
  const pythonName = process.platform === 'win32' ? 'python.exe' : 'python3';
  return path.join(__dirname, '..', '..', 'backend', '.venv', 'Scripts', pythonName);
}

function getBackendCwd() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend');
  }
  return path.join(__dirname, '..', '..', 'backend');
}

function ensureDataDir() {
  const dataDir = getDataDir();
  const subdirs = ['', 'uploads', 'processed', 'chroma_db'];
  subdirs.forEach(sub => {
    const dir = path.join(dataDir, sub);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  });
  return dataDir;
}

function showErrorAndQuit(title, message) {
  console.error(`[Electron] ${title}: ${message}`);
  dialog.showErrorBox(title, message);
  app.quit();
}

function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 500,
    height: 340,
    frame: false,
    transparent: true,
    resizable: false,
    skipTaskbar: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #0f0f13;
    color: #e0e0e0;
    display: flex; align-items: center; justify-content: center;
    height: 100vh; overflow: hidden;
    -webkit-app-region: drag;
  }
  .card {
    text-align: center; padding: 40px 50px;
    background: #1a1a24; border-radius: 16px;
    border: 1px solid #2a2a3a;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  }
  h1 { font-size: 22px; font-weight: 600; margin-bottom: 8px; color: #fff; }
  p { font-size: 13px; color: #888; margin-bottom: 24px; }
  .spinner {
    width: 32px; height: 32px; margin: 0 auto;
    border: 3px solid #2a2a3a; border-top-color: #7c6aef;
    border-radius: 50%; animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style></head>
<body>
  <div class="card">
    <h1>Notebook AI OS</h1>
    <p>Starting backend server...</p>
    <div class="spinner"></div>
  </div>
</body></html>`;

  splashWindow.loadURL(`data:text/html,${encodeURIComponent(html)}`);
  splashWindow.on('closed', () => { splashWindow = null; });
}

function killProcessTree(pid) {
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/F', '/T', '/PID', String(pid)], { stdio: 'ignore' });
    } else {
      process.kill(-pid, 'SIGTERM');
    }
  } catch (e) {
    try { process.kill(pid, 'SIGKILL'); } catch (_) {}
  }
}

function startPythonBackend() {
  if (backendStarted) return;
  backendStarted = true;

  const backendPath = getBackendPath();
  const backendCwd = getBackendCwd();
  const dataDir = ensureDataDir();

  console.log(`[Electron] Backend path: ${backendPath}`);
  console.log(`[Electron] Backend cwd: ${backendCwd}`);
  console.log(`[Electron] Data dir: ${dataDir}`);

  if (!fs.existsSync(backendPath)) {
    showErrorAndQuit(
      'Backend not found',
      `Could not find notebook-backend at:\n${backendPath}\n\nThe application may need to be reinstalled.`
    );
    return;
  }

  const frontendPath = app.isPackaged
    ? path.join(process.resourcesPath, 'frontend', 'build')
    : '';

  const env = {
    ...process.env,
    APP_ENV: 'desktop',
    HOST: '127.0.0.1',
    PORT: String(PYTHON_PORT),
    DATABASE_URL: `sqlite+aiosqlite:///${path.join(dataDir, 'notebook.db')}`,
    CHROMA_DB_PATH: path.join(dataDir, 'chroma_db'),
    UPLOAD_DIR: path.join(dataDir, 'uploads'),
    PROCESSED_DIR: path.join(dataDir, 'processed'),
  };

  if (frontendPath) {
    env.FRONTEND_PATH = frontendPath;
  }

  if (app.isPackaged) {
    pythonProcess = spawn(backendPath, [], {
      cwd: backendCwd,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });
  } else {
    pythonProcess = spawn(backendPath, [
      '-m', 'uvicorn', 'app.main:app',
      '--host', '127.0.0.1',
      '--port', String(PYTHON_PORT),
      '--reload',
    ], {
      cwd: backendCwd,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  }

  backend_stderr = '';

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    const chunk = data.toString().trim();
    console.error(`[Python] ${chunk}`);
    backend_stderr += chunk + '\n';
  });

  pythonProcess.on('error', (err) => {
    showErrorAndQuit(
      'Failed to start backend',
      `Could not launch notebook-backend.exe:\n${err.message}\n\n${backend_stderr || 'No additional error output.'}`
    );
  });

  pythonProcess.on('exit', (code) => {
    console.log(`[Electron] Python exited with code ${code}`);
    pythonProcess = null;
    if (serverReady) {
      // Backend crashed after we were running — restart it
      console.log('[Electron] Backend crashed, restarting...');
      backendStarted = false;
      serverReady = false;
      waitingForServer = false;
      setTimeout(() => {
        startPythonBackend();
        waitForServer(() => {
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.reload();
          } else {
            createWindow();
          }
        });
      }, 1000);
    }
  });
}

function checkHealth() {
  return new Promise((resolve) => {
    const req = http.get(HEALTH_CHECK_URL, { timeout: 2000 }, (res) => {
      resolve(res.statusCode === 200);
      res.resume();
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function waitForServer(callback, retries = HEALTH_CHECK_RETRIES) {
  if (serverReady) {
    callback();
    return;
  }
  if (waitingForServer) {
    console.log('[Electron] Already waiting for server, skipping duplicate call');
    return;
  }
  waitingForServer = true;

  const req = http.get(HEALTH_CHECK_URL, { timeout: 2000 }, (res) => {
    if (res.statusCode === 200 && !serverReady) {
      res.resume();
      console.log('[Electron] Backend is ready');
      serverReady = true;
      waitingForServer = false;
      callback();
    } else if (retries > 0) {
      res.resume();
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else if (!serverReady) {
      res.resume();
      waitingForServer = false;
      showErrorAndQuit(
        'Backend timed out',
        `The backend server did not respond after ${HEALTH_CHECK_RETRIES} seconds.\n\nLast error output:\n${backend_stderr || '(none)'}`
      );
    }
  });

  req.on('error', () => {
    if (retries > 0 && !serverReady) {
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else if (!serverReady) {
      waitingForServer = false;
      showErrorAndQuit(
        'Backend not responding',
        `Could not connect to the backend server on port ${PYTHON_PORT}.\n\nLast error output:\n${backend_stderr || '(none)'}`
      );
    }
  });

  req.on('timeout', () => {
    req.destroy();
    if (retries > 0 && !serverReady) {
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else if (!serverReady) {
      waitingForServer = false;
      showErrorAndQuit(
        'Backend health check timed out',
        `Health check timed out after ${HEALTH_CHECK_RETRIES} attempts.\n\nLast error output:\n${backend_stderr || '(none)'}`
      );
    }
  });
}

function createWindow() {
  if (mainWindow) {
    mainWindow.focus();
    return;
  }

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    title: 'Notebook AI OS',
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    show: false,
    titleBarStyle: 'default',
  });

  mainWindow.loadURL(`http://127.0.0.1:${PYTHON_PORT}`);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }
}

function killPythonBackend() {
  // Kill by tracked PID first
  if (pythonProcess) {
    console.log(`[Electron] Killing Python backend (PID ${pythonProcess.pid})...`);
    killProcessTree(pythonProcess.pid);
    pythonProcess = null;
    return;
  }

  // Fallback: find and kill whatever is listening on our port
  console.log(`[Electron] No tracked PID, scanning port ${PYTHON_PORT}...`);
  try {
    const output = require('child_process').execSync(
      `netstat -ano | findstr :${PYTHON_PORT} | findstr LISTENING`,
      { encoding: 'utf8', timeout: 3000 }
    );
    const lines = output.trim().split('\n');
    const pids = new Set();
    for (const line of lines) {
      const parts = line.trim().split(/\s+/);
      const pid = parts[parts.length - 1];
      if (pid && pid !== '0' && !isNaN(pid)) {
        pids.add(pid);
      }
    }
    for (const pid of pids) {
      console.log(`[Electron] Killing orphan process on port ${PYTHON_PORT} (PID ${pid})`);
      killProcessTree(Number(pid));
    }
  } catch (e) {
    // netstat findstr returns exit code 1 when no match — that's fine
    console.log(`[Electron] No orphan process found on port ${PYTHON_PORT}`);
  }
}

async function launch() {
  console.log('[Electron] Starting Notebook AI OS...');
  console.log(`[Electron] Packaged: ${app.isPackaged}`);

  createSplashWindow();

  const alreadyRunning = await checkHealth();
  if (alreadyRunning) {
    console.log('[Electron] Backend already running, reusing');
    serverReady = true;
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
    }
    createWindow();
    return;
  }

  startPythonBackend();
  waitForServer(() => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
    }
    createWindow();
  });
}

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(launch);
}

app.on('window-all-closed', () => {
  killPythonBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killPythonBackend();
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.destroy();
    splashWindow = null;
  }
});

app.on('activate', () => {
  if (mainWindow === null && serverReady) {
    createWindow();
  }
});
