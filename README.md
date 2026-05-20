# Repo Quiz

Paste a public GitHub repo, wait while it gets indexed and summarized, then quiz yourself on how the code actually works. Questions are generated from the codebase (MCQ, true/false, ordering, pairing, code highlight, etc.) with optional citations back to real files and line ranges.

## How the demo works

1. **Home** — You’ll see repos that have already been analyzed. Click **Add repo**, enter a public GitHub URL, and submit.

2. **Queue** — The API enqueues a job on Redis. A background **worker** clones the repo, runs two pipelines (context, then questions), and streams progress you can watch in the quiz UI.

3. **Context pipeline** — Parses the tree, runs SCIP indexing, builds dependency/call structure, clusters files, and uses an LLM to summarize files, clusters, and the repo. Output lands in a per-repo SQLite `repo.db` and related artifacts in Postgres/Storage.

4. **Questions pipeline** — Reads that context and asks an LLM for structured problems (canonical answer shapes; the frontend shuffles presentation). Results go to Postgres for the live app.

5. **Quiz** — Open a repo to get a file tree, syntax-highlighted source (Shiki), and a quiz pane. Start when problems are ready; progress is stored in the browser per repo.

The live site is a Next.js app talking to a FastAPI backend. The worker must be running (or deployed separately) or new repos will sit in “analyzing…” forever.

## Repository layout

```
frontend/          Next.js UI (Vercel)
backend/           FastAPI + pipeline + worker
  app.py           HTTP API
  pipeline/        context + questions DAGs, worker entrypoint
scripts/           utilities (e.g. wipe_repo.py)
```

## Running locally

You need `backend/.env` configured (same keys you use in production). Then three processes:

```bash
# API
cd backend
# activate backend/pipeline/.venv first
uvicorn app:app --host 0.0.0.0 --port 5000

# Worker
cd backend
python -m pipeline.worker.main

# Frontend
cd frontend
# frontend/.env → NEXT_PUBLIC_BACKEND_URL=http://localhost:5000
npm run dev
```

Open `http://localhost:3000`.

## Deploying

See **[DEPLOY.md](./DEPLOY.md)** for Render/Vercel setup, env vars, and the worker RAM/disk notes.

**Important:** On Vercel, set `NEXT_PUBLIC_BACKEND_URL` to your **public API URL** (e.g. Render). If it’s missing, the built app defaults to `http://localhost:5000` and browsers will ask to access the visitor’s machine—not what you want.

## License

Not specified.
