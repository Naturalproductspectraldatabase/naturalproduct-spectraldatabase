"""CI extraction contract: no actual archive/data/credential bytes are consulted."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[2]/'.github/scripts/extract_synthetic_source.py'


class SyntheticSourceExtraction(unittest.TestCase):
    def test_only_code_sql_and_requirement_manifests_are_allowed(self):
        spec=importlib.util.spec_from_file_location('npdb_ci_extract',SCRIPT)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for name in ('requirements.txt','NMR_Database_Tyas_GitHub_Upload/requirements.txt',
                     'NMR_Database_Tyas_GitHub_Upload/scripts/app.py',
                     'NMR_Database_Tyas_GitHub_Upload/tests/security_schema_gate.sql'):
            self.assertTrue(module.allowed(name),name)
        for name in ('NMR_Database_Tyas_GitHub_Upload/database/nmr.db',
                     'NMR_Database_Tyas_GitHub_Upload/database/backups/private.sql',
                     'NMR_Database_Tyas_GitHub_Upload/data/structures/private.png',
                     'NMR_Database_Tyas_GitHub_Upload/tests/private.csv',
                     'NMR_Database_Tyas_GitHub_Upload/.streamlit/secrets.toml',
                     '../private.py','/etc/private.py',
                     'NMR_Database_Tyas_GitHub_Upload/scripts/../../private.py'):
            self.assertFalse(module.allowed(name),name)
