"""
Parity v1 — AST-level float prohibition (structural, not textual).

Ensures no float usage in backend/v1 that could introduce nondeterminism:
- No ast.Call to float
- No ast.Constant of type float
- math import allowed only for floor (integer-producing)
"""

import ast
import os
import sys
import unittest

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)


def _collect_py_files(root: str) -> list:
    """Collect all .py files under root."""
    out = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith(".py"):
                out.append(os.path.join(dirpath, f))
    return sorted(out)


class TestNoFloatRegression(unittest.TestCase):
    """Structural float prohibition in backend/v1."""

    V1_ROOT = os.path.join(_BACKEND, "v1")

    def test_no_float_calls(self):
        """No ast.Call to float() anywhere in backend/v1."""
        violations = []
        for fpath in _collect_py_files(self.V1_ROOT):
            rel = os.path.relpath(fpath, self.V1_ROOT)
            try:
                with open(fpath, "r") as f:
                    tree = ast.parse(f.read(), filename=fpath)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "float":
                        violations.append(f"{rel}:{node.lineno}")
        self.assertEqual(violations, [], f"float() calls found: {violations}")

    def test_no_float_constants(self):
        """No ast.Constant of type float (e.g. 0.5, 1.0) in backend/v1 core money path."""
        # Core files that handle money/confidence/override math
        core_files = [
            "core/confidence_engine.py",
            "core/metrics_engine.py",
            "core/pipeline.py",
            "core/snapshot_engine.py",
            "core/transfer_matcher.py",
            "core/entities.py",
            "core/classifier.py",
        ]
        violations = []
        for rel in core_files:
            fpath = os.path.join(self.V1_ROOT, rel)
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath, "r") as f:
                    tree = ast.parse(f.read(), filename=fpath)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    violations.append(f"{rel}:{node.lineno} (value={node.value})")
        self.assertEqual(violations, [], f"Float constants found in money path: {violations}")

    def test_math_import_restricted(self):
        """math module: only floor allowed (produces int). No sqrt, etc."""
        allowed_attrs = {"floor"}
        violations = []
        for fpath in _collect_py_files(self.V1_ROOT):
            rel = os.path.relpath(fpath, self.V1_ROOT)
            try:
                with open(fpath, "r") as f:
                    tree = ast.parse(f.read(), filename=fpath)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "math":
                            if node.func.attr not in allowed_attrs:
                                violations.append(f"{rel}:{node.lineno} math.{node.func.attr}")
        self.assertEqual(violations, [], f"Disallowed math usage: {violations}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
