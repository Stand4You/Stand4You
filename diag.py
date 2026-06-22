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

# Scroll to trigger lazy loading
for i in range(8):
    d.execute_script(f"window.scrollTo(0, {(i+1)*1000})")
    time.sleep(1)

time.sleep(3)

result = d.execute_script("""
    // Check for iframes
    const iframes = [...document.querySelectorAll('iframe')].map(f => f.src);

    // Look for any element with exhibitor-related classes or data attributes
    const allEls = [...document.querySelectorAll('[class*="exhibitor"], [data-exhibitor], [class*="Exhibitor"]')];

    // Look for elements that might be list items (li, article, div with many siblings)
    const articles = [...document.querySelectorAll('article, [role="listitem"], li')].slice(0, 5);

    // Get page height to see if content loaded
    const pageHeight = document.body.scrollHeight;

    return {
        iframes: iframes,
        exhibitor_els: allEls.slice(0,5).map(e => ({tag:e.tagName, cls:e.className.slice(0,60), text:e.textContent.trim().slice(0,80)})),
        articles: articles.map(e => ({tag:e.tagName, cls:e.className.slice(0,60), text:e.textContent.trim().slice(0,60)})),
        page_height: pageHeight
    };
""")
print(json.dumps(result, indent=2))
d.quit()
