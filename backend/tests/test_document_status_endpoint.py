import os
import tempfile
import unittest
import uuid
import shutil

from fastapi.testclient import TestClient

import main as backend_main
from local_storage import SQLiteStorage


class TestDocumentStatusEndpoint(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="parity_test_status_")
        self.db_path = os.path.join(self.tmpdir, "test.db")

        backend_main.storage = SQLiteStorage(db_path=self.db_path)
        self.client = TestClient(backend_main.app)

        self.user_id = str(uuid.uuid4())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_partial_status_payload(self):
        doc_id = str(uuid.uuid4())
        backend_main.storage.store_document(
            {
                'id': doc_id,
                'user_id': self.user_id,
                'file_name': 'partial.pdf',
                'file_type': 'pdf',
                'file_url': None,
                'status': 'partial',
                'rows_count': 10,
                'rows_parsed': 10,
                'rows_expected': 25,
                'error_code': 'PARSE_TIMEOUT',
                'error_message': 'We processed 10 rows before timing out.',
                'next_action': 'retry_upload',
            }
        )

        res = self.client.get(f"/documents/{doc_id}/status")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload.get('status'), 'partial')
        self.assertEqual(payload.get('rows_parsed'), 10)
        self.assertEqual(payload.get('rows_expected'), 25)
        self.assertEqual(payload.get('error_code'), 'PARSE_TIMEOUT')
        self.assertEqual(payload.get('next_action'), 'retry_upload')

    def test_password_required_status_payload(self):
        doc_id = str(uuid.uuid4())
        backend_main.storage.store_document(
            {
                'id': doc_id,
                'user_id': self.user_id,
                'file_name': 'locked.pdf',
                'file_type': 'pdf',
                'file_url': None,
                'status': 'partial',
                'rows_count': 0,
                'rows_parsed': 0,
                'rows_expected': None,
                'error_code': 'PASSWORD_REQUIRED',
                'error_message': 'PASSWORD_REQUIRED',
                'next_action': 'provide_password',
            }
        )

        res = self.client.get(f"/documents/{doc_id}/status")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload.get('status'), 'partial')
        self.assertEqual(payload.get('error_code'), 'PASSWORD_REQUIRED')
        self.assertEqual(payload.get('next_action'), 'provide_password')


if __name__ == '__main__':
    unittest.main()
