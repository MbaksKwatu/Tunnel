import hashlib
import re
from typing import Dict, List, Tuple

from ..parsing.common import normalize_descriptor, canonical_hash


def _clean_display_name(raw_descriptor: str, parsed_descriptor: str) -> str:
    """
    Extract a clean, human-readable entity name from a raw transaction descriptor.
    Rules are applied in order — first match wins.
    Falls back to truncated parsed_descriptor if no rule matches.
    """
    raw = (raw_descriptor or parsed_descriptor or "").strip()
    d = raw.upper()

    # Rule 1: MPESA C2B — extract name after last ~ separator
    # e.g. TDF6WQOFHC~254728056542~01192248207900~MPESAC2B_400200~Mourine Catherine
    # Note: some descriptors are truncated and end at MPESAC2B_4 without the person name
    if "MPESAC2B" in d or "MPESA C2B" in d:
        parts = raw.split("~")
        if len(parts) >= 2:
            name = parts[-1].strip()
            # Valid person name: not empty, not digits only, not a MPESAC2B token
            if (name
                and not name.replace(" ", "").isdigit()
                and "MPESAC2B" not in name.upper()
                and not name.upper().startswith("MPESA")
                and len(name) > 3):
                return name.title()
        return "M-Pesa C2B"

    # Rule 2: POS terminal — extract operator name before ~POS
    # e.g. POSAG014812 ~516210002583~moreen~POS17460_01192248207900
    if "POS17460" in d or "POS13362" in d or "POS28487" in d or "POS41371" in d or "~POS" in d:
        parts = raw.split("~")
        for i, p in enumerate(parts):
            if "POS" in p.upper() and i > 0:
                name = parts[i - 1].strip()
                if name and not name.replace(" ", "").isdigit():
                    return f"POS — {name.title()}"
        return "POS Terminal"

    # Rule 3: Safeways Express and similar — extract after account number pattern
    # e.g. AB8500E1D525 097431/480248-Safeways Express safeways Express AL-AQSA...
    safeways_match = re.search(r'\d{6}/\d{6}-(.+?)(?:\s+safeways|\s+AL-AQSA|$)', raw, re.IGNORECASE)
    if safeways_match:
        return safeways_match.group(1).strip().title()

    # Rule 4b: PesaLink outbound — must check before slash rule fires
    if "BP:PESALINK" in d or "MB BP:PESALINK" in d:
        return "PesaLink Transfer"

    # Rule 4: Slash-separated institutional names
    # e.g. KE1OL250811002TB,1/THE SOMO AFRICA TRUST REGISTERED/Investment...
    # e.g. FT2509359FHJ,1/FOURTH GENERATION CAPITAL LIMITED/JGP MAUCA...
    if "/" in raw:
        parts = raw.split("/")
        if len(parts) >= 2:
            candidate = parts[1].strip()
            # Remove trailing ref codes and registered/investment suffixes
            candidate = re.sub(r'\s+(REGISTERED|INVESTMENT|JGP|via API).*$', '', candidate, flags=re.IGNORECASE)
            candidate = candidate.strip()
            if len(candidate) > 3 and not candidate.replace(" ", "").isdigit():
                return candidate.title()

    # Rule 4b: REVERSAL prefix — must run before bill payment rules
    if raw.upper().startswith("REVERSAL:") or raw.upper().startswith("AIRTELMONEYKE-REVERSAL:"):
        return "Reversal — Bill Payment"

    # Rule 5: PesaLink large transfer
    if "PESALINK" in d and ("SENT TO" in d or "TRANSFER" in d or "FUNDS TRANSFER" in d):
        return "PesaLink Transfer"
    if "BP:PESALINK" in d or "MB BP:PESALINK" in d:
        return "PesaLink Transfer"

    # Rule 6: MPESA B2C bill payment
    if "MPESAB2C" in d or "//BILL//MB BP:" in d:
        # Try to extract paybill number context
        match = re.search(r':([\d]+)//', raw)
        if match:
            return f"M-Pesa Bill Payment ({match.group(1)})"
        return "M-Pesa Bill Payment"

    # Rule 7: Bank maintenance fees — normalise labels
    if "MSME_BRONZE_MAINT" in d or "MONTHLY MAINTENANCE FEE" in d:
        return "Monthly Maintenance Fee"

    # Rule 8: KPLC prepaid
    if "KPLC PREPAID" in d or "KPLCPREPAIDCOMM" in d:
        return "Kenya Power (KPLC)"

    # Rule 9: Interest charges
    if "INT.COLL" in d or "INTEREST RUN" in d:
        return "Interest Charge"

    # Rule 10: ATM/Cash withdrawals and charges
    if "ATM CASH" in d:
        return "ATM Withdrawal"
    if "AGENT WDL" in d:
        return "Agent Withdrawal"
    if "ATM CHARGE" in d or "ATM CHRG" in d:
        return "ATM Charge"
    if "CHEQUE WITHDRAWAL" in d:
        return "Cheque Withdrawal"
    if "CASH DEPOSIT" in d:
        return "Cash Deposit"

    # Rule 10b: KCB-specific patterns
    # InHouse CHQ — internal cheque payment
    if "INHOUSE CHQ" in d or "INHOUSE CHEQUE" in d:
        return "InHouse Cheque"
    # Mobile Money Transfer outbound (KCB format)
    if "MOBILE MONEY TR " in d or "MOBILE MONEY TR MM" in d:
        return "Mobile Money Transfer"
    # Mobile Payment inbound (KCB format)
    if d.startswith("MOBILE PAYMENT"):
        return "Mobile Payment"
    # POS transaction — try to extract merchant name
    if d.startswith("POS TXN"):
        parts = raw.split()
        # Last word is often merchant name if it's alphabetic
        if parts and re.match(r'^[A-Za-z]{3,}$', parts[-1]):
            return f"POS — {parts[-1].title()}"
        return "POS Purchase"
    # Airtime purchase (KCB format)
    if "AIR TIME PURCHA" in d or "AIRTIME PURCHA" in d:
        return "Airtime Purchase"
    # Tax amount due (KCB format)
    if "TAX AMOUNT DUE" in d:
        return "Tax Payment"
    # Agency transaction charge (KCB format)
    if "AGENCY TRANSACTION CHARGE" in d:
        return "Agency Charge"
    # Ltd 999999 pattern — unknown company inflow/outflow
    if "999999" in d:
        # Try to extract company name before 999999
        match = re.search(r'^([A-Za-z][A-Za-z\s]{3,}?)\s+999999', raw)
        if match:
            name = match.group(1).strip().title()
            # Reject generic words that aren't real names
            if name.lower() not in ("ltd", "limited", "co", "company"):
                return name
        return "Company Transfer"

    # Rule 10c: ABSA-specific patterns
    # Phone number patterns — M-Pesa inbound from phone number
    if re.match(r'^[A-Z0-9]{8,12}\s+07\d{8}', raw) or re.match(r'^[A-Z0-9]{8,12}\s+2547\d{8}', raw):
        return "M-Pesa Inbound Transfer"
    # Transaction ref + name pattern (e.g. 00010003202308181102417866XTV5 Rashka)
    ref_name = re.match(r'^[0-9A-Z]{15,}\s+([A-Za-z][A-Za-z\s]{3,30})$', raw.strip())
    if ref_name:
        return ref_name.group(1).strip().title()

    # Rule 11: Excise duty and related fees
    if "EXCISE DUTY" in d or "EXCISE CHARGES" in d or d.startswith("EXCISE "):
        return "Excise Duty"

    # Rule 12: Short clean names (likely person names) — return as-is title-cased
    words = raw.strip().split()
    if len(words) <= 4 and all(re.match(r'^[A-Za-z]+$', w) for w in words):
        return raw.strip().title()

    # Fallback: truncate parsed_descriptor to 40 chars
    fallback = (parsed_descriptor or raw_descriptor or "").strip()
    return fallback[:40].strip() if fallback else raw[:40].strip()


