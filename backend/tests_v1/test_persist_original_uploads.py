"""
Original uploaded files are kept in the `uploads` Storage bucket.

Bank statements (single and batch) and audited financials used to be parsed
in memory and discarded, leaving nothing to download later. Each upload path
now writes the original bytes to a deal-scoped path and records it in
original_storage_path, while pds_documents.storage_url keeps its
inline://<filename> form (reconciliation dedups and labels banks by it).

Runs through the real FastAPI routes with in-memory repos; the `uploads`
repo is MemoryUploadsStorageRepo.
"""
import io
import os
import sys
import unittest
from unittest.mock import patch

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.v1.api import router as v1_router
from backend.v1.db.memory_repositories import build_memory_repos


VALID_CSV = b"""date,amount,description,account_id
2024-01-01,1000,Revenue,ACC-1
2024-01-02,-400,Supplier,ACC-1
"""


def _pdf_bytes(pages: int = 1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _fake_extraction(file_bytes, file_name):
    return {
        "company_name": "Maharaji Industries",
        "financial_year": 2025,
        "financial_year_start": "2025-01-01",
        "financial_year_end": "2025-12-31",
        "turnover_cents": 5_000_00,
        "extraction_method": "fake_test",
    }


class _FakeAFRepo:
    _store: dict = {}

    def get_by_deal_year(self, deal_id, financial_year):
        return self._store.get((deal_id, int(financial_year)))

    def upsert(self, data):
        key = (data["deal_id"], int(data["financial_year"]))
        merged = {**self._store.get(key, {}), **data}
        merged.setdefault("id", "af-row-1")
        self._store[key] = merged
        return merged


class _FailingStorage:
    def upload(self, path, content, content_type):
        raise RuntimeError("storage unavailable")


class _UploadTestBase(unittest.TestCase):
    def setUp(self):
        self.repos = build_memory_repos()
        self.storage = self.repos["uploads"]
        app = FastAPI()
        app.state.repos_factory = lambda: self.repos
        app.include_router(v1_router)
        self.client = TestClient(app)
        resp = self.client.post("/v1/deals", data={"currency": "USD"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.deal_id = resp.json()["deal"]["id"]

    def _doc(self, document_id):
        return next(d for d in self.repos["documents"]._store if d["id"] == document_id)


class TestBankStatementUpload(_UploadTestBase):
    def test_single_upload_stores_original_bytes(self):
        resp = self.client.post(
            f"/v1/deals/{self.deal_id}/documents",
            files={"file": ("Equity Statement (Jan).csv", io.BytesIO(VALID_CSV), "text/csv")},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        doc_id = resp.json()["ingestion"]["document_id"]
        doc = self._doc(doc_id)

        expected = f"{self.deal_id}/{doc_id}/Equity_Statement__Jan_.csv"
        self.assertEqual(doc["original_storage_path"], expected)
        self.assertEqual(self.storage.download(expected), VALID_CSV)
        self.assertEqual(self.storage.objects[expected]["content_type"], "text/csv")
        # Unchanged: reconciliation dedups and labels by the inline filename.
        self.assertEqual(doc["storage_url"], "inline://Equity Statement (Jan).csv")
        # Ingestion still ran on the same bytes.
        self.assertEqual(doc["status"], "completed")

    def test_rejected_extension_stores_nothing(self):
        resp = self.client.post(
            f"/v1/deals/{self.deal_id}/documents",
            files={"file": ("notes.txt", io.BytesIO(b"hi"), "text/plain")},
        )
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(self.storage.objects, {})

    def test_storage_failure_does_not_block_ingestion(self):
        self.repos["uploads"] = _FailingStorage()
        resp = self.client.post(
            f"/v1/deals/{self.deal_id}/documents",
            files={"file": ("jan.csv", io.BytesIO(VALID_CSV), "text/csv")},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        doc = self._doc(resp.json()["ingestion"]["document_id"])
        self.assertIsNone(doc["original_storage_path"])
        self.assertEqual(doc["status"], "completed")

    def test_batch_upload_stores_each_original_and_merged(self):
        part1, part2 = _pdf_bytes(1), _pdf_bytes(2)
        with patch("backend.v1.api.IngestionService") as ingestion_cls:
            resp = self.client.post(
                f"/v1/deals/{self.deal_id}/documents/batch",
                files=[
                    ("files", ("KCB Jan.pdf", io.BytesIO(part1), "application/pdf")),
                    ("files", ("KCB Feb.pdf", io.BytesIO(part2), "application/pdf")),
                ],
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        doc_id = resp.json()["document_id"]
        doc = self._doc(doc_id)

        merged_path = f"{self.deal_id}/{doc_id}/batch_1_merged.pdf"
        self.assertEqual(doc["original_storage_path"], merged_path)
        self.assertEqual(doc["storage_url"], "inline://batch_1_merged.pdf")
        prefix = f"{self.deal_id}/{doc_id}/originals"
        self.assertEqual(self.storage.download(f"{prefix}/01_KCB_Jan.pdf"), part1)
        self.assertEqual(self.storage.download(f"{prefix}/02_KCB_Feb.pdf"), part2)
        # The merged object is exactly what was handed to ingestion.
        ingest_kwargs = ingestion_cls.return_value.process_document_background.call_args.kwargs
        self.assertEqual(self.storage.download(merged_path), ingest_kwargs["file_bytes"])


class TestAuditedFinancialsUpload(_UploadTestBase):
    def setUp(self):
        super().setUp()
        _FakeAFRepo._store = {}
        patches = [
            patch(
                "backend.v1.parsing.audited_financials_claude_extractor.extract_audited_financials_claude",
                side_effect=_fake_extraction,
            ),
            patch("backend.v1.db.supabase_repositories.AuditedFinancialsRepo", _FakeAFRepo),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _upload(self, content=b"%PDF-1.4 audited", name="FY2025 Audited Accounts.pdf"):
        return self.client.post(
            f"/v1/deals/{self.deal_id}/upload-financials",
            files={"file": (name, io.BytesIO(content), "application/pdf")},
            data={"declaration_type": "audited"},
        )

    def _row(self):
        return _FakeAFRepo._store[(self.deal_id, 2025)]

    def test_upload_stores_original_and_links_row(self):
        resp = self._upload()
        self.assertEqual(resp.status_code, 200, resp.text)
        path = self._row()["original_storage_path"]
        self.assertTrue(path.startswith(f"{self.deal_id}/audited-financials/"), path)
        self.assertTrue(path.endswith("/FY2025_Audited_Accounts.pdf"), path)
        self.assertEqual(self.storage.download(path), b"%PDF-1.4 audited")
        self.assertEqual(self.storage.objects[path]["content_type"], "application/pdf")

    def test_reupload_points_at_new_file_and_keeps_old(self):
        self.assertEqual(self._upload(b"%PDF v1").status_code, 200)
        first = self._row()["original_storage_path"]
        self.assertEqual(self._upload(b"%PDF v2").status_code, 200)
        second = self._row()["original_storage_path"]
        self.assertNotEqual(first, second)
        self.assertEqual(self.storage.download(first), b"%PDF v1")
        self.assertEqual(self.storage.download(second), b"%PDF v2")

    def test_failed_extraction_stores_nothing(self):
        from backend.v1.parsing.audited_financials_claude_extractor import ClaudeExtractionError

        with patch(
            "backend.v1.parsing.audited_financials_claude_extractor.extract_audited_financials_claude",
            side_effect=ClaudeExtractionError("unreadable"),
        ):
            resp = self._upload()
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(self.storage.objects, {})

    def test_confirmed_record_conflict_stores_nothing(self):
        _FakeAFRepo._store[(self.deal_id, 2025)] = {"id": "x", "confirmed_at": "2026-01-01T00:00:00Z"}
        resp = self._upload()
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self.storage.objects, {})

    def test_storage_failure_still_saves_figures(self):
        self.repos["uploads"] = _FailingStorage()
        resp = self._upload()
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIsNone(self._row()["original_storage_path"])
        self.assertEqual(self._row()["turnover_cents"], 5_000_00)


if __name__ == "__main__":
    unittest.main()
