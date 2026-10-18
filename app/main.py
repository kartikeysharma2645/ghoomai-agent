"""GhoomAI Agent FastAPI application.

Exposes a lightweight health endpoint at ``GET /status``. This endpoint
works without any agent credentials or external service calls.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="GhoomAI Agent",
    description="Python service connecting the GhoomAI travel-planning "
    "application to Fetch.ai Agentverse and ASI:One.",
    version="0.1.0",
)


@app.get("/status", tags=["health"])
async def status() -> dict:
    """Return the running status of the Python service.

    This endpoint does not call GhoomAI, Agentverse, or any external
    service, and does not require agent credentials.
    """
    return {
        "status": "ok",
        "service": "ghoomai-agent",
        "version": "0.1.0",
    }
