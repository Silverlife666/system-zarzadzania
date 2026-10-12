"""Inwentaryzacja i wierne kopie istniejących backupów, bez ich scalania."""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path


CENTER_DIR = "centrum_kopii_bezpieczenstwa"


def _record(path: Path, root: Path, category: str, label: str) -> dict:
    return {"id": hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16], "path": str(path), "relative": str(path.relative_to(root)), "category": category, "label": label, "size": path.stat().st_size, "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"), "name": path.name}


def discover_backup_sources(app_root: Path) -> list[dict]:
    """Zwraca istniejące pliki backupów i wersji, bez folderu centralnych kopii."""
    groups = [
        ("data", "Pełny backup danych", app_root / "dane_aplikacji" / "data_exports", "backup_danych_*.zip"),
        ("data", "Kopia przed aktualizacją", app_root / "backups", "*"),
        ("products", "Backup bazy produktów", app_root / "dane_aplikacji" / "backups_bazy_produktow", "*.db"),
        ("products", "Backup bazy produktów (starszy)", app_root / "backups_bazy_produktow", "*.db"),
        ("documents", "Wersja dokumentu", app_root / "dane_aplikacji" / "dokumenty_zlecen", "**/wersje/*.pdf"),
        ("documents", "Dokument zarchiwizowany", app_root / "dane_aplikacji" / "archiwum_dokumentow_zlecen", "**/*.pdf"),
        ("documents", "Backup usuniętego zlecenia", app_root / "dane_aplikacji" / "backup_usunietych_zlecen", "**/*"),
        ("updates", "Paczka aktualizacji", app_root / "dane_aplikacji" / "update_packages", "*.zip"),
        ("updates", "Paczka aktualizacji (starsza)", app_root / "update", "*.zip"),
    ]
    records = []
    for category, label, base, pattern in groups:
        if not base.is_dir():
            continue
        for path in base.glob(pattern):
            if path.is_file() and CENTER_DIR not in path.parts:
                records.append(_record(path, app_root, category, label))
    return sorted(records, key=lambda item: (item["category"], item["modified"], item["relative"]), reverse=True)


def copy_records_to_center(app_root: Path, records: list[dict]) -> tuple[int, int]:
    """Kopiuje każdy źródłowy plik osobno; nigdy nie nadpisuje ani nie scala danych."""
    copied = skipped = 0
    center = app_root / "dane_aplikacji" / CENTER_DIR
    for record in records:
        source = Path(record["path"])
        try:
            source.resolve().relative_to(app_root.resolve())
            if not source.is_file():
                skipped += 1; continue
            target_dir = center / record["category"]
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{record['id']}_{source.name}"
            if target.exists() and target.stat().st_size == source.stat().st_size:
                skipped += 1; continue
            shutil.copy2(source, target)
            copied += 1
        except (OSError, ValueError):
            skipped += 1
    return copied, skipped


def central_copies(app_root: Path, category: str) -> list[dict]:
    root = app_root / "dane_aplikacji" / CENTER_DIR / category
    if not root.is_dir():
        return []
    return [_record(path, app_root, category, "Kopia centralna") for path in sorted(root.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True) if path.is_file()]
