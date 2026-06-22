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
opts.add_argument("--user-data-dir=C:\\Temp\\chrome-diag4")
s = Service(r"C:\Users\raf\.wdm\drivers\chromedriver\win64\149.0.7827.155\chromedriver-win64\chromedriver.exe")
d = webdriver.Chrome(service=s, options=opts)
d.get("https://www.iltm.com/cannes/en-gb/exhibitor-directory.html")
try:
    WebDriverWait(d, 8).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
    print("cookies ok")
except:
    print("no cookies banner")

time.sleep(4)

# Scroll down to trigger lazy loading
print("Scrolling...")
for i in range(5):
    d.execute_script(f"window.scrollTo(0, {(i+1)*800})")
    time.sleep(1.5)

time.sleep(3)

# Look for exhibitor items
result = d.execute_script("""
    const allA = [...document.querySelectorAll('a')];
    // Find links that look like exhibitor detail pages
    const candidates = allA.filter(a => {
        const href = a.href || '';
        const text = a.textContent.trim();
        return text.length > 2 && text.length < 100 && href.includes('iltm.com') &&
               !href.includes('hub') && !href.includes('about') && !href.includes('contact') &&
               !href.includes('login') && !href.includes('enquire') && !href.includes('.com/cannes/en-gb.html') &&
               !href.includes('sustainability') && !href.includes('media') && !href.includes('programme');
    });
    return {
        total_links: allA.length,
        candidate_count: candidates.length,
        sample: candidates.slice(0, 5).map(a => ({
            href: a.href,
            text: a.textContent.trim().slice(0, 60),
            cls: a.className.slice(0, 60)
        }))
    };
""")
print(json.dumps(result, indent=2))
d.quit()
