@echo off
rem PrimePick Goods: set up and start the app on this computer (Windows).
rem
rem   Double-click start.cmd    Open the desktop app (recommended)
rem   start.cmd --web           Run in your web browser instead, at http://127.0.0.1:8765
rem
rem Needs Python 3.11+ and Node.js 20+ installed. Git Bash and PowerShell are not needed.
rem The first run downloads what the app needs (a few minutes); later runs reuse it and
rem start quickly. Safe to run every time. Shares its setup with start.sh.
setlocal EnableExtensions
title PrimePick Goods
cd /d "%~dp0"
set "ROOT=%CD%"

set "MODE=desktop"
if "%~1"=="" goto :mode_done
if /i "%~1"=="--desktop" goto :mode_done
if /i "%~1"=="--web" set "MODE=web" & goto :mode_done
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
if "%~1"=="/?" goto :help
echo Unknown option: %~1 - use --web or --help
exit /b 2

:help
echo PrimePick Goods: set up and start the app on this computer.
echo.
echo   start.cmd          Open the desktop app (recommended). Double-clicking does the same.
echo   start.cmd --web    Run in your web browser instead, at http://127.0.0.1:8765
echo.
echo Needs Python 3.11+ and Node.js 20+. The first run takes a few minutes; later runs are quick.
exit /b 0

:mode_done

rem --- Python -------------------------------------------------------------------
call :step "Checking Python"
set "PYTHON="
call :try_python py -3
if not defined PYTHON call :try_python python
if not defined PYTHON call :try_python python3
if defined PYTHON goto :python_ok
set "MSG=Python 3.11 or newer was not found. Install it from python.org and tick 'Add python.exe to PATH' in the installer, then run this again."
goto :fail
:python_ok
%PYTHON% -c "import sys; print('Python', sys.version.split()[0])"

rem --- Node.js ------------------------------------------------------------------
call :step "Checking Node.js"
set "MSG=Node.js was not found. Install the LTS version from nodejs.org, then run this again."
where node >nul 2>&1 || goto :fail
where npm >nul 2>&1 || goto :fail
for /f "delims=" %%V in ('node --version') do set "NODE_VERSION=%%V"
set "MSG=Node.js 20 or newer is required, found %NODE_VERSION%. Install the LTS version from nodejs.org."
node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 20 ? 0 : 1)" || goto :fail
echo Node.js %NODE_VERSION%

rem --- Python environment (installed once; refreshed only when requirements change) --
set "VENV_DIR=%ROOT%\.venv-windows"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "HELPER="%VENV_PY%" "%ROOT%\scripts\start_helper.py""
"%VENV_PY%" -c "pass" >nul 2>&1 && goto :venv_ok
call :step "Creating the Python environment (first run only)"
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
set "MSG=Could not create the Python environment."
%PYTHON% -m venv "%VENV_DIR%" || goto :fail
:venv_ok

set "REQ_FILE=%ROOT%\backend\requirements.txt"
set "REQ_MARKER=%VENV_DIR%\.requirements.sha256"
%HELPER% changed "%REQ_FILE%" "%REQ_MARKER%"
if errorlevel 10 goto :install_python_packages
if errorlevel 1 goto :helper_failed
goto :python_packages_ok
:install_python_packages
call :step "Installing Python packages (first run or after an update)"
set "MSG=Could not install the Python packages. Check the internet connection and try again."
"%VENV_PY%" -m pip install --disable-pip-version-check -q -r "%REQ_FILE%" || goto :fail
%HELPER% mark "%REQ_FILE%" "%REQ_MARKER%" || goto :helper_failed
:python_packages_ok

rem --- Node packages (installed once; refreshed only when the lock files change) -----
set "MSG=Could not install the app's interface packages. Check the internet connection and try again."
call :npm_install "%ROOT%" "the app's interface packages" || goto :fail

rem --- Interface build (only when the source changed) ------------------------------
%HELPER% ui-stale
if errorlevel 10 goto :build_ui
if errorlevel 1 goto :helper_failed
goto :ui_ok
:build_ui
call :step "Building the app interface"
set "MSG=The app interface could not be built."
call npm run build --silent || goto :fail
:ui_ok

rem Set by some editors (e.g. VS Code); it stops Electron opening a window.
set "ELECTRON_RUN_AS_NODE="

if /i "%MODE%"=="web" goto :web

rem --- Desktop app ------------------------------------------------------------------
set "MSG=Could not install the desktop app. Check the internet connection and try again."
call :npm_install "%ROOT%\desktop" "the desktop app - downloads Electron, about 150 MB, once" || goto :fail
set "ELECTRON_BIN=%ROOT%\desktop\node_modules\electron\dist\electron.exe"
if exist "%ELECTRON_BIN%" goto :electron_ok
rem npm can skip Electron's download step (e.g. install scripts disabled); run it directly.
call :step "Downloading Electron"
set "MSG=Could not download Electron. Check the internet connection and try again."
pushd "%ROOT%\desktop"
node node_modules\electron\install.js
set "DOWNLOAD_STATUS=%ERRORLEVEL%"
popd
if not "%DOWNLOAD_STATUS%"=="0" goto :fail
if not exist "%ELECTRON_BIN%" goto :fail
:electron_ok

call :step "Starting PrimePick Goods"
echo The app window will open in a moment. Keep this window open while you use the app;
echo closing the app window stops everything.
set "PYTHON_EXECUTABLE=%VENV_PY%"
"%ELECTRON_BIN%" "%ROOT%\desktop"
set "APP_STATUS=%ERRORLEVEL%"
if "%APP_STATUS%"=="0" exit /b 0
echo.
echo The app closed with an error, code %APP_STATUS%.
pause
exit /b %APP_STATUS%

rem --- Web mode --------------------------------------------------------------------
:web
set "PORT=8765"
if defined PRIMEPICK_PORT set "PORT=%PRIMEPICK_PORT%"
call :step "Starting PrimePick Goods (web mode)"
echo Open http://127.0.0.1:%PORT% in your browser. Keep this window open; press Ctrl+C to stop.
echo Note: in web mode, products open in a separate Microsoft Edge window. The desktop app
echo (double-click start.cmd) is recommended, because AliExpress checks work better there.
cd /d "%ROOT%\backend"
"%VENV_PY%" run_backend.py --host 127.0.0.1 --port %PORT%
exit /b %ERRORLEVEL%

rem --- Helpers ----------------------------------------------------------------------
:step
echo.
echo == %~1
exit /b 0

:try_python
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON=%*"
exit /b 0

:npm_install
rem npm_install <folder> <label>: run "npm ci" when package-lock.json changed since the last install.
set "NPM_DIR=%~1"
set "NPM_MARKER=%~1\node_modules\.primepick-lock.sha256"
if not exist "%NPM_DIR%\node_modules" goto :npm_install_run
%HELPER% changed "%NPM_DIR%\package-lock.json" "%NPM_MARKER%"
if errorlevel 10 goto :npm_install_run
if errorlevel 1 exit /b 1
exit /b 0
:npm_install_run
call :step "Installing %~2 (first run or after an update)"
pushd "%NPM_DIR%"
call npm ci --no-audit --no-fund
set "NPM_STATUS=%ERRORLEVEL%"
popd
if not "%NPM_STATUS%"=="0" exit /b 1
%HELPER% mark "%NPM_DIR%\package-lock.json" "%NPM_MARKER%"
exit /b %ERRORLEVEL%

:helper_failed
set "MSG=The setup check failed. Delete the .venv-windows folder and run this again."
goto :fail

:fail
echo.
echo PrimePick Goods could not start: %MSG%
echo.
pause
exit /b 1
