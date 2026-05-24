import re
import time
import random
import logging
from pathlib import Path

log = logging.getLogger("naukri")

APPLIED_FILE = Path("applied_jobs.txt")


# ── Timing ─────────────────────────────────────────────────────────────────────
def human_sleep(lo: float = 1.5, hi: float = 3.5):
    time.sleep(random.uniform(lo, hi))


# ── Freshness scoring ──────────────────────────────────────────────────────────
def get_job_priority(time_label: str) -> int:
    label = time_label.lower().strip()
    if "just now" in label:  return 1
    if "minute"   in label:  return 2
    if "hour"     in label:  return 3
    if "today"    in label:  return 4
    if "1 day"    in label:  return 5
    if "2 day"    in label:  return 6
    if "3 day"    in label:  return 7
    return 99  # 4+ days or unknown → stop


# ── Location scoring ───────────────────────────────────────────────────────────
def get_location_priority(location_text: str) -> int:
    """
    Returns location score:
    1 = Indore (best)
    2 = Remote / WFH
    3 = Hybrid
    4 = Other India city
    """
    loc = location_text.lower().strip()

    if "indore" in loc:
        return 1

    if any(w in loc for w in ["remote", "work from home", "wfh", "anywhere", "pan india"]):
        return 2

    if "hybrid" in loc:
        return 3

    return 4


def is_preferred_location(location_text: str) -> bool:
    """Returns True if location is Indore, Remote, WFH, or Hybrid."""
    loc = location_text.lower()
    return any(w in loc for w in [
        "indore", "remote", "work from home",
        "wfh", "hybrid", "anywhere", "pan india",
    ])


# ── Title keyword filter ───────────────────────────────────────────────────────
GENERIC_TITLES = [
    "software developer",
    "software engineer",
    "web developer",
    "web engineer",
    "application developer",
    "ai developer",
    "ai engineer",
    "generative ai",
    "python developer",
]


def is_valid_title(title: str) -> tuple:
    """
    Returns (is_valid: bool, needs_description_check: bool)

    is_valid = False                       → skip immediately
    is_valid = True, needs_check = False   → apply directly (clear match)
    is_valid = True, needs_check = True    → open job, verify description has React/Node
    """
    import config
    title_lower = title.lower().strip()

    for word in config.REJECT_KEYWORDS:
        if word in title_lower:
            return False, False

    for word in config.ACCEPT_KEYWORDS:
        if word in title_lower:
            for generic in GENERIC_TITLES:
                if generic in title_lower:
                    return True, True
            return True, False

    return False, False


def check_description_for_skills(driver) -> bool:
    """
    Read the job description from the current tab and return True
    if it mentions React/Node/MERN skills. Used for generic titles.
    """
    SKILL_KEYWORDS = [
        "react", "node", "javascript", "mern",
        "mongodb", "express", "full stack",
        "frontend", "next.js", "typescript",
        "rest api", "vue", "angular",
    ]
    try:
        from selenium.webdriver.common.by import By
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        matches = [kw for kw in SKILL_KEYWORDS if kw in body]
        if matches:
            log.info(f"  ✅ Description has skills: {', '.join(matches[:4])}")
            return True
        log.info("  ⏭  No relevant skills found in description")
        return False
    except Exception:
        return True  # Can't read description — attempt apply anyway


# ── Job ID extraction ──────────────────────────────────────────────────────────
def extract_job_id(url: str) -> str:
    m = re.search(r"-(\d{7,})(?:[?#]|$)", url)
    if m:
        return m.group(1)
    clean = url.split("?")[0].rstrip("/")
    return clean.split("/")[-1]


