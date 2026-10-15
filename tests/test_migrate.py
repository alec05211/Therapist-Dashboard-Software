from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from database.migrate import checksum, compatible_checksums


class MigrationChecksumTests(unittest.TestCase):
    def test_checksum_is_stable_across_line_endings(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            lf_path = root / "lf.sql"
            crlf_path = root / "crlf.sql"
            lf_path.write_bytes(b"BEGIN;\nSELECT 1;\nCOMMIT;\n")
            crlf_path.write_bytes(b"BEGIN;\r\nSELECT 1;\r\nCOMMIT;\r\n")

            self.assertEqual(checksum(lf_path), checksum(crlf_path))

    def test_legacy_crlf_checksum_is_compatible_with_lf_checkout(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "001_initial_schema.sql"
            lf_bytes = b"BEGIN;\nSELECT 1;\nCOMMIT;\n"
            path.write_bytes(lf_bytes)
            legacy_crlf = hashlib.sha256(
                lf_bytes.replace(b"\n", b"\r\n")
            ).hexdigest()

            self.assertIn(legacy_crlf, compatible_checksums(path))

    def test_semantic_change_is_not_compatible(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "001_initial_schema.sql"
            path.write_bytes(b"BEGIN;\nSELECT 2;\nCOMMIT;\n")
            original = hashlib.sha256(
                b"BEGIN;\r\nSELECT 1;\r\nCOMMIT;\r\n"
            ).hexdigest()

            self.assertNotIn(original, compatible_checksums(path))


if __name__ == "__main__":
    unittest.main()
