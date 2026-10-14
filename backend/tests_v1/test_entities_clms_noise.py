"""
Equity CLMS narratives carry per-transaction tokens (customer ref S1234567,
10-char transaction ref, phone numbers, account / invoice numbers). Entity
extraction must strip them so repeat counterparties collapse into one entity,
without touching the transaction descriptors that feed canonical_hash.
"""
import copy
import unittest

from backend.v1.core.entities import _clean_display_name, build_entities
from backend.v1.parsing.common import canonical_hash, normalize_descriptor


def _name(desc: str) -> str:
    return _clean_display_name(desc, desc)


def _txs(descs):
    return [
        {
            "txn_id": f"t{i}",
            "raw_descriptor": d,
            "parsed_descriptor": d,
            "normalized_descriptor": normalize_descriptor(d),
        }
        for i, d in enumerate(descs)
    ]


class TestClmsDisplayNames(unittest.TestCase):
    def test_mpesa_masked_phone_collapses_to_sender(self):
        a = "MPS 2547****1616 TIF9Z4OE57 CHARLES S5712345 KOECH ATIENO"
        b = "MPS 2547****9031 TLPVK73DQS CHARLES S6729496 KOECH ATIENO"
        self.assertEqual(_name(a), "Charles Koech Atieno")
        self.assertEqual(_name(a), _name(b))

    def test_mpesa_full_phone_and_truncated_account_fragment(self):
        # Buildex layout: phone + paybill account + ref, truncated account tail
        a = "MPS 254722237482 0570283582241 TC46DKWNE4 RICHARD S5988141 OGWENO MUMA 05"
        b = "MPS 254722237482 0570283582241 TB46DKWNX1 RICHARD S5988999 OGWENO MUMA 0570"
        self.assertEqual(_name(a), "Richard Ogweno Muma")
        self.assertEqual(_name(a), _name(b))

    def test_mpesa_xlsx_export_without_s_ref(self):
        self.assertEqual(_name("MPS 254743391150 TC12VYJ3KK DENNIS KARONJI"), "Dennis Karonji")

    def test_pesalink_outward_supplier(self):
        a = "PESALINK OUTWARD JC5X4YKY1E TO MAVUNO S4198968 FERTILIZER DISTRIBUTORS LTD INV 1234567"
        b = "PESALINK OUTWARD NJSSXJEOJC TO MAVUNO FERTILIZER S2214500 DISTRIBUTORS LTD INV 7654321"
        self.assertEqual(_name(a), "Mavuno Fertilizer Distributors Ltd")
        self.assertEqual(_name(a), _name(b))

    def test_rtgs_and_pesalink_same_supplier_collapse(self):
        a = "RTGS OUTWARD JC5X4YKY1E TO RIFTLINE S4198968 MOTORS LTD"
        b = "PESALINK OUTWARD ZX9Y8W7V6U TO RIFTLINE MOTORS S1111111 LTD"
        self.assertEqual(_name(a), "Riftline Motors Ltd")
        self.assertEqual(_name(a), _name(b))

    def test_pesalink_inward_customer(self):
        d = "TPG PESALINK INWARD 6951008970 OHA7TAX8I6 FROM NJORO S5312955 AGROVET CENTRE INV 8175"
        self.assertEqual(_name(d), "Njoro Agrovet Centre")

    def test_eazzy_funds_transfer(self):
        d = "EAZZY-FUNDS TRNSF FRM 100641997721 S50034875 ERIC KANYINGI LUSENO"
        self.assertEqual(_name(d), "Eric Kanyingi Luseno")

    def test_cheque_deposit_drawer(self):
        d = "CHQ DEP 616440 UVL5UB2C5E CHEQUE S2471425 DEPOSIT KURESOI FARMERS SACCO"
        self.assertEqual(_name(d), "Kuresoi Farmers Sacco")

    def test_salary_payment_collapses_across_months(self):
        a = "EFT OUTWARD SALARIES H3YB0OUMTV SALARY S5797215 PAYMENT SEP 2025 MOSES GITAU"
        b = "EFT OUTWARD SALARIES TYUB0ZXK8Q SALARY S4072533 PAYMENT APR 2025 MOSES GITAU"
        self.assertEqual(_name(a), "Moses Gitau")
        self.assertEqual(_name(a), _name(b))

    def test_bank_fees(self):
        self.assertEqual(
            _name("CHG XPBXSWG7LM PESALINK FEE S3419288 OUTWARD TRANSFER"),
            _name("CHG WVOC45S4ON PESALINK FEE S2614407 OUTWARD TRANSFER"),
        )
        self.assertEqual(_name("CHG JEJ635CL1L EXCISE DUTY S2587069 ON TRANSFER CHARGE"), "Excise Duty")

    def test_shared_rules_run_on_cleaned_text(self):
        d = "PAYBILL 888880 K2LM9QW1ZX KPLC PREPAID S3300112 TOKENS METER 14212345678"
        self.assertEqual(_name(d), "Kenya Power (KPLC)")
        self.assertEqual(_name("DAVECOM GYPSUM 000004472674 S54931934 CENTRE"), "Davecom Gypsum Centre")


