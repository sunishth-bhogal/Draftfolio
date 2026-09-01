"""FastAPI entrypoint."""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, catalog, daily_router, explore_router, leaderboard, orders, rivals_router, trade, valuation

app = FastAPI(title="Draftfolio API", version="0.1.0")

# Local dev: allow the Next.js frontend to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, tags=["auth"])
app.include_router(rivals_router.router, tags=["rivals"])
app.include_router(daily_router.router, tags=["daily"])
app.include_router(explore_router.router, tags=["explore"])
app.include_router(trade.router, tags=["trade"])
app.include_router(catalog.router, tags=["catalog"])
app.include_router(orders.router, tags=["orders"])
app.include_router(valuation.router, tags=["valuation"])
app.include_router(leaderboard.router, tags=["leaderboard"])


@app.get("/health")
def health() -> dict:
    """Liveness + a place to surface data freshness later."""
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "data_freshness": None,
    }
