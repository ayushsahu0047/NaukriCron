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
MAX_APPLY = int(os.getenv("MAX_APPLY", "40"))
HEADLESS  = os.getenv("HEADLESS", "false").lower() == "true"

# ── Resume — searched in order, first existing file wins ──────────────────────
RESUME_PATHS = [
    Path(os.getenv("RESUME_PATH", "resume.pdf")),
    Path(r"C:\Users\hp\Downloads\NaukriCronChecker\resume.pdf"),
    Path(r"C:\Users\hp\Downloads\resume.pdf"),
    Path(r"C:\Users\hp\Desktop\resume.pdf"),
    Path(r"C:\Users\hp\Documents\resume.pdf"),
]
RESUME_PATH = next((p for p in RESUME_PATHS if p.exists()), RESUME_PATHS[0])

# ── Search URLs — 20 URLs × 2 pages = 800 jobs pool ──────────────────────────
SEARCH_URLS = [
    "https://www.naukri.com/mern-stack-developer-jobs?experience=3",
    "https://www.naukri.com/mern-jobs?experience=3",
    "https://www.naukri.com/mern-stack-developer-jobs-in-remote?experience=3",
    "https://www.naukri.com/react-js-jobs?experience=3",
    "https://www.naukri.com/react-developer-jobs?experience=3",
    "https://www.naukri.com/reactjs-jobs?experience=3",
    "https://www.naukri.com/node-js-jobs?experience=3",
    "https://www.naukri.com/nodejs-developer-jobs?experience=3",
    "https://www.naukri.com/full-stack-developer-jobs?experience=3",
    "https://www.naukri.com/full-stack-developer-jobs-in-remote?experience=3",
    "https://www.naukri.com/fullstack-developer-jobs?experience=3",
    "https://www.naukri.com/javascript-jobs?experience=3",
    "https://www.naukri.com/javascript-developer-jobs?experience=3",
    "https://www.naukri.com/front-end-developer-jobs?experience=3",
    "https://www.naukri.com/frontend-developer-jobs?experience=3",
    "https://www.naukri.com/backend-developer-jobs?experience=3",
    "https://www.naukri.com/web-developer-jobs?experience=3",
    "https://www.naukri.com/software-developer-jobs?experience=3",
    "https://www.naukri.com/web-developer-jobs-in-remote?experience=3",
    "https://www.naukri.com/next-js-developer-jobs?experience=3",
]

# ── Extra personalised Naukri pages (processed after main URLs) ───────────────
EXTRA_URLS = [
    "https://www.naukri.com/mnjuser/recommendedjobs",
    "https://www.naukri.com/mnjuser/jobsearchrecommendation",
]

# ── STEP 1 — Hard-reject: ANY match in title → skip immediately ───────────────
REJECT_KEYWORDS = [
    # Seniority mismatch
    "fresher", "trainee", "intern",
    # Finance / banking / back-office
    "banking officer", "back office", "banker",
    "loan officer", "finance executive",
    # BPO / support / sales / HR
    "support", "bpo", "telecaller", "customer service",
    "voice process", "chat process", "call centre", "call center",
    "coordinator", "sales", "business development",
    "recruiter", "hr executive", "hr manager",
    "talent acquisition", "marketing executive",
    # Data / analytics / ML (not MERN)
    "data entry", "data scientist", "data analyst",
    "machine learning", "remote sensing",
    "power bi", "tableau", "etl",
    # Ops / infra / QA (not MERN)
    "devops", "cloud engineer",
    "automation tester", "qa engineer", "qa tester",
    "manual tester", "selenium tester",
    "business analyst",
    "shell scripting", "networking", "hardware engineer",
    # Wrong mobile / cross-platform stacks
    "android", "ios",
    "flutter", "dart",
    # Wrong backend stacks
    "ruby", "rails",
    "perl", "scala", "kotlin",
    "haskell", "erlang", "elixir",
    "fortran", "matlab", "r language",
    "cobol", "assembly", "lua",
    "groovy", "clojure", "lisp",
    "ocaml", "julia", "f#",
    "objective-c", "swift",
    "rust developer",
    "dot net", ".net developer", "asp.net",
    "php developer", "laravel developer",
    # CMS / ecommerce platforms
    "wordpress", "shopify", "magento", "woocommerce",
    # Embedded / hardware
    "embedded", "firmware", "vlsi", "vhdl", "fpga",
    # Non-tech
    "graphic designer", "video editor",
    "content writer", "seo",
    "mechanical", "civil", "electrical", "accountant",
    # AI evaluation spam jobs
    "ai evaluation", "ai code evaluation",
    # Gig / blockchain / legacy
    "freelance", "game developer",
    "blockchain", "solidity",
    "sap", "oracle developer",
]

# ── STEP 2 — Must match at least ONE accept keyword ───────────────────────────
# ACCEPT_SPECIFIC: clear tech match → apply without opening job page
ACCEPT_SPECIFIC = [
    "full stack", "fullstack", "full-stack",
    "mern", "mean", "pern", "fern",
    "react", "reactjs", "react.js",
    "node", "nodejs", "node.js",
    "javascript", "typescript",
    "next.js", "nextjs",
    "express", "expressjs",
    "mongo", "mongodb",
    "frontend developer", "frontend engineer",
    "front-end developer", "front end developer",
    "backend developer", "backend engineer",
    "back-end developer", "back end developer",
    "ui developer",
]

# ACCEPT_GENERIC: vague title → must also pass description skill check (STEP 3)
ACCEPT_GENERIC = [
    "web developer", "web engineer",
    "software developer", "software engineer",
    "application developer",
    "product engineer", "product developer",
    "sde", "sde-1", "sde1", "sde-2",
    "junior developer", "senior developer", "associate developer",
    "programmer",
]

ACCEPT_KEYWORDS = ACCEPT_SPECIFIC + ACCEPT_GENERIC

# ── STEP 3 — Description skill check (at least 1 required for generic titles) ─
REQUIRED_SKILLS = [
    "react", "reactjs", "node", "nodejs",
    "javascript", "mern", "mongodb", "mongo",
    "express", "expressjs", "next.js", "nextjs",
    "redux", "rest api", "graphql", "typescript",
    "html", "css", "tailwind",
]

# ── Cover letter ───────────────────────────────────────────────────────────────
COVER_LETTER = (
    f"I am a MERN Stack Developer with {EXPERIENCE} years of hands-on experience "
    "in React.js, Node.js, MongoDB, and Express.js. I have built scalable "
    "full-stack applications and REST APIs. I am available immediately and "
    "very excited about this opportunity."
)
