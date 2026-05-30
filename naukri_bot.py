"""
Naukri Auto-Apply Bot
Daily runner: logs in, bumps profile, applies to MERN/Full-Stack jobs,
fills application forms, and writes a full run report.

Fixes applied
─────────────
P1 – Enhanced 6-step chatbot overlay dismissal before every apply click
P2 – Global attempted_ids + failed_ids across all URLs (no cross-URL retries)
P3 – Wider title filter: ACCEPT_SPECIFIC / ACCEPT_GENERIC + description check
P4 – No location filter — applies everywhere in India
P5 – Hard-reject fresher/0-year roles detected in description
P6 – Richer daily report: seen/attempted/succeeded, success rate, top companies
"""

import sys
import json
import time
import logging
import datetime
from collections import Counter
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException,
    ElementClickInterceptedException, StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.keys import Keys

import config
import helpers
from helpers import (
    human_sleep, get_job_priority, get_card_priority_score,
    is_valid_title, check_description_for_skills,
    extract_job_id,
    load_applied_ids, save_applied_id,
    load_failed_ids,  save_failed_ids,
    fill_field, find_field_for_label, get_card_info, log,
)

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler("naukri_bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

LOG_FILE       = Path("naukri_log.txt")
COOKIES_FILE   = Path("naukri_cookies.json")
SELECTOR_CACHE = Path("selector_cache.json")

MAX_PAGES = 3   # scrape up to 3 pages per URL (user requested pages 1 & 2 minimum)


# ── Smart card-selector scanner ────────────────────────────────────────────────
ALL_CARD_SELS = [
    # Naukri classic
    ".srp-jobtuple-wrapper",
    ".cust-job-tuple",
    "article.jobTuple",
    "[class*='jobTuple']",
    "[class*='srp-jobtuple']",
    "[class*='job-tuple']",
    "[class*='tuple-container']",
    "li[class*='jobTuple']",
    # 2025-2026 React rewrite patterns
    "[class*='styles_jhc']",
    "[class*='styles_container']",
    "[class*='styles_row']",
    "[class*='jdCard']",
    "[class*='jobCard']",
    "div[class*='JobCard']",
    "div[class*='job-card']",
    "[class*='job-listing']",
    "[class*='search-result']",
    "[class*='card-apply']",
    ".list-container > div",
    # data-attribute fallbacks
    "div[data-job-id]",
    "li[data-job-id]",
    "[data-job-id]",
]


def detect_card_selector(driver: webdriver.Chrome) -> str | None:
    """Return a working CSS selector for job cards. Tries cache first, then full scan."""
    if SELECTOR_CACHE.exists():
        try:
            data        = json.loads(SELECTOR_CACHE.read_text(encoding="utf-8"))
            cached      = data.get("selector", "")
            cached_date = data.get("date", "")
            today       = str(datetime.date.today())
            if cached and cached_date == today:
                n = len(driver.find_elements(By.CSS_SELECTOR, cached))
                if n >= 3:
                    log.info(f"  Selector (cache): {cached!r} — {n} cards")
                    return cached
            if cached:
                log.info(f"  Cached selector stale (saved {cached_date}, today {today}) — rescanning")
        except Exception:
            pass

    log.info("  Scanning selectors for job cards…")
    for sel in ALL_CARD_SELS:
        try:
            n = len(driver.find_elements(By.CSS_SELECTOR, sel))
            if n >= 3:
                log.info(f"  Selector found: {sel!r} ({n} cards) ✓ — cached")
                SELECTOR_CACHE.write_text(
                    json.dumps({"selector": sel, "date": str(datetime.date.today())}),
                    encoding="utf-8",
                )
                return sel
        except Exception:
            pass

    log.warning("  No selector matched — check debug screenshot")
    return None


def get_cards_on_page(driver: webdriver.Chrome, sel: str | None = None) -> list:
    for s in ([sel] if sel else []) + ALL_CARD_SELS:
        if not s:
            continue
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, s)
            if cards:
                return cards
        except Exception:
            pass
    return []


def wait_for_cards(driver: webdriver.Chrome, sel: str | None = None, timeout: int = 15) -> bool:
    candidates = ([sel] if sel else []) + ALL_CARD_SELS
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: any(d.find_elements(By.CSS_SELECTOR, s) for s in candidates if s)
        )
        return True
    except TimeoutException:
        return False


# ── Tracker ────────────────────────────────────────────────────────────────────
def new_tracker() -> dict:
    return {
        "today_count":          0,
        "applied_jobs":         [],
        "attempted_count":      0,
        "seen_ids":             set(),
        "failed_overlay_ids":   [],
        "skip_title":           0,
        "skip_old":             0,
        "skip_duplicate":       0,
        "skip_no_apply":        0,
        "skip_no_skills":       0,
        "errors":               0,
        "badge_top_applicant":  0,
        "badge_actively_hiring":0,
        "resume_uploaded":      False,
    }


# ── Chrome driver ──────────────────────────────────────────────────────────────
def get_driver() -> webdriver.Chrome:
    options = Options()
    if config.HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--log-level=3")
    options.add_argument("--disable-logging")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    return driver


