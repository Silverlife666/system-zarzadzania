import tempfile
import unittest
from pathlib import Path

from services.backup_center import copy_records_to_center, discover_backup_sources


class BackupCenterTests(unittest.TestCase):
    def test_discovers_and_copies_without_merging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "dane_aplikacji" / "data_exports"; source.mkdir(parents=True)
            (source / "backup_danych_20260914.zip").write_bytes(b"test")
            records = discover_backup_sources(root)
            self.assertEqual(len(records), 1)
            copied, skipped = copy_records_to_center(root, records)
            self.assertEqual((copied, skipped), (1, 0))
            copied, skipped = copy_records_to_center(root, records)
            self.assertEqual((copied, skipped), (0, 1))


if __name__ == "__main__":
    unittest.main()
