"""
debug_naukri.py — Run this FIRST to find correct Naukri selectors.
It opens Chrome, loads the search page, tries every known selector,
saves the full page source, and keeps the browser open for inspection.

Run: python debug_naukri.py
Then share the printed output so the bot can be fixed.
"""

import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TARGET_URL = "https://www.naukri.com/mern-stack-jobs?jobAge=3"

# ── Chrome (visible, suppress noise) ──────────────────────────────────────────
options = Options()
options.add_argument("--log-level=3")
options.add_argument("--disable-logging")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

print("Launching Chrome...")
driver = webdriver.Chrome(options=options)
driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

print(f"Opening: {TARGET_URL}")
driver.get(TARGET_URL)

print("Waiting 8 seconds for full page load (JS rendering)...")
time.sleep(8)

print(f"\nFinal URL after redirect: {driver.current_url}")
print(f"Page title              : {driver.title}")

# ── Selectors to test ──────────────────────────────────────────────────────────
SELECTORS = {
    # ── By CLASS_NAME ──────────────────────────────────────────────────────────
    "CLASS jobTuple":               (By.CLASS_NAME,   "jobTuple"),
    "CLASS job-tuple":              (By.CLASS_NAME,   "job-tuple"),
    "CLASS cust-job-tuple":         (By.CLASS_NAME,   "cust-job-tuple"),
    "CLASS srp-jobtuple-wrapper":   (By.CLASS_NAME,   "srp-jobtuple-wrapper"),
    "CLASS jobTupleHeader":         (By.CLASS_NAME,   "jobTupleHeader"),
    "CLASS listContainer":          (By.CLASS_NAME,   "listContainer"),
    "CLASS list":                   (By.CLASS_NAME,   "list"),

    # ── By CSS_SELECTOR (attribute) ────────────────────────────────────────────
    "CSS [data-job-id]":            (By.CSS_SELECTOR, "[data-job-id]"),
    "CSS [class*='tuple']":         (By.CSS_SELECTOR, "[class*='tuple']"),
    "CSS [class*='job-card']":      (By.CSS_SELECTOR, "[class*='job-card']"),
    "CSS [class*='jobCard']":       (By.CSS_SELECTOR, "[class*='jobCard']"),
    "CSS [class*='listing']":       (By.CSS_SELECTOR, "[class*='listing']"),
    "CSS [class*='srp']":           (By.CSS_SELECTOR, "[class*='srp']"),
    "CSS [class*='result']":        (By.CSS_SELECTOR, "[class*='result']"),
    "CSS [class*='job-container']": (By.CSS_SELECTOR, "[class*='job-container']"),
    "CSS [class*='jobContainer']":  (By.CSS_SELECTOR, "[class*='jobContainer']"),

    # ── By TAG ────────────────────────────────────────────────────────────────
    "TAG article":                  (By.TAG_NAME,     "article"),

    # ── Links / titles ────────────────────────────────────────────────────────
    "CSS a.title":                  (By.CSS_SELECTOR, "a.title"),
    "CSS a[class*='title']":        (By.CSS_SELECTOR, "a[class*='title']"),
    "CSS a.jobTitle":               (By.CSS_SELECTOR, "a.jobTitle"),
    "CSS [class*='jobTitle']":      (By.CSS_SELECTOR, "[class*='jobTitle']"),
    "CSS [class*='job-title']":     (By.CSS_SELECTOR, "[class*='job-title']"),

    # ── Company name ──────────────────────────────────────────────────────────
    "CSS a.comp-name":              (By.CSS_SELECTOR, "a.comp-name"),
    "CSS [class*='comp-name']":     (By.CSS_SELECTOR, "[class*='comp-name']"),
    "CSS [class*='company']":       (By.CSS_SELECTOR, "[class*='company']"),

    # ── Posted time ───────────────────────────────────────────────────────────
    "CSS span.job-post-day":        (By.CSS_SELECTOR, "span.job-post-day"),
    "CSS [class*='job-post-day']":  (By.CSS_SELECTOR, "[class*='job-post-day']"),
    "CSS [class*='date']":          (By.CSS_SELECTOR, "[class*='date']"),
    "CSS [class*='posted']":        (By.CSS_SELECTOR, "[class*='posted']"),

    # ── Apply button ──────────────────────────────────────────────────────────
    "XPATH Apply button":           (By.XPATH, "//button[contains(text(),'Apply')]"),
}

