#!/usr/bin/env bash
# dev.sh - start the backend (uvicorn) and frontend (Vite) together.
# Works on Windows (Git Bash / MSYS), WSL, macOS, and Linux.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"

BACKEND_PORT=8000
FRONTEND_PORT=5173
BACKEND_URL="http://localhost:$BACKEND_PORT"
FRONTEND_URL="http://localhost:$FRONTEND_PORT"

log_step() { echo ""; echo "==> $1"; }
log_ok()   { echo "    $1"; }
log_warn() { echo "    WARNING: $1"; }
log_err()  { echo "    ERROR: $1" >&2; }

# ---------------------------------------------------------------------------
# Backend: locate or create a venv, install deps, ensure .env
# ---------------------------------------------------------------------------
PYTHON=""
for candidate in "$BACKEND_DIR/.venv/Scripts/python.exe" "$BACKEND_DIR/.venv/bin/python"; do
  if [[ -f "$candidate" ]]; then
    PYTHON="$candidate"
    break
  fi
done

if [[ -z "$PYTHON" ]]; then
  log_step "No backend venv found. Creating backend/.venv ..."
  (cd "$BACKEND_DIR" && {
    if command -v uv >/dev/null 2>&1; then
      uv venv
    elif command -v python3 >/dev/null 2>&1; then
      python3 -m venv .venv
    elif command -v python >/dev/null 2>&1; then
      python -m venv .venv
    else
      log_err "Python not found. Install Python 3.10+ or uv first."
      exit 1
    fi
  })
  for candidate in "$BACKEND_DIR/.venv/Scripts/python.exe" "$BACKEND_DIR/.venv/bin/python"; do
    if [[ -f "$candidate" ]]; then PYTHON="$candidate"; break; fi
  done
fi

if [[ -z "$PYTHON" ]]; then
  log_err "Could not create a Python venv. Install Python 3.10+ or uv first."
  exit 1
fi

if ! "$PYTHON" -c "import fastapi, uvicorn, pydantic" >/dev/null 2>&1; then
  log_step "Installing backend dependencies (this may take a while)..."
  "$PYTHON" -m pip install --upgrade pip >/dev/null
  "$PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt"
fi

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  log_ok "Created backend/.env from backend/.env.example"
fi

# ---------------------------------------------------------------------------
# Frontend: ensure npm and node_modules
# ---------------------------------------------------------------------------
NPM="$(command -v npm || true)"
if [[ -z "$NPM" ]]; then
  log_err "npm not found. Install Node.js 20+ first."
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  log_step "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && "$NPM" install)
fi

# ---------------------------------------------------------------------------
# Port conflict check
# ---------------------------------------------------------------------------
if command -v curl >/dev/null 2>&1; then
  if curl -s -o /dev/null "$BACKEND_URL/health"; then
    log_warn "Something is already listening on port $BACKEND_PORT."
  fi
  if curl -s -o /dev/null "$FRONTEND_URL"; then
    log_warn "Something is already listening on port $FRONTEND_PORT."
  fi
fi

# ---------------------------------------------------------------------------
# Start servers
# ---------------------------------------------------------------------------
log_step "Starting backend (uvicorn) on $BACKEND_URL"
"$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload \
  > "$BACKEND_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

log_step "Starting frontend (Vite) on $FRONTEND_URL"
(cd "$FRONTEND_DIR" && "$NPM" run dev > "$FRONTEND_DIR/frontend.log" 2>&1) &
FRONTEND_PID=$!

cleanup() {
  echo ""
  log_step "Stopping servers..."
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  # On Windows, also kill the full process trees (uvicorn reloader, node children).
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      if command -v taskkill >/dev/null 2>&1; then
        [[ -n "${BACKEND_PID:-}" ]] && taskkill //PID "$BACKEND_PID" //T //F >/dev/null 2>&1 || true
        [[ -n "${FRONTEND_PID:-}" ]] && taskkill //PID "$FRONTEND_PID" //T //F >/dev/null 2>&1 || true
      fi
      ;;
  esac
}
trap cleanup INT TERM EXIT

# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------
wait_for() {
  local name="$1" url="$2" i
  printf "    Waiting for %s ..." "$name"
  for i in $(seq 1 60); do
    if curl -s -o /dev/null "$url" 2>/dev/null; then
      printf " ready\n"
      return 0
    fi
    printf "."
    sleep 1
  done
  printf " NOT ready after 60s\n"
  return 1
}

command -v curl >/dev/null 2>&1 || log_warn "curl not found; skipping health checks."

if command -v curl >/dev/null 2>&1; then
  wait_for "backend"  "$BACKEND_URL/health" || true
  wait_for "frontend" "$FRONTEND_URL"        || true
fi

# ---------------------------------------------------------------------------
# Open the browser and keep running
# ---------------------------------------------------------------------------
open_browser() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) cmd.exe /c start "" "$1" ;;
    Darwin) open "$1" ;;
    *) xdg-open "$1" >/dev/null 2>&1 & ;;
  esac
}
open_browser "$FRONTEND_URL"

echo ""
log_ok "Backend:  $BACKEND_URL  (log: backend/backend.log)"
log_ok "Frontend: $FRONTEND_URL (log: frontend/frontend.log)"
log_ok "Press Ctrl+C to stop both servers."

# Stay in the foreground while both servers run.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
echo "A server exited; shutting down the other..."
