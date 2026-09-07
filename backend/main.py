"""
Parity Backend — PDS v1 API only.
All legacy routes decommissioned. Use /v1/* exclusively.
"""
import asyncio
import re
import traceback
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from dotenv import load_dotenv

from v1 import api as v1_api
from v1.ingestion.service import register_ingestion_startup
from v1.integrations.musa_api import router as musa_router
from v1.integrations.musa_parser_request_sla import (
    parser_request_retention_sweeper,
    parser_request_sla_sweeper,
)
from v1.core.pdf_jobs import pdf_job_retention_sweeper

load_dotenv()

# Sentry must be initialized before the FastAPI app is created so that the
# FastAPI/Starlette integrations are registered at app startup.
# DSN is injected per-service via Google Secret Manager (SENTRY_DSN);
# if absent (local dev without the secret), Sentry is silently disabled.
# send_default_pii=False: this backend handles real financial data — PII
# capture (request headers, IPs, user context) is an explicit opt-in later.
# Tracing and profiling are deliberately off (Weever's call, PAR-sentry).
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        send_default_pii=False,
        enable_logs=True,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if _sentry_dsn:
    logger.info("[Sentry] initialized")
else:
    logger.warning("[Sentry] SENTRY_DSN not set — error tracking disabled")

@asynccontextmanager
async def lifespan(app: FastAPI):
    sla_task = asyncio.create_task(parser_request_sla_sweeper.start())
    retention_task = asyncio.create_task(parser_request_retention_sweeper.start())
    pdf_job_reaper_task = asyncio.create_task(pdf_job_retention_sweeper.start())
    yield
    parser_request_sla_sweeper.stop()
    parser_request_retention_sweeper.stop()
    pdf_job_retention_sweeper.stop()
    sla_task.cancel()
    retention_task.cancel()
    pdf_job_reaper_task.cancel()


app = FastAPI(
    title="Parity PDS API",
    description="Deterministic v1 API for deal analysis and snapshots",
    version="2.0.0",
    lifespan=lifespan,
)

# PAR-83: CORS_ORIGINS has historically been set as either comma- or
# space-separated (or a mix, from manual workarounds). Split on any run of
# whitespace and/or commas so the parsing tolerates either convention.
_CORS_ORIGINS = re.split(r"[\s,]+", os.getenv("CORS_ORIGINS", "").strip())
_EXPLICIT_ORIGINS = [
    "https://parityfinance.vercel.app",
    "https://parity-sme-staging.vercel.app",
    "https://parity-ingestion-gmkewhxbha-uc.a.run.app",
    "http://localhost:8000",
    "http://localhost:3000",
]
_ALL_ORIGINS = list({o.strip() for o in _CORS_ORIGINS + _EXPLICIT_ORIGINS if o.strip()})
logger.info("[CORS] allow_origins=%s", _ALL_ORIGINS)

# Intentionally scoped to *.vercel.app only (Vercel preview/staging URLs we
# don't want to hardcode individually). Custom domains (paritytunnel.com and
# its subdomains) are NOT matched by this regex on purpose — they must be
# added explicitly to CORS_ORIGINS, same as any other production origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALL_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# V1 deterministic API — only active router
app.include_router(v1_api.router)

# Musa Ventures integration
app.include_router(musa_router)

register_ingestion_startup(app)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error("[UNHANDLED] %s: %s\n%s", type(exc).__name__, exc, tb)
    # FastAPI's custom exception handler swallows the exception before Sentry's
    # middleware can see it, so we capture explicitly here.
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )


# VERIFICATION ROUTE — remove or keep gated before closing PAR-sentry.
# Raises a deliberate ZeroDivisionError so Sentry receipt can be confirmed
# in the Sentry dashboard immediately after deploy. Only registered when
# SENTRY_DEBUG_ROUTE=true is set on the service (staging only).
if os.getenv("SENTRY_DEBUG_ROUTE") == "true":
    @app.get("/v1/sentry-debug")
    async def sentry_debug():
        """Temporary: triggers a ZeroDivisionError to verify Sentry capture."""
        return 1 / 0


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Parity PDS API",
        "status": "running",
        "version": "2.0.0",
        "api": "v1",
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api": "v1",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
