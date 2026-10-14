"""
Equity channel narratives (APP / USSD / WEB / EVA, EazzyBiz, PAYED) and KCB
M-Pesa paybill narratives carry per-row codes without the CLMS S-ref. Each
layout is matched exactly so repeat counterparties collapse, while narratives
that don't match keep exactly the old names.
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


class TestEquityChannelNames(unittest.TestCase):
    def test_app_ussd_web_eva_collapse(self):
        a = "APP/KIPKIRUI GIDEON A91893E8BEC7 54351035 KOSKEI/ 2"
        b = "APP/KIPKIRUI GIDEON A76C6C99C354 54316803 KOSKEI/ A"
        self.assertEqual(_name(a), "Kipkirui Gideon Koskei")
        self.assertEqual(_name(a), _name(b))
        self.assertEqual(_name("USSD/JULIAN ADERO U71C660D48A3 54313880 ODOYO/ B"), "Julian Adero Odoyo")
        self.assertEqual(_name("EVA/CHARLES ANDIKA CFEEF362149D 54116398 OMMATERA/ 8"), "Charles Andika Ommatera")
        self.assertEqual(_name("APP/NYANCHAMA ANNE X43CAFB09A93 54105152 ONG'ERA/ E"), "Nyanchama Anne Ong'Era")

    def test_channel_row_number_after_slash(self):
        a = "WEB/SIGOMERE WA467286D934 HARDWARE/SIGOMERE 54499892 E HARDWARE"
        b = "APP/SIGOMERE A25898BA111D HARDWARE/SIGOMERE 54424207 0 HARDWARE"
        self.assertEqual(_name(a), "Sigomere Hardware")
        self.assertEqual(_name(a), _name(b))

    def test_channel_wrapped_code_tail_dropped(self):
        a = "APP/FILMAS BUILDERS AB971C01F032 CHOICE HARDWARE 5417412 E LIMITED/MARBLE"
        b = "USSD/FILMAS BUILDERS UEA475CC003 CHOICE HARDWARE 54965854 84 LIMITED/"
        self.assertEqual(_name(a), "Filmas Builders Choice Hardware Limited")
        self.assertEqual(_name(a), _name(b))

    def test_eazzybiz_transfer(self):
        a = "EAZZYBIZ TRSF HODGE C75602052508 54677792 VENTURES L 3535"
        b = "EAZZYBIZ TRSF HODGE C71111052508 54600001 VENTURES L 0001"
        self.assertEqual(_name(a), "Hodge Ventures L")
        self.assertEqual(_name(a), _name(b))
        self.assertEqual(
            _name("EAZZYBIZ TRSF BIASHARA TB2512030048 MASTER SAW MILLS LIMI 54292896 9428 TB25"),
            "Biashara Master Saw Mills Limi",
        )
        self.assertEqual(_name("EAZZYBIZ TRSF QIN C75601082507 54125358 XIAOMEI C7 4733"), "Qin Xiaomei")
        self.assertEqual(_name("0790583864 EAZZYBIZ TRSF C72208112510 54262629 SAFAR 1050"), "Safar")
        self.assertEqual(_name("EAZZYBIZ TRSF TO C79530082508 54166978 0570286095843 2640"), "EazzyBiz Transfer")

    def test_account_transfer_charges(self):
        a = "CHARGES ACCOUNT TO C72601042508 54975977 ACCOUNT TH 3023"
        b = "CHARGES ACCOUNT TO TB2512010037 54556872 ACCOUNT THIRD PARTY 9350"
        self.assertEqual(_name(a), "Account Transfer Charges")
        self.assertEqual(_name(a), _name(b))

    def test_payed_by(self):
        a = "PAYED 919519000628 BY:CHRIS/919519000628/22- 54772219 09-2025 17:53:30"
        b = "PAYED 768005668741 BY:CHRIS/768005668741/29- 54377429 01-2025 16:42:08"
        self.assertEqual(_name(a), "Chris")
        self.assertEqual(_name(a), _name(b))
        self.assertEqual(
            _name("PAYED BY:FILMAS 432343680759 HW/432343680759/16-10- 5488770 2025 09:28:1"),
            "Filmas Hw",
        )

    def test_transfer_charge(self):
        self.assertEqual(_name("Transfer Charge 54214109"), "Transfer Charge")
        self.assertEqual(_name("Transfer Charge 5495494"), "Transfer Charge")


class TestStatutoryMonths(unittest.TestCase):
    def test_statutory_month_suffix_dropped(self):
        for head, expected in (
            ("NSSF", "Paybill Nssf Contribution"),
            ("SHIF", "Paybill Shif Contribution"),
            ("HOUSING LEVY", "Paybill Housing Levy Contribution"),
        ):
            with self.subTest(head=head):
                a = f"PAYBILL 208632 0NX9KQC429 {head} S3226622 CONTRIBUTION FEB 2025"
                b = f"PAYBILL 227364 YL3ZB72LJE {head} S2485834 CONTRIBUTION DEC 2024"
                self.assertEqual(_name(a), expected)
                self.assertEqual(_name(a), _name(b))

    def test_salary_month_rule_unchanged(self):
        d = "EFT OUTWARD SALARIES H3YB0OUMTV SALARY S5797215 PAYMENT SEP 2025 MOSES GITAU"
        self.assertEqual(_name(d), "Moses Gitau")


class TestKcbMobi(unittest.TestCase):
    def test_sender_keyed_by_phone(self):
        a = "Mobi 522522 MPESA TEU2SZ7YQM 254721577540 SERA /"
        b = "Mobi 522522 MPESA TGL3XV7EAD 254721577540 Sera /"
        self.assertEqual(_name(a), "Sera (254721577540)")
        self.assertEqual(_name(a), _name(b))

    def test_same_truncated_name_different_phone_stays_apart(self):
        a = "Mobi 522522 MPESA TIK6SSRR7O 254714333394 VICT /"
        b = "Mobi 522522 MPESA TC46CQN7ZS 254728243847 VICT /"
        self.assertNotEqual(_name(a), _name(b))

    def test_without_phone(self):
        a = "Mobi 522522 MPESA TFL9RCBDFL KOPOKOPO MERCHAN /"
        b = "Mobi 522522 MPESA TG893UYWWN KOPOKOPO MERCHAN /"
        self.assertEqual(_name(a), "Kopokopo Merchan")
        self.assertEqual(_name(a), _name(b))
        self.assertEqual(_name("Mobi 522522 MPESA TI923LCUGK 254719550972 /"), "M-Pesa 254719550972")


class TestNonMatchingUnchanged(unittest.TestCase):
    """Narratives outside the exact layouts must produce exactly the old names."""

    CASES = {
        # KCB rows other than Mobi 522522
        "Transfer Charge P052149574N AC- 11089762": "Transfer Charge P052149574N AC- 11089762",
        "Transfer Charge AC-1201978769": "Transfer Charge AC-1201978769",
        "Transfer filla filla 999999": "Transfer Filla Filla",
        "BillPay 20055678933 NSSF 825001454202 NSSF - COLLECTION ACCOUNT": "BillPay 20055678933 NSSF 825001454202 NS",
        # Channel prefix without the channel ref
        "APP/SOME SUPPLIER LTD/INVOICE": "Some Supplier Ltd",
        # EazzyBiz without a C7 / TB ref
        "EAZZYBIZ TRSF HODGE VENTURES": "Eazzybiz Trsf Hodge Ventures",
        # Contribution month outside CLMS rows
        "NSSF CONTRIBUTION FEB": "Nssf Contribution Feb",
        "Transfer Charge": "Transfer Charge",
        "KENYA REVENUE AUTHORITY PAYE": "Kra",
    }

    def test_names(self):
        for desc, expected in self.CASES.items():
            with self.subTest(desc=desc):
                self.assertEqual(_name(desc), expected)


class TestChannelEntities(unittest.TestCase):
    DESCS = [
        "APP/KIPKIRUI GIDEON A91893E8BEC7 54351035 KOSKEI/ 2",
        "USSD/KIPKIRUI GIDEON U6F5F25300C7 54505083 KOSKEI/ 1",
        "CHARGES ACCOUNT TO C72601042508 54975977 ACCOUNT TH 3023",
        "CHARGES ACCOUNT TO C76727062508 5485013 ACCOUNT TH 2859",
        "Mobi 522522 MPESA TEU2SZ7YQM 254721577540 SERA /",
        "Mobi 522522 MPESA TGL3XV7EAD 254721577540 SERA /",
    ]

    def test_repeat_counterparties_share_one_entity(self):
        entities, txn_map, _ = build_entities("deal-1", _txs(self.DESCS))
        self.assertEqual(
            sorted(e["display_name"] for e in entities),
            ["Account Transfer Charges", "Kipkirui Gideon Koskei", "Sera (254721577540)"],
        )
        self.assertEqual(txn_map["t0"], txn_map["t1"])
        self.assertEqual(txn_map["t2"], txn_map["t3"])
        self.assertEqual(txn_map["t4"], txn_map["t5"])

    def test_transaction_descriptors_and_hash_untouched(self):
        txs = _txs(self.DESCS)
        before = copy.deepcopy(txs)
        hash_before = canonical_hash(before)
        build_entities("deal-1", txs)
        self.assertEqual(txs, before)
        self.assertEqual(canonical_hash(txs), hash_before)

    def test_deterministic_across_row_order(self):
        e1, _, h1 = build_entities("deal-1", _txs(self.DESCS))
        e2, _, h2 = build_entities("deal-1", _txs(list(reversed(self.DESCS))))
        self.assertEqual(h1, h2)
        self.assertEqual(e1, e2)


if __name__ == "__main__":
    unittest.main()
