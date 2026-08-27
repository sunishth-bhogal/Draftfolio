# Deploying Draftfolio

Two pieces: the **API + Postgres** on [Render](https://render.com) (declared in
`render.yaml`) and the **frontend** on [Vercel](https://vercel.com). CI
(`.github/workflows/ci.yml`) runs the tests + a production build on every push.

I can't create accounts or enter your credentials, so the steps below are yours
to click through. Everything they reference is already committed.

## 1. API + database — Render (from `render.yaml`)

1. Push this repo to GitHub (done) and sign in to Render with GitHub.
2. **New → Blueprint**, pick this repo. Render reads `render.yaml` and proposes
   `draftfolio-api` (Docker web service) + `draftfolio-db` (managed Postgres).
3. Click **Apply**. On first boot the container runs `alembic upgrade head`
   automatically (see `backend/entrypoint.sh`), so the schema is created for you.
4. When it's live, note the URL, e.g. `https://draftfolio-api.onrender.com`.
   Check `‹url›/health` returns `{"status":"ok"}` and `‹url›/docs` loads.

`DATABASE_URL` is wired automatically from the database. You'll set
`CORS_ORIGINS` in step 3 once you know the Vercel URL.

### Seed demo data (once, optional)
From the Render dashboard **Shell** on the API service:
```bash
python -m scripts.seed_demo
```
This populates the 6 demo portfolios so the leaderboard isn't empty.

## 2. Frontend — Vercel

1. Sign in to Vercel with GitHub, **Add New → Project**, pick this repo.
2. Set **Root Directory** to `frontend` (Vercel auto-detects Next.js there).
3. Add an environment variable:
   - `NEXT_PUBLIC_API_URL` = your Render API URL (e.g. `https://draftfolio-api.onrender.com`)
4. **Deploy.** Note the resulting URL, e.g. `https://draftfolio.vercel.app`.

## 3. Connect them (CORS)

Back on Render → `draftfolio-api` → **Environment**, set:
- `CORS_ORIGINS` = your Vercel origin (e.g. `https://draftfolio.vercel.app`)

Save; the API redeploys. The browser can now call the API cross-origin.

## Notes / caveats

- **Free tiers sleep.** Render's free web service spins down when idle; the first
  request after a nap takes ~30s. Fine for a portfolio demo, not for production.
- **Fresh drafts show n/a analytics** until they have ≥2 daily snapshots. In a
  real deployment you'd add a scheduled job that calls `take_snapshot` daily
  (Phase 4 background worker) so history accrues.
- **Alternatives:** the same Docker image runs on Fly.io or Railway; only the
  Postgres wiring differs. `app/config.py` already normalizes a `postgres://`
  URL to the driver-qualified scheme those hosts also use.
