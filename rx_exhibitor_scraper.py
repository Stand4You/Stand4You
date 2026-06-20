"""
ILTM Cannes Exhibitor Scraper — RX Global / Reed Exhibitions
Usage:
  python rx_exhibitor_scraper.py                        # list only (name, stand, url)
  python rx_exhibitor_scraper.py --with-details         # + website/email/phone
  python rx_exhibitor_scraper.py --with-details --limit 50   # sample run
  python rx_exhibitor_scraper.py --with-details --show-browser  # force headed
  python rx_exhibitor_scraper.py --with-details --headless      # force headless
"""

import asyncio
import csv
import re
import sys
import time
import argparse
import random
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

DIRECTORY_URL = "https://www.iltm.com/cannes/en-gb/exhibitor-directory.html"
OUTPUT_FILE = "iltm_exhibitors.csv"
CONTACT_SELECTOR = ".exhibitor-details-contact-us-links"

# Full stealth init script — patches the most common bot-detection vectors
STEALTH_SCRIPT = """
// 1. Hide webdriver flag
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. Add realistic chrome runtime object (absent in headless Chromium)
if (!window.chrome) {
    window.chrome = {
        runtime: {
            connect: () => {},
            sendMessage: () => {},
            onMessage: { addListener: () => {} },
            id: undefined,
        },
        loadTimes: () => {},
        csi: () => {},
        app: {},
    };
}

// 3. Realistic navigator.plugins (headless has 0 plugins)
const pluginData = [
    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
];
const pluginArray = pluginData.map(p => {
    const plugin = { name: p.name, filename: p.filename, description: p.description, length: 1 };
    plugin[0] = { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: p.description, enabledPlugin: plugin };
    return plugin;
});
pluginArray.length = pluginData.length;
Object.setPrototypeOf(pluginArray, PluginArray.prototype);
Object.defineProperty(navigator, 'plugins', { get: () => pluginArray });

// 4. Realistic languages
Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });

// 5. Permissions API — headless returns 'denied' for notifications
const originalQuery = window.Permissions?.prototype?.query;
if (originalQuery) {
    window.Permissions.prototype.query = function(parameters) {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission, onchange: null });
        }
        return originalQuery.apply(this, [parameters]);
    };
}

// 6. WebGL vendor/renderer — headless shows 'Google SwiftShader'
try {
    const getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Intel Inc.';   // UNMASKED_VENDOR_WEBGL
        if (param === 37446) return 'Intel Iris OpenGL Engine';  // UNMASKED_RENDERER_WEBGL
        return getParam.apply(this, [param]);
    };
} catch(e) {}

// 7. Screen dimensions — match a realistic display
Object.defineProperty(screen, 'width',  { get: () => 1920 });
Object.defineProperty(screen, 'height', { get: () => 1080 });
Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
Object.defineProperty(window, 'outerWidth',  { get: () => 1920 });
Object.defineProperty(window, 'outerHeight', { get: () => 1040 });

// 8. Hide automation-related properties sometimes checked
delete Object.getPrototypeOf(navigator).webdriver;
"""


async def accept_cookies(page):
    """Click OneTrust accept button if present."""
    try:
        btn = page.locator("#onetrust-accept-btn-handler")
        await btn.wait_for(state="visible", timeout=6000)
        await btn.click()
        await asyncio.sleep(1)
        print("  [cookies] Bannière acceptée.")
    except PlaywrightTimeout:
        pass  # no banner, fine


async def extract_list(page) -> list[dict]:
    """Extract all exhibitors from the directory page via a single evaluate()."""
    print("Extraction de la liste exposants...")
    await page.goto(DIRECTORY_URL, wait_until="networkidle", timeout=60000)
    await accept_cookies(page)

    # Wait for cards to appear
    await page.wait_for_selector(".exhibitor-list-item, .c-exhibitor-list-item, [class*='exhibitor']", timeout=30000)

    exhibitors = await page.evaluate("""
        () => {
            const results = [];
            // Try multiple possible selectors for the list items
            const selectors = [
                'a.exhibitor-list-item',
                'a[class*="exhibitor-list"]',
                '.exhibitor-list a',
                '[data-exhibitor] a',
            ];
            let items = [];
            for (const sel of selectors) {
                items = [...document.querySelectorAll(sel)];
                if (items.length > 0) break;
            }
            // Fallback: any link inside a known exhibitor container
            if (items.length === 0) {
                items = [...document.querySelectorAll('.exhibitor-list-item')];
            }
            for (const el of items) {
                const name = (el.querySelector('.exhibitor-list-item-name, h3, h2, .name')?.textContent || el.textContent || '').trim();
                const stand = (el.querySelector('.exhibitor-list-item-stand, .stand, [class*="stand"]')?.textContent || '').trim();
                const href = el.href || el.querySelector('a')?.href || '';
                if (name) results.push({ name, stand, detail_url: href });
            }
            return results;
        }
    """)

    print(f"  → {len(exhibitors)} exposants trouvés.")
    return exhibitors