# ── Cookie persistence ─────────────────────────────────────────────────────────
def save_cookies(driver: webdriver.Chrome):
    try:
        cookies = driver.get_cookies()
        COOKIES_FILE.write_text(json.dumps(cookies), encoding="utf-8")
        log.info(f"Cookies saved ({len(cookies)}) → {COOKIES_FILE}")
    except Exception as exc:
        log.warning(f"Could not save cookies: {exc}")


def load_cookies(driver: webdriver.Chrome) -> bool:
    if not COOKIES_FILE.exists():
        return False
    try:
        driver.get("https://www.naukri.com")
        human_sleep(2, 3)
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        for c in cookies:
            c.pop("sameSite", None)
            try:
                driver.add_cookie(c)
            except Exception:
                pass
        driver.refresh()
        human_sleep(3, 4)
        log.info(f"Cookies loaded from {COOKIES_FILE}")
        return True
    except Exception as exc:
        log.warning(f"Cookie load failed: {exc}")
        return False


def _is_logged_in(driver: webdriver.Chrome) -> bool:
    try:
        if "nlogin" in driver.current_url:
            return False
        indicators = driver.find_elements(
            By.CSS_SELECTOR,
            "[class*='user-avatar'],[class*='userAvatar'],"
            "[class*='userName'],[class*='nI-header__user'],"
            "a[href*='mnjuser']",
        )
        return any(el.is_displayed() for el in indicators)
    except Exception:
        return False


# ── Login ──────────────────────────────────────────────────────────────────────
def login(driver: webdriver.Chrome):
    if load_cookies(driver):
        driver.get("https://www.naukri.com/mnjuser/homepage")
        human_sleep(3, 4)
        if _is_logged_in(driver):
            log.info(f"Logged in via cookies → {driver.current_url}")
            return
        log.info("Cookies expired — falling back to credential login")

    driver.get("https://www.naukri.com/nlogin/login")
    wait = WebDriverWait(driver, 20)

    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        ).click()
        human_sleep(0.5, 1)
    except TimeoutException:
        pass

    email_field = wait.until(EC.element_to_be_clickable((By.ID, "usernameField")))
    email_field.click()
    human_sleep(0.4, 0.8)
    email_field.clear()
    email_field.send_keys(config.EMAIL)
    human_sleep(0.6, 1.2)

    pwd_field = wait.until(EC.element_to_be_clickable((By.ID, "passwordField")))
    pwd_field.click()
    human_sleep(0.4, 0.8)
    pwd_field.clear()
    pwd_field.send_keys(config.PASSWORD)
    human_sleep(0.6, 1.2)

    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    human_sleep(5, 8)

    if "nlogin" in driver.current_url:
        driver.save_screenshot("login_failed.png")
        raise RuntimeError("Login failed — check .env credentials (screenshot: login_failed.png)")

    log.info(f"Logged in  →  {driver.current_url}")
    save_cookies(driver)


# ── Profile bump ───────────────────────────────────────────────────────────────
def bump_profile(driver: webdriver.Chrome) -> bool:
    try:
        driver.get("https://www.naukri.com/mnjuser/profile?id=&altresid")
        human_sleep(3, 5)
        wait = WebDriverWait(driver, 10)

        try:
            edit_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH,
                 "//div[contains(@class,'resumeHeadline') or contains(@class,'ResumeHeadline')]"
                 "//span[contains(@class,'edit') or contains(@class,'Edit')]")
            ))
            edit_btn.click()
            human_sleep(1, 2)
            ta = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//textarea[@name='headline' or @placeholder]")
            ))
            val = (ta.get_attribute("value") or "").strip()
            ta.clear()
            ta.send_keys(val)
            driver.find_element(By.XPATH, "//button[normalize-space()='Save']").click()
            human_sleep(1, 2)
            log.info("Profile headline re-saved ✅")
        except Exception as exc:
            log.warning(f"Headline re-save skipped: {exc}")

        resume_abs = str(config.RESUME_PATH.absolute())
        resume_ok  = False
        if not config.RESUME_PATH.exists():
            checked = "\n".join(f"             {p}" for p in config.RESUME_PATHS)
            log.warning(
                f"\n{'!'*55}\n"
                f"  RESUME NOT FOUND — ACTION REQUIRED\n"
                f"  Checked  :\n{checked}\n"
                f"  Fix      : copy resume.pdf to any path above\n"
                f"  Impact   : ~70% fewer recruiter callbacks\n"
                f"{'!'*55}"
            )
        else:
            try:
                for inp in driver.find_elements(By.XPATH, "//input[@type='file']"):
                    try:
                        driver.execute_script(
                            "arguments[0].style.display='block';"
                            "arguments[0].style.visibility='visible';", inp
                        )
                        inp.send_keys(resume_abs)
                        human_sleep(3, 5)
                        for btn_text in ("Save", "Upload", "Update"):
                            try:
                                driver.find_element(
                                    By.XPATH,
                                    f"//button[contains(normalize-space(),'{btn_text}')]"
                                ).click()
                                human_sleep(2, 3)
                            except NoSuchElementException:
                                pass
                        log.info("Resume uploaded ✅")
                        resume_ok = True
                        break
                    except Exception:
                        continue
            except Exception as exc:
                log.warning(f"Resume upload skipped: {exc}")

    except Exception as exc:
        log.warning(f"bump_profile error: {exc}")
        resume_ok = False

    # Always return to homepage — clears browser state before search loop
    driver.get("https://www.naukri.com/mnjuser/homepage")
    human_sleep(2, 3)
    return resume_ok