print("\n" + "="*70)
print("SELECTOR RESULTS")
print("="*70)

found_any = False
working_selectors = []

for label, (by, value) in SELECTORS.items():
    try:
        elements = driver.find_elements(by, value)
        count = len(elements)
        if count > 0:
            found_any = True
            working_selectors.append((label, by, value, count))
            first = elements[0]
            cls   = first.get_attribute("class") or "(no class)"
            txt   = first.text.strip().replace("\n", " ")[:100]
            tag   = first.tag_name
            print(f"\n✅ FOUND  [{label}]")
            print(f"   Count   : {count}")
            print(f"   Tag     : <{tag}>")
            print(f"   Class   : {cls[:100]}")
            print(f"   Text    : {txt}")
        else:
            print(f"❌ EMPTY  [{label}]")
    except Exception as exc:
        print(f"⚠️  ERROR  [{label}] — {exc}")

print("\n" + "="*70)

# ── Try to find job count text ─────────────────────────────────────────────────
print("\nJOB COUNT TEXT (looking for 'X of Y jobs'):")
count_sels = [
    "[class*='count']", "[class*='result-count']",
    "[class*='jobCount']", "[class*='job-count']",
    "span[class*='srp']", ".styles_count-string__DlPaZ",
]
for sel in count_sels:
    try:
        els = driver.find_elements(By.CSS_SELECTOR, sel)
        for el in els[:3]:
            txt = el.text.strip()
            if txt:
                print(f"  [{sel}] → '{txt}'")
    except Exception:
        pass

# Try XPATH for "jobs" keyword in spans
try:
    spans = driver.find_elements(By.XPATH, "//span[contains(text(),'jobs') or contains(text(),'Jobs')]")
    for s in spans[:5]:
        txt = s.text.strip()
        if txt:
            print(f"  SPAN jobs text → '{txt}'")
except Exception:
    pass

# ── Dump ALL unique top-level class names from the page body ───────────────────
print("\nTOP-LEVEL DIV CLASSES ON PAGE (first 40 unique non-empty):")
try:
    divs = driver.find_elements(By.XPATH, "//div[@class]")
    seen = set()
    for div in divs:
        cls = (div.get_attribute("class") or "").strip()
        if cls and cls not in seen:
            seen.add(cls)
            if len(seen) <= 40:
                print(f"  {cls}")
except Exception as exc:
    print(f"  Error: {exc}")

# ── Save full page source ──────────────────────────────────────────────────────
print("\nSaving page source to page_source.html ...")
try:
    Path("page_source.html").write_text(driver.page_source, encoding="utf-8")
    print("  Saved ✅  Open page_source.html in VS Code and search for job card classes.")
except Exception as exc:
    print(f"  Failed: {exc}")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("SUMMARY — WORKING SELECTORS:")
if working_selectors:
    for label, by, value, count in working_selectors:
        print(f"  ✅ {label:<40} → {count} elements")
else:
    print("  ⚠️  NO selectors found job cards!")
    print("  The page may require login, or Naukri changed their HTML.")
    print("  Check page_source.html and look for what wraps job listings.")

print("="*70)
print("\nBrowser staying open for 60 seconds — inspect with DevTools (F12).")
print("Look at the job cards in the Elements tab and copy their class names.")
print("Share the output above (copy-paste the terminal) to fix the bot.\n")

time.sleep(60)
driver.quit()
print("Browser closed.")
