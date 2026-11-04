"""Reproduce unresolved science assertions separately from the normal xfail suite.

Exit 0 means the documented failures were reproduced, NOT scientific acceptance.
No app startup, network, external data or credentials.
"""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest

os.environ["NPDB_STRICT_DESIRED"] = "1"
path = Path(__file__).resolve().parents[1] / "tests/test_science_qa_round2.py"
spec = importlib.util.spec_from_file_location("science_round2_strict", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
suite = unittest.defaultTestLoader.loadTestsFromModule(module)
def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item
expected = {test.id() for test in flatten(suite) if ".test_desired_" in test.id()}
result = unittest.TextTestRunner(verbosity=2).run(suite)
actual = {test.id() for test, _ in result.failures}
report = {"meaning": "Known unresolved assertions reproduced; release BLOCKED",
          "tests_run": result.testsRun, "expected_failure_count": len(expected),
          "assertion_failures": sorted(actual), "errors": len(result.errors),
          "skips": len(result.skipped)}
print(json.dumps(report, indent=2))
# Require RDKit and all 45 tests. An exception, skip or unexpected pass is a failure of this reproduction gate.
sys.exit(0 if len(expected) == 16 and actual == expected and result.testsRun == 45
         and not result.errors and not result.skipped else 1)
