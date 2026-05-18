# Deploying Repo Quiz

Three processes, two codebases:

| Service | Codebase | Start command |
|---------|----------|---------------|
| **Frontend** | `frontend/` | `npm run build` → host on Vercel (or similar) |
| **API** | `backend/` | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| **Worker** | `backend/` (same image) | `python -m pipeline.worker.main` |

Postgres (Supabase), Upstash Redis, and Supabase Storage are already external — no extra deploy for those.

## Environment variables

### Backend (`backend/.env`) — API **and** worker

Copy from your local `backend/.env`:

- `OPENAI_API_KEY`
- `DATABASE_URL`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_SOURCES_BUCKET` (e.g. `repos`)
- `SUPABASE_ARTIFACTS_BUCKET` (e.g. `pipeline-artifacts`)

Optional: `PORT` (default `5000` for API).

### Frontend (`frontend/` on Vercel)

- `NEXT_PUBLIC_BACKEND_URL` = public URL of the API (e.g. `https://your-api.onrender.com`)

Do **not** put backend secrets on the frontend.

## Backend on Render (example)

Create **two** Web Services from the same repo, root directory `backend`, using the Dockerfile (or native Python):

**1. API service**

- Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/healthz`
- Instance: at least 512MB RAM

**2. Worker service**

- Start: `python -m pipeline.worker.main`
- **Persistent disk** (recommended): mount at `/app/backend/data` so clones survive restarts
- Instance: **2GB+ RAM** (sentence-transformers + SCIP). This is the slow/expensive one.

The API can restore source tarballs from Supabase when a repo is not on local disk (separate API/worker instances are OK). The worker still needs disk for clones, venvs, and `repo.db` during runs.

## Frontend on Vercel

1. Import repo, set root directory to `frontend`.
2. Framework preset: Next.js.
3. Env: `NEXT_PUBLIC_BACKEND_URL=https://<your-api-host>`.
4. Deploy.

## Railway / Fly

Same pattern: one service running uvicorn, one long-running worker with a volume on `backend/data` if the platform supports it. Use the `backend/Dockerfile` for both; only the start command differs.

## Local parity

```text
# Terminal 1 — API
cd backend
.\pipeline\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn[standard]
uvicorn app:app --host 0.0.0.0 --port 5000

# Terminal 2 — worker
cd backend
.\pipeline\.venv\Scripts\Activate.ps1
python -m pipeline.worker.main

# Terminal 3 — frontend
cd frontend
npm run dev
```

## Smoke check after deploy

1. `GET https://<api>/healthz` → `{"ok":true}`
2. Open the Vercel URL, submit a public repo, confirm progress bar moves.
3. When done, quiz loads with questions and file tree.
