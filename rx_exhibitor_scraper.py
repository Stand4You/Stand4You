"""
ILTM Cannes Exhibitor Scraper — undetected-chromedriver + Selenium
Usage:
  py -3.12 rx_exhibitor_scraper.py                          # list only
  py -3.12 rx_exhibitor_scraper.py --with-details           # + website/email/phone
  py -3.12 rx_exhibitor_scraper.py --with-details --limit 50
  py -3.12 rx_exhibitor_scraper.py --with-details --headless
"""

import csv
import time
import random
import argparse
import sys
from pathlib import Path

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

DIRECTORY_URL = "https://www.iltm.com/cannes/en-gb/exhibitor-directory.html"
OUTPUT_FILE = "iltm_exhibitors.csv"
CONTACT_SELECTOR = ".exhibitor-details-contact-us-links"


def make_driver(headless: bool) -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=fr-FR")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    if headless:
        options.add_argument("--headless=new")
    driver = uc.Chrome(options=options, use_subprocess=True)
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {
        "userAgent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    })
    return driver


def accept_cookies(driver):
    try:
        btn = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        btn.click()
        time.sleep(1)
        print("  [cookies] Bannière acceptée.")
    except TimeoutException:
        pass


def extract_list(driver) -> list[dict]:
    print("Chargement de la page annuaire...")
    driver.get(DIRECTORY_URL)

    # Accept cookies
    accept_cookies(driver)

    # Wait for exhibitor cards
    selectors = [
        "a.exhibitor-list-item",
        "a[class*='exhibitor-list']",
        ".exhibitor-list a",
    ]
    wait = WebDriverWait(driver, 30)
    for sel in selectors:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            break
        except TimeoutException:
            continue

    print("Extraction de la liste via JavaScript...")
    exhibitors = driver.execute_script("""
        const results = [];
        const selectors = [
            'a.exhibitor-list-item',
            'a[class*="exhibitor-list"]',
            '.exhibitor-list a',
            '.exhibitor-list-item',
        ];
        let items = [];
        for (const sel of selectors) {
            items = [...document.querySelectorAll(sel)];
            if (items.length > 0) break;
        }
        for (const el of items) {
            const anchor = el.tagName === 'A' ? el : el.querySelector('a');
            const name = (
                el.querySelector('.exhibitor-list-item-name, h3, h2, .name')?.textContent
                || el.textContent || ''
            ).trim();
            const stand = (
                el.querySelector('.exhibitor-list-item-stand, .stand, [class*="stand"]')?.textContent || ''
            ).trim();
            const href = anchor ? anchor.href : '';
            if (name) results.push({ name, stand, detail_url: href });
        }
        return results;
    """)

    print(f"  → {len(exhibitors)} exposants trouvés.")
    return exhibitors


def extract_contact(driver, url: str, retries: int = 2) -> dict:
    contact = {"website": "", "email": "", "phone": ""}

    for attempt in range(retries):
        try:
            driver.get(url)
            time.sleep(random.uniform(0.8, 2.0))

            # Try to find contact block
            contact_found = False
            alt_selectors = [
                CONTACT_SELECTOR,
                ".exhibitor-details-contact",
                "[class*='contact-us']",
                ".exhibitor-contact",
            ]
            for sel in alt_selectors:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    contact_found = True
                    break
                except TimeoutException:
                    continue

            if not contact_found:
                print(f"    [warn] Bloc contact introuvable: {url}")
                return contact

            contact = driver.execute_script(f"""
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
            """)
            return contact

        except Exception as e:
            if attempt < retries - 1:
                wait = 3 * (attempt + 1)
                print(f"    [retry {attempt+1}] Erreur sur {url}: {e}, attente {wait}s...")
                time.sleep(wait)
            else:
                print(f"    [fail] Abandon: {url}")

    return contact


def main():
    parser = argparse.ArgumentParser(description="ILTM Exhibitor Scraper")
    parser.add_argument("--with-details", action="store_true",
                        help="Visite chaque fiche pour récupérer website/email/phone")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limite le nombre de fiches (test)")
    parser.add_argument("--headless", action="store_true",
                        help="Mode headless (sans fenêtre)")
    parser.add_argument("--output", default=OUTPUT_FILE,
                        help=f"Fichier CSV de sortie (défaut: {OUTPUT_FILE})")
    args = parser.parse_args()

    headless = args.headless
    print(f"Mode: {'headless' if headless else 'headed (fenêtre visible)'}")
    print("Démarrage du navigateur...")

    driver = make_driver(headless)

    try:
        exhibitors = extract_list(driver)

        if not exhibitors:
            print("ERREUR: Aucun exposant extrait. Vérifiez les sélecteurs CSS.")
            sys.exit(1)

        if args.limit:
            exhibitors = exhibitors[:args.limit]
            print(f"Mode échantillon: {len(exhibitors)} fiches.")

        if args.with_details:
            print(f"\nEnrichissement contact ({len(exhibitors)} fiches)...")
            t0 = time.time()
            ok = 0
            for i, ex in enumerate(exhibitors, 1):
                url = ex.get("detail_url", "")
                if not url:
                    continue
                print(f"  [{i}/{len(exhibitors)}] {ex['name'][:50]}")
                contact = extract_contact(driver, url)
                ex.update(contact)
                if contact.get("email") or contact.get("phone"):
                    ok += 1
                if i % 50 == 0:
                    elapsed = time.time() - t0
                    rate = i / elapsed
                    remaining = (len(exhibitors) - i) / rate
                    print(f"  → {i}/{len(exhibitors)} | {ok} contacts | ETA ~{remaining/60:.0f} min")

            print(f"\nContacts récupérés: {ok}/{len(exhibitors)} ({ok/len(exhibitors)*100:.1f}%)")

    finally:
        driver.quit()

    # Write CSV
    fieldnames = ["name", "stand", "detail_url", "website", "email", "phone"]
    out_path = Path(args.output)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for ex in exhibitors:
            writer.writerow({k: ex.get(k, "") for k in fieldnames})

    print(f"\nCSV écrit: {out_path.resolve()} ({len(exhibitors)} lignes)")


if __name__ == "__main__":
    main()
