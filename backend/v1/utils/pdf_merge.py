"""
PDF merging utilities for batch uploads.
Merges multiple PDFs from Supabase storage into a single document.
"""

import io
import httpx
from pypdf import PdfWriter
from typing import List
import logging

logger = logging.getLogger(__name__)


async def download_pdf_from_url(url: str) -> bytes:
    """Download PDF from URL (Supabase storage)"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def merge_pdfs_from_urls(pdf_urls: List[str]) -> bytes:
    """
    Merge multiple PDFs from Supabase storage URLs into one PDF.

    Args:
        pdf_urls: List of public Supabase storage URLs

    Returns:
        Merged PDF as bytes

    Raises:
        httpx.HTTPError: If download fails
        Exception: If merge fails
    """
    if not pdf_urls:
        raise ValueError("No PDFs provided to merge")

    if len(pdf_urls) == 1:
        # Single file, just download and return
        logger.info(f"Single file, no merge needed: {pdf_urls[0]}")
        return await download_pdf_from_url(pdf_urls[0])

    logger.info(f"Merging {len(pdf_urls)} PDFs")

    writer = PdfWriter()

    # Download and append each PDF
    for i, url in enumerate(pdf_urls, 1):
        logger.info(f"Downloading PDF {i}/{len(pdf_urls)}: {url[:60]}...")
        pdf_bytes = await download_pdf_from_url(url)

        # Append to merged document
        pdf_stream = io.BytesIO(pdf_bytes)
        writer.append(pdf_stream)
        logger.info(f"  ✓ Appended PDF {i}")

    # Write merged PDF to bytes
    output = io.BytesIO()
    writer.write(output)
    merged_bytes = output.getvalue()

    logger.info(f"✓ Merge complete: {len(merged_bytes)} bytes")
    return merged_bytes


def validate_pdf_count(file_count: int, max_files: int = 3) -> None:
    """
    Validate that file count is within allowed limit.

    Args:
        file_count: Number of files being uploaded
        max_files: Maximum allowed (default 3)

    Raises:
        ValueError: If count exceeds limit
    """
    if file_count < 1:
        raise ValueError("Must upload at least 1 file")

    if file_count > max_files:
        raise ValueError(
            f"Maximum {max_files} files per batch. "
            f"Received {file_count} files."
        )