def build_entities(deal_id: str, transactions: List[Dict]) -> Tuple[List[Dict], Dict[str, str], str]:
    """
    Deterministically derive entities from clean display names.
    entity_id = sha256(deal_id + "|" + clean_display_name.lower())
    Transactions with the same clean display name share an entity_id.
    This collapses repeated counterparties (e.g. 46 Safeways Express rows → 1 entity).
    Returns (entities, txn_entity_map, entities_hash)
    txn_entity_map: txn_id -> entity_id
    """
    name_to_entity: Dict[str, str] = {}  # group_key -> entity_id
    norm_to_entity: Dict[str, str] = {}  # normalized_name -> entity_id
    entities: List[Dict] = []
    txn_entity_map: Dict[str, str] = {}

    for tx in transactions:
        display_name = _clean_display_name(
            tx.get("raw_descriptor", ""),
            tx.get("parsed_descriptor", "")
        )
        # Use lower-cased display name as grouping key for deduplication
        group_key = display_name.lower().strip()
        if group_key not in name_to_entity:
            # Derive normalized_name from display_name so it is always unique
            # per entity. Using tx.normalized_descriptor (the raw descriptor) was
            # wrong: two display_name groups could share the same descriptor value
            # after normalization, violating the pds_entities_unique_name constraint.
            normalized_name = normalize_descriptor(display_name)
            if normalized_name in norm_to_entity:
                # Two display_names that differ only in whitespace/casing collapse
                # to the same normalized form — merge into the existing entity.
                eid = norm_to_entity[normalized_name]
            else:
                eid = hashlib.sha256(f"{deal_id}|{group_key}".encode("utf-8")).hexdigest()
                norm_to_entity[normalized_name] = eid
                entities.append(
                    {
                        "entity_id": eid,
                        "deal_id": deal_id,
                        "normalized_name": normalized_name,
                        "display_name": display_name,
                        "strong_identifiers": {},
                    }
                )
            name_to_entity[group_key] = eid
        txn_entity_map[tx["txn_id"]] = name_to_entity[group_key]

    entities_sorted = sorted(entities, key=lambda e: e["entity_id"])
    entities_hash = canonical_hash(entities_sorted)
    return entities_sorted, txn_entity_map, entities_hash
