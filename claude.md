# Naukri Auto Applier Bot — Claude Instructions

## Project Overview
Selenium-based Python bot that automatically applies to MERN/Full Stack 
Developer jobs on Naukri.com. Runs daily via Windows Task Scheduler.

## Environment
- OS: Windows 11
- Python: 3.11
- Chrome: 140
- ChromeDriver: auto-managed
- IDE: VS Code
- Project Path: C:\Users\hp\Downloads\NaukriCronChecker

## Account Details
- Email: ayushsahupip@gmail.com
- Experience Filter: 3 years
- Target: 40 successful applications per run
- Max pages per URL: 2 (page 1 + page 2)

## File Structure
NaukriCronChecker/
├── CLAUDE.md
├── bot.py              → main bot logic
├── config.py           → all settings, keywords, URLs
├── apply.py            → apply button + overlay handler
├── report.py           → daily report generator
├── filters.py          → title/skill/seniority filters
├── tracker.py          → attempted_ids, failed_ids manager
├── logs/               → daily .log files
├── data/
│   ├── failed_ids.json → permanently failed job IDs
│   └── applied.json    → successfully applied job IDs
└── requirements.txt

## Tech Stack
- selenium
- webdriver-manager
- python-dotenv
- colorlog
- json
- schedule

## Search URLs (always scrape page 1 AND page 2)
https://www.naukri.com/mern-stack-developer-jobs?experience=3
https://www.naukri.com/mern-jobs?experience=3
https://www.naukri.com/full-stack-developer-jobs?experience=3
https://www.naukri.com/react-js-jobs?experience=3
https://www.naukri.com/node-js-jobs?experience=3
https://www.naukri.com/javascript-jobs?experience=3
https://www.naukri.com/software-developer-jobs?experience=3
https://www.naukri.com/web-developer-jobs?experience=3
https://www.naukri.com/front-end-developer-jobs?experience=3
https://www.naukri.com/web-developer-jobs-in-remote?experience=3

## ✅ Accept Job Title If Contains (case-insensitive)
full stack, fullstack, mern, mean, react, node,
nodejs, javascript, nextjs, next.js, express,
mongo, frontend, front end, backend, back end,
web developer, software developer, software engineer,
sde, sde-1, sde1, ui developer, product engineer,
application developer, associate engineer,
junior developer, senior developer

## ❌ Hard Reject Job Title If Contains (case-insensitive)
fresher, intern, trainee, support, sales,
voice process, data entry, back office,
banking officer, bpo, telecaller,
customer service, customer care,
machine learning, ml engineer, data scientist,
devops, cloud engineer, qa engineer,
automation tester, business analyst,
remote sensing, sap, oracle, embedded,
android, ios, flutter, game developer

## ✅ Accept Job If Description Contains (at least 1 skill)
react, reactjs, node, nodejs, javascript,
mern, mongodb, mongo, express, expressjs,
nextjs, next.js, redux, rest api, restful,
graphql, typescript, html, css, tailwind,
material ui, ant design, socket.io, jest

## ❌ Reject If Description Contains These Seniority Red Flags
"0 years", "0-1 years", "freshers only",
"no experience required", "fresher preferred",
"banking", "insurance", "bfsi"

## Location Rules
- NO location filtering whatsoever
- Apply to ALL cities: Indore, Remote, Bangalore,
  Chennai, Hyderabad, Pune, Mumbai, Delhi, anywhere
- Never skip a job based on location
- Never add location to search URLs

## Core Logic Rules

### Overlay Fix (MOST IMPORTANT)
Before every apply button click:
1. Check for div.chatbot_Overlay.show using find_elements
2. If found → driver.execute_script("arguments[0].remove()", overlay)
3. Run JS: document.querySelectorAll('.chatbot_Overlay').forEach(e=>e.remove())
4. Press Escape key as fallback
5. Wait 1 second
6. Retry apply button click
7. If still fails → JS click: driver.execute_script("arguments[0].click()", btn)
8. Wrap ALL of this in try/except — never crash

### Deduplication (CRITICAL)
- ONE global attempted_ids = set() created BEFORE the URL loop
- ONE global failed_ids loaded from data/failed_ids.json at startup
- Pass both sets into every URL processing function
- Add job_id to attempted_ids BEFORE attempting
- Add job_id to failed_ids if error occurs
- Save failed_ids to JSON after every run
- Skip any job_id in either set immediately

### Pagination
- Always scrape page 1 and page 2 for every URL
- Use ?page=2 or click next page button
- Stop if page has 0 job cards

### Age Filter
- Skip jobs older than 3 days
- Accept: "Just now", "Today", "1 day ago", "2 days ago", "3 days ago"
- Reject: "4 days ago" and older

## Daily Report Format
╔══════════════════════════════════════════╗
║        NAUKRI BOT — DAILY REPORT         ║
╠══════════════════════════════════════════╣
║ Date      :                              ║
║ Account   :                              ║
║ Duration  :                              ║
╠══════════════════════════════════════════╣
║ ✅ Applied    : X / 40                   ║
║    📍 Indore   : X jobs                  ║
║    🌐 Remote   : X jobs                  ║
║    🗺️  Other    : X jobs                 ║
╠══════════════════════════════════════════╣
║ ⏭  Skipped    : X                       ║
║    Title mismatch   : X                 ║
║    Too old          : X                 ║
║    Already applied  : X                 ║
║    No skills in JD  : X                 ║
║    No Easy Apply    : X                 ║
║    Page errors      : X                 ║
╠══════════════════════════════════════════╣
║ 📊 Stats:                               ║
║    Unique jobs seen    : X              ║
║    Unique jobs tried   : X              ║
║    Success rate        : X%             ║
║    Top companies       : X, X, X        ║
╠══════════════════════════════════════════╣
║ APPLIED JOBS:                           ║
║   🗺️  [Location] Title | Company        ║
╠══════════════════════════════════════════╣
║ ❌ FAILED JOB IDs (saved to JSON):      ║
║   ID1, ID2, ID3                         ║
╚══════════════════════════════════════════╝

## Claude Behaviour Rules
1. Reply with CODE ONLY — no explanations unless asked
2. No unnecessary comments in code
3. Never rewrite working code — only fix what is broken
4. Always use try/except around every Selenium action
5. Never reset attempted_ids or failed_ids between URLs
6. Preserve login flow exactly as is
7. Preserve report format exactly as above
8. Keep all settings in config.py not hardcoded in bot.py
9. Functions must be small and single-purpose
10. Always save failed_ids.json and applied.json after run

## Do NOT Touch
- Login / session handling code
- ChromeDriver initialization
- Report print format
- Log file naming convention

## Known Fixed Bugs (do not reintroduce)
- chatbot_Overlay blocking apply → fixed with remove() + retry
- Same job IDs retried across URLs → fixed with global sets
- Fresher/banking jobs applied to → fixed with hard reject filter
- Only page 1 scraped → fixed with pagination loop

## When I Say...
- "fix the overlay" → update apply.py overlay dismissal logic
- "bot not applying" → check filters.py accept/reject keywords
- "duplicate applies" → check tracker.py global sets
- "add new URL" → add to config.py URL list only
- "show report" → print last entry from logs/ folder