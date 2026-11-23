# PrimePick Goods — Quick Start

## Install (one time)

You don't need to install Python, Node.js, a browser, or anything else. Everything the app needs is inside the setup file.

1. Download **PrimePick-Goods-Setup-0.1.0.exe** from the link you were sent.
2. Double-click the file.
3. If Windows shows **"Windows protected your PC"**, select **More info**, then **Run anyway**. This warning appears because the app is new and not yet signed with a paid publisher certificate. It does not mean anything is wrong.
4. Follow the installer and select **Install**. Admin rights are not needed. The app opens when the installer finishes, and a **PrimePick Goods Listing Generator** shortcut is added to your desktop and Start menu.

To uninstall, open Windows **Settings → Apps**, find PrimePick Goods Listing Generator, and select **Uninstall**.

## First launch

1. Open PrimePick Goods Listing Generator from the desktop shortcut or the Start menu.
2. Choose **Settings** in the left navigation.
3. Enter your own OpenAI API key, confirm the model setting, and select **Save settings**. The saved key is hidden in the app and stored for your Windows user.
4. Choose **New listing**.

## Create a listing

1. Paste a public AliExpress product URL and select **Open product**.
2. The product page opens in a browser panel inside the app. Use it like a normal browser: if AliExpress asks you to verify that you are not a robot, complete the check in the panel. When the product page is showing, select **Extract this product**. PrimePick Goods does not solve or bypass the check; you complete it yourself.
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
