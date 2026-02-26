"""
GET /v1/system/health — Deterministic engine identity.

No DB required.  Identical output across requests within the same build.
"""

import json
import os
import sys
import unittest

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.v1.api import router as v1_router
from backend.v1.config import SCHEMA_VERSION, CONFIG_VERSION


def _make_app():
    app = FastAPI()
    app.include_router(v1_router)
    return app


class TestSystemHealth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _make_app()
        cls.client = TestClient(cls.app)

    def test_returns_200(self):
        resp = self.client.get("/v1/system/health")
        self.assertEqual(resp.status_code, 200)

    def test_deterministic_mode_true(self):
        body = self.client.get("/v1/system/health").json()
        self.assertIs(body["deterministic_mode"], True)

    def test_schema_version_matches_config(self):
        body = self.client.get("/v1/system/health").json()
        self.assertEqual(body["schema_version"], SCHEMA_VERSION)

    def test_config_version_matches_config(self):
        body = self.client.get("/v1/system/health").json()
        self.assertEqual(body["config_version"], CONFIG_VERSION)

    def test_required_fields_present(self):
        body = self.client.get("/v1/system/health").json()
        for key in ("schema_version", "config_version", "git_commit", "build_timestamp", "deterministic_mode"):
            self.assertIn(key, body, f"Missing field: {key}")

    def test_no_extra_fields(self):
        body = self.client.get("/v1/system/health").json()
        allowed = {"schema_version", "config_version", "git_commit", "build_timestamp", "deterministic_mode"}
        extra = set(body.keys()) - allowed
        self.assertEqual(extra, set(), f"Unexpected fields: {extra}")

    def test_identical_across_10_calls(self):
        responses = [
            json.dumps(self.client.get("/v1/system/health").json(), sort_keys=True)
            for _ in range(10)
        ]
        self.assertEqual(len(set(responses)), 1, "Response must be identical across requests")

    def test_git_commit_is_string_or_none(self):
        body = self.client.get("/v1/system/health").json()
        self.assertIn(type(body["git_commit"]), (str, type(None)))

    def test_build_timestamp_is_string(self):
        body = self.client.get("/v1/system/health").json()
        self.assertIsInstance(body["build_timestamp"], str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
