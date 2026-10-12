import json
import unittest

from modules.work_settlement_archive_screen import (
    export_work_settlement_archive,
    merge_work_settlement_archives,
    parse_work_settlement_archive_import,
)


class WorkSettlementArchiveTests(unittest.TestCase):
    def test_export_and_import_round_trip(self):
        source = {
            "entries": [{"date": "2026-09-14", "employee": "Adrian", "quantity": 12}],
            "changeovers": [{"date": "2026-09-14", "machine": "M1", "duration_minutes": 30}],
        }
        payload = export_work_settlement_archive(source)
        self.assertEqual(json.loads(payload.decode("utf-8"))["format"], "system-zarzadzania-produkcja/work-settlement-archive")
        entries, changeovers, skipped = parse_work_settlement_archive_import(payload)
        self.assertEqual(skipped, 0)
        self.assertEqual(entries, source["entries"])
        self.assertEqual(changeovers, source["changeovers"])

    def test_merge_preserves_local_records_and_skips_duplicates(self):
        local_entry = {"date": "2026-09-14", "employee": "Adrian", "quantity": 12}
        remote_entry = {"date": "2026-09-15", "employee": "Anna", "quantity": 8}
        local = {"entries": [local_entry], "changeovers": []}
        merged, stats = merge_work_settlement_archives(local, [local_entry, remote_entry], [])
        self.assertEqual(len(merged["entries"]), 2)
        self.assertEqual(stats, {"entries": 1, "changeovers": 0, "duplicates": 1})

    def test_import_rejects_other_archive(self):
        with self.assertRaises(ValueError):
            parse_work_settlement_archive_import(b'{"format":"other", "entries":[], "changeovers":[]}')


if __name__ == "__main__":
    unittest.main()
