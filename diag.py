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
opts.add_argument("--user-data-dir=C:\\Temp\\chrome-diag4")
s = Service(r"C:\Users\raf\.wdm\drivers\chromedriver\win64\149.0.7827.155\chromedriver-win64\chromedriver.exe")
d = webdriver.Chrome(service=s, options=opts)
d.get("https://www.iltm.com/cannes/en-gb/exhibitor-directory.html")
try:
    WebDriverWait(d, 8).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
    print("cookies ok")
except:
    print("no cookies banner")
time.sleep(8)
text = d.execute_script("return document.body.innerText.slice(0, 1000)")
print(text)
print("---")
count = d.execute_script("return document.querySelectorAll('a').length")
print("Total liens:", count)
d.quit()
