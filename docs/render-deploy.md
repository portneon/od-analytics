# Deploying to Render

This repo includes [`render.yaml`](../render.yaml), a Blueprint that provisions:
Postgres, Redis (Key Value), the backend API, a Celery worker, and the frontend
static site. Render doesn't have an API key configured in this environment, so
these steps are manual, done once in the Render dashboard.

## 1. Object storage (required before first deploy)

The backend and worker run as separate containers on Render, so
`STORAGE_USE_LOCAL_FS=true` (local disk) won't work -- the worker can't see files
the backend saved. Create a bucket with any S3-compatible provider (AWS S3,
Cloudflare R2, Backblaze B2, ...) and have its endpoint URL, bucket name, access
key, and secret key ready. `render.yaml` already sets `STORAGE_USE_LOCAL_FS=false`
and leaves `STORAGE_ENDPOINT` / `STORAGE_BUCKET` / `STORAGE_ACCESS_KEY` /
`STORAGE_SECRET_KEY` as `sync: false` (secret, entered manually) on both the
backend and worker services.

## 2. Create the Blueprint

1. In the Render dashboard: **New +** → **Blueprint**.
2. Connect the `portneon/od-analytics` GitHub repo, branch `main`.
3. Render reads `render.yaml` and lists the services it will create. Confirm.
4. Before the first deploy, fill in the secret env vars it prompts for:
   - `od-analytics-backend` and `od-analytics-worker`: `STORAGE_ENDPOINT`,
     `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`.
   - `od-analytics-backend`: `LLM_API_KEY` (Groq key), if you want the AI
     Analyst enabled. Leave blank to run in fallback mode.

## 3. After the first deploy: fix the cross-service URLs

Static-site env vars are baked in at build time, and `render.yaml` can't yet
predict the exact `*.onrender.com` hostnames, so two values need one manual
update after the first deploy:

1. Note the real URLs Render assigned, e.g.
   `https://od-analytics-backend-xxxx.onrender.com` and
   `https://od-analytics-frontend-xxxx.onrender.com`.
2. On `od-analytics-backend`, set `CORS_ORIGINS` to the real frontend URL.
3. On `od-analytics-frontend`, set `VITE_API_BASE_URL` to
   `https://<real-backend-url>/api/v1`, then trigger a manual redeploy (Vite
   bakes this in at build time, so just changing the env var isn't enough).

## 4. Verify

- `GET https://<backend-url>/health` should return 200.
- Log in via the frontend, upload a CSV, confirm the dataset processes (this
  exercises backend → object storage → worker → Postgres end to end).
- Check the `od-analytics-worker` logs for `celery ... worker` startup and task
  processing.

See [deployment.md](deployment.md) for the underlying production configuration
this blueprint implements (`JWT_SECRET`, `CORS_ORIGINS`, storage, etc.).
