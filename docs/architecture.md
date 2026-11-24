# Architecture and packaging notes

## Runtime architecture

- **Electron** (`desktop/main.cjs`) is the desktop shell and lifecycle owner. It picks a free loopback port, starts the backend (the bundled `PrimePickGoodsBackend.exe` when packaged, `python backend/run_backend.py` in development), waits for `/api/health`, and loads the UI from the backend. On shutdown it calls a token-protected backend shutdown endpoint (`PRIMEPICK_SHUTDOWN_TOKEN`) so running tasks close cleanly.
- **FastAPI** (`backend/app/main.py`) serves the built React app from `frontend_dist/` and exposes a local JSON API. In developer mode Vite serves the UI and proxies `/api` to port 8765.
- **Built-in product browser (desktop app):** the AliExpress page opens in an Electron `WebContentsView` placed over the "New listing" page, in its own persistent session (`persist:product-browser`). It is driven only by the user. No automation or DevTools protocol is attached, so the page sees a normal Chromium browser. The session uses a standard Chrome user agent, denies permission requests and blocks downloads. Pop-ups open inside the panel, and only web URLs can be loaded. When the user selects **Extract this product**, the renderer asks the main process (IPC `product-browser:get-page`) for the panel's current HTML and posts it to `POST /api/extractions/html`. The preload script (`desktop/preload.cjs`) exposes only that small `primepickDesktop.productBrowser` API, and each IPC handler checks that the request came from the main window.
- **Browser-mode fallback:** when the UI runs in a plain web browser (`bash start.sh --web` or `npm run dev`), there is no panel. Instead the backend starts an extraction job that opens a visible Microsoft Edge window through Playwright (falling back to Chrome, then Playwright Chromium) with a persistent per-user profile. If a verification page is detected, the job waits until the user completes it and selects **Continue**. Playwright is not bundled in the Windows installer.
- **No bypassing:** neither path solves CAPTCHAs or uses stealth or fingerprint workarounds. Block and verification pages (for example AliExpress "unusual traffic" or slider pages and `/_____tmd_____/punish` URLs) are detected and reported to the user, never parsed as products.
- **Parsing:** BeautifulSoup reads the rendered page HTML and embedded JSON into a Pydantic product snapshot (`backend/app/extractor.py`).
  - Titles prefer the Open Graph `og:title`.
  - Descriptions prefer a complete "AI Overview of Item", then the metadata description, then DOM and JSON-LD fallbacks.
  - The parser keeps a list of missing information for the user to review.
- **AI generation:** OpenAI receives the extracted snapshot and a system prompt requiring a strict JSON schema. The response is validated with Pydantic before it reaches the editor. The AI never generates HTML.
- **HTML rendering:** Jinja2 renders `backend/app/templates/listing.html` independently of the AI. Autoescaping is on, and the template uses inline styles and tables, with no JavaScript or external stylesheets.
- **Local storage:** SQLite stores listing history, model preferences and per-generation OpenAI token usage. USD totals are estimates from built-in per-model rates (`backend/app/ai_pricing.py`); usage for unknown models is counted but not priced. The OpenAI key is stored in the OS credential vault when one is available, with a Fernet-encrypted file fallback.

## Data and privacy boundaries

- The UI talks to the local backend through relative `/api` paths. The backend binds to loopback (`127.0.0.1`) only.
- Product data goes to OpenAI only when the user generates listing copy. The application has no hosted account or shared API key.
- Product image URLs stay remote and are included only when selected. The app does not upload, download or host images.
- The listing database, settings, logs, encrypted key fallback and browser profiles live in the per-user app-data folder (Electron's `userData` for the desktop app). `PRIMEPICK_DATA_DIR` overrides this for development and testing.

## Local run script

`start.sh` is the no-installer way to run the app on a machine that has Python 3.11+, Node.js 20+ and Bash (Git Bash on Windows). Each run:

1. Checks Python and Node.js.
2. Creates `.venv-<platform>/` if it doesn't exist.
3. Reinstalls Python packages only when the sha256 of `backend/requirements.txt` changes.
4. Runs `npm ci` only when a `package-lock.json` hash changes.
5. Rebuilds `frontend_dist/` only when the UI sources are newer than the last build.
6. Launches Electron with `PYTHON_EXECUTABLE` pointing at the venv's Python. With `--web`, it serves the app on `127.0.0.1:8765` instead.

## Windows package assembly

`scripts/build_windows.sh` (Git Bash) and `scripts/build_windows.ps1` (PowerShell) assemble the installer:

1. Build the Vite static assets into `frontend_dist/`.
2. Create a Python build environment and package the backend with PyInstaller (onedir) into `desktop/resources/backend/PrimePickGoodsBackend/`, with the template and `frontend_dist` as data. Playwright and greenlet are excluded.
3. Build the Electron NSIS installer into `desktop/dist/PrimePick-Goods-Setup-<version>.exe`.

The installer contains Electron, the backend executable and its runtime files, and the static frontend. It contains no browser and no OpenAI API key. It installs per user without admin rights.

Build notes:

- Build on Windows x64 so the bundled Python and native packages target Windows.
- `desktop/package.json` sets `"packageManager": "traversal@1.0.0"` so electron-builder collects node modules without spawning PowerShell.
- The installer is unsigned, so SmartScreen shows a warning on first run. For production distribution, add a code-signing certificate to the electron-builder configuration.

## Known constraints

AliExpress page markup, access rules, regions and verification behaviour are outside the app's control. AliExpress may block some networks entirely. When that happens the app reports it and does not try to work around it. eBay may sanitize description HTML and can change its listing rules, so check the final pasted HTML on eBay before publishing.
