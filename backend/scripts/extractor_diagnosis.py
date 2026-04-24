#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

# Ensure parity-ingestion app imports resolve regardless of invocation path.
_REPO_ROOT = "/Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel"
_PARITY_INGESTION_ROOT = os.path.join(_REPO_ROOT, "parity-ingestion")
if _PARITY_INGESTION_ROOT not in sys.path:
    sys.path.insert(0, _PARITY_INGESTION_ROOT)

from app.extractors.router import route_extract  # noqa: E402
from app.models import ExtractionResult  # noqa: E402


FIXTURES: List[Tuple[str, str]] = [
    ("Co-op", "/Users/mbakswatu/Desktop/Demofiles/MAUCABANKCOP.pdf"),
    ("KCB", "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples/KCB Bank Statement (1).pdf"),
    ("ABSA", "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples/absa.pdf"),
    ("Equity", "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples/Unlock PDF Equity Unlocked.pdf"),
    ("M-Pesa", "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples/OLIechodhiambompesasample.pdf"),
    ("Sassy-Equity-Apr-2025", "/Users/mbakswatu/Desktop/Demofiles/Sassy Cosmetics - Equity Bank - 1180279761781 - Apr 2025.pdf"),
    ("Sassy-Equity-May-2025", "/Users/mbakswatu/Desktop/Demofiles/Sassy Cosmetics - Equity Bank - 1180279761781 - May 2025.pdf"),
    ("Sassy-Equity-Jun-2025", "/Users/mbakswatu/Desktop/Demofiles/Sassy Cosmetics - Equity Bank - 1180279761781 - Jun 2025.pdf"),
]


def _now() -> float:
    return time.perf_counter()


def _truncate(s: str, n: int = 200) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def _peak_mem_mb() -> Optional[float]:
    if psutil is None:
        return None
    try:
        proc = psutil.Process(os.getpid())
        return float(proc.memory_info().rss) / (1024 * 1024)
    except Exception:
        return None


def _extract_raw_text(path: str) -> Tuple[int, float, List[List[str]]]:
    t0 = _now()
    pages_lines: List[List[str]] = []
    page_count = 0
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            txt = page.extract_text() or ""
            lines = txt.splitlines()
            pages_lines.append(lines)
    elapsed = _now() - t0
    return page_count, elapsed, pages_lines


def _resolve_sassy_path(label: str, desktop_path: str) -> Tuple[Optional[str], List[str]]:
    """
    Resolve Sassy fixture paths with iCloud fallback checks.
    Returns (resolved_path_or_none, precheck_lines).
    """
    out: List[str] = []
    filename = os.path.basename(desktop_path)
    icloud_path = (
        "/Users/mbakswatu/Library/Mobile Documents/com~apple~CloudDocs/Desktop/Demofiles/"
        + filename
    )
    icloud_stub = icloud_path + ".icloud"

    out.append(f"SASSY PRECHECK: {label}")
    out.append(f"- Desktop path: {desktop_path}")
    d_exists = os.path.exists(desktop_path)
    out.append(f"- Desktop exists: {'FOUND' if d_exists else 'NOT FOUND'}")
    if d_exists:
        try:
            sz = os.path.getsize(desktop_path)
            out.append(f"- Desktop size_bytes: {sz}")
            if sz > 10 * 1024:
                return desktop_path, out
        except Exception:
            out.append("- Desktop size_bytes: <error>")

    out.append(f"- iCloud path: {icloud_path}")
    i_exists = os.path.exists(icloud_path)
    out.append(f"- iCloud exists: {'FOUND' if i_exists else 'NOT FOUND'}")
    if i_exists:
        try:
            sz = os.path.getsize(icloud_path)
            out.append(f"- iCloud size_bytes: {sz}")
            if sz > 10 * 1024:
                return icloud_path, out
        except Exception:
            out.append("- iCloud size_bytes: <error>")

    stub_exists = os.path.exists(icloud_stub)
    out.append(f"- iCloud .icloud exists: {'FOUND' if stub_exists else 'NOT FOUND'}")
    if stub_exists:
        out.append("ICLOUD STUB — file not downloaded, skipping")

    out.append("SKIP — not available locally")
    return None, out


def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()  # pydantic v2
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict()  # pydantic v1
        except Exception:
            pass
    if isinstance(obj, dict):
        return obj
    return {}