async def extract_contact(page, url: str, retries: int = 2) -> dict:
    """Visit a detail page and extract website/email/phone."""
    contact = {"website": "", "email": "", "phone": ""}

    for attempt in range(retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # Small random delay to look human
            await asyncio.sleep(random.uniform(0.8, 2.5))

            try:
                await page.wait_for_selector(CONTACT_SELECTOR, timeout=12000)
            except PlaywrightTimeout:
                # Try alternative selectors
                alt_selectors = [
                    ".exhibitor-details-contact",
                    "[class*='contact-us']",
                    ".exhibitor-contact",
                ]
                found = False
                for sel in alt_selectors:
                    try:
                        await page.wait_for_selector(sel, timeout=3000)
                        found = True
                        break
                    except PlaywrightTimeout:
                        continue
                if not found:
                    print(f"    [warn] Bloc contact introuvable sur {url}")
                    return contact

            contact = await page.evaluate(f"""
                () => {{
                    const container = document.querySelector('{CONTACT_SELECTOR}')
                        || document.querySelector('.exhibitor-details-contact')
                        || document.querySelector('[class*="contact-us"]')
                        || document.body;

                    const links = [...container.querySelectorAll('a[href]')];
                    let website = '', email = '', phone = '';

                    for (const a of links) {{
                        const href = a.href || '';
                        if (href.startsWith('mailto:') && !email) {{
                            email = href.replace('mailto:', '').split('?')[0].trim();
                        }} else if (href.startsWith('tel:') && !phone) {{
                            phone = href.replace('tel:', '').trim();
                        }} else if (href.startsWith('http') && !href.includes('iltm.com') && !website) {{
                            website = href;
                        }}
                    }}
                    return {{ website, email, phone }};
                }}
            """)
            return contact

        except PlaywrightTimeout as e:
            if attempt < retries - 1:
                wait = 3 * (attempt + 1)
                print(f"    [retry {attempt+1}] Timeout sur {url}, attente {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"    [fail] Abandon après {retries} tentatives: {url}")

    return contact


async def run(args):
    headless_mode = not args.show_browser
    if args.headless:
        headless_mode = True
    if args.show_browser:
        headless_mode = False

    print(f"Mode: {'headless' if headless_mode else 'headed (fenêtre visible)'}")

    async with async_playwright() as p:
        # Try real Chrome first (less fingerprint issues), fallback to Chromium
        browser_kwargs = dict(
            headless=headless_mode,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu" if headless_mode else "",
                "--window-size=1920,1080",
                "--lang=fr-FR",
            ],
        )
        # Remove empty strings from args
        browser_kwargs["args"] = [a for a in browser_kwargs["args"] if a]

        try:
            browser = await p.chromium.launch(channel="chrome", **browser_kwargs)
            print("Browser: Chrome (système)")
        except Exception:
            browser = await p.chromium.launch(**browser_kwargs)
            print("Browser: Chromium (Playwright)")

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            timezone_id="Europe/Paris",
            java_script_enabled=True,
            accept_downloads=False,
            extra_http_headers={
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        # Inject stealth patches on every new page/frame
        await context.add_init_script(STEALTH_SCRIPT)

        page = await context.new_page()

        # Step 1: extract list
        exhibitors = await extract_list(page)

        if not exhibitors:
            print("ERREUR: Aucun exposant extrait. Vérifiez les sélecteurs CSS.")
            await browser.close()
            sys.exit(1)

        if args.limit:
            exhibitors = exhibitors[: args.limit]
            print(f"Mode échantillon: {len(exhibitors)} fiches.")

        # Step 2 (optional): enrich with contact details
        if args.with_details:
            print(f"\nEnrichissement contact ({len(exhibitors)} fiches)...")
            t0 = time.time()
            ok = 0
            for i, ex in enumerate(exhibitors, 1):
                url = ex.get("detail_url", "")
                if not url:
                    continue
                print(f"  [{i}/{len(exhibitors)}] {ex['name'][:50]}")
                contact = await extract_contact(page, url)
                ex.update(contact)
                if contact.get("email") or contact.get("phone"):
                    ok += 1
                # Progress ETA every 50
                if i % 50 == 0:
                    elapsed = time.time() - t0
                    rate = i / elapsed
                    remaining = (len(exhibitors) - i) / rate
                    print(f"  → {i}/{len(exhibitors)} | {ok} contacts | ETA ~{remaining/60:.0f} min")

            print(f"\nContacts récupérés: {ok}/{len(exhibitors)} ({ok/len(exhibitors)*100:.1f}%)")

        await browser.close()

        # Write CSV
        fieldnames = ["name", "stand", "detail_url", "website", "email", "phone"]
        out_path = Path(OUTPUT_FILE)
        with out_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for ex in exhibitors:
                writer.writerow({k: ex.get(k, "") for k in fieldnames})

        print(f"\nCSV écrit: {out_path.resolve()} ({len(exhibitors)} lignes)")
        return exhibitors


def main():
    global OUTPUT_FILE
    parser = argparse.ArgumentParser(description="ILTM Exhibitor Scraper")
    parser.add_argument("--with-details", action="store_true",
                        help="Visite chaque fiche pour récupérer website/email/phone")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limite le nombre de fiches (test)")
    parser.add_argument("--show-browser", action="store_true",
                        help="Mode headed (fenêtre visible) — contourne la détection bot")
    parser.add_argument("--headless", action="store_true",
                        help="Force le mode headless")
    parser.add_argument("--output", default=OUTPUT_FILE,
                        help=f"Fichier CSV de sortie (défaut: {OUTPUT_FILE})")
    args = parser.parse_args()
    OUTPUT_FILE = args.output

    asyncio.run(run(args))


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()
