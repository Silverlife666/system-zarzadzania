"""Eksport i bezpieczne przygotowanie pełnej kopii danych aplikacji."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile


MANIFEST = "data_backup_manifest.json"
DATA_ROOT = "dane_aplikacji"
ALLOWED_ROOT_FILE = ".streamlit/pass.toml"
EXCLUDED_DATA_PARTS = {"pending_updates", "pending_data_restore", "data_exports", "update_packages", "update_catalog"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _allowed(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    return name == ALLOWED_ROOT_FILE or (len(path.parts) > 1 and path.parts[0] == DATA_ROOT)


def _files(app_root: Path):
    data_root = app_root / DATA_ROOT
    if data_root.exists():
        for path in data_root.rglob("*"):
            if path.is_file():
                relative = path.relative_to(app_root).as_posix()
                if not any(part in EXCLUDED_DATA_PARTS for part in PurePosixPath(relative).parts):
                    yield path, relative
    credentials = app_root / ALLOWED_ROOT_FILE
    if credentials.is_file():
        yield credentials, ALLOWED_ROOT_FILE


def create_data_backup(app_root: Path) -> tuple[Path, dict]:
    output_dir = app_root / DATA_ROOT / "data_exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    files = [{"path": relative, "sha256": _sha(path.read_bytes()), "size": path.stat().st_size} for path, relative in _files(app_root)]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = output_dir / f"backup_danych_{stamp}.zip"
    manifest = {"format": 1, "created_at": datetime.now().isoformat(timespec="seconds"), "files": files, "token": _sha("|".join(sorted(f"{item['path']}:{item['sha256']}" for item in files)).encode())[:16]}
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for path, relative in _files(app_root):
            archive.write(path, relative)
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
    return target, manifest


def validate_data_backup(path: Path) -> tuple[bool, str, dict]:
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            if MANIFEST not in names:
                return False, "Brak manifestu backupu danych.", {}
            manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
            files = manifest.get("files", []) if isinstance(manifest, dict) else []
            if not isinstance(files, list) or not files:
                return False, "Backup nie zawiera danych.", {}
            expected = {item.get("path"): item for item in files if isinstance(item, dict)}
            for name in names:
                if name != MANIFEST and not _allowed(name):
                    return False, f"Niedozwolona ścieżka: {name}", {}
            for relative, item in expected.items():
                if not _allowed(relative) or relative not in names:
                    return False, f"Brak lub nieprawidłowy plik: {relative}", {}
                if _sha(archive.read(relative)) != item.get("sha256"):
                    return False, f"Nie zgadza się suma pliku: {relative}", {}
            return True, "Backup danych jest poprawny.", manifest
    except Exception as error:
        return False, f"Nie można odczytać backupu: {error}", {}


def stage_data_restore(app_root: Path, source: Path) -> tuple[bool, str, dict]:
    valid, message, manifest = validate_data_backup(source)
    if not valid:
        return False, message, {}
    pending_dir = app_root / DATA_ROOT / "pending_data_restore"
    pending_dir.mkdir(parents=True, exist_ok=True)
    staged = pending_dir / source.name
    if source.resolve() != staged.resolve():
        shutil.copy2(source, staged)
    (pending_dir / "pending_restore.json").write_text(json.dumps({"package": str(staged), "manifest": manifest, "staged_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, "Backup przygotowano do przywrócenia po zamknięciu aplikacji.", manifest
