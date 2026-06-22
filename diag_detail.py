"""
Inspecte une fiche exposant ILTM pour voir toutes les données disponibles.
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, json

opts = Options()
opts.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
opts.add_argument("--no-sandbox")
opts.add_argument("--no-first-run")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--user-data-dir=C:\\Temp\\chrome-iltm")
opts.page_load_strategy = "none"
s = Service(r"C:\Users\raf\.wdm\drivers\chromedriver\win64\149.0.7827.155\chromedriver-win64\chromedriver.exe")
d = webdriver.Chrome(service=s, options=opts)

# Use a known exhibitor with data
url = "https://www.iltm.com/cannes/en-gb/exhibitor-directory/exhibitor-details.fraser%20yachts.org-d0d47a24-cf1a-4d40-9a82-acde67da8e73.html"
d.get(url)
time.sleep(4)

result = d.execute_script("""
    // Dump everything visible on the page
    const getText = sel => {
        const el = document.querySelector(sel);
        return el ? el.textContent.trim() : null;
    };
    const getAll = sel => [...document.querySelectorAll(sel)].map(e => e.textContent.trim()).filter(Boolean);
    const getLinks = sel => [...document.querySelectorAll(sel + ' a[href]')].map(a => ({text: a.textContent.trim(), href: a.href}));

    // All sections on the page
    const sections = [...document.querySelectorAll('[class*="exhibitor-details"], [class*="exhibitor-contact"], [class*="exhibitor-summary"], [class*="exhibitor-desc"], [class*="description"]')];

    // All links on page
    const allLinks = [...document.querySelectorAll('a[href]')].map(a => ({
        href: a.href,
        text: a.textContent.trim().slice(0,60),
        cls: a.className.slice(0,40)
    })).filter(a => a.href && !a.href.includes('#') && a.text);

    // All text blocks with their class
    const textBlocks = sections.map(el => ({
        cls: el.className,
        text: el.innerText.trim().slice(0, 300)
    }));

    return {
        title: document.title,
        links: allLinks.filter(a => !a.href.includes('iltm.com/cannes/en-gb.html') && !a.href.includes('mega-nav')).slice(0, 30),
        text_blocks: textBlocks
    };
""")

print("=== TITRE ===")
print(result['title'])
print("\n=== LIENS (website/email/tel/social) ===")
for l in result['links']:
    print(f"  [{l['cls'][:30]}] {l['href'][:80]} | {l['text'][:40]}")
print("\n=== BLOCS TEXTE ===")
for b in result['text_blocks']:
    print(f"\n--- {b['cls']} ---")
    print(b['text'])

d.quit()
