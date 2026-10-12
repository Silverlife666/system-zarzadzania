"""Tworzenie i bezpieczna walidacja paczek aktualizacyjnych aplikacji."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile


VERSION_FILE = "version.json"
MANIFEST_FILE = "update_manifest.json"
EXCLUDED_TOP_LEVEL = {"dane_aplikacji", "backups", "__pycache__", "tmp", ".git", ".agents", "mobile_inventory_app"}
ALLOWED_ROOT_FILES = {"app.py", "version.json", "Uruchom_web.bat", "start.vbs", "updater.py", "Zastosuj_aktualizacje.bat", "restore_data.py", "Przywroc_dane.bat"}
ALLOWED_FOLDERS = {"modules", "services", "core"}
SOURCE_STATE_FILE = "dane_aplikacji/update_catalog/current_source.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_version(app_root: Path) -> dict:
    path = app_root / VERSION_FILE
    default = {"version": "0.1.0", "build_id": "local", "updated_at": ""}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return {**default, **value} if isinstance(value, dict) else default
    except (OSError, json.JSONDecodeError):
        return default


def write_version(app_root: Path, version: str, build_id: str | None = None) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    value = {"version": version.strip(), "build_id": build_id or f"{datetime.now():%Y%m%d-%H%M%S}", "updated_at": now}
    (app_root / VERSION_FILE).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return value


def is_allowed_relative_path(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return False
    if len(path.parts) == 1:
        return path.name in ALLOWED_ROOT_FILES
    return path.parts[0] in ALLOWED_FOLDERS and path.suffix in {".py", ".json"}


def iter_update_files(app_root: Path):
    for path in app_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(app_root)
        if any(part in EXCLUDED_TOP_LEVEL for part in relative.parts):
            continue
        posix_name = relative.as_posix()
        if is_allowed_relative_path(posix_name):
            yield path, posix_name


def source_manifest(app_root: Path) -> list[dict]:
    return [
        {"path": relative, "sha256": sha256_bytes(path.read_bytes()), "size": path.stat().st_size}
        for path, relative in iter_update_files(app_root)
    ]


def token_for_files(files: list[dict]) -> str:
    rows = []
    for item in files:
        rows.append(f"{item['path']}:{item['sha256']}")
    return sha256_bytes("|".join(sorted(rows)).encode("utf-8"))[:16]


def source_token(app_root: Path) -> str:
    """Krótki, powtarzalny odcisk aktualnego kodu aplikacji."""
    return token_for_files(source_manifest(app_root))


def _source_state_path(app_root: Path) -> Path:
    return app_root / SOURCE_STATE_FILE


def read_source_state(app_root: Path) -> dict:
    try:
        value = json.loads(_source_state_path(app_root).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and isinstance(value.get("files"), list) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_source_state(app_root: Path, version: dict, files: list[dict]) -> None:
    path = _source_state_path(app_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {"version": version["version"], "build_id": version["build_id"], "token": token_for_files(files), "files": files}
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def next_incremental_version(version: str) -> str:
    try:
        major_text, minor_text = version.strip().split(".")
        major, minor = int(major_text), int(minor_text)
    except (ValueError, AttributeError):
        raise ValueError("Wersja bazowa musi mieć format 1.00.")
    if major < 0 or minor < 0:
        raise ValueError("Wersja bazowa musi być dodatnia.")
    if minor >= 99:
        return f"{major + 1}.00"
    return f"{major}.{minor + 1:02d}"


def incremental_transition_allowed(app_root: Path, manifest: dict) -> tuple[bool, str]:
    if manifest.get("package_type") != "incremental":
        return True, "Pełna paczka może zostać wdrożona niezależnie od bieżącej wersji."
    current = read_version(app_root)
    expected_version = manifest.get("base_version")
    expected_token = manifest.get("base_token")
    if current.get("version") != expected_version or source_token(app_root) != expected_token:
        return False, "Ta paczka przyrostowa wymaga dokładnie wersji bazowej i niezmienionego tokenu kodu. Wgraj wcześniejszą paczkę albo paczkę całkowitą."
    try:
        next_version = next_incremental_version(str(expected_version))
    except ValueError as error:
        return False, str(error)
    if manifest.get("target_version") != next_version:
        return False, f"Nieprawidłowy indeks przyrostowy. Po {expected_version} dozwolona jest wyłącznie paczka {next_version}."
    return True, "Paczka przyrostowa ma prawidłową wersję bazową."


def create_update_package(app_root: Path, output_dir: Path, target_version: str, package_type: str = "full") -> tuple[Path, dict]:
    if package_type not in {"full", "incremental"}:
        raise ValueError("Nieznany typ paczki.")
    current = read_version(app_root)
    base_state = read_source_state(app_root)
    if package_type == "incremental":
        expected = next_incremental_version(current["version"])
        if target_version != expected:
            raise ValueError(f"Dla wersji {current['version']} następna paczka przyrostowa musi mieć numer {expected}.")
        if base_state.get("version") != current["version"] or not base_state.get("token"):
            raise ValueError("Brak punktu bazowego dla tej wersji. Utwórz najpierw paczkę całkowitą.")
    version = write_version(app_root, target_version)
    all_files = source_manifest(app_root)
    base_files = {item["path"]: item for item in base_state.get("files", []) if isinstance(item, dict) and item.get("path")}
    current_files = {item["path"]: item for item in all_files}
    files = all_files if package_type == "full" else [item for item in all_files if base_files.get(item["path"], {}).get("sha256") != item["sha256"]]
    deleted_files = [] if package_type == "full" else sorted(set(base_files) - set(current_files))
    manifest = {
        "format": 2, "package_type": package_type, "source_version": current.get("version", ""), "target_version": version["version"],
        "build_id": version["build_id"], "created_at": version["updated_at"],
        "token": token_for_files(all_files), "base_version": current.get("version", "") if package_type == "incremental" else None,
        "base_token": base_state.get("token") if package_type == "incremental" else None,
        "files": files, "deleted_files": deleted_files,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "przyrostowa" if package_type == "incremental" else "calkowita"
    package = output_dir / f"aktualizacja_{prefix}_{version['version'].replace('.', '_')}_{version['build_id']}.zip"
    if package.exists():
        raise FileExistsError(f"Paczka {package.name} już istnieje i nie zostanie nadpisana.")
    with ZipFile(package, "w", compression=ZIP_DEFLATED) as archive:
        paths = {relative: path for path, relative in iter_update_files(app_root)}
        for item in files:
            archive.write(paths[item["path"]], item["path"])
        archive.writestr(MANIFEST_FILE, json.dumps(manifest, ensure_ascii=False, indent=2))
    save_source_state(app_root, version, all_files)
    return package, manifest


def validate_update_package(package_path: Path) -> tuple[bool, str, dict]:
    try:
        with ZipFile(package_path) as archive:
            names = archive.namelist()
            if MANIFEST_FILE not in names:
                return False, "Brak manifestu aktualizacji.", {}
            manifest = json.loads(archive.read(MANIFEST_FILE).decode("utf-8"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
                return False, "Manifest ma nieprawidłowy format.", {}
            if manifest.get("package_type", "full") not in {"full", "incremental"}:
                return False, "Nieznany typ paczki aktualizacji.", {}
            expected = {item.get("path"): item for item in manifest["files"] if isinstance(item, dict)}
            if not expected:
                return False, "Paczka nie zawiera plików aktualizacji.", {}
            for name in names:
                if name == MANIFEST_FILE:
                    continue
                if not is_allowed_relative_path(name):
                    return False, f"Niedozwolona ścieżka w paczce: {name}", {}
            for relative, item in expected.items():
                if relative not in names or not is_allowed_relative_path(relative):
                    return False, f"Brak lub niedozwolony plik: {relative}", {}
                if sha256_bytes(archive.read(relative)) != item.get("sha256"):
                    return False, f"Nie zgadza się suma kontrolna: {relative}", {}
            for relative in manifest.get("deleted_files", []):
                if not isinstance(relative, str) or not is_allowed_relative_path(relative):
                    return False, f"Niedozwolony plik do usunięcia: {relative}", {}
            return True, "Paczka poprawna.", manifest
    except Exception as error:
        return False, f"Nie można zweryfikować paczki: {error}", {}


def stage_update_package(app_root: Path, uploaded_bytes: bytes, file_name: str) -> tuple[bool, str, dict, Path | None]:
    pending_dir = app_root / "dane_aplikacji" / "pending_updates"
    pending_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file_name).name
    candidate = pending_dir / safe_name
    candidate.write_bytes(uploaded_bytes)
    valid, message, manifest = validate_update_package(candidate)
    if not valid:
        candidate.unlink(missing_ok=True)
        return False, message, {}, None
    allowed, reason = incremental_transition_allowed(app_root, manifest)
    if not allowed:
        candidate.unlink(missing_ok=True)
        return False, reason, manifest, None
    pending = {"package": str(candidate), "manifest": manifest, "staged_at": datetime.now().isoformat(timespec="seconds")}
    (pending_dir / "pending_update.json").write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, message, manifest, candidate


def read_pending_update(app_root: Path) -> dict:
    path = app_root / "dane_aplikacji" / "pending_updates" / "pending_update.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def append_update_history(app_root: Path, item: dict) -> None:
    path = app_root / "dane_aplikacji" / "update_history.json"
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
        history = history if isinstance(history, list) else []
    except (OSError, json.JSONDecodeError):
        history = []
    history.insert(0, item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history[:50], ensure_ascii=False, indent=2), encoding="utf-8")
