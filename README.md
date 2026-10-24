# ResumeForgeAI

Each user has one resume profile, and it drives two outputs:

- **ATS PDF**: a plain, single-column PDF that ATS parsers can read (Jinja2 template → Playwright/Chromium → PDF).
- **Cinematic page**: an animated, shareable HTML page served at `/r/{slug}`.

Both are rendered from the same JSON profile (`resumes.profile_json`), so they never drift apart.

```
React (Vite) ──HTTPS+JWT──▶ FastAPI ──▶ MySQL 8     (users, resume, upload/job records)
                               ├──────▶ S3          (photos/, exports/, uploads/)
                               ├──────▶ Groq LLM    (parse + spelling/grammar, background only)
                               └──────▶ BackgroundTasks worker ──▶ Playwright PDF / cinematic HTML
```

## Project layout

```
resume-stack/
├── docker-compose.yml        MySQL 8 + backend + frontend
├── .env.example              every setting, copy to .env
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app, CORS, routers, dev file serving
│   │   ├── config.py         env-driven settings
│   │   ├── db.py, models.py  SQLAlchemy 2.0 models (users, resumes, resume_uploads, export_jobs)
│   │   ├── schemas.py        Pydantic API models + the fixed `Profile` schema
│   │   ├── core/security.py  bcrypt (passlib) + JWT access/refresh tokens
│   │   ├── routers/          auth, resume, export, public (/r/{slug})
│   │   ├── services/         auth, resume, export, file validation, text extraction
│   │   ├── clients/          llm_client (Groq), storage_client (S3 / local)
│   │   ├── workers/tasks.py  background jobs: parse upload, grammar pass, render export
│   │   └── templates/        ats.html, cinematic.html
│   ├── alembic/              migrations (0001_initial)
│   └── tests/                pytest suite (SQLite + fakes; no MySQL/S3/Groq needed)
└── frontend/
    └── src/                  api.js, auth.jsx, pages/ (Auth, Dashboard, Editor), components/
```

## Running locally

Prerequisites: Python 3.11+, Node 20+, and Docker (for MySQL).

```bash
cp .env.example .env            # then fill in GROQ_API_KEY and JWT_SECRET

# 1. Database
docker compose up -d mysql

# 2. Backend  (http://localhost:8000, docs at /docs)
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
playwright install chromium
alembic upgrade head
uvicorn app.main:app --reload

# 3. Frontend (http://localhost:5173)
cd ../frontend
npm install
npm run dev
```

With `STORAGE_BACKEND=local`, files are written to `backend/local_storage/`, and `photos/` and `exports/` are served from `/files/...`. AWS isn't needed for development. To use S3, set `STORAGE_BACKEND=s3` and the `S3_*` variables.

### Running with Docker

```bash
cp .env.example .env            # set JWT_SECRET and GROQ_API_KEY
docker compose up -d --build    # MySQL + backend (runs migrations) + frontend
```

Then open http://localhost:5173 (app), http://localhost:8000/docs (API) or connect to MySQL on `localhost:3307`. If port 3307 is also taken, set `MYSQL_HOST_PORT` in `.env`. After changing any `VITE_*` value, rebuild the frontend with `docker compose up -d --build frontend`, because Vite bakes those values in at build time.

### Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

The suite covers auth (including refresh-token misuse), one-resume-per-user upsert, upload → draft autofill, magic-byte rejection of spoofed files, per-user isolation, photo crop validation, both exports, the public page (including stripping `javascript:` links), and the LLM correction guard.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/signup` | Create account |
| POST | `/auth/login` | Issue access + refresh JWT |
| POST | `/auth/refresh` | Exchange refresh token for new tokens |
| GET | `/auth/me` | Current user |
| GET | `/resume` | The user's one resume (404 if none yet) |
| PUT | `/resume` | Upsert; `correct_text: true` queues a grammar pass after saving |
| POST | `/resume/upload` | Upload PDF/DOCX → 202 + upload id (parsed in background) |
| GET | `/resume/upload/{id}` | Poll parse status; `parsed_json` is the draft to review |
| POST | `/resume/photo` | Photo + optional square crop (`crop_x`, `crop_y`, `crop_size`) |
| POST | `/resume/export` | `{type: "ats" \| "cinematic"}` → 202 + job id |
| GET | `/resume/export/{job_id}` | Poll job; `output_url` (PDF) or `public_url` (page) |
| GET | `/r/{slug}` | Public cinematic page, no auth |

## LLM (Groq) behaviour

- Parsing uses `openai/gpt-oss-20b` in JSON mode, validated against the Pydantic `Profile` schema. On a schema mismatch it retries once on the 20B model, then falls back to `openai/gpt-oss-120b`.
- Correction only fixes spelling and grammar. The model sees only free-text fields, as an `{id: text}` map, so it can't change structure. A code guard rejects any correction that changes the word count by more than about 15% or adds a number that wasn't in the original.
- On rate limits (429) and connection errors, it retries with exponential backoff (2s, 4s, 8s, 16s).
- Groq is never called on the request thread. If Groq fails, parsing fails with a friendly message and saving still works. The grammar pass runs after the save, so it never blocks one.

## Changes from the architecture doc

The implementation follows the doc, with these deliberate additions:

- **Profile schema** adds `basics` (name, headline, email, phone, location) to the doc's fixed keys. A resume needs contact details, and both templates render them.
- **`resume_uploads`** gets `parsed_json` and `error`, and **`export_jobs`** gets `error`. `GET /resume/upload/{id}` needs somewhere to hold the draft, and failed jobs need a reason to show.
- **Upload parsing is asynchronous** (202 + poll). This matches the API table and the rule that LLM calls must stay off the request thread. The sequence diagram draws it as synchronous.
- **The S3 bucket has a third prefix, `uploads/`, and it's private.** Raw resumes are kept for the audit trail but are never served publicly. Only `photos/` and `exports/` should be public in the bucket policy or CloudFront.
- **Added `POST /auth/refresh` and `GET /auth/me`.** The auth component description mentions refresh, but the API table doesn't list it.
- **Added `STORAGE_BACKEND=local`** so the app runs in development without AWS.
- **`/r/{slug}` is served by FastAPI** from the stored HTML, with a strict CSP. It can also be fronted by CloudFront, since the file lives at `exports/cinematic/{slug}.html`.

Deferred, as in the doc: malware scanning, Celery/Redis, email verification, CDN invalidation, and multi-region storage.