# ── Applied-jobs persistence ───────────────────────────────────────────────────
def load_applied_ids() -> set:
    if APPLIED_FILE.exists():
        return set(
            line.strip()
            for line in APPLIED_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return set()


def save_applied_id(job_id: str):
    with APPLIED_FILE.open("a", encoding="utf-8") as f:
        f.write(job_id + "\n")


# ── Form field helpers ─────────────────────────────────────────────────────────
def fill_field(field, value: str):
    from selenium.webdriver.support.ui import Select
    tag = field.tag_name.lower()
    try:
        if tag == "select":
            sel = Select(field)
            options = [o.text.strip() for o in sel.options]
            val_lower = value.lower().strip()
            matched = next(
                (o for o in options if val_lower in o.lower() or o.lower() in val_lower),
                None,
            )
            if matched:
                sel.select_by_visible_text(matched)
            else:
                log.debug(f"No dropdown match for '{value}' in {options[:6]}")
        else:
            field.click()
            human_sleep(0.2, 0.5)
            field.clear()
            field.send_keys(value)
            human_sleep(0.3, 0.6)
    except Exception as exc:
        log.debug(f"fill_field: {exc}")


def find_field_for_label(driver, label):
    from selenium.common.exceptions import NoSuchElementException
    from selenium.webdriver.common.by import By

    for_id = label.get_attribute("for")
    if for_id:
        try:
            return driver.find_element(By.ID, for_id)
        except NoSuchElementException:
            pass

    for xp in (
        "following-sibling::input[1]",
        "following-sibling::select[1]",
        "following-sibling::textarea[1]",
        "..//input[not(@type='hidden')][1]",
        "..//select[1]",
        "..//textarea[1]",
    ):
        try:
            el = label.find_element(By.XPATH, xp)
            if el.is_displayed():
                return el
        except NoSuchElementException:
            pass
    return None


# ── Card info extraction ───────────────────────────────────────────────────────
_TITLE_SELS = [
    "a.title", "a[class*='title']", "a.jobTitle",
    "[class*='jobTitle'] a", "h2 a", "h3 a",
    "a[class*='Title']", "[class*='job-title'] a",
    "[class*='designation'] a", "a[class*='designation']",
    "a[class*='jd-header']",
]
_COMP_SELS = [
    "a.comp-name", "[class*='comp-name']", "a.companyName",
    "[class*='company'] a", "[class*='companyName']",
    "[class*='comp-link']", "a[class*='company']",
    "[class*='company-name']",
]
_TIME_SELS = [
    "span.job-post-day", "[class*='job-post-day']",
    "span[title*='ago']", ".date", "[class*='postedDate']",
    "[class*='posted']", "span[class*='date']",
    "[class*='post-date']", "[class*='freshness']",
]
_LOCATION_SELS = [
    ".location",
    ".loc",
    "[class*='location']",
    "[class*='Location']",
    "[class*='loc-']",
    "span.locWdth",
    "[class*='locWdth']",
    "li.location",
    "[title*='location']",
    "[class*='city']",
]


def get_card_info(card) -> dict:
    from selenium.common.exceptions import NoSuchElementException
    from selenium.webdriver.common.by import By

    info = {"title": "", "company": "", "time_label": "", "url": "", "location": ""}

    for sel in _TITLE_SELS:
        try:
            el = card.find_element(By.CSS_SELECTOR, sel)
            info["title"] = el.text.strip()
            info["url"]   = el.get_attribute("href") or ""
            if info["title"]:
                break
        except NoSuchElementException:
            pass

    for sel in _COMP_SELS:
        try:
            info["company"] = card.find_element(By.CSS_SELECTOR, sel).text.strip()
            if info["company"]:
                break
        except NoSuchElementException:
            pass

    for sel in _TIME_SELS:
        try:
            el = card.find_element(By.CSS_SELECTOR, sel)
            info["time_label"] = el.text.strip() or el.get_attribute("title") or ""
            if info["time_label"]:
                break
        except NoSuchElementException:
            pass

    if not info["time_label"]:
        try:
            for span in card.find_elements(By.TAG_NAME, "span"):
                txt = span.text.strip().lower()
                if any(w in txt for w in ("ago", "today", "just now", "hour", "minute", "day")):
                    info["time_label"] = span.text.strip()
                    break
        except Exception:
            pass

    for sel in _LOCATION_SELS:
        try:
            el = card.find_element(By.CSS_SELECTOR, sel)
            loc = el.text.strip() or el.get_attribute("title") or ""
            if loc:
                info["location"] = loc
                break
        except NoSuchElementException:
            pass

    return info
