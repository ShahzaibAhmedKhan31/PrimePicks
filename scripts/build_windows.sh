#!/usr/bin/env bash
# Build the PrimePick Goods Windows installer from Git Bash (no PowerShell needed).
#   bash scripts/build_windows.sh
# Optional: PYTHON=/c/path/to/python.exe bash scripts/build_windows.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP="$ROOT/desktop"
VENV="$ROOT/.venv-build"
VENV_PY="$VENV/Scripts/python.exe"
BACKEND_OUT="$DESKTOP/resources/backend"

say()  { printf '\n\033[36m== %s ==\033[0m\n' "$*"; }
fail() { printf '\n\033[31mBUILD FAILED: %s\033[0m\n' "$*" >&2; exit 1; }
win()  { cygpath -w "$1"; }

version_ge() { # version_ge 3.12.1 3.11.0
  [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]
}

say "PrimePick Goods Windows build"

# --- Tool checks -------------------------------------------------------------
command -v cygpath >/dev/null || fail "Run this script from Git Bash on Windows."
command -v npm >/dev/null || fail "Node.js and npm are required on the build computer (not for app users)."
NODE_VER="$(node --version | tr -d 'v\r')"
version_ge "$NODE_VER" "22.12.0" || fail "Node.js 22.12+ is required (found $NODE_VER)."

pick_python() {
  if [[ -n "${PYTHON:-}" ]]; then echo "$PYTHON"; return; fi
  local candidates=("py -3.12" "py -3.13" "py -3.11" "python" "python3")
  for c in "${candidates[@]}"; do
    if $c -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
      echo "$c"; return
    fi
  done
}
PY="$(pick_python)"
[[ -n "$PY" ]] || fail "Python 3.11+ is required on the build computer (it is bundled into the app)."
echo "Using Python: $($PY -c 'import sys; print(sys.executable, sys.version.split()[0])')"

cd "$ROOT"

# --- 1. Frontend -------------------------------------------------------------
say "Building React frontend"
npm ci || fail "npm ci failed for the React frontend."
npm run build || fail "The React frontend build failed."

# --- 2. Python build environment --------------------------------------------
say "Preparing Python build environment"
if [[ ! -x "$VENV_PY" ]]; then
  $PY -m venv "$(win "$VENV")" || fail "Could not create the Python build environment."
fi
"$VENV_PY" -m pip install --upgrade pip || fail "Could not update pip."
"$VENV_PY" -m pip install -r "$(win "$ROOT/backend/requirements-build.txt")" \
  || fail "Could not install the backend build requirements."

# --- 3. Backend executable (PyInstaller) -------------------------------------
say "Packaging Python backend"
rm -rf "$BACKEND_OUT"
mkdir -p "$BACKEND_OUT"
COLLECT=()
for pkg in fastapi starlette pydantic uvicorn anyio openai bs4 jinja2 platformdirs cryptography keyring; do
  COLLECT+=(--collect-all "$pkg")
done
"$VENV_PY" -m PyInstaller \
  --noconfirm --clean --onedir \
  --name PrimePickGoodsBackend \
  --distpath "$(win "$BACKEND_OUT")" \
  --workpath "$(win "$ROOT/backend/build")" \
  --specpath "$(win "$ROOT/backend/build")" \
  --paths "$(win "$ROOT/backend")" \
  --add-data "$(win "$ROOT/backend/app/templates");app/templates" \
  --add-data "$(win "$ROOT/frontend_dist");frontend_dist" \
  "${COLLECT[@]}" \
  --exclude-module playwright --exclude-module greenlet \
  "$(win "$ROOT/backend/run_backend.py")" \
  || fail "PyInstaller could not package the Python backend."

# --- 4. Electron installer ---------------------------------------------------
say "Building Electron installer"
cd "$DESKTOP"
npm ci || fail "npm ci failed for the Electron desktop shell."
npm run dist:win || fail "Electron Builder could not create the Windows installer."

INSTALLER="$(ls -1 "$DESKTOP"/dist/*.exe 2>/dev/null | head -n1 || true)"
[[ -n "$INSTALLER" ]] || fail "No installer .exe was produced in desktop/dist."
printf '\n\033[32mInstaller ready:\033[0m %s (%s)\n' "$(win "$INSTALLER")" "$(du -h "$INSTALLER" | cut -f1)"
