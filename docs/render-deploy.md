# Deploying for $0 (Render free tier + Neon free tier)

This repo's [`render.yaml`](../render.yaml) provisions a **zero-cost** stack:

- **Database**: not on Render. Render's own free Postgres auto-deletes after
  30 days (44 with the grace period) — it's a trial, not free hosting. Use
  [Neon](https://neon.tech)'s free tier instead: persistent Postgres, no
  auto-deletion (the project pauses after inactivity and wakes on the next
  query — no data loss).
- **Backend**: one free Render web service. No separate Celery worker and no
  Redis — Render's background workers have **no free tier** ($7/mo minimum).
  Instead, `CELERY_TASK_ALWAYS_EAGER=true` makes ingestion tasks run inline
  in the same request/process.
- **Frontend**: a free Render static site.

No credit card is required for any of this.

## Trade-offs of the free shape

- The backend spins down after 15 min idle; the next request eats a ~1 min
  cold start.
- CSV uploads process synchronously (eager mode) instead of being queued —
  a large upload blocks the request until it finishes. Fine for occasional/
  personal use; revisit (paid worker + Redis, or `render.yaml`'s original
  worker-based version) if uploads get large or frequent.
- Local filesystem storage is ephemeral: fine because the backend is the
  only process touching it, but raw uploaded CSVs won't survive a redeploy
  or a cold-start container recycle. The parsed data already committed to
  Postgres is unaffected either way.

## 1. Create the free Neon database

1. Sign up at [neon.tech](https://neon.tech) (free, no card).
2. Create a project, e.g. database name `email_intel`.
3. Copy the connection string it gives you — looks like
   `postgresql://user:password@ep-xxxx.neon.tech/email_intel?sslmode=require`.

## 2. Create the Render Blueprint

1. Render dashboard → **New +** → **Blueprint**.
2. Connect the `portneon/od-analytics` GitHub repo, branch `main`.
3. Render reads `render.yaml` and lists `od-analytics-backend` (free web
   service) and `od-analytics-frontend` (free static site). Confirm.
4. When prompted for secrets:
   - `od-analytics-backend`: `DATABASE_URL` = the Neon connection string
     from step 1. `LLM_API_KEY` is optional — leave blank to run the AI
     Analyst in fallback mode (still $0 either way; Groq also has a free
     tier if you want it enabled).

## 3. After the first deploy: fix the cross-service URLs

`render.yaml` guesses the URLs as `https://od-analytics-backend.onrender.com`
and `https://od-analytics-frontend.onrender.com` (Render uses the exact
service name as the subdomain unless someone else already claimed it). Check
the real URLs Render assigned:

1. If either differs from the guess, update it:
   - `od-analytics-backend` → env var `CORS_ORIGINS` = real frontend URL.
   - `od-analytics-frontend` → env var `VITE_API_BASE_URL` =
     `https://<real-backend-url>/api/v1`, then trigger a manual redeploy
     (Vite bakes this in at build time — just changing the env var isn't
     enough).

## 4. Verify

- `GET https://<backend-url>/health` → 200 (expect a ~1 min cold start if
  the service had been idle).
- Log in via the frontend, upload a CSV, confirm it processes (the request
  will hang until processing finishes — that's the eager-mode trade-off).

## Staying within free limits

- Render: 750 free instance-hours/month per workspace, 100 GB bandwidth,
  500 build minutes — one always-on-ish small service comfortably fits.
- Neon free tier: check current storage/compute limits at
  [neon.tech/pricing](https://neon.tech/pricing) if the dataset grows large.

## If you outgrow this later

Switch back to the worker-based architecture: a paid Render background
worker + Redis (Key Value), and real S3-compatible object storage instead
of local disk (needed once backend and worker are separate containers
again). See `docs/deployment.md` for the production configuration this
scales up to.
