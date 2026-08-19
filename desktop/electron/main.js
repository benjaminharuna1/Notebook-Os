const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

let pythonProcess = null;
let mainWindow = null;
let backendStarted = false;
let serverReady = false;
let backendOwned = false; // true if WE started the backend (not reused)

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
    console.error(`[Electron] Backend not found at: ${backendPath}`);
    app.quit();
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

  backendOwned = true;

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.on('error', (err) => {
    console.error(`[Electron] Failed to start Python: ${err.message}`);
    app.quit();
  });

  pythonProcess.on('exit', (code) => {
    console.log(`[Electron] Python exited with code ${code}`);
    pythonProcess = null;
    if (serverReady) {
      // Backend crashed after we were running — restart it
      console.log('[Electron] Backend crashed, restarting...');
      backendStarted = false;
      serverReady = false;
      backendOwned = false;
      setTimeout(() => {
        startPythonBackend();
        waitForServer(() => {
          if (mainWindow) mainWindow.reload();
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

  const req = http.get(HEALTH_CHECK_URL, { timeout: 2000 }, (res) => {
    if (res.statusCode === 200 && !serverReady) {
      res.resume();
      console.log('[Electron] Backend is ready');
      serverReady = true;
      callback();
    } else if (retries > 0) {
      res.resume();
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else if (!serverReady) {
      res.resume();
      console.error('[Electron] Backend failed to start after all retries');
      app.quit();
    }
  });

  req.on('error', () => {
    if (retries > 0 && !serverReady) {
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else if (!serverReady) {
      console.error('[Electron] Backend failed to respond');
      app.quit();
    }
  });

  req.on('timeout', () => {
    req.destroy();
    if (retries > 0 && !serverReady) {
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else if (!serverReady) {
      console.error('[Electron] Backend health check timed out');
      app.quit();
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
  if (pythonProcess && backendOwned) {
    console.log('[Electron] Killing Python backend...');
    killProcessTree(pythonProcess.pid);
    pythonProcess = null;
  }
}

async function launch() {
  console.log('[Electron] Starting Notebook AI OS...');
  console.log(`[Electron] Packaged: ${app.isPackaged}`);

  // Check if backend is already running (reuse it)
  const alreadyRunning = await checkHealth();
  if (alreadyRunning) {
    console.log('[Electron] Backend already running, reusing');
    serverReady = true;
    createWindow();
    return;
  }

  // Start our own backend
  startPythonBackend();
  waitForServer(() => {
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
});

app.on('activate', () => {
  if (mainWindow === null && serverReady) {
    createWindow();
  }
});
