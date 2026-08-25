"""FastAPI entrypoint."""

from datetime import datetime, timezone

from fastapi import FastAPI

from app.routers import orders

app = FastAPI(title="Draftfolio API", version="0.1.0")
app.include_router(orders.router, tags=["orders"])


@app.get("/health")
def health() -> dict:
    """Liveness + a place to surface data freshness later."""
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "data_freshness": None,  # Phase 1+: last market-data timestamp
    }
