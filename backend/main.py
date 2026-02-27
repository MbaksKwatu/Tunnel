"""
Parity Backend — PDS v1 API only.
All legacy routes decommissioned. Use /v1/* exclusively.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://paritytunnel-w7d2.onrender.com",
        "https://*.vercel.app",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# V1 deterministic API — only active router
app.include_router(v1_api.router)


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
