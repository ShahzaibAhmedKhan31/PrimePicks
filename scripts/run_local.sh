#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
cd "$ROOT"

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

HOST_OS="$(uname -s 2>/dev/null || printf 'unknown')"
case "$HOST_OS" in
  MINGW*|MSYS*|CYGWIN*)
    PLATFORM="windows"
    VENV_PYTHON_SUFFIX="Scripts/python.exe"
    if command -v py >/dev/null 2>&1; then
      PYTHON=(py -3)
    elif command -v python >/dev/null 2>&1; then
      PYTHON=(python)
    elif command -v python3 >/dev/null 2>&1; then
      PYTHON=(python3)
    else
      fail 'Install Python 3.11 or newer for Windows and make it available in Git Bash PATH.'
    fi
    ;;
  Darwin*)
    PLATFORM="macos"
    VENV_PYTHON_SUFFIX="bin/python"
    if command -v python3 >/dev/null 2>&1; then
      PYTHON=(python3)
    elif command -v python >/dev/null 2>&1; then
      PYTHON=(python)
    else
      fail 'Install Python 3.11 or newer and make python3 available in Bash PATH.'
    fi
    ;;
  *)
    PLATFORM="linux"
    VENV_PYTHON_SUFFIX="bin/python"
    if command -v python3 >/dev/null 2>&1; then
      PYTHON=(python3)
    elif command -v python >/dev/null 2>&1; then
      PYTHON=(python)
    else
      fail 'Install Python 3.11 or newer and make python3 available in Bash PATH.'
    fi
    ;;
esac

if ! "${PYTHON[@]}" -c 'import sys; print("Python " + sys.version.split()[0]); sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  fail 'Python 3.11 or newer is required.'
fi

command -v node >/dev/null 2>&1 || fail 'Install Node.js 20 or newer and make node available in Bash PATH.'
command -v npm >/dev/null 2>&1 || fail 'npm was not found. Install Node.js 20 or newer, which includes npm.'
NODE_VERSION="$(node --version | sed 's/^v//')"
NODE_MAJOR="${NODE_VERSION%%.*}"
[[ "$NODE_MAJOR" =~ ^[0-9]+$ ]] || fail "Could not read the Node.js version: $NODE_VERSION"
(( NODE_MAJOR >= 20 )) || fail "Node.js 20 or newer is required; found $NODE_VERSION."

VENV_DIR="$ROOT/.venv-$PLATFORM"
VENV_PYTHON="$VENV_DIR/$VENV_PYTHON_SUFFIX"
if [[ ! -f "$VENV_PYTHON" ]]; then
  if [[ -e "$VENV_DIR" ]]; then
    fail "The existing $VENV_DIR environment is incomplete. Remove only that generated environment folder, then run this script again."
  fi
  printf '\nCreating the local Python environment...\n'
  "${PYTHON[@]}" -m venv "$VENV_DIR"
fi

REQUIREMENTS_HASH="$("$VENV_PYTHON" -c 'import hashlib, pathlib; print(hashlib.sha256(pathlib.Path("backend/requirements.txt").read_bytes()).hexdigest())')"
REQUIREMENTS_MARKER="$VENV_DIR/.requirements.sha256"
if [[ ! -f "$REQUIREMENTS_MARKER" ]] || [[ "$(cat "$REQUIREMENTS_MARKER")" != "$REQUIREMENTS_HASH" ]]; then
  printf '\nInstalling the Python application dependencies...\n'
  "$VENV_PYTHON" -m pip install --disable-pip-version-check -r backend/requirements.txt
  printf '%s\n' "$REQUIREMENTS_HASH" > "$REQUIREMENTS_MARKER"
fi

command -v node >/dev/null 2>&1 || fail 'Node.js is required to build the local web interface.'
LOCK_HASH="$(node -e 'const fs=require("node:fs"), crypto=require("node:crypto"); process.stdout.write(crypto.createHash("sha256").update(fs.readFileSync("package-lock.json")).digest("hex"))')"
LOCK_MARKER="$ROOT/node_modules/.primepick-lock.sha256"
if [[ ! -d "$ROOT/node_modules" ]] || [[ ! -f "$LOCK_MARKER" ]] || [[ "$(cat "$LOCK_MARKER" 2>/dev/null || true)" != "$LOCK_HASH" ]]; then
  printf '\nInstalling the web interface dependencies...\n'
  npm ci
  printf '%s\n' "$LOCK_HASH" > "$LOCK_MARKER"
fi

printf '\nBuilding the local web interface...\n'
npm run build

printf '\nChecking that Playwright Chromium is installed...\n'
"$VENV_PYTHON" -m playwright install chromium

if [[ "$PLATFORM" == "linux" && -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  printf '\nWarning: no desktop display was detected. The app can open, but product extraction needs a visible Chromium window. On WSL, use WSLg; on Linux, use a graphical desktop session.\n' >&2
fi

PORT="${PRIMEPICK_PORT:-8765}"
[[ "$PORT" =~ ^[0-9]+$ ]] || fail 'PRIMEPICK_PORT must be a number between 1 and 65535.'
(( PORT >= 1 && PORT <= 65535 )) || fail 'PRIMEPICK_PORT must be a number between 1 and 65535.'

printf '\nPrimePick Goods is ready at: http://127.0.0.1:%s\n' "$PORT"
printf 'This local server is bound to this computer only. Keep this terminal open; press Ctrl+C to stop it.\n'
printf 'Enter the client’s own OpenAI API key in Settings after opening the app.\n\n'

exec "$VENV_PYTHON" "$ROOT/backend/run_backend.py" --host 127.0.0.1 --port "$PORT"
