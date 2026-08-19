const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

let pythonProcess = null;
let mainWindow = null;

const PYTHON_PORT = 8199;
const HEALTH_CHECK_URL = `http://127.0.0.1:${PYTHON_PORT}/health`;
const HEALTH_CHECK_RETRIES = 60;
const HEALTH_CHECK_DELAY = 1000;

function getBackendPath() {
  if (app.isPackaged) {
    // Production: PyInstaller output in resources/backend/
    const exeName = process.platform === 'win32' ? 'notebook-backend.exe' : 'notebook-backend';
    return path.join(process.resourcesPath, 'backend', exeName);
  }
  // Development: use venv Python
  const pythonName = process.platform === 'win32' ? 'python.exe' : 'python3';
  return path.join(__dirname, '..', '..', 'backend', '.venv', 'Scripts', pythonName);
}

function getBackendCwd() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend');
  }
  return path.join(__dirname, '..', '..', 'backend');
}

function startPythonBackend() {
  const backendPath = getBackendPath();
  const backendCwd = getBackendCwd();

  console.log(`[Electron] Backend path: ${backendPath}`);
  console.log(`[Electron] Backend cwd: ${backendCwd}`);

  if (!fs.existsSync(backendPath)) {
    console.error(`[Electron] Backend not found at: ${backendPath}`);
    app.quit();
    return;
  }

  if (app.isPackaged) {
    // Production: run PyInstaller exe directly
    pythonProcess = spawn(backendPath, [], {
      cwd: backendCwd,
      env: {
        ...process.env,
        APP_ENV: 'desktop',
        HOST: '127.0.0.1',
        PORT: String(PYTHON_PORT),
        FRONTEND_PATH: path.join(process.resourcesPath, 'frontend', 'build'),
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } else {
    // Development: use uvicorn with --reload
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
  });
}

function waitForServer(callback, retries = HEALTH_CHECK_RETRIES) {
  const req = http.get(HEALTH_CHECK_URL, { timeout: 2000 }, (res) => {
    if (res.statusCode === 200) {
      console.log('[Electron] Backend is ready');
      callback();
    } else if (retries > 0) {
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else {
      console.error('[Electron] Backend failed to start after all retries');
      app.quit();
    }
  });

  req.on('error', () => {
    if (retries > 0) {
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else {
      console.error('[Electron] Backend failed to respond');
      app.quit();
    }
  });

  req.on('timeout', () => {
    req.destroy();
    if (retries > 0) {
      setTimeout(() => waitForServer(callback, retries - 1), HEALTH_CHECK_DELAY);
    } else {
      console.error('[Electron] Backend health check timed out');
      app.quit();
    }
  });
}

function createWindow() {
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

  // Load the backend URL (serves both API + static frontend)
  mainWindow.loadURL(`http://127.0.0.1:${PYTHON_PORT}`);

  // Show window when ready to prevent flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Open external links in system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // DevTools in development only
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }
}

function killPythonBackend() {
  if (pythonProcess) {
    console.log('[Electron] Killing Python backend...');
    pythonProcess.kill();
    pythonProcess = null;
  }
}

// App lifecycle
app.whenReady().then(() => {
  console.log('[Electron] Starting Notebook AI OS...');
  console.log(`[Electron] Packaged: ${app.isPackaged}`);

  startPythonBackend();

  waitForServer(() => {
    createWindow();
  });
});

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
  if (mainWindow === null) {
    createWindow();
  }
});