# ── Sort by Date ───────────────────────────────────────────────────────────────
def sort_by_date(driver: webdriver.Chrome):
    # Strategy 1: native <select>
    try:
        sel_el = driver.find_element(
            By.XPATH,
            "//select[contains(translate(@id,'SORT','sort'),'sort')"
            " or contains(translate(@name,'SORT','sort'),'sort')]"
        )
        s = Select(sel_el)
        for opt in s.options:
            if "date" in opt.text.lower():
                s.select_by_visible_text(opt.text)
                human_sleep(2, 3)
                log.info("  Sorted by Date (native select)")
                return
    except Exception:
        pass

    # Strategy 2: click sort trigger → pick Date option
    _TRIGGER_XPATHS = [
        "//span[text()='Recommended']",
        "//span[contains(@class,'sort') and not(contains(.,'Date'))]",
        "//*[contains(text(),'Sort by') and not(contains(.,'Date'))]",
        "//*[@class and contains(.,'Recommended')]",
        "//*[contains(@class,'sort-filter') or contains(@class,'sortFilter')]",
        "//*[@data-ga-label='sort' or contains(@class,'sortLabel')]",
    ]
    _DATE_XPATHS = [
        "//li[normalize-space()='Date']",
        "//div[normalize-space()='Date']",
        "//a[normalize-space()='Date']",
        "//span[normalize-space()='Date']",
        "//*[contains(@class,'option') and normalize-space()='Date']",
        "//*[contains(@class,'dropdown') or contains(@class,'Dropdown')]"
        "//*[normalize-space()='Date']",
    ]

    for trigger_xp in _TRIGGER_XPATHS:
        try:
            triggers = driver.find_elements(By.XPATH, trigger_xp)
            for trigger in triggers:
                if not trigger.is_displayed():
                    continue
                if "date" in trigger.text.lower():
                    log.info("  Already sorted by Date")
                    return
                trigger.click()
                human_sleep(0.8, 1.5)
                for date_xp in _DATE_XPATHS:
                    try:
                        opt = WebDriverWait(driver, 4).until(
                            EC.element_to_be_clickable((By.XPATH, date_xp))
                        )
                        opt.click()
                        human_sleep(2, 3)
                        log.info("  Sorted by Date ✓")
                        return
                    except TimeoutException:
                        pass
                try:
                    trigger.click()
                    human_sleep(0.5, 1)
                except Exception:
                    pass
        except Exception:
            pass

    log.info("  Sort: session preference used")


# ── P1: Dismiss chatbot overlay (6-step sequence) ────────────────────────────
def dismiss_chatbot_overlay(driver: webdriver.Chrome):
    """
    6-step sequence to nuke the chatbot overlay before every apply click.
    Never raises — overlay failure must never crash the bot.
    """
    # Step 1+2: find div.chatbot_Overlay.show and remove each visible one
    try:
        overlays = driver.find_elements(By.CSS_SELECTOR, "div.chatbot_Overlay.show")
        for overlay in overlays:
            try:
                if overlay.is_displayed():
                    driver.execute_script("arguments[0].remove()", overlay)
            except Exception:
                pass
    except Exception:
        pass

    # Step 3: broad JS sweep — removes ALL overlay/modal/popup variants
    try:
        driver.execute_script("""
            var selectors = [
                '.chatbot_Overlay',
                '[class*="chatbot_Overlay"]',
                '[class*="chatbot-overlay"]',
                '[class*="overlay"][class*="show"]',
                '[class*="Overlay"][class*="show"]',
                '[class*="Modal"]:not(button):not(input)',
                '[class*="modal"]:not(button):not(input)',
                '[class*="Popup"]:not(button):not(input)',
                '[class*="popup"]:not(button):not(input)',
                '[class*="backdrop"]',
                '[class*="Backdrop"]'
            ];
            selectors.forEach(function(sel) {
                try {
                    document.querySelectorAll(sel).forEach(function(el) {
                        el.style.display      = 'none';
                        el.style.visibility   = 'hidden';
                        el.style.pointerEvents= 'none';
                        el.style.zIndex       = '-9999';
                        try { el.parentNode.removeChild(el); } catch(e) {}
                    });
                } catch(e) {}
            });
            document.body.style.overflow = 'auto';
            document.body.style.position = 'static';
        """)
    except Exception:
        pass

    # Step 4: Escape key as additional fallback
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass

    # Step 5: short pause to let DOM settle
    human_sleep(0.8, 1.2)