class TestNonClmsUnchanged(unittest.TestCase):
    """Narratives without CLMS markers must produce exactly the old names."""

    CASES = {
        "TDF6WQOFHC~254728056542~01192248207900~MPESAC2B_400200~Mourine Catherine": "Mourine Catherine",
        "Transfer Charge P052149574N AC- 11089762": "Transfer Charge P052149574N AC- 11089762",
        "Transfer filla filla 999999": "Transfer Filla Filla",
        "KENYA REVENUE AUTHORITY PAYE": "Kra",
        "EXCISE DUTY": "Excise Duty",
    }

    def test_names(self):
        for desc, expected in self.CASES.items():
            with self.subTest(desc=desc):
                self.assertEqual(_name(desc), expected)


class TestClmsEntities(unittest.TestCase):
    def test_repeat_counterparties_share_one_entity(self):
        txs = _txs([
            "PESALINK OUTWARD JC5X4YKY1E TO MAVUNO S4198968 FERTILIZER DISTRIBUTORS LTD INV 1234567",
            "PESALINK OUTWARD AB1CD2EF3G TO MAVUNO S1000001 FERTILIZER DISTRIBUTORS LTD INV 7654321",
            "RTGS OUTWARD QW9ER8TY7U TO MAVUNO FERTILIZER S2000002 DISTRIBUTORS LTD INV 1111111",
            "MPS 2547****1616 TIF9Z4OE57 CHARLES S5712345 KOECH ATIENO",
            "MPS 2547****2222 TLPVK73DQS CHARLES S6729496 KOECH ATIENO",
        ])
        entities, txn_map, _ = build_entities("deal-1", txs)
        self.assertEqual(
            sorted(e["display_name"] for e in entities),
            ["Charles Koech Atieno", "Mavuno Fertilizer Distributors Ltd"],
        )
        self.assertEqual(len({txn_map["t0"], txn_map["t1"], txn_map["t2"]}), 1)
        self.assertEqual(txn_map["t3"], txn_map["t4"])

    def test_transaction_descriptors_and_hash_untouched(self):
        txs = _txs([
            "MPS 2547****1616 TIF9Z4OE57 CHARLES S5712345 KOECH ATIENO",
            "RTGS OUTWARD JC5X4YKY1E TO RIFTLINE S4198968 MOTORS LTD",
        ])
        before = copy.deepcopy(txs)
        hash_before = canonical_hash(before)
        build_entities("deal-1", txs)
        self.assertEqual(txs, before)
        self.assertEqual(canonical_hash(txs), hash_before)

    def test_deterministic_across_row_order(self):
        descs = [
            "MPS 2547****1616 TIF9Z4OE57 CHARLES S5712345 KOECH ATIENO",
            "RTGS OUTWARD JC5X4YKY1E TO RIFTLINE S4198968 MOTORS LTD",
            "PESALINK OUTWARD ZX9Y8W7V6U TO RIFTLINE MOTORS S1111111 LTD",
        ]
        e1, _, h1 = build_entities("deal-1", _txs(descs))
        e2, _, h2 = build_entities("deal-1", _txs(list(reversed(descs))))
        self.assertEqual(h1, h2)
        self.assertEqual(e1, e2)


if __name__ == "__main__":
    unittest.main()