def _validate_missing_fields(
    raw_rows: List[Dict[str, Any]],
    norm_rows: List[Dict[str, Any]],
) -> Dict[str, int]:
    missing = {
        "txn_date": 0,
        "amount_cents": 0,
        "descriptor": 0,
        "role": 0,
    }

    # Use normalised rows where possible; fall back to raw.
    if norm_rows:
        for r in norm_rows:
            if not r.get("date"):
                missing["txn_date"] += 1
            if r.get("debit_cents") is None and r.get("credit_cents") is None:
                missing["amount_cents"] += 1
            if not (r.get("description") or "").strip():
                missing["descriptor"] += 1
            # role not present in parity-ingestion normalised rows
            missing["role"] += 1
    else:
        for r in raw_rows:
            if not (r.get("date_raw") or "").strip():
                missing["txn_date"] += 1
            if not (r.get("debit_raw") or "").strip() and not (r.get("credit_raw") or "").strip():
                missing["amount_cents"] += 1
            if not (r.get("description") or "").strip():
                missing["descriptor"] += 1
            if not (r.get("pattern_hint") or "").strip():
                missing["role"] += 1

    return missing


def _count_duplicate_txn_ids(raw_rows: List[Dict[str, Any]], norm_rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    txn_ids: List[Any] = []
    for r in raw_rows:
        if "txn_id" in r:
            txn_ids.append(r.get("txn_id"))
    for r in norm_rows:
        if "txn_id" in r:
            txn_ids.append(r.get("txn_id"))

    ids = [x for x in txn_ids if x is not None and str(x) != ""]
    if not ids:
        return 0, 0
    seen: Dict[str, int] = {}
    dups = 0
    for x in ids:
        k = str(x)
        seen[k] = seen.get(k, 0) + 1
    for v in seen.values():
        if v > 1:
            dups += (v - 1)
    return len(ids), dups


def diagnose_fixture(label: str, path: str) -> Tuple[str, Dict[str, Any]]:
    lines: List[str] = []
    stats: Dict[str, Any] = {
        "extractor": label,
        "pages": 0,
        "txn_count": 0,
        "total_time_s": 0.0,
        "text_extract_s": 0.0,
        "errors": 0,
    }

    resolved_path = path
    precheck_lines: List[str] = []
    if label in {"Sassy-Equity-Apr-2025", "Sassy-Equity-May-2025", "Sassy-Equity-Jun-2025"}:
        resolved_path, precheck_lines = _resolve_sassy_path(label, path)
        if resolved_path is None:
            section_lines = [f"=== FIXTURE NAME === {label}", f"Path: {path}", ""]
            section_lines.extend(precheck_lines)
            section_lines.append("")
            return "\n".join(section_lines), stats
    elif not os.path.exists(path):
        # skip silently for non-Sassy fixtures
        return "", stats

    lines.append(f"=== FIXTURE NAME === {label}")
    lines.append(f"Path: {resolved_path}")
    if precheck_lines:
        lines.append("")
        lines.extend(precheck_lines)

    file_size = os.path.getsize(resolved_path)
    lines.append("")
    lines.append("1) FILE STATS")
    lines.append(f"- file_size_bytes: {file_size}")

    page_count = 0
    text_extract_s = 0.0
    page_lines: List[List[str]] = []
    try:
        page_count, text_extract_s, page_lines = _extract_raw_text(resolved_path)
        stats["pages"] = page_count
        stats["text_extract_s"] = text_extract_s
        lines.append(f"- page_count: {page_count}")
        lines.append(f"- raw_text_extract_seconds: {text_extract_s:.6f}")
    except Exception:
        stats["errors"] += 1
        lines.append("- file_stats_error: yes")
        lines.append(traceback.format_exc())

    lines.append("")
    lines.append("2) EXTRACTION PERFORMANCE")
    mem_before = _peak_mem_mb()
    t0 = _now()
    extraction_exception: Optional[str] = None
    result_obj: Any = None
    try:
        result_obj = route_extract(resolved_path)
    except Exception:
        extraction_exception = traceback.format_exc()
    total_s = _now() - t0
    mem_after = _peak_mem_mb()
    stats["total_time_s"] = total_s

    lines.append(f"- total_wall_seconds: {total_s:.6f}")
    lines.append(f"- text_extract_seconds: {text_extract_s:.6f}")
    parse_only = max(0.0, total_s - text_extract_s)
    lines.append(f"- parse_plus_postprocess_seconds_approx: {parse_only:.6f}")
    if mem_before is not None and mem_after is not None:
        lines.append(f"- memory_mb_before: {mem_before:.2f}")
        lines.append(f"- memory_mb_after: {mem_after:.2f}")
        lines.append(f"- memory_mb_delta: {mem_after - mem_before:.2f}")
    else:
        lines.append("- memory_mb: unavailable (psutil not installed)")

    lines.append("")
    lines.append("3) TRANSACTION OUTPUT")
    raw_rows: List[Dict[str, Any]] = []
    norm_rows: List[Dict[str, Any]] = []
    classification_none = 0
    pattern_none = 0
    pattern_set = 0
    currency_none = 0
    currency_set = 0

    if extraction_exception:
        stats["errors"] += 1
        lines.append("- extraction_result: exception")
    else:
        if isinstance(result_obj, dict) and result_obj.get("status") == "UNSUPPORTED_FORMAT":
            lines.append("- extraction_result: UNSUPPORTED_FORMAT")
        elif isinstance(result_obj, ExtractionResult):
            raw_rows = [_to_dict(r) for r in result_obj.raw_transactions]
            norm_rows = [_to_dict(r) for r in result_obj.normalised_transactions]
            stats["txn_count"] = len(raw_rows)
            lines.append(f"- transaction_count: {len(raw_rows)}")
            first3 = [_truncate(str(x), 200) for x in raw_rows[:3]]
            last3 = [_truncate(str(x), 200) for x in raw_rows[-3:]]
            lines.append(f"- first_3_transactions: {first3}")
            lines.append(f"- last_3_transactions: {last3}")

            for r in raw_rows:
                v = r.get("classification_status")
                if v is None or str(v).strip() == "":
                    classification_none += 1
                p = r.get("pattern_hint")
                if p is None:
                    pattern_none += 1
                else:
                    pattern_set += 1

            for n in norm_rows:
                c = n.get("currency")
                if c is None or str(c).strip() == "":
                    currency_none += 1
                else:
                    currency_set += 1

            lines.append(f"- classification_status_none_or_empty: {classification_none}")
            lines.append(f"- pattern_hint_none: {pattern_none}")
            lines.append(f"- pattern_hint_set: {pattern_set}")
            lines.append(f"- currency_none (normalised): {currency_none}")
            lines.append(f"- currency_set (normalised): {currency_set}")
        else:
            lines.append("- extraction_result: unknown_result_type")
            lines.append(f"- result_type: {type(result_obj).__name__}")

    lines.append("")
    lines.append("4) ERROR SURFACE")
    if extraction_exception:
        lines.append("- extraction_exception_traceback:")
        lines.append(extraction_exception.rstrip())
    else:
        lines.append("- extraction_exception_traceback: none")

    missing = _validate_missing_fields(raw_rows, norm_rows)
    lines.append(f"- missing_required_fields: {missing}")

    seen_count, dup_count = _count_duplicate_txn_ids(raw_rows, norm_rows)
    lines.append(f"- txn_id_seen_count: {seen_count}")
    lines.append(f"- txn_id_duplicate_count: {dup_count}")

    lines.append("")
    lines.append("5) RAW TEXT SAMPLE")
    if page_lines:
        p1 = page_lines[0][:50]
        lines.append("- page_1_first_50_lines:")
        for ln in p1:
            lines.append(ln)
        if len(page_lines) > 1:
            p2 = page_lines[1][:50]
            lines.append("- page_2_first_50_lines:")
            for ln in p2:
                lines.append(ln)
        else:
            lines.append("- page_2_first_50_lines: <no page 2>")
    else:
        lines.append("- raw_text_sample: unavailable")

    lines.append("")
    return "\n".join(lines), stats


def main() -> int:
    all_sections: List[str] = []
    summary_rows: List[Dict[str, Any]] = []

    for label, path in FIXTURES:
        section, stats = diagnose_fixture(label, path)
        if section:
            all_sections.append(section)
            summary_rows.append(stats)

    lines: List[str] = []
    if all_sections:
        lines.extend(all_sections)
        lines.append("")
    lines.append("=== SUMMARY TABLE ===")
    lines.append("Extractor | Pages | Txn Count | Total Time(s) | Text Extract(s) | Errors")
    for s in summary_rows:
        lines.append(
            f"{s['extractor']} | {s['pages']} | {s['txn_count']} | "
            f"{s['total_time_s']:.4f} | {s['text_extract_s']:.4f} | {s['errors']}"
        )

    output = "\n".join(lines) + "\n"
    print(output, end="")

    out_path = "/Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel/backend/scripts/extractor_diagnosis_output.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

