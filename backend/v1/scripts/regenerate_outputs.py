"""
Parity — Regenerate snapshot PDF and classified CSV for an existing deal.

Does NOT re-ingest. Reads the latest committed snapshot from Supabase,
runs analytics, and writes both files to ~/Documents/Parity/.

USAGE:
    cd backend
    python3 v1/scripts/regenerate_outputs.py <deal_id>

EXAMPLE:
    python3 v1/scripts/regenerate_outputs.py 8c3fcd64-7b70-426d-b011-6ba6ae1fcbc5
"""
from __future__ import annotations

import base64
import csv
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend/ is on sys.path so `v1.*` imports resolve regardless of cwd
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/v1/scripts/ → backend/
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ── STEP 1  Load environment ──────────────────────────────────────────────────

def _load_env() -> None:
    """Load .env.backup → .env → repo-root .env.local, first file with both keys wins."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv not installed. Run: pip install python-dotenv")
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent          # backend/v1/scripts/
    backend_dir = script_dir.parent.parent                # backend/
    repo_dir    = backend_dir.parent                      # Tunnel/

    candidates = [
        backend_dir / ".env.backup",
        backend_dir / ".env",
        repo_dir / ".env.local",
        repo_dir / ".env",
    ]

    for path in candidates:
        if path.exists():
            load_dotenv(path, override=False)
            if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
                return  # found both keys

    # Nothing worked — check if already in environment
    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY not found in any .env file.")
        print("Searched:", [str(p) for p in candidates])
        sys.exit(1)


def _get_supabase():
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase-py not installed. Run: pip install supabase")
        sys.exit(1)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


# ── Helpers ───────────────────────────────────────────────────────────────────

_GZIP_PREFIX = "__PDS1_GZIP_B64__:"


def _decompress(stored: str) -> str:
    if not stored:
        return stored
    if stored.startswith(_GZIP_PREFIX):
        raw = base64.b64decode(stored[len(_GZIP_PREFIX):].encode("ascii"))
        return gzip.decompress(raw).decode("utf-8")
    return stored


def _safe_int(value, label: str) -> int:
    """Return integer or raise ValueError immediately — no floats allowed."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise ValueError(f"FLOAT DETECTED in {label}: {value!r}. Money must be integer cents only.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Cannot convert {value!r} to int in {label}")


def _versioned_path(base: Path) -> Path:
    """Return base if it doesn't exist, else base_v2, base_v3, …"""
    if not base.exists():
        return base
    stem  = base.stem
    suffix = base.suffix
    parent = base.parent
    version = 2
    while True:
        candidate = parent / f"{stem}_v{version}{suffix}"
        if not candidate.exists():
            return candidate
        version += 1