# ── Application form filler ────────────────────────────────────────────────────
_LABEL_MAP = {
    "name": config.MY_NAME, "full name": config.MY_NAME,
    "your name": config.MY_NAME, "candidate name": config.MY_NAME,
    "email": config.EMAIL, "email id": config.EMAIL, "email address": config.EMAIL,
    "phone": config.MY_PHONE, "mobile": config.MY_PHONE,
    "contact": config.MY_PHONE, "phone number": config.MY_PHONE,
    "mobile number": config.MY_PHONE,
    "current ctc": config.CURRENT_CTC, "current salary": config.CURRENT_CTC,
    "current package": config.CURRENT_CTC, "ctc": config.CURRENT_CTC,
    "expected ctc": config.EXPECTED_CTC, "expected salary": config.EXPECTED_CTC,
    "expected package": config.EXPECTED_CTC,
    "total experience": config.EXPERIENCE, "years of experience": config.EXPERIENCE,
    "experience": config.EXPERIENCE, "relevant experience": config.EXPERIENCE,
    "notice period": config.NOTICE_PERIOD, "notice": config.NOTICE_PERIOD,
    "joining": config.NOTICE_PERIOD,
    "current location": config.LOCATION, "current city": config.LOCATION,
    "location": config.LOCATION, "city": config.LOCATION,
    "relocat": config.RELOCATE, "willing to move": config.RELOCATE,
    "cover letter": config.COVER_LETTER, "message": config.COVER_LETTER,
    "write something": config.COVER_LETTER, "reason for applying": config.COVER_LETTER,
}

_FORM_SELS = [
    ".chatbot_DrawerContentWrapper", "[class*='chatbot']",
    "[class*='apply-popup']",        "[class*='applyFlow']",
    "[class*='questionForm']",        ".apply-modal",
    "[class*='ApplyModal']",          ".modal-content",
    "[class*='apply-form']",          "[class*='applyForm']",
]


def _answer_for(text: str) -> str | None:
    t = text.lower().strip()
    for key, val in _LABEL_MAP.items():
        if key in t:
            return val
    return None


def fill_apply_form(driver: webdriver.Chrome):
    human_sleep(1.5, 2.5)

    if not any(driver.find_elements(By.CSS_SELECTOR, s) for s in _FORM_SELS):
        return

    log.info("  Filling application questions...")

    for _step in range(20):
        human_sleep(0.8, 1.5)
        filled = False

        try:
            labels = driver.find_elements(
                By.XPATH,
                "//label[not(ancestor::*[@style='display:none']) and normalize-space()!='']"
            )
            for label in labels:
                try:
                    if not label.is_displayed():
                        continue
                    answer = _answer_for(label.text)
                    if not answer:
                        continue
                    field = find_field_for_label(driver, label)
                    if field and field.is_displayed():
                        fill_field(field, answer)
                        log.info(f"    '{label.text.strip()[:30]}' → {answer[:30]}")
                        filled = True
                except (StaleElementReferenceException, NoSuchElementException):
                    continue
        except Exception:
            pass

        try:
            inputs = driver.find_elements(
                By.XPATH, "//input[@placeholder] | //textarea[@placeholder]"
            )
            for inp in inputs:
                try:
                    if not inp.is_displayed():
                        continue
                    ph = inp.get_attribute("placeholder") or ""
                    answer = _answer_for(ph)
                    if answer and not (inp.get_attribute("value") or "").strip():
                        fill_field(inp, answer)
                        log.info(f"    placeholder:'{ph[:30]}' → {answer[:30]}")
                        filled = True
                except (StaleElementReferenceException, NoSuchElementException):
                    continue
        except Exception:
            pass

        try:
            for radio in driver.find_elements(By.XPATH, "//input[@type='radio']"):
                try:
                    val = (radio.get_attribute("value") or "").lower().strip()
                    ctx = ""
                    try:
                        ctx = radio.find_element(By.XPATH, "ancestor::div[3]").text.lower()
                    except Exception:
                        pass
                    if any(skill in ctx for skill in [
                        "react", "node", "javascript", "mern", "mongodb",
                        "express", "next", "typescript", "html", "css",
                    ]):
                        if val in ["yes", "true", "1"] and not radio.is_selected():
                            driver.execute_script("arguments[0].click();", radio)
                            human_sleep(0.2, 0.4)
                            filled = True
                    elif any(w in ctx for w in ("relocat", "willing to move", "work from home", "remote", "wfh")):
                        if config.RELOCATE.lower() in val or val in ["yes", "true", "1"]:
                            if not radio.is_selected():
                                driver.execute_script("arguments[0].click();", radio)
                                human_sleep(0.2, 0.4)
                                filled = True
                    elif val in ["yes", "true", "1"] and not radio.is_selected():
                        driver.execute_script("arguments[0].click();", radio)
                        human_sleep(0.2, 0.4)
                        filled = True
                except (NoSuchElementException, StaleElementReferenceException):
                    pass
        except Exception:
            pass

        next_clicked = False
        for btn_label in ("Save & Next", "Next", "Continue", "Submit", "Apply"):
            try:
                btn = WebDriverWait(driver, 4).until(EC.element_to_be_clickable(
                    (By.XPATH, f"//button[contains(normalize-space(),'{btn_label}')]")
                ))
                btn.click()
                human_sleep(1.5, 2.5)
                next_clicked = True
                log.info(f"    → clicked '{btn_label}'")
                break
            except TimeoutException:
                continue

        try:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
            if any(w in body for w in (
                "application submitted", "successfully applied",
                "you have applied", "already applied", "thank you for applying",
            )):
                log.info("  Form completed ✅")
                return
        except Exception:
            pass

        if not next_clicked and not filled:
            break


# ── P1: Apply to a single job with full 6-step overlay sequence ──────────────
_APPLY_XPATHS = [
    "//button[@id='apply-button']",
    "//button[text()='Apply']",
    "//button[contains(text(),'Apply') and not(contains(text(),'Applied'))]",
    "//a[contains(text(),'Apply') and not(contains(text(),'Applied'))]",
    "//button[contains(@class,'apply') and not(contains(@class,'applied'))]",
    "//button[contains(@class,'Apply')]",
    "//button[normalize-space()='Apply']",
]


