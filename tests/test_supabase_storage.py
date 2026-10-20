import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.supabase_storage import CloudStorageUnavailable, SupabaseStateStore


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


if __name__ == "__main__":
    unittest.main()
