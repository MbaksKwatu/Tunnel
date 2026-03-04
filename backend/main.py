"""
Parity Backend — PDS v1 API only.
All legacy routes decommissioned. Use /v1/* exclusively.
"""
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from dotenv import load_dotenv

from v1 import api as v1_api

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Parity PDS API",
    description="Deterministic v1 API for deal analysis and snapshots",
    version="2.0.0",
)

_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")
_EXPLICIT_ORIGINS = [
    "https://paritytunnel-w7d2.onrender.com",
    # Primary Vercel deployment — explicit entry in addition to regex to ensure
    # CORS headers are injected even on 5xx error responses.
    "https://v0-fund-iq-1-0.vercel.app",
]
_ALL_ORIGINS = list({o.strip() for o in _CORS_ORIGINS + _EXPLICIT_ORIGINS if o.strip()})
logger.info("[CORS] allow_origins=%s", _ALL_ORIGINS)

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error("[UNHANDLED] %s: %s\n%s", type(exc).__name__, exc, tb)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )


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
