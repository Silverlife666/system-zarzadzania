"""Trwałe reguły dostępu użytkowników i ról, niezależne od Streamlit."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def build_role_permissions(users: dict, module_options: dict, configured: dict | None = None) -> dict[str, set[int]]:
    """Łączy domyślne uprawnienia z zapisanymi wyjątkami dla ról."""
    configured = configured or {}
    roles = {data.get("role", "Użytkownik") for data in (users or {}).values()}
    roles.update(configured)
    roles.update(role for config in module_options.values() for role in config.get("roles", []))
    permissions = {}
    for role in roles:
        default_ids = {config["id"] for config in module_options.values() if role in config.get("roles", [])}
        selected_ids = configured.get(role, default_ids)
        if isinstance(selected_ids, dict):
            selected_ids = selected_ids.get("modules", default_ids)
        permissions[role] = {int(module_id) for module_id in selected_ids}
    # Moduły administracyjne muszą pozostać dostępne także dla istniejących konfiguracji ról.
    permissions.setdefault("Administrator", set()).update({14, 21, 22, 23, 29, 30})
    return permissions


def apply_role_permissions(module_options: dict, permissions: dict[str, set[int]]) -> dict:
    """Zwraca konfigurację modułów z rolami obliczonymi z tabeli uprawnień."""
    return {
        label: {**config, "roles": sorted(role for role, module_ids in permissions.items() if config["id"] in module_ids)}
        for label, config in module_options.items()
    }


def update_user_credentials(users: dict, username: str, new_username: str, new_password: str = "") -> dict:
    """Zwraca zaktualizowaną kopię kont bez ujawniania obecnego hasła."""
    updated_users = {name: dict(data) for name, data in (users or {}).items()}
    target_name = str(new_username or "").strip()
    if username not in updated_users:
        raise KeyError("Wybrany użytkownik nie istnieje.")
    if not target_name:
        raise ValueError("Nazwa użytkownika nie może być pusta.")
    if target_name != username and target_name in updated_users:
        raise ValueError("Taka nazwa użytkownika już istnieje.")
    account = updated_users.pop(username)
    if new_password:
        account["password"] = new_password
    updated_users[target_name] = account
    return updated_users


def save_user_access_config(path: str | Path, users: dict, permissions: dict[str, set[int]]) -> None:
    """Zapisuje konta i role do TOML, zachowując kopię poprzedniego pliku."""
    path = Path(path)
    backup_path = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        shutil.copy2(path, backup_path)
    lines = ["# Zarządzane przez Panel użytkowników aplikacji.", ""]
    for username, data in sorted(users.items(), key=lambda item: item[0].casefold()):
        lines.extend([
            f"[users.{json.dumps(username)}]",
            f"password = {json.dumps(str(data.get('password', '')))}",
            f"role = {json.dumps(str(data.get('role', 'Użytkownik')))}",
            "",
        ])
    for role, module_ids in sorted(permissions.items(), key=lambda item: item[0].casefold()):
        lines.extend([
            f"[role_permissions.{json.dumps(role)}]",
            "modules = [" + ", ".join(str(module_id) for module_id in sorted(module_ids)) + "]",
            "",
        ])
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text("\n".join(lines), encoding="utf-8")
    temporary_path.replace(path)
