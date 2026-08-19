# Building Notebook AI OS Desktop App

This guide covers building the Notebook AI OS desktop application for Windows.

## How to Compile to EXE (Quick Reference)

**Full build command (from project root):**

```bash
cd desktop
npm install
npm run build:all
```

**Output:** `desktop/release/Notebook AI OS Setup 0.1.0.exe`

**What happens:**
1. Frontend compiles to static files (`frontend/build/`)
2. Python backend freezes to exe (`backend/dist/notebook-backend/notebook-backend.exe`)
3. Electron packages everything into Windows installer (`desktop/release/*.exe`)

---

## Prerequisites

### Required
- **Node.js** 18+ — https://nodejs.org
- **Python** 3.10+ with `uv` package manager — https://docs.astral.sh/uv/
- **PyInstaller** — `pip install pyinstaller` (or `uv pip install pyinstaller`)

### Verify installations
```bash
node --version    # Should show v18+
python --version  # Should show 3.10+
pyinstaller --version  # Should show 6.x.x
```

## One-Time Setup

Install all dependencies:

```bash
# From project root
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..
cd desktop && npm install && cd ..
```

## Build for Distribution

### Option A: Single Command (Recommended)

```bash
cd desktop
npm run build:all
```

This runs all three steps automatically.

### Option B: Step-by-Step

```bash
# Step 1: Build frontend (compile SvelteKit to static files)
cd frontend
npm run build
cd ..

# Step 2: Build backend (freeze Python to exe)
cd backend
pyinstaller backend.spec --clean --noconfirm
cd ..

# Step 3: Package as Windows installer
cd desktop
npm run build:electron
cd ..
```

### Output Location

```
desktop/release/
└── Notebook AI OS Setup 0.1.0.exe    ← Windows installer
```

### File Size

~500MB-1GB (includes Python runtime, ChromaDB, sentence-transformers, all dependencies)

## Build Steps (Detailed)

### Step 1: Build Frontend

```bash
cd frontend
npm run build
```

Output: `frontend/build/` (static HTML/CSS/JS)

### Step 2: Build Backend (PyInstaller)

```bash
cd backend
../backend/.venv/Scripts/pyinstaller.exe backend.spec --clean --noconfirm
```

Output: `backend/dist/notebook-backend/` (Python app + dependencies)

**Note:** First build takes 5-15 minutes depending on your machine. Subsequent builds are faster.

### Step 3: Build Electron Installer

```bash
cd desktop
npm run build:electron
```

Output: `desktop/release/*.exe` (Windows installer)

## Development Mode

To run the app in development mode:

```bash
# Terminal 1: Backend
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8199 --reload

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: Electron
cd desktop
npm start
```

Or use the concurrent dev command:

```bash
cd desktop
npm run dev
```

## Troubleshooting

### PyInstaller Fails with "Module not found"

Add the missing module to `hiddenimports` in `backend/backend.spec`:

```python
hiddenimports=[
    # ... existing imports ...
    'missing_module_name',
]
```

### Frontend Build Fails

Ensure `frontend/build/` exists after `npm run build`. If it fails:

```bash
cd frontend
rm -rf node_modules
npm install
npm run build
```

### Electron Builder Fails

1. Ensure `backend/dist/notebook-backend/notebook-backend.exe` exists
2. Ensure `frontend/build/` exists
3. Check `desktop/release/` directory is writable

### App Shows Blank Screen

The backend may not be ready yet. The app waits up to 60 seconds for the backend to start. Check:

1. Is the backend process running?
2. Can you access `http://127.0.0.1:8199/health` in a browser?

### Windows SmartScreen Warning

Unsigned executables trigger SmartScreen. Options:

1. **Recommended:** Sign the executable with a code signing certificate
2. **Developer:** Right-click → Properties → Unblock
3. **Temporary:** Click "More info" → "Run anyway"

## Architecture

```
Notebook AI OS.exe
├── resources/
│   ├── backend/
│   │   └── notebook-backend.exe  (PyInstaller frozen Python)
│   └── frontend/
│       └── build/                (SvelteKit static files)
└── electron/
    ├── main.js                   (Electron main process)
    └── preload.js                (Context bridge)
```

**Runtime flow:**
1. Electron starts
2. Spawns `notebook-backend.exe` on port 8199
3. Waits for `/health` endpoint to respond
4. Loads `http://127.0.0.1:8199` in BrowserWindow
5. FastAPI serves both API (`/api/v1/*`) and static frontend (`/*`)
6. On quit, kills Python process

## Customization

### Change Port

Edit `desktop/electron/main.js`:
```javascript
const PYTHON_PORT = 8199;  // Change this
```

### Change App Name

Edit `desktop/package.json`:
```json
{
  "productName": "Your App Name"
}
```

### Add Files to Backend Bundle

Edit `backend/backend.spec`:
```python
datas=[
    # ... existing data ...
    ('path/to/file', 'destination/in/bundle'),
]
```

## CI/CD (Optional)

For automated builds, add to your CI pipeline:

```yaml
- name: Build Desktop App
  run: |
    cd backend
    pip install pyinstaller
    pyinstaller backend.spec --clean --noconfirm
    
    cd ../frontend
    npm ci
    npm run build
    
    cd ../desktop
    npm ci
    npm run build:electron
```

## Git Ignore Rules

The following folders are **ignored** (not pushed to GitHub):

| Folder | Reason |
|--------|--------|
| `backend/dist/` | PyInstaller output (generated) |
| `backend/.venv/` | Python virtual environment |
| `backend/data/` | Runtime data (DB, uploads) |
| `backend/models/` | Downloaded GGUF models |
| `frontend/build/` | Compiled frontend (generated) |
| `frontend/node_modules/` | npm dependencies |
| `desktop/node_modules/` | npm dependencies |
| `desktop/release/` | Build output (generated) |

**What IS pushed to GitHub:**

| File | Purpose |
|------|---------|
| `backend/backend.spec` | PyInstaller configuration |
| `desktop/package.json` | Electron dependencies |
| `desktop/electron/main.js` | Electron main process |
| `desktop/electron/preload.js` | Context bridge |
| `desktop/assets/icon.ico` | App icon |
| `desktop/BUILD.md` | This file |
