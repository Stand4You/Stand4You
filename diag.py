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
opts.add_argument("--user-data-dir=C:\\Temp\\chrome-diag5")
s = Service(r"C:\Users\raf\.wdm\drivers\chromedriver\win64\149.0.7827.155\chromedriver-win64\chromedriver.exe")
d = webdriver.Chrome(service=s, options=opts)
d.get("https://www.iltm.com/cannes/en-gb/exhibitor-directory.html")
try:
    WebDriverWait(d, 8).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
    print("cookies ok")
except:
    print("no cookies banner")

time.sleep(5)

# Scroll to trigger lazy loading of all exhibitors
print("Scrolling to load all exhibitors...")
last_height = 0
for _ in range(30):
    d.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1.5)
    new_height = d.execute_script("return document.body.scrollHeight")
    count = d.execute_script("return document.querySelectorAll('.exhibitor-category').length")
    print(f"  height={new_height} exhibitors={count}")
    if new_height == last_height and count > 100:
        break
    last_height = new_height

print("Extracting...")
result = d.execute_script("""
    const items = [...document.querySelectorAll('.exhibitor-category')];
    return items.slice(0, 5).map(el => {
        const nameEl = el.querySelector('.exhibitor-name, h3, h2');
        const standEl = el.querySelector('.exhibitor-contact-container, [class*="stand"]');
        const linkEl = el.querySelector('a') || el.closest('a');
        const href = linkEl ? linkEl.href : '';
        return {
            name: nameEl ? nameEl.textContent.trim() : '',
            stand: standEl ? standEl.textContent.trim().slice(0, 30) : '',
            href: href
        };
    });
""")
print("Sample exhibitors:")
print(json.dumps(result, indent=2))

total = d.execute_script("return document.querySelectorAll('.exhibitor-category').length")
print(f"\nTotal .exhibitor-category dans le DOM: {total}")
d.quit()
