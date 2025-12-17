import os
import tempfile
import unittest
import uuid
import shutil

from fastapi.testclient import TestClient

import main as backend_main
from local_storage import SQLiteStorage


class TestInsightsSnapshotAPI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="parity_test_")
        self.db_path = os.path.join(self.tmpdir, "test.db")

        backend_main.storage = SQLiteStorage(db_path=self.db_path)
        self.client = TestClient(backend_main.app)

        self.document_id = str(uuid.uuid4())
        backend_main.storage.store_document(
            {
                'id': self.document_id,
                'user_id': str(uuid.uuid4()),
                'file_name': 'test.csv',
                'file_type': 'csv',
                'file_url': None,
                'status': 'completed',
            }
        )

        self.rows = [
            {
                'transaction_date': '2024-01-01',
                'amount': 100.0,
                'description': 'Sale',
            },
            {
                'transaction_date': '2024-01-02',
                'amount': -25.0,
                'description': 'Supplies',
            },
        ]
        backend_main.storage.store_rows(self.document_id, self.rows)

        self.anomalies = [
            {
                'row_index': 1,
                'anomaly_type': 'expense_integrity',
                'severity': 'medium',
                'description': 'Test anomaly',
                'raw_json': self.rows[1],
                'evidence': {'field': 'amount', 'value': -25.0},
            }
        ]
        backend_main.storage.store_anomalies(self.document_id, self.anomalies)

    def tearDown(self):
        try:
            backend_main.storage.delete_document(self.document_id)
        except Exception:
            pass
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_rows_endpoint_returns_persisted_rows(self):
        res = self.client.get(f"/document/{self.document_id}/rows", params={'limit': 100, 'offset': 0})
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload.get('document_id'), self.document_id)
        self.assertEqual(payload.get('count'), 2)
        rows = payload.get('rows') or []
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['raw_json']['transaction_date'], '2024-01-01')
        self.assertEqual(rows[0]['raw_json']['amount'], 100.0)
        self.assertEqual(rows[1]['raw_json']['transaction_date'], '2024-01-02')
        self.assertEqual(rows[1]['raw_json']['amount'], -25.0)

    def test_anomalies_endpoint_returns_persisted_anomalies(self):
        res = self.client.get(f"/document/{self.document_id}/anomalies")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload.get('document_id'), self.document_id)
        self.assertEqual(payload.get('count'), 1)
        anomalies = payload.get('anomalies') or []
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0].get('anomaly_type'), 'expense_integrity')
        self.assertEqual(anomalies[0].get('severity'), 'medium')


if __name__ == '__main__':
    unittest.main()
