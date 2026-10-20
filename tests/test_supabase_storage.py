import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from services.supabase_storage import CloudStorageUnavailable, SupabaseStateStore
from services.storage import SharedStateStore


class SupabaseStateStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = SupabaseStateStore(":memory:", ".", "https://example.supabase.co", "test-key")

    @patch("services.supabase_storage.urlopen", side_effect=OSError("offline"))
    def test_read_does_not_fall_back_to_stale_local_mirror(self, _urlopen):
        # Stary plik wdrożenia nie może wskrzeszać danych, gdy chmura nie odpowiada.
        with TemporaryDirectory() as directory:
            mirror = Path(directory) / "stale.json"
            mirror.write_text('{"orders":["old-order"]}', encoding="utf-8")
            with self.assertRaises(CloudStorageUnavailable):
                self.store.load("orders", str(mirror), {"orders": []})
        self.assertIsNotNone(self.store.last_error)

    @patch("services.supabase_storage.urlopen", side_effect=OSError("offline"))
    def test_write_fails_instead_of_saving_only_locally(self, _urlopen):
        with self.assertRaises(CloudStorageUnavailable):
            self.store.save("orders", "missing-local.json", {"orders": [{"id": "new"}]})

    def test_local_atomic_writes_do_not_share_a_temporary_filename(self):
        with TemporaryDirectory() as directory:
            target = str(Path(directory) / "state.json")
            store = SharedStateStore(str(Path(directory) / "state.db"), directory)
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda value: store.atomic_write_json(target, {"value": value}), (1, 2)))
            self.assertIn(json.loads(Path(target).read_text(encoding="utf-8"))["value"], (1, 2))


if __name__ == "__main__":
    unittest.main()
