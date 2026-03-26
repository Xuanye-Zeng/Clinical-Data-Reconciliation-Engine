"""FastAPI application entry point.

Registers CORS middleware, mounts the reconciliation and data quality
routers, and exposes a /health endpoint for basic liveness checks.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.data_quality import router as data_quality_router
from app.api.routes.reconcile import router as reconcile_router
from app.core.config import settings


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reconcile_router)
app.include_router(data_quality_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
