# PrimePick Goods — AI eBay Listing Generator

PrimePick Goods is a local-first desktop application for turning an AliExpress product page into an editable, fact-led eBay US listing. It combines a built-in browser panel (where the seller opens the product and completes any verification by hand), a modular Python extractor, OpenAI structured JSON output, a Jinja2-branded HTML template, and local SQLite history.

> **Repository note:** the starting repository contained only a README. There was no AliExpress scraper or client HTML template to inspect or reuse. This implementation therefore adds a conservative DOM-based extractor and a new PRIMEPICK GOODS starter template. If the client has the original store template, replace `backend/app/templates/listing.html` while keeping its dynamic fields; the template remains independent from AI prompts and extraction logic.

## What is included

- **Dashboard:** paste an AliExpress URL and watch clear extraction progress.
- **Built-in product browser:** in the desktop app, AliExpress opens in a normal browser panel inside the app window (an Electron `WebContentsView` with no automation or debugging protocol attached). The user completes any AliExpress check by hand, then selects **Extract this product**; the app reads the page they are viewing and sends the HTML to the backend parser. There is no CAPTCHA bypass, stealth mode, or access-restriction workaround. When the UI runs in a plain browser (developer mode), extraction falls back to a Playwright-driven Edge window.
- **Product review:** edit the extracted title and description, inspect specifications/variations/package details, and select product images.
- **AI content editor:** generate and edit an 80-character eBay title, description, features, specifications, package contents, instructions, warnings, and private review flags.
- **Branded HTML:** Jinja2 builds a script-free, table-based PRIMEPICK GOODS listing with inline styling. It is rendered in a sandboxed iframe; source view, copy, and HTML download are provided.
- **History, settings, and OpenAI usage:** listings, token totals, and estimated USD usage persist in local SQLite. Settings shows all-time input/output tokens, generations, and estimated spend; the OpenAI key is not returned to the UI and is stored in the OS credential vault when available (encrypted local fallback otherwise).
- **Windows desktop packaging:** Electron starts and shuts down a bundled FastAPI backend. The Windows build bundles the frontend and Python backend in an NSIS installer with desktop/start-menu shortcuts. No browser or Playwright is bundled: product pages open in the app's own browser panel.

## End-user workflow

1. Install and open **PrimePick Goods Listing Generator**.
2. Open **Settings**, paste an OpenAI API key, and save it. The app does not include or supply an API key.
3. Paste one public AliExpress product URL and select **Open product**.
4. The page opens in the app's browser panel. If AliExpress shows a robot check, complete it yourself in the panel, then select **Extract this product**. If the product page cannot be read, the app will explain that and will not silently create a listing.
5. Review the extracted facts and choose the images to use.
6. Generate the copy, review the private seller notes, edit the fields, and preview the branded HTML.
7. Copy the complete source, download an `.html` file, and/or save the listing to local history.

Internet access is needed to open AliExpress and call OpenAI. OpenAI usage is billed to the user's own OpenAI account according to that account's terms and pricing. The Settings page also shows locally stored token counts and an estimated USD total; built-in rates may differ from actual invoices, and unknown models are counted but not priced.

## Run in developer mode

Prerequisites: Python 3.11+, Node.js 22.12+ for the desktop shell/Windows installer (Node.js 20+ is sufficient for the React-only dev server), npm, and Microsoft Edge or Google Chrome (or Playwright Chromium via `python -m playwright install chromium`). These are developer requirements only; the packaged Windows user does not install Python or Node.js.

### 1. Python backend

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux:       source .venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install chromium
python backend/run_backend.py
```

### 2. React UI

In a second terminal at the repository root:

```bash
npm install
npm run dev
```

Open the Vite address it prints (normally `http://localhost:5173`). Vite proxies `/api` requests to the local backend on port `8765`. In a plain browser there is no built-in panel, so extraction uses the fallback: the Python backend launches a visible Edge (or Chrome/Chromium) window via Playwright on the same computer. Running the desktop shell against the dev backend (`cd desktop && npx electron .`) uses the built-in panel.

