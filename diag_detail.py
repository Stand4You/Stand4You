"""
Inspecte une fiche exposant ILTM pour voir toutes les données disponibles.
Récupère d'abord une vraie URL depuis la liste, puis inspecte la fiche.
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

opts = Options()
opts.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
opts.add_argument("--no-sandbox")
opts.add_argument("--no-first-run")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--user-data-dir=C:\\Temp\\chrome-iltm")
opts.page_load_strategy = "none"
s = Service(r"C:\Users\raf\.wdm\drivers\chromedriver\win64\149.0.7827.155\chromedriver-win64\chromedriver.exe")
d = webdriver.Chrome(service=s, options=opts)

# Step 1: get a real URL from the directory
print("Chargement de l'annuaire pour obtenir une vraie URL...")
d.get("https://www.iltm.com/cannes/en-gb/exhibitor-directory.html")
try:
    WebDriverWait(d, 8).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
except:
    pass
time.sleep(4)
# Scroll a little to load some exhibitors
for i in range(3):
    d.execute_script(f"window.scrollTo(0, {(i+1)*2000})")
    time.sleep(1.5)

urls = d.execute_script("""
    return [...document.querySelectorAll('.exhibitor-category a')].slice(0,3).map(a => ({name: a.textContent.trim().slice(0,50), href: a.href}));
""")
print("URLs trouvées:", urls)

if not urls:
    print("Aucune URL trouvée.")
    d.quit()
    exit()

# Step 2: visit the first detail page
url = urls[0]['href']
name = urls[0]['name']
print(f"\nInspection de : {name}\n{url}\n")

d.get(url)
time.sleep(4)

result = d.execute_script("""
    // All links on the page excluding navigation
    const navClasses = ['global-nav', 'mega-nav', 'mobile-nav', 'tile__base', 'footer', 'skip-link'];
    const allLinks = [...document.querySelectorAll('a[href]')].filter(a => {
        const cls = a.className || '';
        return !navClasses.some(nc => cls.includes(nc));
    }).map(a => ({
        href: a.href,
        text: a.textContent.trim().slice(0, 60),
        cls: a.className.slice(0, 40)
    })).filter(a => a.text);

    // All visible text sections
    const mainContent = document.querySelector('main, [class*="exhibitor-details"], #main, .main-content');
    const mainText = mainContent ? mainContent.innerText.trim() : document.body.innerText.slice(0, 3000);

    return {
        links: allLinks,
        main_text: mainText.slice(0, 3000)
    };
""")

print("=== CONTENU DE LA PAGE ===")
print(result['main_text'])
print("\n=== LIENS (hors navigation) ===")
for l in result['links']:
    print(f"  {l['href'][:80]} | {l['text'][:50]}")

d.quit()
