from datetime import datetime
from typing import Dict, List, Tuple


def _date_diff_days(d1: str, d2: str) -> int:
    dt1 = datetime.strptime(d1, "%Y-%m-%d").date()
    dt2 = datetime.strptime(d2, "%Y-%m-%d").date()
    return abs((dt1 - dt2).days)


def match_transfers(transactions: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Deterministic transfer pairing.
    Rules (all must hold):
      - same abs_amount_cents
      - opposite sign
      - within 2 calendar days
      - different account_id
      - exactly one candidate match per txn
    If multiple candidates exist for a txn, it remains non-transfer.
    """
    by_abs = {}
    for tx in transactions:
        amt = abs(int(tx["signed_amount_cents"]))
        by_abs.setdefault(amt, []).append(tx)

    transfer_links: List[Dict] = []
    for amt, group in by_abs.items():
        # Separate positive/negative
        positives = [g for g in group if g["signed_amount_cents"] > 0]
        negatives = [g for g in group if g["signed_amount_cents"] < 0]
        for pos in positives:
            candidates = [
                neg
                for neg in negatives
                if neg["account_id"] != pos["account_id"]
                and _date_diff_days(neg["txn_date"], pos["txn_date"]) <= 2
            ]
            if len(candidates) != 1:
                continue
            neg = candidates[0]
            # Ensure symmetry: pos is unique candidate for neg too
            rev_candidates = [
                p
                for p in positives
                if p["account_id"] != neg["account_id"]
                and _date_diff_days(p["txn_date"], neg["txn_date"]) <= 2
            ]
            if len(rev_candidates) != 1 or rev_candidates[0] is not pos:
                continue
            # Pair them
            pos["is_transfer"] = True
            neg["is_transfer"] = True
            link = {
                "id": None,  # to be set by caller if persisted
                "deal_id": pos.get("deal_id"),
                "txn_out_id": neg.get("id"),
                "txn_in_id": pos.get("id"),
                "abs_amount_cents": amt,
                "match_rule_version": "v1_transfer_rule",
            }
            transfer_links.append(link)

    return transactions, transfer_links
