import json
import unittest

from modules.preorder_screen import (
    export_preorder_archive,
    merge_preorder_archives,
    parse_preorder_archive_import,
)


class PreorderArchiveTests(unittest.TestCase):
    def test_export_and_import_round_trip(self):
        source = {"preorders": [{"id": "PRE001", "created_at": "2026-09-14T10:00:00", "meta": {"order_no": "PRE-1"}, "items": [{"product_name": "Box"}]}]}
        payload = export_preorder_archive(source)
        decoded = json.loads(payload.decode("utf-8"))
        self.assertEqual(decoded["format"], "system-zarzadzania-produkcja/preorder-archive")
        imported, skipped = parse_preorder_archive_import(payload)
        self.assertEqual(skipped, 0)
        self.assertEqual(imported, source["preorders"])

    def test_merge_skips_identical_and_renames_conflicting_id(self):
        local = {"preorders": [{"id": "SAME", "created_at": "2026-09-14T10:00:00", "meta": {}, "items": [{"product_name": "Lokalny"}]}]}
        identical = {"id": "SAME", "created_at": "2026-09-14T10:00:00", "meta": {}, "items": [{"product_name": "Lokalny"}]}
        conflict = {"id": "SAME", "created_at": "2026-09-14T11:00:00", "meta": {}, "items": [{"product_name": "Import"}]}
        merged, stats = merge_preorder_archives(local, [identical, conflict])
        self.assertEqual(stats["duplicates"], 1)
        self.assertEqual(stats["imported"], 1)
        self.assertEqual(stats["renamed"], 1)
        self.assertEqual(len(merged["preorders"]), 2)
        self.assertNotEqual(merged["preorders"][1]["id"], "SAME")

    def test_import_rejects_wrong_format(self):
        with self.assertRaises(ValueError):
            parse_preorder_archive_import(b'{"format":"other", "preorders":[]}')


if __name__ == "__main__":
    unittest.main()
