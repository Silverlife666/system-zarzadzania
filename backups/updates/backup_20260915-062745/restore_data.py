"""Przywraca przygotowany backup danych po zamknięciu Streamlit."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from services.data_backup_manager import MANIFEST, _allowed, validate_data_backup

ROOT = Path(__file__).resolve().parent
PENDING = ROOT / "dane_aplikacji" / "pending_data_restore" / "pending_restore.json"


def main() -> int:
    try:
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
        package = Path(pending["package"])
    except Exception:
        print("Brak przygotowanego backupu do przywrócenia.")
        return 1
    valid, message, manifest = validate_data_backup(package)
    if not valid:
        print(f"Przywracanie odrzucone: {message}")
        return 1
    backup_root = ROOT / "backups" / "data_restore" / f"before_restore_{datetime.now():%Y%m%d-%H%M%S}"
    try:
        if (ROOT / "dane_aplikacji").exists():
            shutil.copytree(ROOT / "dane_aplikacji", backup_root / "dane_aplikacji", dirs_exist_ok=True, ignore=shutil.ignore_patterns("pending_data_restore", "data_exports"))
        if (ROOT / ".streamlit" / "pass.toml").is_file():
            (backup_root / ".streamlit").mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / ".streamlit" / "pass.toml", backup_root / ".streamlit" / "pass.toml")
        with ZipFile(package) as archive:
            for item in manifest["files"]:
                relative = item["path"]
                if not _allowed(relative):
                    raise ValueError(f"Niedozwolony plik: {relative}")
                target = ROOT / Path(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(relative))
        PENDING.unlink(missing_ok=True)
        print(f"Dane przywrócone. Poprzedni stan: {backup_root}")
        return 0
    except Exception as error:
        print(f"Przywracanie nie powiodło się: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
