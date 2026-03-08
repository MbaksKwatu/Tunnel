from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from app.models import ExtractionResult
from app.extractors.pdf_extractor import extract_scb_pdf
from app.extractors.mpesa_extractor import extract_mpesa_csv
from app.extractors.pdf_type_detector import is_scanned_pdf
from app.extractors.docai_extractor import extract_with_docai
from app.normaliser import normalise_all

app = FastAPI(
    title="Parity Ingestion Service",
    version="1.0.0-phase3",
    description="Phase 1+3: raw extraction + normalisation (integer cents, ISO dates).",
)

_UPLOAD_DIR = Path("/tmp/parity-ingestion/uploads")
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# In-memory result store — intentionally stateless across restarts (Phase 1)
_results: dict[str, ExtractionResult] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "parity-ingestion", "version": "1.0.0-phase3"}


@app.post("/v1/ingest/upload", response_model=ExtractionResult)
async def upload(file: UploadFile = File(...)) -> ExtractionResult:
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()

    if ext not in (".pdf", ".csv"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Accepted: .pdf, .csv",
        )

    # Write to temp location
    result_id = str(uuid.uuid4())
    dest = _UPLOAD_DIR / f"{result_id}{ext}"
    content = await file.read()
    dest.write_bytes(content)

    try:
        if ext == ".pdf":
            if is_scanned_pdf(str(dest)):
                result = extract_with_docai(str(dest), doc_id=result_id, filename=filename)
            else:
                result = extract_scb_pdf(str(dest))
        else:
            result = extract_mpesa_csv(str(dest))
        normalise_all(result)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result.result_id = result_id
    result.source_file = filename  # return original name, not temp path
    _results[result_id] = result

    return result


@app.get("/v1/ingest/result/{result_id}", response_model=ExtractionResult)
def get_result(result_id: str) -> ExtractionResult:
    result = _results.get(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result
