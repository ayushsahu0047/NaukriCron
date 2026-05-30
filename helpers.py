import re
import json
import time
import random
import logging
from pathlib import Path

log = logging.getLogger("naukri")

APPLIED_FILE = Path("applied_jobs.txt")
FAILED_FILE  = Path("failed_jobs.json")   # permanently broken job IDs


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


# ── Location helpers (kept for display; no filtering applied) ──────────────────
def get_location_priority(location_text: str) -> int:
    loc = location_text.lower().strip()
    if "indore" in loc:                                                  return 1
    if any(w in loc for w in ["remote", "work from home", "wfh"]):      return 2
    if "hybrid" in loc:                                                  return 3
    return 4


def is_preferred_location(location_text: str) -> bool:
    """Kept for reference; location filtering is disabled — bot applies everywhere."""
    return True  # always True: no location restriction


# ── Title keyword filter ───────────────────────────────────────────────────────
def is_valid_title(title: str) -> tuple:
    """
    Two-stage title check:
      (False, False)  → hard reject immediately
      (True,  False)  → specific tech match → apply directly
      (True,  True)   → generic title → open job page, verify skills in description

    Logic (Problem 3):
      1. If title contains any REJECT keyword           → reject
      2. If title contains any ACCEPT_SPECIFIC keyword  → accept (no desc check)
      3. If title contains any ACCEPT_GENERIC keyword   → accept (needs desc check)
      4. Otherwise                                      → reject
    """
    import config
    title_lower = title.lower().strip()

    if not title_lower:
        # Cannot read title from card — URL is already relevant, attempt apply
        return True, False

    # Step 1: hard reject
    for word in config.REJECT_KEYWORDS:
        if word in title_lower:
            return False, False

    # Step 2: specific tech keyword → direct apply
    for word in config.ACCEPT_SPECIFIC:
        if word in title_lower:
            return True, False

    # Step 3: generic keyword → needs description confirmation
    for word in config.ACCEPT_GENERIC:
        if word in title_lower:
            return True, True

    return False, False


# ── Description skill check + fresher/0-year detection ────────────────────────
_SKILL_KEYWORDS = [
    "react", "reactjs", "node", "nodejs",
    "javascript", "mern", "mongodb", "mongo",
    "express", "expressjs", "next.js", "nextjs",
    "redux", "rest api", "graphql", "typescript",
    "html", "css", "tailwind", "material ui",
    "ant design", "socket.io",
]

_FRESHER_PATTERNS = [
    r'\b0\s*(?:to|-)\s*1\s*year',
    r'\b0\s*years?\s*(?:of\s*)?experience',
    r'\bfreshers?\s+(?:only|preferred|can apply)',
    r'no\s+experience\s+required',
    r'experience\s*:\s*0',
]


def check_description_for_skills(driver) -> bool:
    """
    Open-tab description check (called only for generic titles).

    Returns False if:
      - Description signals a fresher/0-year role (Problem 5)
      - No MERN-stack skills found

    Returns True if at least 1 skill keyword is present.
    """
    try:
        from selenium.webdriver.common.by import By
        body = driver.find_element(By.TAG_NAME, "body").text.lower()

        # Problem 5: reject fresher / 0-year roles in description
        for pattern in _FRESHER_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                log.info("  ⏭  Description requires 0 yrs / fresher — skip")
                return False

        # Problem 3: at least 1 MERN skill must appear
        matches = [kw for kw in _SKILL_KEYWORDS if kw in body]
        if matches:
            log.info(f"  ✅ Description skills: {', '.join(matches[:4])}")
            return True

        log.info("  ⏭  No MERN skills found in description")
        return False

    except Exception:
        # Can't read description → attempt apply anyway (fail-safe)
        return True


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


# ── Failed-jobs persistence (Problem 2) ───────────────────────────────────────
def load_failed_ids() -> set:
    """Load permanently broken job IDs so they are skipped on future runs."""
    if FAILED_FILE.exists():
        try:
            data = json.loads(FAILED_FILE.read_text(encoding="utf-8"))
            ids = set(str(x) for x in data if x)
            log.info(f"Loaded {len(ids)} permanently failed job IDs from {FAILED_FILE}")
            return ids
        except Exception as exc:
            log.warning(f"Could not read {FAILED_FILE}: {exc}")
    return set()


def save_failed_ids(failed_ids: set):
    """Persist the current failed-ID set for the next run."""
    try:
        FAILED_FILE.write_text(
            json.dumps(sorted(failed_ids), indent=2),
            encoding="utf-8",
        )
        log.info(f"Saved {len(failed_ids)} failed IDs → {FAILED_FILE}")
    except Exception as exc:
        log.warning(f"Could not save failed IDs: {exc}")


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


def get_card_priority_score(info: dict) -> int:
    score = 0
    if info.get("is_top_applicant"):    score += 100
    if info.get("is_actively_hiring"):  score += 80
    if info.get("is_recently_active"):  score += 60
    if info.get("has_easy_apply"):      score += 20
    tp = get_job_priority(info.get("time_label", ""))
    score += {1: 40, 2: 35, 3: 30, 4: 25, 5: 20, 6: 10, 7: 5}.get(tp, 0)
    return score


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

    # Badge detection for priority scoring
    try:
        card_text = card.text.lower()
        card_html = card.get_attribute("innerHTML").lower()
        info["is_top_applicant"]   = "top applicant" in card_text
        info["is_actively_hiring"] = (
            "actively hiring" in card_text or "urgently hiring" in card_text
        )
        info["is_recently_active"] = (
            "recruiter was active" in card_text or
            "recently active" in card_text or
            "recruiter recently active" in card_text
        )
        info["has_easy_apply"] = "easy apply" in card_html or "1-click" in card_html
    except Exception:
        info["is_top_applicant"]   = False
        info["is_actively_hiring"] = False
        info["is_recently_active"] = False
        info["has_easy_apply"]     = False

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
