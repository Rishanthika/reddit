# FutureGrad Reddit Lead Intelligence System — Phase 1 MVP

An internal tool for **FutureGrad** ([gofuturegrad.com](https://gofuturegrad.com/)), a
study-abroad consultancy in Coimbatore, that monitors public Reddit posts for
genuine study-abroad intent and helps staff prioritize which students to follow up
with.

This is **Phase 1**: a local, CLI-based MVP. It does **not** send messages,
DM users, or contact anyone automatically. It only reads public posts and
surfaces the ones worth a human counsellor's attention.

---

## 1. What this project does

```text
Apify Actor (automation-lab/reddit-scraper)
    ↓
Selected Subreddits
    ↓
Retrieve New Posts
    ↓
Keyword / Rule Pre-filter      (app/filters.py — cheap, runs first)
    ↓
AI Lead Classification         (app/ai_classifier.py — OpenAI, semantic signals only)
    ↓
Deterministic Lead Scoring     (app/lead_scoring.py — Python decides the number)
    ↓
SQLite Database                (app/database.py — dedup + storage)
    ↓
Terminal Output                (app/main.py — human-readable leads)
```

The AI never invents the final score — it only extracts structured signals
(intent, destination, course, services needed). A transparent, tunable Python
formula turns those signals into a 0–100 score and a HOT / WARM / COLD label.

**This tool does not, and will not in this phase:**
- Automatically message or DM Reddit users
- Scrape Reddit outside of the official API
- Attempt to deanonymize users or find private contact information
- Send Slack/email notifications or run a dashboard (Phase 2/3 — see [Roadmap](#16-future-roadmap-not-yet-implemented))

---

## 2. Architecture

```text
futuregrad-reddit-leads/
│
├── app/
│   ├── __init__.py
│   ├── config.py          # settings loader + tunable constants (keywords, weights, thresholds)
│   ├── reddit_client.py   # Apify wrapper — Actor run + dataset retrieval + normalization
│   ├── filters.py         # Stage 1: cheap keyword/rule pre-filter
│   ├── ai_classifier.py   # Stage 2: OpenAI call + strict Pydantic schema
│   ├── lead_scoring.py    # Stage 3: deterministic scoring, HOT/WARM/COLD
│   ├── database.py        # SQLAlchemy models + repository over SQLite
│   └── main.py            # Pipeline orchestration + terminal output
│
├── config/
│   └── settings.example.env   # duplicate of .env.example, kept for reference
│
├── data/
│   └── .gitkeep                # leads.db is created here at runtime (git-ignored)
│
├── tests/
│   ├── __init__.py
│   ├── test_filters.py         # no API keys required
│   └── test_lead_scoring.py    # no API keys required
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

`app/config.py` is an addition beyond the minimum file list: it centralizes
environment loading *and* the tunable business constants (keyword groups,
scoring weights, thresholds) so `filters.py` and `lead_scoring.py` stay
readable and so those values can be tuned in one place without touching
pipeline logic.

Each stage only depends on plain data structures (`RedditPost`, `FilterResult`,
`LeadAnalysis`, `LeadScore`) — not on each other's internals — so Phase 2
(notifications) and Phase 3 (dashboard) can be added without rewriting the
Reddit client, classifier, scorer, or database.

---

## 3. Requirements

- Python 3.11+
- A Reddit account with a registered "script" app (free)
- An OpenAI API key
- Windows, macOS, or Linux

---

## 4. Reddit collection setup (via Apify)

> **Update:** Phase 1 originally collected posts through the official Reddit
> API (PRAW). Reddit collection now goes through the Apify Actor
> **`automation-lab/reddit-scraper`** instead — no Reddit developer app or
> OAuth credentials are needed any more. Everything downstream (keyword
> pre-filter, AI classifier, deterministic scoring, SQLite storage, terminal
> output) is unchanged.

1. Create a free account at <https://console.apify.com/sign-up> if you don't
   have one.
2. Go to **Settings → Integrations** in the Apify Console and copy your
   **Personal API token** → `APIFY_API_TOKEN`.
3. Leave `APIFY_ACTOR_ID` at its default, `automation-lab/reddit-scraper`,
   unless you intentionally want to point at a different Actor.
4. No further setup is required — the app runs the Actor for you with the
   subreddits from `SUBREDDITS` each time you run `python -m app.main`.
5. The app requests **posts only** (`includeComments: False`), sorted
   `new`, and never uses the Actor's own keyword filter or AI/LLM output
   formats — FutureGrad's own pre-filter and AI classifier remain the only
   filtering/AI stages in the pipeline.
6. Apify bills per post scraped (see the Actor's pricing page) — keep
   `POST_LIMIT` reasonable while testing to avoid unnecessary usage.

---

## 5. OpenAI API setup

1. Create an account at <https://platform.openai.com/>.
2. Go to **API keys** and create a new secret key → `OPENAI_API_KEY`.
3. Pick a model you have access to (e.g. `gpt-4o-mini`) → `OPENAI_MODEL`.
   The classifier uses OpenAI's JSON-mode response format, so the model you
   choose must support `response_format={"type": "json_object"}`.

---

## 6. Installation (Windows first)

### Windows — PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

### Windows — Command Prompt (cmd.exe)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then open `.env` in a text editor and fill in the values you got in steps
4 and 5 above.

---

## 7. Environment variables

| Variable                | Required | Default                                     | Notes                                             |
|--------------------------|:--------:|----------------------------------------------|----------------------------------------------------|
| `APIFY_API_TOKEN`        | Yes      | —                                            | Apify Console → Settings → Integrations            |
| `APIFY_ACTOR_ID`         | No       | `automation-lab/reddit-scraper`              | Change only to point at a different Actor          |
| `OPENAI_API_KEY`         | Yes      | —                                            | From your OpenAI account                           |
| `OPENAI_MODEL`           | No       | `gpt-4o-mini`                                | Must support JSON-object response format           |
| `SUBREDDITS`             | No       | `studyabroad,gradadmissions`                 | Comma-separated, no `r/` prefix                    |
| `POST_LIMIT`             | No       | `25`                                         | New posts fetched per subreddit, per run           |
| `DATABASE_PATH`          | No       | `data/leads.db`                              | SQLite file path, created automatically            |
| `LOG_LEVEL`              | No       | `INFO`                                       | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`|

The app fails fast with a clear message if a required variable is missing —
it will never silently run with blank credentials.

---

## 8. Running the application

```bash
python -m app.main
```

Each run fetches the most recent `POST_LIMIT` new posts from each configured
subreddit, filters and classifies them, and prints any HOT/WARM leads to the
terminal. Run it again later (e.g. on a schedule via Task Scheduler / cron) —
already-processed posts are automatically skipped.

---

## 9. Running tests

```bash
pytest
```

Tests in `tests/test_filters.py` and `tests/test_lead_scoring.py` require
**no** Reddit or OpenAI credentials — they construct `RedditPost` /
`LeadAnalysis` / `FilterResult` objects directly in memory.

---

## 10. Database location

SQLite database file: `data/leads.db` (configurable via `DATABASE_PATH`).
It is created automatically on first run and is safe to delete if you want
to start fresh (you will simply re-process currently-new posts).

The `leads` table stores, per post: Reddit metadata (id, username, subreddit,
title, url, text, created_at), AI results (destination, course, intent,
services, is_lead, confidence, reason), scoring results (pre-filter score,
lead score, HOT/WARM/COLD), and workflow fields (`lead_status`, defaulting to
`NEW`, and `assigned_counsellor`, for staff to fill in later).

---

## 11. Lead scoring methodology

The AI classifier returns **semantic signals only** — it never assigns a
final number. `app/lead_scoring.py` deterministically converts those signals
(plus the keyword pre-filter's matched groups) into a score:

| Signal                                         | Points |
|-------------------------------------------------|:------:|
| Explicitly looking for counselling/consultant    | +25    |
| Asking how/where to apply                        | +20    |
| Specific destination named                       | +15    |
| Specific course/program named                    | +10    |
| University/course selection question             | +15    |
| Visa/application/SOP guidance                    | +10    |
| Strong study-abroad intent (AI: `intent="high"`) | +10    |
| General study-abroad discussion (fallback)       | +5     |
| AI determined post is not a lead                 | −50    |

The score is clamped to **0–100**. Classification:

- **80–100 → HOT**
- **50–79 → WARM**
- **0–49 → COLD**

Weights and thresholds live in `app/config.py` (`SCORING_WEIGHTS`,
`HOT_THRESHOLD`, `WARM_THRESHOLD`) so they can be tuned without touching the
scoring logic itself.

---

## 12. Example terminal output

```text
============================================================
🔥 NEW REDDIT LEAD (HOT)
============================================================

Score: 80/100
Classification: HOT

Student: u/example
Community: r/studyabroad

Destination: Canada
Course: Unknown
Intent: High

Services:
- Consultant Recommendation
- Visa Guidance

Reason:
Student is actively seeking a consultant and visa/application guidance for Canada.

Post:
Can someone recommend a consultant for studying in Canada? Need help with my visa and application too.

Reddit:
https://reddit.com/r/studyabroad/comments/xyz789

Status: NEW

============================================================
```

COLD posts are logged as a single compact line (e.g.
`[COLD] r/studyabroad — Germany is beautiful (score=0)`) rather than a full
block, so the terminal stays focused on leads worth reviewing. On terminals
without Unicode support, the 🔥 banner automatically falls back to plain
`[HOT]` / `[WARM]` text tags.

---

## 13. Troubleshooting

- **"Missing required environment variable"** — you haven't copied
  `.env.example` to `.env`, or a required field is still blank.
- **"Apify Actor run failed" / 401 from Apify** — double check
  `APIFY_API_TOKEN` in `.env`.
- **"Apify Actor run did not return a dataset id"** — the Actor run itself
  failed or was aborted on Apify's side; check the run in the Apify Console
  for details.
- **Fewer posts than expected** — some subreddits are simply quieter than
  others, or the Actor's public-page recovery paths returned partial data
  for that run; try again later or raise `POST_LIMIT`.
- **OpenAI errors / invalid JSON** — logged as `AI classification failed for
  post ...` and that post is simply skipped (no lead is invented). Check your
  `OPENAI_API_KEY` and that your chosen `OPENAI_MODEL` supports JSON-object
  responses.
- **No leads appearing** — this is expected on quiet subreddits/days. Try a
  higher-traffic subreddit or increase `POST_LIMIT`, and check `LOG_LEVEL=DEBUG`
  to see pre-filter rejection reasons.
- **Nothing but `[COLD]` lines** — that's the pre-filter/AI doing their job;
  it means no strong intent was detected in that batch of posts.

---

## 14. Privacy considerations

This tool only reads **public** Reddit content (via the Apify Actor
`automation-lab/reddit-scraper`, which itself only accesses public Reddit
pages) and stores only what's needed for internal lead triage: the public username,
subreddit, post title/text/URL, and the derived classification. It does
**not**:

- Look up or infer real names, emails, or phone numbers
- Attempt to deanonymize Reddit usernames
- Access private profiles or bypass any Reddit privacy control
- Enrich records with data from outside the post itself

All outreach remains a manual, human decision by FutureGrad staff.

---

## 15. Reddit data collection compliance considerations

- Collection is delegated to the Apify Actor `automation-lab/reddit-scraper`,
  which accesses only **public** Reddit pages — no login, no private
  content, no bypassing of Reddit access controls.
- This app never posts, comments, votes, or messages — it only reads the
  Actor's dataset output.
- Only records whose subreddit matches the configured `SUBREDDITS`
  allowlist are used; anything else the Actor returns is discarded.
- Comments are never requested (`includeComments: False`); only a small,
  explicitly configured set of subreddits is monitored — no broad or
  opportunistic crawling.
- The Actor's own AI/LLM output formats and keyword-filtering option are
  never used — FutureGrad's own pre-filter and AI classifier remain the
  only filtering/AI stages.
- You are responsible for reviewing Apify's and Reddit's current Terms of
  Use, and each monitored subreddit's own rules regarding automated tools,
  for your specific use case.

---

## 16. Future roadmap (NOT yet implemented)

**Phase 2 — Notifications**
```text
HOT/WARM lead → Notification Router → Slack / Email → Manager + Counsellor
```

**Phase 3 — Dashboard**
```text
SQLite/PostgreSQL → FastAPI → React/Next.js Dashboard
```
Metrics: total leads, HOT/WARM/COLD counts, country/course breakdowns, lead
status, counsellor assignment, recent leads, conversion metrics.

**Phase 4 — CRM & conversion intelligence**
```text
Reddit Post → Lead → Counsellor → Conversation → Application → Student → Conversion
```

The current architecture (separate Reddit client, filter, classifier,
scorer, and database modules, each communicating through plain data
structures) is designed so these phases can be added without rewriting
Phase 1 components.

---

## 17. Known limitations (Phase 1)

- Single-run CLI — no built-in scheduler; use Task Scheduler (Windows) or
  cron (macOS/Linux) to run it periodically.
- Keyword pre-filter is intentionally simple; short abbreviations (e.g.
  "UK", "MS", "CV") carry inherent ambiguity, mitigated but not eliminated
  by requiring cross-group or strong-group keyword signal.
- No notifications or CRM integration — the web dashboard (§18) and the
  SQLite database are the only outputs; there is no automated
  notification/CRM sync yet.
- No automatic outreach of any kind — a human must always review and act on
  a lead.
- Only monitors submissions ("new posts"), not comments.
- Single OpenAI call per relevant post, with no automatic retry beyond what
  the OpenAI SDK does internally — a failed classification is logged and
  skipped, not retried indefinitely.

---

## 18. Web Dashboard (local product layer)

FutureGrad Reddit Lead Intelligence also ships a local web dashboard —
**FutureGrad Intelligence** — on top of the CLI/database engine described
above. It is a separate **product layer**: it does not change, duplicate,
or redesign Reddit retrieval, filtering, classification, or scoring — it
reads and writes the same `data/leads.db` SQLite database as
`python -m app.main`, through the same `Database` class, via a small
FastAPI backend and a React (Vite) frontend.

```
app/api.py            FastAPI backend — REST endpoints only, no business logic
app/scan_service.py   Background scan/validation orchestration, reusing the
                       exact same RedditClient / filter_post / classifier /
                       calculate_lead_score / Database.save_lead calls
                       app/main.py already uses
app/database.py       Additively extended: lead status, counsellor notes,
                       and a minimal real activity log (no fabricated data)
web/                  React + Vite + Tailwind frontend
```

This is a **local-only internal tool** — single user/team, localhost,
SQLite, no authentication, no cloud infrastructure. It is intentionally
not built for public deployment yet.

### 18.1 Launch it

Two terminals — the backend (Python/FastAPI) and the frontend (Vite) run
as separate processes.

**Terminal 1 — backend** (from the project root, with your `.venv`
activated and `.env` already configured per §4–§7 above):

```bash
pip install -r requirements.txt   # only needed once, adds fastapi/uvicorn
uvicorn app.api:app --reload --port 8000
```

**Terminal 2 — frontend** (first time only, then just `npm run dev`):

```bash
cd web
npm install
npm run dev
```

Open **http://localhost:3000** — this takes you straight to the dashboard
(no login, per the local-only brief). The backend must be running on port
8000 for any data to load; the frontend calls it directly
(`web/src/lib/api.ts`, hardcoded to `http://localhost:8000` since this is
a single local instance, not a multi-environment deployment).

### 18.2 What's in the dashboard

- **Dashboard** — greeting, hero, Scan Reddit / View HOT Leads actions,
  and a live stat strip (Total / HOT / WARM / COLD / New Today) pulled
  from the real database — never hard-coded.
- **Leads** — filterable, searchable table (priority, title, destination,
  course, service, status, subreddit, timestamp).
- **Lead detail** — AI Insight (intent/destination/course/services/
  confidence/reason), the original Reddit post text, a full breakdown of
  the deterministic score (matching `app/lead_scoring.py`'s actual
  weights: intent base + destination/course/service bonuses), and a
  clickable Lead Journey (NEW → CONTACTED → RESPONDED → COUNSELLING →
  APPLICATION → CONVERTED, plus NO_RESPONSE/NOT_QUALIFIED/CLOSED) with
  counsellor notes.
- **Pipeline** — a Kanban board over the same statuses.
- **Analytics** — priority distribution, pipeline conversion, subreddit/
  destination/course distribution, and service demand, all computed from
  real leads. Any dimension with no data yet shows "Not enough historical
  data yet." rather than a fabricated chart.
- **Scan Reddit** — configured sources/post limit (read from `.env`),
  a Start Scan action, and **real** stage-by-stage progress (discovering →
  filtering → analyzing → scoring) polled from the backend — not a fake
  animated percentage. Results are written to the database exactly like
  the CLI does.
- **Validation** — the same read-only `CLASSIFIER_VALIDATION_MODE`
  workflow, clearly labeled "READ-ONLY VALIDATION," with a per-post result
  table. Never writes to the database.
- **Activity** — a real, persisted activity log (scans, validations,
  status changes, notes) — not fabricated sample activity.
- **Settings** — connector/provider/database status only. `APIFY_API_TOKEN`
  and `OPENAI_API_KEY` are read only by the Python backend from your local
  `.env` and are never sent to the frontend or shown in Settings.

### 18.3 Branding note

No local FutureGrad logo asset was available in this project, so the
sidebar uses a clean wordmark (an "F" mark in ink/gold plus the
"FutureGrad — Reddit Intelligence" lockup) rather than a generated or
third-party logo. Drop a real logo file into `web/src/assets/` and swap it
into `web/src/components/Sidebar.tsx` when one is available. The palette
and typography (a warm gold/ink academic palette, "Fraunces" for display
type, "Public Sans" for UI, "IBM Plex Mono" for scores/data) were chosen
to feel distinct from generic AI-dashboard/Bootstrap-admin defaults, not
copied from the FutureGrad marketing site.

### 18.4 Testing

`tests/test_api.py` covers the FastAPI backend and the new `database.py`
methods (list/filter leads, status changes + activity logging, notes,
pipeline grouping, analytics, and — importantly — that `/api/settings`
never leaks `APIFY_API_TOKEN`/`OPENAI_API_KEY`) using a temporary SQLite
file and FastAPI's `TestClient`. No real Apify/OpenAI calls. Run it with
everything else:

```bash
pytest -q
```

The frontend has no live browser tests in this environment (see §18.5),
but `npm run build` (from `web/`) type-checks the whole app and produces a
production bundle — run it after any frontend change to catch errors
before opening the dashboard.

### 18.5 Known limitations

- I could not literally open the dashboard in a browser to visually
  inspect it from the environment this was built in — no headless browser
  could be installed there (no network access to download one). What I
  did verify directly: the backend serves real, correct data for every
  endpoint (tested end-to-end with `curl` against a live server), the
  frontend's production build compiles with zero TypeScript errors, and
  the built frontend correctly serves `FutureGrad | Reddit Lead
  Intelligence` as the browser title with the right fonts/favicon
  loading. **Please do the final visual/interaction pass yourself** —
  click through every page listed in §18.2 once both servers are running,
  per the brief's own "actually run it" requirement.
- The scan/validation background jobs use simple in-process state (one
  scan and one validation run at a time, tracked in memory) — correct for
  a single local user, but state resets if you restart the backend
  mid-scan.
- No dark mode implemented yet.
- The API base URL is hard-coded to `http://localhost:8000` in
  `web/src/lib/api.ts` — fine for local-only use; would need an env-based
  config if this ever moves beyond localhost.
