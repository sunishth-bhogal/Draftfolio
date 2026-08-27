# Draftfolio

[![CI](https://github.com/sunishth-bhogal/Draftfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/sunishth-bhogal/Draftfolio/actions/workflows/ci.yml)

Risk-aware fantasy investing — draft a virtual stock/ETF portfolio under a
salary cap and compete on **risk-adjusted** performance, not raw return.

The technical heart is a virtual brokerage **ledger you cannot lose or invent
money in**: an append-only transaction log, idempotent orders, `Decimal` money,
and financial invariants verified with property-based tests. See
[DESIGN.md](DESIGN.md).

## Status

Phase 0 — ledger domain core + proven invariants. Persistence and API next.

## Quickstart

```bash
# 1. Backend deps
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the property tests (no infra needed — pure domain)
pytest tests/test_ledger_invariants.py -q

# 3. Bring up Postgres + Redis (needs Docker Desktop running)
cd ..
docker compose up -d

# 4. Run the API
cd backend
uvicorn app.main:app --reload      # http://localhost:8000/health, /docs
```

## Layout

```
backend/
  app/
    domain/      pure ledger + Money value object (no DB/framework)
    models/      SQLAlchemy ORM (persistence)
    routers/     FastAPI endpoints
    services/    orchestration between domain and persistence
  tests/         property-based invariant tests
docker-compose.yml   Postgres + Redis
DESIGN.md            architecture, invariants, ADRs
```

## Deploy

API + Postgres on Render (via `render.yaml`), frontend on Vercel. Step-by-step in [DEPLOY.md](DEPLOY.md). CI runs the test suite + a production build on every push.