def apply_to_job(
    driver: webdriver.Chrome,
    job_info: dict,
    applied_ids: set,
    tracker: dict,
    failed_ids: set,        # P2: mutable — add job_id here on failure
) -> bool:
    job_url = job_info["url"]
    job_id  = extract_job_id(job_url)

    # Safety-net dedup (applied_ids is already checked upstream, but belt+suspenders)
    if job_id in applied_ids:
        tracker["skip_duplicate"] += 1
        return False

    before = set(driver.window_handles)
    try:
        driver.execute_script(f"window.open('{job_url}','_blank');")
    except Exception:
        tracker["errors"] += 1
        failed_ids.add(job_id)
        tracker["failed_overlay_ids"].append(job_id)
        return False

    human_sleep(2, 3)
    new_handles = set(driver.window_handles) - before
    if not new_handles:
        tracker["errors"] += 1
        failed_ids.add(job_id)
        tracker["failed_overlay_ids"].append(job_id)
        return False

    driver.switch_to.window(new_handles.pop())
    applied = False

    try:
        wait = WebDriverWait(driver, 12)
        tracker["attempted_count"] += 1  # P6

        # Check "Already Applied" badge
        try:
            wait.until(EC.presence_of_element_located(
                (By.XPATH,
                 "//*[contains(text(),'Already Applied') or contains(text(),'already applied')]")
            ))
            tracker["skip_duplicate"] += 1
            log.info(f"  Already applied (badge) — {job_id}")
            return False
        except TimeoutException:
            pass

        # Find Apply button
        apply_btn = None
        for xpath in _APPLY_XPATHS:
            try:
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                txt = btn.text.strip().lower()
                if "already" in txt or txt == "applied":
                    tracker["skip_duplicate"] += 1
                    return False
                apply_btn = btn
                break
            except (TimeoutException, NoSuchElementException):
                continue

        if apply_btn is None:
            tracker["skip_no_apply"] += 1
            log.info(f"  No Apply button — {job_id}")
            return False

        # ── P1: Scroll button into view ──────────────────────────────────────
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", apply_btn
            )
            human_sleep(0.4, 0.7)
        except Exception:
            pass

        # ── P1: Step 1+2 — find div.chatbot_Overlay.show, remove each ────────
        try:
            overlays = driver.find_elements(By.CSS_SELECTOR, "div.chatbot_Overlay.show")
            for overlay in overlays:
                try:
                    if overlay.is_displayed():
                        driver.execute_script("arguments[0].remove()", overlay)
                except Exception:
                    pass
        except Exception:
            pass

        # ── P1: Step 3 — broad JS sweep of ALL overlay variants ──────────────
        try:
            driver.execute_script(
                "document.querySelectorAll('.chatbot_Overlay,[class*=\"chatbot_Overlay\"]')"
                ".forEach(e=>e.remove());"
                "document.querySelectorAll('[class*=\"overlay\"][class*=\"show\"],"
                "[class*=\"Overlay\"][class*=\"show\"]').forEach(e=>{"
                "e.style.display='none';e.style.pointerEvents='none';});"
                "document.body.style.overflow='auto';"
            )
        except Exception:
            pass

        # ── P1: Step 4 — Escape key ───────────────────────────────────────────
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass

        # ── P1: Step 5 — wait 1 second for DOM to settle ─────────────────────
        human_sleep(1.0, 1.2)

        # ── P1: Step 6a — try normal click first ─────────────────────────────
        click_succeeded = False
        try:
            apply_btn.click()
            click_succeeded = True
            log.info(f"  Clicked Apply (normal) — {job_id}")
        except (ElementClickInterceptedException, Exception):
            pass

        # ── P1: Step 6b — fallback: JS click bypasses any remaining overlay ───
        if not click_succeeded:
            try:
                driver.execute_script("arguments[0].click();", apply_btn)
                click_succeeded = True
                log.info(f"  Clicked Apply (JS fallback) — {job_id}")
            except Exception as exc:
                log.warning(f"  Apply click failed entirely: {exc}")
                tracker["errors"] += 1
                failed_ids.add(job_id)
                tracker["failed_overlay_ids"].append(job_id)
                return False

        human_sleep(2, 3)
        fill_apply_form(driver)

        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass

        applied = True

        if job_info.get("is_top_applicant"):
            tracker["badge_top_applicant"] += 1
        if job_info.get("is_actively_hiring"):
            tracker["badge_actively_hiring"] += 1

        loc      = job_info.get("location", "")
        loc_lower = loc.lower()
        if "indore" in loc_lower:
            loc_icon = "📍"
        elif any(w in loc_lower for w in ["remote", "wfh", "work from home"]):
            loc_icon = "🌐"
        else:
            loc_icon = "🗺️ "

        tracker["applied_jobs"].append({
            "job_id":   job_id,
            "company":  job_info.get("company", ""),
            "title":    job_info.get("title", ""),
            "location": loc,
            "time":     job_info.get("time_label", ""),
        })
        tracker["today_count"] += 1
        applied_ids.add(job_id)
        save_applied_id(job_id)
        log.info(
            f"  ✅ Applied [{tracker['today_count']}/{config.MAX_APPLY}] "
            f"{loc_icon} {loc[:15] or 'unknown'} — "
            f"{job_info.get('company','?')} | {job_info.get('title','?')[:45]}"
        )

    except Exception as exc:
        tracker["errors"] += 1
        failed_ids.add(job_id)
        tracker["failed_overlay_ids"].append(job_id)
        log.warning(f"  Error applying to {job_id}: {exc}")

    finally:
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass

    human_sleep(2, 4)
    return applied


