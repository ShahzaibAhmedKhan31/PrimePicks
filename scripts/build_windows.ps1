$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PythonEnv = Join-Path $Root '.venv'
$Python = Join-Path $PythonEnv 'Scripts/python.exe'
$Desktop = Join-Path $Root 'desktop'
$BrowserDir = Join-Path $Desktop 'resources/playwright-browsers'

Write-Host '== PrimePick Goods Windows build ==' -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.11 or newer is required on the build computer. It is bundled in the finished app.'
}
$PythonVersionText = python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ([version]$PythonVersionText -lt [version]'3.11.0') {
    throw 'Python 3.11 or newer is required on the build computer.'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'Node.js and npm are required on the build computer. They are not required by app users.'
}
$NodeVersionText = (node --version).Trim().TrimStart('v')
if ([version]$NodeVersionText -lt [version]'22.12.0') {
    throw 'Node.js 22.12 or newer is required to build the Electron desktop app.'
}

Push-Location $Root
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed for the React frontend.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'The React frontend build failed.' }

    if (-not (Test-Path $Python)) {
        python -m venv $PythonEnv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python build environment.' }
    }
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Could not update pip in the Python build environment.' }
    & $Python -m pip install -r (Join-Path $Root 'backend/requirements-build.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the backend build requirements.' }

    if (Test-Path $BrowserDir) { Remove-Item -Recurse -Force $BrowserDir }
    New-Item -ItemType Directory -Force -Path $BrowserDir | Out-Null
    $env:PLAYWRIGHT_BROWSERS_PATH = $BrowserDir
    & $Python -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Could not download the bundled Playwright Chromium browser.' }

    $BackendResources = Join-Path $Desktop 'resources/backend'
    if (Test-Path $BackendResources) { Remove-Item -Recurse -Force $BackendResources }
    New-Item -ItemType Directory -Force -Path $BackendResources | Out-Null
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --name PrimePickGoodsBackend `
        --distpath $BackendResources `
        --workpath (Join-Path $Root 'backend/build') `
        --paths (Join-Path $Root 'backend') `
        --add-data "$(Join-Path $Root 'backend/app/templates');app/templates" `
        --add-data "$(Join-Path $Root 'frontend_dist');frontend_dist" `
        --collect-all playwright `
        --collect-all greenlet `
        --collect-all fastapi `
        --collect-all starlette `
        --collect-all pydantic `
        --collect-all uvicorn `
        --collect-all anyio `
        --collect-all openai `
        --collect-all bs4 `
        --collect-all jinja2 `
        --collect-all platformdirs `
        --collect-all cryptography `
        --collect-all keyring `
        (Join-Path $Root 'backend/run_backend.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller could not package the Python backend.' }

    Push-Location $Desktop
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed for the Electron desktop shell.' }
        npm run dist:win
        if ($LASTEXITCODE -ne 0) { throw 'Electron Builder could not create the Windows installer.' }
    } finally {
        Pop-Location
    }
    Write-Host "`nInstaller created in $Desktop/dist" -ForegroundColor Green
} finally {
    Pop-Location
}
