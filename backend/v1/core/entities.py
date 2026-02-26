import hashlib
from typing import Dict, List, Tuple

from ..parsing.common import normalize_descriptor, canonical_hash


def build_entities(deal_id: str, transactions: List[Dict]) -> Tuple[List[Dict], Dict[str, str], str]:
    """
    Deterministically derive entities from normalized descriptors.
    entity_id = sha256(deal_id + "|" + normalized_name)
    Returns (entities, txn_entity_map, entities_hash)
    txn_entity_map: txn_id -> entity_id
    """
    name_to_entity: Dict[str, str] = {}
    entities: List[Dict] = []
    txn_entity_map: Dict[str, str] = {}

    for tx in transactions:
        normalized_name = normalize_descriptor(tx.get("normalized_descriptor", ""))
        if normalized_name not in name_to_entity:
            eid = hashlib.sha256(f"{deal_id}|{normalized_name}".encode("utf-8")).hexdigest()
            name_to_entity[normalized_name] = eid
            entities.append(
                {
                    "entity_id": eid,
                    "deal_id": deal_id,
                    "normalized_name": normalized_name,
                    "display_name": tx.get("parsed_descriptor") or tx.get("raw_descriptor") or normalized_name,
                    "strong_identifiers": {},
                }
            )
        txn_entity_map[tx["txn_id"]] = name_to_entity[normalized_name]

    entities_sorted = sorted(entities, key=lambda e: e["entity_id"])
    entities_hash = canonical_hash(entities_sorted)
    return entities_sorted, txn_entity_map, entities_hash