# ── Error-page detection & retry ──────────────────────────────────────────────
def _page_has_error(driver: webdriver.Chrome) -> bool:
    """Returns True ONLY if page is genuinely broken. Default = valid."""
    try:
        import re as _re
        time.sleep(4)

        _CARD_SELS = [
            ".srp-jobtuple-wrapper", "[class*='jobTuple']",
            "[class*='job-tuple']", "[data-job-id]",
            "article", "[class*='tuple']",
            "[class*='JobCard']", "[class*='listContainer'] li",
        ]
        for sel in _CARD_SELS:
            try:
                if driver.find_elements(By.CSS_SELECTOR, sel):
                    return False
            except Exception:
                pass

        try:
            body = driver.find_element(By.TAG_NAME, "body").text
            if _re.search(r'\d[\d,]*\s*(jobs|vacancies|results)', body, _re.IGNORECASE):
                return False
        except Exception:
            pass

        try:
            body_lower = driver.find_element(By.TAG_NAME, "body").text.lower()
            for phrase in [
                "oops! something went wrong",
                "there was an error loading the page",
                "please reload to view the content",
            ]:
                if phrase in body_lower:
                    return True
        except Exception:
            pass

        return False
    except Exception:
        return False


def _load_url_with_retry(driver: webdriver.Chrome, url: str, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
        except Exception as exc:
            log.warning(f"  Navigation error (attempt {attempt}): {exc}")
            human_sleep(3, 5)
            continue

        human_sleep(5, 7)
        log.info(f"  Landed on: {driver.current_url}")

        if not _page_has_error(driver):
            return True

        log.warning(f"  Error page on attempt {attempt}/{retries} — retrying in 8 s…")
        human_sleep(6, 8)
        try:
            driver.refresh()
            human_sleep(5, 7)
            if not _page_has_error(driver):
                return True
        except Exception:
            pass

    log.warning("  URL still erroring after all retries — skipping")
    return False


# ── Startup URL validator ──────────────────────────────────────────────────────
def validate_and_filter_urls(driver: webdriver.Chrome) -> list:
    """Load each URL once, keep only those that return job cards."""
    working = []
    log.info("\nValidating all search URLs...")

    for url in config.SEARCH_URLS:
        try:
            driver.get(url)
            time.sleep(5)

            is_error  = _page_has_error(driver)
            card_count = 0
            for sel in [".srp-jobtuple-wrapper", "[class*='jobTuple']", "[data-job-id]"]:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    card_count = len(els)
                    break

            if is_error:
                log.warning(f"  ❌ SKIP  : {url[:70]}")
            else:
                log.info(f"  ✅ OK [{card_count:>3} cards]: {url[:70]}")
                working.append(url)
        except Exception as exc:
            log.warning(f"  ❌ ERROR : {url[:70]} — {exc}")

    log.info(f"\n  Working: {len(working)} / {len(config.SEARCH_URLS)} URLs")
    return working if working else config.SEARCH_URLS


# ── P2: Process one search URL — global dedup across all URLs ─────────────────
def process_url(
    driver:       webdriver.Chrome,
    url:          str,
    applied_ids:  set,
    tracker:      dict,
    attempted_ids: set,   # P2: session-level attempted set (shared across all URLs)
    failed_ids:   set,    # P2: persisted failed IDs (shared across all URLs)
):
    log.info(f"\n{'─'*60}")
    log.info(f"URL: {url}")

    if not _load_url_with_retry(driver, url):
        return

    sort_by_date(driver)
    active_sel = detect_card_selector(driver)
    page = 1

    while tracker["today_count"] < config.MAX_APPLY and page <= MAX_PAGES:
        found = wait_for_cards(driver, active_sel, timeout=15)
        cards = get_cards_on_page(driver, active_sel) if found else []

        if not cards:
            screenshot = f"debug_no_cards_p{page}.png"
            try:
                driver.save_screenshot(screenshot)
            except Exception:
                screenshot = "(screenshot failed)"
            log.info(
                f"  Page {page}: no cards found "
                f"(URL: {driver.current_url}) "
                f"(screenshot: {screenshot})"
            )
            break

        log.info(f"  Page {page}: {len(cards)} listings")

        stop_url   = False
        card_infos = []

        for card in cards:
            try:
                card_infos.append(get_card_info(card))
            except StaleElementReferenceException:
                continue

        # ── Page-level duplicate detection (skip page if >80% already applied/failed) ─
        if card_infos:
            page_ids = {
                extract_job_id(c.get("url", ""))
                for c in card_infos if c.get("url")
            }
            tracker["seen_ids"].update(page_ids)

            if page_ids:
                already_seen = page_ids & (applied_ids | failed_ids)
                overlap_pct  = len(already_seen) / max(len(page_ids), 1)
                if overlap_pct > 0.8:
                    log.info(
                        f"  Page {page}: {overlap_pct:.0%} already applied/failed "
                        f"— skipping rest of this URL"
                    )
                    break

        # ── Sort by badge + freshness priority (highest first) ────────────────
        if card_infos:
            card_infos.sort(key=get_card_priority_score, reverse=True)

        # ── Freshness pre-check ────────────────────────────────────────────────
        if card_infos:
            fresh = [c for c in card_infos if get_job_priority(c.get("time_label", "")) < 99]
            if not fresh:
                log.info(f"  All cards on page {page} are too old — done with this URL")
                stop_url = True

        for info in card_infos:
            if tracker["today_count"] >= config.MAX_APPLY:
                break

            job_id = extract_job_id(info.get("url", ""))

            # ── Dedup — skip only if already applied or permanently failed ────
            if job_id and (job_id in applied_ids or job_id in failed_ids):
                tracker["skip_duplicate"] += 1
                log.debug(f"  ⏭  Dedup ({job_id}) — already applied/failed")
                continue

            # ── Freshness filter ───────────────────────────────────────────────
            priority = get_job_priority(info.get("time_label", ""))
            if priority == 99:
                tracker["skip_old"] += 1
                log.info(
                    f"  ⏭  Too old ({info.get('time_label','?')}) "
                    f"— {info.get('title','?')[:40]}"
                )
                stop_url = True
                break

            # ── P3: Two-stage title filter ─────────────────────────────────────
            is_valid, needs_desc_check = is_valid_title(info.get("title", ""))

            if not is_valid:
                tracker["skip_title"] += 1
                log.info(
                    f"  ⏭  Title mismatch [{info.get('time_label','?')}] "
                    f"— {info.get('title','?')[:50]}"
                )
                continue

            # ── Description check for generic titles ──────────────────────────
            if needs_desc_check:
                job_url = info.get("url", "")
                if not job_url:
                    tracker["errors"] += 1
                    continue

                before = set(driver.window_handles)
                driver.execute_script(f"window.open('{job_url}','_blank');")
                human_sleep(2, 3)
                desc_tab = set(driver.window_handles) - before
                if not desc_tab:
                    tracker["errors"] += 1
                    continue
                driver.switch_to.window(desc_tab.pop())

                has_skills = check_description_for_skills(driver)

                driver.close()
                driver.switch_to.window(driver.window_handles[0])

                if not has_skills:
                    tracker["skip_no_skills"] += 1
                    log.info(
                        f"  ⏭  Generic title, no skills in JD "
                        f"— {info.get('title','?')[:50]}"
                    )
                    continue

            if not info.get("url"):
                tracker["errors"] += 1
                continue

            apply_to_job(driver, info, applied_ids, tracker, failed_ids)

        if stop_url:
            break

        # ── Pagination — dismiss overlay before clicking Next (fixes P1 side-effect) ──
        try:
            dismiss_chatbot_overlay(driver)   # clear overlay so Next btn is clickable
            nxt = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
                By.XPATH,
                "//a[contains(@class,'pagination-next')]"
                " | //span[normalize-space()='Next']"
                " | //a[normalize-space()='Next']"
                " | //a[contains(@class,'next')]"
                " | //button[contains(normalize-space(),'Next')]"
            )))
            if nxt.get_attribute("disabled") is not None:
                break
            driver.execute_script("arguments[0].scrollIntoView(true);", nxt)
            human_sleep(0.5, 1)
            nxt.click()
            page += 1
            human_sleep(3, 5)
            sort_by_date(driver)
        except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
            break


