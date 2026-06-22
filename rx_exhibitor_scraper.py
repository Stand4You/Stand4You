"""
ILTM Cannes Exhibitor Scraper — Selenium + Chrome
Usage:
  py -3.12 rx_exhibitor_scraper.py                          # list only (2799 lignes)
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

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

DIRECTORY_URL = "https://www.iltm.com/cannes/en-gb/exhibitor-directory.html"
OUTPUT_FILE = "iltm_exhibitors.csv"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = r"C:\Temp\chrome-iltm"


def make_driver(headless: bool) -> webdriver.Chrome:
    opts = Options()
    opts.binary_location = CHROME_PATH
    opts.add_argument("--no-sandbox")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=fr-FR")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.page_load_strategy = "none"  # don't wait for full page load
    if headless:
        opts.add_argument("--headless=new")

    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


def accept_cookies(driver):
    try:
        WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        ).click()
        time.sleep(1)
        print("  [cookies] Bannière acceptée.")
    except TimeoutException:
        pass


def extract_list(driver) -> list[dict]:
    print("Chargement de la page annuaire...")
    driver.get(DIRECTORY_URL)
    accept_cookies(driver)
    time.sleep(4)

    print("Scroll pour charger tous les exposants...")
    last_height = 0
    for i in range(60):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        count = driver.execute_script(
            "return document.querySelectorAll('.exhibitor-category').length"
        )
        if (i + 1) % 5 == 0:
            print(f"  scroll {i+1}: {count} exposants chargés...")
        if new_height == last_height and count > 100:
            print(f"  → Fin du scroll. {count} exposants dans le DOM.")
            break
        last_height = new_height

    print("Extraction des données...")
    exhibitors = driver.execute_script("""
        const items = [...document.querySelectorAll('.exhibitor-category')];
        return items.map(el => {
            const nameEl = el.querySelector('.exhibitor-name, h3, h2');
            const standEl = el.querySelector('.exhibitor-contact-container');
            const linkEl = el.querySelector('a') || el.closest('a');
            const name = nameEl ? nameEl.textContent.trim() : '';
            const standText = standEl ? standEl.textContent.trim() : '';
            const stand = standText.replace(/^Stand\\s*/i, '').trim();
            const href = linkEl ? linkEl.href : '';
            return { name, stand, detail_url: href };
        }).filter(e => e.name);
    """)

    print(f"  → {len(exhibitors)} exposants extraits.")
    return exhibitors


def extract_contact(driver, url: str, retries: int = 2) -> dict:
    contact = {"website": "", "email": "", "phone": "", "address": "", "country": ""}

    for attempt in range(retries):
        try:
            driver.get(url)
            time.sleep(random.uniform(2.5, 4.0))

            contact = driver.execute_script("""
                const links = [...document.querySelectorAll('a[href]')];
                let website = '', email = '', phone = '';
                const skipCls = ['global-nav','mega-nav','footer','tile__base','link-list','mobile-nav'];
                for (const a of links) {
                    const href = a.href || '';
                    const cls = a.className || '';
                    if (skipCls.some(s => cls.includes(s))) continue;
                    const skipDomains = ['iltm.com','rxglobal','reedexpo','privacy','twitter','x.com','facebook','instagram','linkedin','youtube','google','onetrust','trademark','accessibility','legal','pub-mediabox','rxweb-prd','wtm.com','ibtm','igtm'];
                    if (href.startsWith('mailto:') && !email)
                        email = href.replace('mailto:', '').split('?')[0].trim();
                    else if (href.startsWith('tel:') && !phone)
                        phone = href.replace('tel:', '').trim();
                    else if (href.startsWith('http') && !skipDomains.some(d => href.includes(d)) && !website)
                        website = href;
                }
                return { website, email, phone };
            """)

            # Extract address from page text in Python
            body = driver.execute_script("return document.body.innerText;")
            address = ""
            marker = "COMPANY ADDRESS"
            idx = body.find(marker)
            if idx != -1:
                after = body[idx + len(marker):]
                end_markers = ["FOLLOW US", "STAND(S)", "Recommended", "CATEGORIES", "DOCUMENTS"]
                end_idx = len(after)
                for m in end_markers:
                    i = after.find(m)
                    if i != -1 and i < end_idx:
                        end_idx = i
                addr_block = after[:end_idx].strip()
                addr_lines = [l.strip() for l in addr_block.split("\n") if l.strip()][:8]
                address = ", ".join(addr_lines)
                country = addr_lines[-1] if addr_lines else ""
                contact["address"] = address
                contact["country"] = country

            return contact

        except Exception as e:
            if attempt < retries - 1:
                wait_s = 3 * (attempt + 1)
                print(f"    [retry {attempt+1}] {e} — attente {wait_s}s...")
                time.sleep(wait_s)
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
    parser.add_argument("--output", default=OUTPUT_FILE)
    args = parser.parse_args()

    print(f"Mode: {'headless' if args.headless else 'headed (fenêtre visible)'}")
    print("Démarrage du navigateur...")

    driver = make_driver(args.headless)

    try:
        exhibitors = extract_list(driver)

        if not exhibitors:
            print("ERREUR: Aucun exposant extrait.")
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

            total = len(exhibitors)
            print(f"\nContacts récupérés: {ok}/{total} ({ok/total*100:.1f}%)")

    finally:
        driver.quit()

    fieldnames = ["name", "country", "website", "email", "phone", "address"]
    out_path = Path(args.output)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for ex in exhibitors:
            writer.writerow({k: ex.get(k, "") for k in fieldnames})

    print(f"\nCSV écrit: {out_path.resolve()} ({len(exhibitors)} lignes)")


if __name__ == "__main__":
    main()
