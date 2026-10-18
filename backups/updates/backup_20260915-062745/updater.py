"""Wdraża przygotowaną paczkę aktualizacji po zamknięciu aplikacji."""
from __future__ import annotations

import argparse
import json
import py_compile
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from services.update_manager import (
    MANIFEST_FILE,
    append_update_history,
    incremental_transition_allowed,
    is_allowed_relative_path,
    read_pending_update,
    read_version,
    save_source_state,
    source_manifest,
    validate_update_package,
)


APP_ROOT = Path(__file__).resolve().parent


def apply_latest_update() -> int:
    pending = read_pending_update(APP_ROOT)
    package = Path(str(pending.get("package", "")))
    if not package.is_file():
        print("Brak przygotowanej paczki aktualizacji.")
        return 1

    valid, message, manifest = validate_update_package(package)
    if not valid:
        print(f"Aktualizacja odrzucona: {message}")
        return 1
    allowed, reason = incremental_transition_allowed(APP_ROOT, manifest)
    if not allowed:
        print(f"Aktualizacja odrzucona: {reason}")
        return 1

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = APP_ROOT / "backups" / "updates" / f"backup_{timestamp}"
    created_paths: list[Path] = []
    overwritten_paths: list[Path] = []
    deleted_paths: list[Path] = []
    try:
        with ZipFile(package) as archive:
            for file_info in manifest["files"]:
                relative = str(file_info["path"])
                if not is_allowed_relative_path(relative):
                    raise ValueError(f"Niedozwolony plik: {relative}")
                target = APP_ROOT / Path(relative)
                if target.exists():
                    backup_path = backup_root / Path(relative)
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup_path)
                    overwritten_paths.append(target)
                else:
                    created_paths.append(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(relative))
            for relative in manifest.get("deleted_files", []):
                target = APP_ROOT / Path(relative)
                if target.exists():
                    backup_path = backup_root / Path(relative)
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup_path)
                    overwritten_paths.append(target)
                    target.unlink()
                    deleted_paths.append(target)

        for file_info in manifest["files"]:
            relative = str(file_info["path"])
            if relative.endswith(".py"):
                py_compile.compile(str(APP_ROOT / Path(relative)), doraise=True)
        save_source_state(APP_ROOT, read_version(APP_ROOT), source_manifest(APP_ROOT))
        record = {"applied_at": datetime.now().isoformat(timespec="seconds"), "status": "success", "version": manifest.get("target_version"), "build_id": manifest.get("build_id"), "token": manifest.get("token"), "backup": str(backup_root), "package": package.name}
        append_update_history(APP_ROOT, record)
        (APP_ROOT / "dane_aplikacji" / "pending_updates" / "pending_update.json").unlink(missing_ok=True)
        print(f"Aktualizacja {manifest.get('target_version')} została wdrożona. Kopia: {backup_root}")
        return 0
    except Exception as error:
        for target in created_paths:
            target.unlink(missing_ok=True)
        for target in overwritten_paths:
            source = backup_root / target.relative_to(APP_ROOT)
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        append_update_history(APP_ROOT, {"applied_at": datetime.now().isoformat(timespec="seconds"), "status": "failed", "error": str(error), "package": package.name})
        print(f"Aktualizacja nie została wdrożona: {error}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-latest", action="store_true")
    args = parser.parse_args()
    sys.exit(apply_latest_update() if args.apply_latest else 0)
