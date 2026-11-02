"""Synthetic-only tests: NP-MRD public ZIP schema probe never exposes rows."""
import io
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from npdb_npmrd_schema_probe import zip_schema_report


def make_zip(filename: str, data: bytes):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(filename, data)
    return stream.getvalue()


class NP_MRDSchemaProbeTests(unittest.TestCase):
    def test_only_headers_are_returned(self):
        data = b"NP_ID,assignment_id,delta_ppm\nNP12345,SECRET_ROW_MARKER,4.23\n"
        report = zip_schema_report(make_zip("assignments.csv", data))
        self.assertEqual(report["csv_files"], 1)
        self.assertEqual(report["unique_csv_headers"], [["NP_ID","assignment_id","delta_ppm"]])
        self.assertNotIn("SECRET_ROW_MARKER", str(report))
        self.assertNotIn("NP12345", str(report))

    def test_non_csv_files_cannot_be_misclassified(self):
        report = zip_schema_report(make_zip("spectra/NP0000001.txt", b"FAKE NMR 1.23"))
        self.assertEqual(report["csv_files"], 0)
        self.assertEqual(report["file_extensions"], {".txt": 1})

    def test_bad_zip_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"not a ZIP"):
            zip_schema_report(b"invalid")

    def test_header_injection_is_rejected_without_printing_record(self):
        with self.assertRaisesRegex(ValueError,"non-schema-looking"):
            zip_schema_report(make_zip("x.csv", b"SECRET=private-password,delta_ppm\nVALUE,2.2\n"))

    def test_empty_zip_is_valid_but_has_no_csv_schema(self):
        z = io.BytesIO()
        with zipfile.ZipFile(z,"w"):
            pass
        self.assertEqual(zip_schema_report(z.getvalue())["files_total"],0)


if __name__ == "__main__":
    unittest.main()
