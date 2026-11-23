# PrimePick Goods — Quick Start

## First launch (Windows installer)

1. Install PrimePick Goods Listing Generator using the Windows setup file and open it from the desktop shortcut or Start menu.
2. Choose **Settings** in the left navigation.
3. Enter your own OpenAI API key, confirm the model setting, and select **Save settings**. The saved key is hidden in the app and stored for your Windows user.
4. Choose **New listing**.

## Run from the repository with Bash (instead of installing the Windows app)

This option runs the application locally from source in a browser. It does not create or install an `.exe`.

Requirements: Git and Bash, Python 3.11+, and Node.js 20+ with npm. On Windows, run the script in **Git Bash** and make sure Windows Python and Node.js are on its `PATH`. On Ubuntu/WSL, use Linux Python and Node.js; WSLg or another graphical display is required for the visible Chromium product browser.

```bash
git clone https://github.com/ShahzaibAhmedKhan31/PrimePicks.git
cd PrimePicks
bash scripts/run_local.sh
```

The first run installs dependencies and Playwright Chromium, builds the interface, and starts the local server at `http://127.0.0.1:8765`. Keep the terminal open while using the app; press **Ctrl+C** to stop it. The app is only reachable from the same computer. In **Settings**, enter the client's own OpenAI API key; it is not in the repository. Initial setup requires internet access.

## Create a listing

1. Paste a public AliExpress product URL and select **Extract product**.
2. A normal Chromium window opens on the product page. If AliExpress asks you to verify that you are human, complete the check in Chromium. Return to the app and press **Continue**. PrimePick Goods does not solve or bypass the challenge.
3. Review the title, description, specifications, variations, package details, warnings, and image choices. The extractor prefers the page's Open Graph title and a complete item AI overview when available; otherwise it uses metadata description and other page fallbacks. Confirm important information on the source page.
4. Select **Generate eBay copy**. OpenAI creates a structured draft; the app displays any missing or uncertain facts as private seller review notes.
5. Edit the title and listing fields as needed. Review product compatibility and safety details before publishing.
6. Select **Preview HTML**. Switch between **Preview** and **HTML source**, then **Copy HTML**, **Download**, or **Save to history**.

## Saved listings

Choose **Listing history** to reopen a saved listing. From its preview you can edit, copy, or download the HTML again. History is local to this Windows user and does not sync to eBay or another device.

## OpenAI usage

Open **Settings** to view all-time input, output, and total tokens plus estimated USD spend and the number of generations tracked on this computer. Usage totals persist locally in SQLite. Dollar amounts are estimates based on built-in standard model rates; cached-token discounts, price changes, credits, taxes, and account adjustments may make the OpenAI invoice differ. Token usage for an unrecognized model is still counted, but its cost is excluded from the USD estimate.

## Helpful notes

- The product browser is visible and uses a local profile, so normal page cookies can persist between runs. You are responsible for any sign-in activity in that browser.
- A browser verification screen should be completed only by the user. If it remains on screen, wait until the page changes before pressing **Continue**.
- Remote product images may not be suitable or available for an eBay description. Check image permissions and availability before publishing.
- The application needs internet access for AliExpress and OpenAI. OpenAI calls use your account and API billing.
- If a page fails, try the original public product URL again. Do not share API keys with anyone.
