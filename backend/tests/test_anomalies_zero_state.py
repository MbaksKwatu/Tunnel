import os
import tempfile
import unittest
import uuid
import shutil

import pytest
from fastapi.testclient import TestClient

import main as backend_main


pytestmark = pytest.mark.xfail(
    reason="SQLiteStorage demo backend has been removed; test needs SupabaseStorage rewrite.",
    strict=False,
)


class TestAnomaliesZeroState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="parity_test_anom_")
        self.db_path = os.path.join(self.tmpdir, "test.db")

        backend_main.storage = SQLiteStorage(db_path=self.db_path)
        self.client = TestClient(backend_main.app)

        self.document_id = str(uuid.uuid4())
        backend_main.storage.store_document(
            {
                'id': self.document_id,
                'user_id': str(uuid.uuid4()),
                'file_name': 'clean.csv',
                'file_type': 'csv',
                'file_url': None,
                'status': 'completed',
            }
        )

        # Store rows but do NOT store anomalies
        rows = [
            {'transaction_date': '2024-01-01', 'amount': 100.0, 'description': 'Sale'},
            {'transaction_date': '2024-01-02', 'amount': -25.0, 'description': 'Supplies'},
        ]
        backend_main.storage.store_rows(self.document_id, rows)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_document_anomalies_endpoint_returns_empty_list(self):
        res = self.client.get(f"/document/{self.document_id}/anomalies")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload.get('document_id'), self.document_id)
        self.assertEqual(payload.get('count'), 0)
        self.assertEqual(payload.get('anomalies'), [])

    def test_api_anomalies_alias_endpoint_returns_empty_list(self):
        res = self.client.get("/api/anomalies", params={"doc_id": self.document_id})
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload.get('count'), 0)
        self.assertEqual(payload.get('anomalies'), [])
        self.assertNotIn('document_id', payload)

    def test_anomalies_with_null_metadata(self):
        # Insert an anomaly without metadata (NULL in DB)
        backend_main.storage.store_anomalies(
            self.document_id,
            [
                {
                    'row_index': 0,
                    'anomaly_type': 'unsupervised_outlier',
                    'severity': None,
                    'description': None,
                    'score': None,
                    'suggested_action': None,
                    'metadata': None,
                    'raw_json': {'transaction_date': '2024-01-01', 'amount': 100.0, 'description': 'Sale'},
                    'evidence': None,
                }
            ],
        )

        res = self.client.get("/api/anomalies", params={"doc_id": self.document_id})
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        anomalies = payload.get('anomalies')
        self.assertIsInstance(anomalies, list)
        self.assertEqual(payload.get('count'), len(anomalies))
        self.assertGreaterEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0].get('metadata'), {})


if __name__ == '__main__':
    unittest.main()
