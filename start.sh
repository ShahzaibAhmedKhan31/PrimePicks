#!/usr/bin/env bash
# PrimePick Goods: set up and start the app on this computer.
#
#   bash start.sh          Open the desktop app (recommended)
#   bash start.sh --web    Run in your web browser instead, at http://127.0.0.1:8765
#
# Needs Python 3.11+ and Node.js 20+ installed. The first run downloads what the app
# needs (a few minutes); later runs reuse it and start quickly. Safe to run every time.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"

MODE="desktop"
case "${1:-}" in
  ""|--desktop) MODE="desktop" ;;
  --web) MODE="web" ;;
  -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) printf 'Unknown option: %s (use --web or --help)\n' "$1" >&2; exit 2 ;;
esac

step() { printf '\n\033[36m== %s\033[0m\n' "$*"; }
# Keep the window open when the script was started by double-clicking it.
pause_if_interactive() { if [[ -t 0 && -t 1 ]]; then read -r -p "Press Enter to close this window..." _ || true; fi; }
fail() {
  printf '\n\033[31mPrimePick Goods could not start: %s\033[0m\n' "$1" >&2
  pause_if_interactive
  exit 1
}
trap 'fail "an unexpected error happened on line $LINENO. Scroll up for details."' ERR

# --- Platform ------------------------------------------------------------------
case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows"; VENV_PY_SUFFIX="Scripts/python.exe"; PY_CANDIDATES=("py -3" "python" "python3") ;;
  Darwin*)              PLATFORM="macos";   VENV_PY_SUFFIX="bin/python";         PY_CANDIDATES=("python3" "python") ;;
  *)                    PLATFORM="linux";   VENV_PY_SUFFIX="bin/python";         PY_CANDIDATES=("python3" "python") ;;
esac

# --- Python --------------------------------------------------------------------
step "Checking Python"
PYTHON=""
for candidate in "${PY_CANDIDATES[@]}"; do
  if $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
[[ -n "$PYTHON" ]] || fail "Python 3.11 or newer was not found. Install it from python.org (tick \"Add python.exe to PATH\"), then run this again."
$PYTHON -c 'import sys; print("Python", sys.version.split()[0])'

# --- Node.js -------------------------------------------------------------------
step "Checking Node.js"
command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 \
  || fail "Node.js was not found. Install the LTS version from nodejs.org, then run this again."
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
(( NODE_MAJOR >= 20 )) || fail "Node.js 20 or newer is required (found $(node --version)). Install the LTS version from nodejs.org."
echo "Node.js $(node --version)"

# --- Python environment (installed once; refreshed only when requirements change) --
VENV_DIR="$ROOT/.venv-$PLATFORM"
VENV_PY="$VENV_DIR/$VENV_PY_SUFFIX"
if [[ ! -x "$VENV_PY" ]]; then
  step "Creating the Python environment (first run only)"
  rm -rf "$VENV_DIR"
  $PYTHON -m venv "$VENV_DIR" || fail "Could not create the Python environment."
fi

hash_file() { "$VENV_PY" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }

REQ_HASH="$(hash_file backend/requirements.txt)"
REQ_MARKER="$VENV_DIR/.requirements.sha256"
if [[ "$(cat "$REQ_MARKER" 2>/dev/null || true)" != "$REQ_HASH" ]]; then
  step "Installing Python packages (first run or after an update)"
  "$VENV_PY" -m pip install --disable-pip-version-check -q -r backend/requirements.txt \
    || fail "Could not install the Python packages. Check the internet connection and try again."
  echo "$REQ_HASH" > "$REQ_MARKER"
fi

# --- Node packages (installed once; refreshed only when the lock files change) -----
npm_install_if_needed() { # npm_install_if_needed <folder> <label>
  local dir="$1" label="$2" lock_hash marker
  lock_hash="$(hash_file "$dir/package-lock.json")"
  marker="$dir/node_modules/.primepick-lock.sha256"
  if [[ ! -d "$dir/node_modules" || "$(cat "$marker" 2>/dev/null || true)" != "$lock_hash" ]]; then
    step "Installing $label (first run or after an update)"
    (cd "$dir" && npm ci --no-audit --no-fund) || fail "Could not install $label. Check the internet connection and try again."
    echo "$lock_hash" > "$marker"
  fi
}
npm_install_if_needed "$ROOT" "the app's interface packages"

# --- Interface build (only when the source changed) ------------------------------
if [[ ! -f frontend_dist/index.html ]] \
   || [[ -n "$(find src index.html vite.config.js package.json -newer frontend_dist/index.html -print -quit 2>/dev/null)" ]]; then
  step "Building the app interface"
  npm run build --silent || fail "The app interface could not be built."
fi

# Settings, listings and logs are kept in the same per-user folder the installed app uses.
unset ELECTRON_RUN_AS_NODE  # set by some editors (e.g. VS Code); it stops Electron opening a window

if [[ "$MODE" == "desktop" ]]; then
  npm_install_if_needed "$ROOT/desktop" "the desktop app (downloads Electron, about 150 MB, once)"
  ELECTRON_BIN="$ROOT/desktop/node_modules/electron/dist/electron"
  [[ "$PLATFORM" == "windows" ]] && ELECTRON_BIN+=".exe"
  [[ "$PLATFORM" == "macos" ]] && ELECTRON_BIN="$ROOT/desktop/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron"
  if [[ ! -x "$ELECTRON_BIN" ]]; then
    # npm can skip Electron's download step (e.g. install scripts disabled); run it directly.
    step "Downloading Electron"
    (cd "$ROOT/desktop" && node node_modules/electron/install.js) || fail "Could not download Electron. Check the internet connection and try again."
  fi

  step "Starting PrimePick Goods"
  echo "The app window will open in a moment. Keep this window open while you use the app;"
  echo "closing the app window stops everything."
  trap - ERR
  set +e
  PYTHON_EXECUTABLE="$VENV_PY" "$ELECTRON_BIN" "$ROOT/desktop"
  status=$?
  if (( status != 0 )); then
    printf '\nThe app closed with an error (code %s).\n' "$status"
    pause_if_interactive
  fi
  exit "$status"
fi

# --- Web mode -------------------------------------------------------------------
PORT="${PRIMEPICK_PORT:-8765}"
step "Starting PrimePick Goods (web mode)"
echo "Open http://127.0.0.1:$PORT in your browser. Keep this window open; press Ctrl+C to stop."
echo "Note: in web mode, products open in a separate Microsoft Edge window. The desktop app"
echo "(bash start.sh) is recommended, because AliExpress checks work better there."
trap - ERR
cd "$ROOT/backend"
exec "$VENV_PY" run_backend.py --host 127.0.0.1 --port "$PORT"
