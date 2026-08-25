"""FastAPI entrypoint.

Phase 0: a health endpoint and a data-freshness stub. The ledger order endpoint
lands in Phase 1 on top of the domain core in app/domain/.
"""

from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="Draftfolio API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Liveness + a place to surface data freshness later."""
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "data_freshness": None,  # Phase 1: last market-data timestamp
    }