Optional developer defaults are documented in `.env.example`. The OpenAI key should be entered through the app's Settings page, not committed to a file or source control.

## Windows installer build

The installer scripts target **Windows x64**. The build machine needs Python 3.11+, Node.js 22.12+, and npm. Run one of these:

```bash
# Git Bash: use this when PowerShell scripts are blocked
bash scripts/build_windows.sh
```

```powershell
# PowerShell
.\scripts\build_windows.ps1
```

The Bash script picks Python automatically. To use a specific interpreter, set it explicitly, e.g. `PYTHON=/c/Python314/python.exe bash scripts/build_windows.sh`.

### Sharing the installer with users (free)

Upload `desktop/dist/PrimePick-Goods-Setup-<version>.exe` to a **GitHub Release** (Releases → Draft a new release → attach the file) or to Google Drive/OneDrive, and send the user the download link. Users only need [docs/end-user.md](docs/end-user.md).

Both scripts build the React UI, install backend build dependencies, package the backend with PyInstaller, and creates an NSIS installer at:

```text
desktop/dist/PrimePick-Goods-Setup-0.1.2.exe
```

No browser or Playwright is bundled (product pages open in the app's own Electron browser panel), which keeps the installer around 145 MB. The end user's API key is deliberately **not** bundled. Windows code signing is not configured; Windows SmartScreen may show an unsigned-app warning until a publisher certificate is added. Build outputs and downloaded browsers are ignored by Git.

## Tests

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q backend
```

The tests cover URL restrictions and DOM extraction, missing-information flags, structured AI response validation and token accounting, persisted usage totals, model-price matching, title limits, and safe/brand-template HTML rendering. They do not access AliExpress or OpenAI.

## Project layout

```text
backend/app/
  ai.py                 OpenAI prompt, response validation, and token usage capture
  ai_pricing.py         Built-in per-model USD pricing estimates
  config.py             Per-user data paths and packaged resource paths
  database.py           SQLite history, preferences, and usage totals
  extractor.py          Visible Playwright browser and BeautifulSoup extraction
  main.py               FastAPI routes and extraction job lifecycle
  models.py             Pydantic API/data contracts
  renderer.py           Jinja2 rendering entry point
  secrets.py            OS credential vault / encrypted local fallback
  templates/listing.html PRIMEPICK GOODS eBay description template
backend/tests/          Offline unit tests
src/                    React workflow, editor, history, settings and preview
desktop/                Electron lifecycle, preload and NSIS installer settings
scripts/                Local run helper and Windows installer build script
docs/                   Behavior and packaging notes
```

## Important limitations and safety notes

- AliExpress changes page markup, may show sign-in/region-specific pages, or may not expose all details in the rendered page. The extractor only reads the normal rendered page; it does not evade challenges or use stealth techniques. Recheck all facts, especially specifications, variants, included items, warnings, and compatibility.
- Extracted product images keep their original remote URLs. Those images must remain publicly reachable and acceptable to eBay; confirm they load in eBay's listing editor. The app does not download, host, or relicense images.
- The AI is instructed not to invent claims, but generated text must still be reviewed by the seller. Missing/uncertain extraction details are surfaced as private review flags and are not included in the public HTML.
- Product text sent to OpenAI is sent to the user's configured OpenAI account for generation. The app has no shared service or bundled credential.
- The generated template uses inline styles and tables, with no scripts or external stylesheets. eBay may sanitize description HTML and platform policies can change; inspect the final listing in eBay before publishing.
- Listing history, application preferences, encrypted fallback credentials, the persistent browser profile, and backend diagnostic logs live under the current user's app-data folder. Removing the app does not necessarily remove this user data; remove listings/API credentials in the app or clear that folder when appropriate.