def _slugify(name: str) -> str:
    """Turn a deal name into a safe filename component."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]


# ── STEP 2  Fetch deal ────────────────────────────────────────────────────────

def fetch_deal(client, deal_id: str) -> dict:
    r = client.table("pds_deals").select("id,name,currency,created_at").eq("id", deal_id).execute()
    if not r.data:
        print(f"ERROR: Deal {deal_id!r} not found in pds_deals.")
        sys.exit(1)
    return r.data[0]


# ── STEP 3 + 4  Fetch snapshot and build transaction list ────────────────────

def fetch_canonical(client, deal_id: str) -> tuple[dict, dict]:
    """
    Returns (canonical_dict, snapshot_meta).

    Uses the latest committed snapshot — already contains fully joined
    transactions, txn_entity_map (roles), and entities.
    No re-ingestion. Read-only.

    Two-step fetch: metadata first (to get snapshot id), then canonical_json
    separately to avoid PostgREST response-size limits on multi-MB blobs.
    """
    # Step A: fetch metadata only (fast, small payload)
    r_meta = (
        client.table("pds_snapshots")
        .select("id,sha256_hash,financial_state_hash,created_at")
        .eq("deal_id", deal_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r_meta.data:
        print(f"ERROR: No snapshot found for deal {deal_id}. Run the export first.")
        sys.exit(1)

    snap_meta = r_meta.data[0]
    snapshot_id = snap_meta["id"]
    snapshot_meta = {
        "id":                   snap_meta.get("id"),
        "sha256_hash":          snap_meta.get("sha256_hash"),
        "financial_state_hash": snap_meta.get("financial_state_hash"),
        "created_at":           snap_meta.get("created_at"),
    }

    # Step B: fetch canonical_json by snapshot id (avoids ordering + limit on heavy column)
    r_cj = (
        client.table("pds_snapshots")
        .select("canonical_json")
        .eq("id", snapshot_id)
        .execute()
    )
    if not r_cj.data:
        print(f"ERROR: canonical_json not found for snapshot {snapshot_id}.")
        sys.exit(1)

    cj = _decompress(r_cj.data[0].get("canonical_json") or "")
    if not cj:
        print("ERROR: canonical_json is empty in the latest snapshot.")
        sys.exit(1)

    canonical = json.loads(cj)
    return canonical, snapshot_meta


# ── Build analytics-ready tagged transaction list ─────────────────────────────

def build_tagged(canonical: dict) -> list[dict]:
    """
    Join transactions ← txn_entity_map → entities.
    Each output dict has: txn_date, description, amount_cents (int), account_id,
                          txn_id (sha256), entity_name, role.
    Raises ValueError immediately on any non-integer amount_cents.
    """
    transactions   = canonical.get("transactions", [])
    txn_entity_map = canonical.get("txn_entity_map", [])
    entities       = canonical.get("entities", [])

    # Build role + entity_id lookup keyed by UUID (txn_entity_map.txn_id = UUID after export)
    role_map: dict[str, str] = {}
    eid_map:  dict[str, str] = {}
    for m in txn_entity_map:
        tid = str(m.get("txn_id") or "")
        if tid:
            role_map[tid] = m.get("role") or "other"
            eid_map[tid]  = str(m.get("entity_id") or "")

    # Build entity display name lookup
    entity_names: dict[str, str] = {
        str(e.get("entity_id") or ""): (e.get("display_name") or "")
        for e in entities
    }

    tagged: list[dict] = []
    for t in transactions:
        uuid_id = str(t.get("id") or "")
        sha_id  = str(t.get("txn_id") or "")

        # Primary key is UUID (post-export map); fall back to SHA256 for in-memory data
        lookup_key = uuid_id if uuid_id in role_map else sha_id
        role       = role_map.get(lookup_key, "other")
        entity_id  = eid_map.get(lookup_key, "")
        entity_name = entity_names.get(entity_id) or str(t.get("normalized_descriptor", ""))[:40]

        raw_amt = t.get("signed_amount_cents", 0)
        amount_cents = _safe_int(raw_amt, f"txn {sha_id or uuid_id}")

        tagged.append({
            "txn_date":    str(t.get("txn_date", "")),
            "description": str(t.get("normalized_descriptor") or t.get("description", "")),
            "amount_cents": amount_cents,
            "account_id":  str(t.get("account_id", "")),
            "txn_id":      sha_id,
            "entity_name": entity_name,
            "role":        role,
        })

    return tagged


# ── STEP 5  Run analytics ─────────────────────────────────────────────────────

def run_analytics(tagged: list[dict]) -> dict:
    from v1.analytics import (
        annual_revenue_summary,
        loan_drawdowns,
        kra_summary,
        top_expenses_with_frequency,
    )

    annual   = annual_revenue_summary(tagged)
    draws    = loan_drawdowns(tagged)
    kra      = kra_summary(tagged)
    expenses = top_expenses_with_frequency(tagged, top_n=10)

    # Print one-line summaries
    total_rev = annual["total_all_years_cents"]
    years     = annual["years_covered"]
    print(f"  Annual revenue: {len(years)} year(s) covered, total KES {total_rev // 100:,}")

    print(f"  Loan drawdowns: {draws['drawdown_count']} drawdown(s), KES {draws['total_drawdown_cents'] // 100:,}")

    kra_total = kra["total_tax_cents"]
    print(f"  KRA: {kra['compliance']} — {kra['months_with_payment']} month(s), KES {kra_total // 100:,}")

    if expenses:
        top = expenses[0]
        print(f"  Top expense: {top['entity_name'][:40]} KES {top['total_cents'] // 100:,} across {top['txn_count']} transaction(s)")
    else:
        print("  Top expense: none detected")

    return {
        "annual_revenue":    annual,
        "loan_drawdowns":    draws,
        "kra_summary":       kra,
        "expense_frequency": expenses,
    }


# ── STEP 6  Export classified CSV ─────────────────────────────────────────────

def export_csv(tagged: list[dict], deal_name: str, out_dir: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug  = _slugify(deal_name)
    base  = out_dir / f"{slug}_{today}_classified.csv"
    path  = _versioned_path(base)

    # Sort: txn_date ascending, then txn_id ascending
    rows = sorted(tagged, key=lambda r: (r["txn_date"], r["txn_id"]))

    columns = ["txn_date", "description", "amount_cents", "account_id", "txn_id", "entity_name", "role"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return path


# ── STEP 7  Generate PDF snapshot ─────────────────────────────────────────────

def export_pdf(
    canonical: dict,
    analytics: dict,
    snapshot_meta: dict,
    deal_name: str,
    out_dir: Path,
) -> Path:
    from v1.core.pdf_generator import generate_pdf

    # Inject analytics results into canonical so pdf_generator can read them
    canonical_with_analytics = {
        **canonical,
        "annual_revenue":    analytics["annual_revenue"],
        "loan_drawdowns":    analytics["loan_drawdowns"],
        "kra_summary":       analytics["kra_summary"],
        "expense_frequency": analytics["expense_frequency"],
    }

    pdf_bytes = generate_pdf(canonical_with_analytics, snapshot_meta=snapshot_meta)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug  = _slugify(deal_name)
    base  = out_dir / f"{slug}_{today}_snapshot.pdf"
    path  = _versioned_path(base)

    with open(path, "wb") as f:
        f.write(pdf_bytes)

    return path


# ── STEP 8  Main ──────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 v1/scripts/regenerate_outputs.py <deal_id>")
        sys.exit(1)

    deal_id = sys.argv[1].strip()

    # Step 1 — env
    _load_env()

    client = _get_supabase()

    # Step 2 — deal metadata
    deal = fetch_deal(client, deal_id)
    deal_name = deal.get("name") or deal_id
    currency  = deal.get("currency", "KES")
    print(f"\nDeal: {deal_name}  |  currency: {currency}  |  id: {deal_id}")

    # Step 3 — fetch canonical snapshot (read-only, no re-ingestion)
    print("Fetching snapshot from Supabase (read-only)…")
    canonical, snapshot_meta = fetch_canonical(client, deal_id)
    raw_txn_count = len(canonical.get("transactions", []))
    print(f"Fetched {raw_txn_count:,} transactions for deal: {deal_name}")

    # Step 4 — build tagged transaction list
    print("Building tagged transaction list…")
    tagged = build_tagged(canonical)

    # Step 5 — run analytics
    print("Running analytics…")
    analytics = run_analytics(tagged)

    # Prepare output directory
    out_dir = Path.home() / "Documents" / "Parity"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 6 — CSV export
    print("Exporting CSV…")
    csv_path = export_csv(tagged, deal_name, out_dir)

    # Step 7 — PDF export
    print("Generating PDF…")
    pdf_path = export_pdf(canonical, analytics, snapshot_meta, deal_name, out_dir)

    # Step 8 — confirmation
    print()
    print(f"CSV saved:  {csv_path}")
    print(f"PDF saved:  {pdf_path}")
    print(f"Done. {len(tagged):,} transactions exported.")


if __name__ == "__main__":
    main()