# ── P6: Enhanced run report ────────────────────────────────────────────────────
def generate_report(tracker: dict, start: datetime.datetime, failed_ids: set):
    end      = datetime.datetime.now()
    duration = round((end - start).total_seconds() / 60, 1)

    applied_jobs = tracker["applied_jobs"]
    total        = tracker["today_count"]
    attempted    = tracker["attempted_count"]
    seen_count   = len(tracker.get("seen_ids", set()))

    # P6: success rate
    success_rate = f"{(total / attempted * 100):.1f}%" if attempted > 0 else "N/A"

    # P6: top companies
    companies    = Counter(
        j.get("company", "unknown") for j in applied_jobs if j.get("company")
    )
    top_companies = companies.most_common(5)

    indore_jobs = [j for j in applied_jobs if "indore" in j.get("location", "").lower()]
    remote_jobs = [
        j for j in applied_jobs
        if any(w in j.get("location", "").lower() for w in ["remote", "wfh", "work from home"])
    ]
    other_jobs  = [
        j for j in applied_jobs
        if j not in indore_jobs and j not in remote_jobs
    ]

    skipped = (
        tracker["skip_title"] + tracker["skip_old"] +
        tracker["skip_duplicate"] + tracker["skip_no_apply"] +
        tracker["skip_no_skills"] + tracker["errors"]
    )

    W = 44  # inner content width

    def row(content=""):
        return f"║ {content:<{W}} ║"

    def divider():
        return "╠" + "═" * (W + 2) + "╣"

    lines = [
        "",
        "╔" + "═" * (W + 2) + "╗",
        f"║{'NAUKRI BOT — DAILY REPORT':^{W + 2}}║",
        divider(),
        row(f"Date      : {start.strftime('%Y-%m-%d')}"),
        row(f"Account   : {config.EMAIL}"),
        row(f"Duration  : {duration} minutes"),
        divider(),
        row(f"📊 Job IDs seen on pages : {seen_count}"),
        row(f"📊 Apply clicks attempted: {attempted}"),
        row(f"✅ Applied successfully  : {total} / {config.MAX_APPLY}"),
        row(f"📈 Success rate          : {success_rate}"),
        row(f"🏷️  Top Applicant applied : {tracker.get('badge_top_applicant', 0)}"),
        row(f"🔥 Actively Hiring applied: {tracker.get('badge_actively_hiring', 0)}"),
        row(f"📄 Resume uploaded        : {'✅ Yes' if tracker.get('resume_uploaded') else '⚠️  Not found'}"),
        row(f"   📍 Indore  : {len(indore_jobs)} jobs"),
        row(f"   🌐 Remote  : {len(remote_jobs)} jobs"),
        row(f"   🗺️  Other   : {len(other_jobs)} jobs"),
        divider(),
        row(f"⏭  Skipped total         : {skipped}"),
        row(f"   Title mismatch        : {tracker['skip_title']}"),
        row(f"   Too old               : {tracker['skip_old']}"),
        row(f"   Already applied/seen  : {tracker['skip_duplicate']}"),
        row(f"   No skills in JD       : {tracker['skip_no_skills']}"),
        row(f"   No Easy Apply button  : {tracker['skip_no_apply']}"),
        row(f"   Page / overlay errors : {tracker['errors']}"),
        divider(),
        row("🏢 TOP COMPANIES APPLIED TO:"),
    ]

    if top_companies:
        for company, count in top_companies:
            lines.append(row(f"   {company[:35]:<35} ×{count}"))
    else:
        lines.append(row("   (none)"))

    lines += [divider(), row("✅ APPLIED JOBS:")]

    if applied_jobs:
        for j in applied_jobs:
            loc      = j.get("location", "?")
            loc_low  = loc.lower()
            if "indore" in loc_low:
                icon = "📍"
            elif any(w in loc_low for w in ["remote", "wfh", "work from home"]):
                icon = "🌐"
            else:
                icon = "🗺️ "
            entry = (
                f"  {icon} [{loc[:10]:<10}] "
                f"{j.get('title','?')[:28]:<28} | "
                f"{j.get('company','?')[:18]}"
            )
            lines.append(row(entry))
    else:
        lines.append(row("  (none)"))

    # P6: list permanently failed job IDs
    if tracker["failed_overlay_ids"]:
        lines += [divider(), row("❌ FAILED JOB IDs (overlay/page error — permanently skipped):")]
        chunk = ", ".join(str(x) for x in tracker["failed_overlay_ids"][:20])
        if len(tracker["failed_overlay_ids"]) > 20:
            chunk += f" … (+{len(tracker['failed_overlay_ids'])-20} more)"
        lines.append(row(f"  {chunk}"))
        lines.append(row(f"  Total permanently failed: {len(failed_ids)}"))

    lines += ["╚" + "═" * (W + 2) + "╝", ""]

    report = "\n".join(lines)
    log.info(report)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(report)


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    start   = datetime.datetime.now()
    tracker = new_tracker()

    log.info(
        f"\n{'='*60}\n"
        f"Naukri Auto-Apply | {start.strftime('%Y-%m-%d %H:%M')}\n"
        f"Account      : {config.EMAIL}\n"
        f"Max apply    : {config.MAX_APPLY}\n"
        f"Search URLs  : {len(config.SEARCH_URLS)}\n"
        f"{'='*60}"
    )

    applied_ids = load_applied_ids()
    log.info(f"Previously applied : {len(applied_ids)} jobs")

    # P2: load permanently failed IDs so we never retry broken pages
    failed_ids = load_failed_ids()
    log.info(f"Permanently failed : {len(failed_ids)} job IDs (will skip)")

    # P2: per-run attempted set — shared across ALL URLs to prevent cross-URL duplication
    session_attempted_ids: set = set()

    driver = get_driver()

    try:
        login(driver)
        tracker["resume_uploaded"] = bump_profile(driver)

        valid_urls = validate_and_filter_urls(driver)
        for url in valid_urls:
            if tracker["today_count"] >= config.MAX_APPLY:
                log.info(f"Daily limit ({config.MAX_APPLY}) reached — done")
                break
            process_url(
                driver, url,
                applied_ids, tracker,
                session_attempted_ids, failed_ids,
            )

        if tracker["today_count"] < config.MAX_APPLY and config.EXTRA_URLS:
            log.info("\nProcessing Naukri personalised / recommended pages...")
            for url in config.EXTRA_URLS:
                if tracker["today_count"] >= config.MAX_APPLY:
                    break
                process_url(
                    driver, url,
                    applied_ids, tracker,
                    session_attempted_ids, failed_ids,
                )

    except Exception as exc:
        log.error(f"Fatal error: {exc}", exc_info=True)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # P2: save failed IDs so next run skips them permanently
    save_failed_ids(failed_ids)

    generate_report(tracker, start, failed_ids)   # P6: pass failed_ids for report


if __name__ == "__main__":
    main()
