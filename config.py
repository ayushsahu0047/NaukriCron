import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Credentials ────────────────────────────────────────────────────────────────
EMAIL    = os.getenv("NAUKRI_EMAIL", "")
PASSWORD = os.getenv("NAUKRI_PASSWORD", "")
MY_NAME  = os.getenv("MY_NAME", "")
MY_PHONE = os.getenv("MY_PHONE", "")

# ── Application answers ────────────────────────────────────────────────────────
CURRENT_CTC   = os.getenv("CURRENT_CTC", "8")
EXPECTED_CTC  = os.getenv("EXPECTED_CTC", "12")
EXPERIENCE    = os.getenv("EXPERIENCE_YEARS", "3")
NOTICE_PERIOD = os.getenv("NOTICE_PERIOD", "Immediate")
LOCATION      = os.getenv("CURRENT_LOCATION", "Indore")
RELOCATE      = os.getenv("WILLING_TO_RELOCATE", "Yes")

# ── Run settings ───────────────────────────────────────────────────────────────
MAX_APPLY   = int(os.getenv("MAX_APPLY", "40"))
HEADLESS    = os.getenv("HEADLESS", "false").lower() == "true"
RESUME_PATH = Path(os.getenv("RESUME_PATH", "resume.pdf"))

# ── Search URLs — All India + Remote, last 24 hrs, newest first ────────────────
SEARCH_URLS = [
    # ── Confirmed working Naukri slug URLs ────────────────────────────────────
    "https://www.naukri.com/mern-stack-jobs?experience=3",
    "https://www.naukri.com/mern-stack-developer-jobs?experience=3",
    "https://www.naukri.com/mern-jobs?experience=3",
    "https://www.naukri.com/mern-stack-developer-jobs-in-remote?experience=3",
    "https://www.naukri.com/full-stack-developer-jobs?experience=3",
    "https://www.naukri.com/react-js-jobs?experience=3",
    "https://www.naukri.com/node-js-jobs?experience=3",
    "https://www.naukri.com/javascript-jobs?experience=3",
    "https://www.naukri.com/software-developer-jobs?experience=3",
    "https://www.naukri.com/web-developer-jobs?experience=3",
    "https://www.naukri.com/front-end-developer-jobs?experience=3",
    "https://www.naukri.com/full-stack-developer-jobs-in-remote?experience=3",
]

# ── Title keyword filters ──────────────────────────────────────────────────────
ACCEPT_KEYWORDS = [
    # Core MERN
    "mern", "mean",
    # Full Stack
    "full stack", "fullstack", "full-stack",
    # React
    "react", "reactjs", "react.js",
    # Node
    "node", "nodejs", "node.js",
    # JavaScript / TypeScript
    "javascript", "typescript", "js developer",
    # Frontend
    "frontend", "front-end", "front end",
    "ui developer", "ui engineer",
    "next.js", "nextjs",
    # Backend
    "backend", "back-end",
    "express", "mongodb",
    # General
    "software developer", "software engineer",
    "web developer", "web engineer",
    "application developer",
    "ai developer",
    "python developer",
    "api developer",
]

REJECT_KEYWORDS = [
    # Non-tech
    "back office", "data entry",
    "chat support", "voice process",
    "bpo", "call centre", "call center",
    "phone banking", "branch banking",
    "banking operation",
    # HR / Sales
    "recruiter", "hr executive",
    "talent acquisition",
    "sales executive", "marketing",
    # Wrong tech stack
    "embedded", "firmware", "simulation",
    "mechanical", "civil",
    "graphic designer", "video editor",
    "content writer",
    "dot net", ".net developer",
    "java developer", "php developer",
    "android developer", "ios developer",
    "flutter developer",
    "data scientist",
    "machine learning engineer",
    "devops engineer",
    "manual tester", "qa engineer",
]

# ── Cover letter ───────────────────────────────────────────────────────────────
COVER_LETTER = (
    f"I am a MERN Stack Developer with {EXPERIENCE} years of hands-on experience "
    "in React.js, Node.js, MongoDB, and Express.js. I have built scalable "
    "full-stack applications and REST APIs. I am available immediately and "
    "very excited about this opportunity."
)
