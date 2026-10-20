"""Bezpieczna migracja lokalnego stanu aplikacji do Supabase.

Domyślnie wykonuje wyłącznie raport. Flaga ``--apply`` tworzy w Supabase
brakujące rekordy, ale nigdy nie nadpisuje już istniejącego rekordu w chmurze.
To pozwala przenieść dane z dysku bez ryzyka wskrzeszenia starszego stanu.

Uruchomienie:
    python scripts/migrate_local_state_to_supabase.py
    python scripts/migrate_local_state_to_supabase.py --apply
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "dane_aplikacji"
STATE_DB = DATA_DIR / "magazyn_stanu_aplikacji.db"

# Rekordy wykorzystywane bezpośrednio przez aplikację mają historyczne,
# specjalne nazwy. Wszystkie pozostałe JSON-y otrzymują stabilny klucz po
# nazwie pliku, niezależny od komputera i katalogu wdrożenia.
SPECIAL_JSON_KEYS = {
    "print_db.json": "application_dictionary",
    "rejestr_dokumentow.json": "document_registry",
    "konteksty_zlecen.json": "order_contexts",
    "active_sessions.json": "active_sessions_v1",
}
OPERATIONAL_FILES = {
    "archiwum_rozliczen_pracy.json",
    "rozliczenie_bobin.json",
    "bobbin_calibrations.json",
    "inwentaryzacja_bobin.json",
    "magazyn_papieru_w_stosach.json",
}


def jsonb_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): jsonb_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonb_safe(item) for item in value]
    return value


def configuration() -> tuple[str, str]:
    """Pobiera poświadczenia ze środowiska albo lokalnego secrets.toml."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        secrets_path = ROOT / ".streamlit" / "secrets.toml"
        if secrets_path.exists():
            secrets = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
            supabase = secrets.get("supabase", {})
            url = url or str(supabase.get("url", "")).strip()
            key = key or str(supabase.get("key", "")).strip()
    if not url or not key:
        raise SystemExit("Brak danych Supabase. Ustaw SUPABASE_URL i SUPABASE_SERVICE_ROLE_KEY albo [supabase] w .streamlit/secrets.toml.")
    return url.rstrip("/") + "/rest/v1", key


def request_json(base_url: str, key: str, method: str, path: str, payload: Any | None = None) -> Any:
    data = None
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(jsonb_safe(payload), ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{base_url}/{path}", data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Nie można połączyć się z Supabase: {error}") from error


def cloud_state(base_url: str, key: str) -> dict[str, Any]:
    rows = request_json(base_url, key, "GET", "application_state?select=state_key,payload,updated_at")
    return {str(row["state_key"]): row.get("payload") for row in rows if isinstance(row, dict) and row.get("state_key")}


def key_for_file(path: Path) -> str:
    if path.name in SPECIAL_JSON_KEYS:
        return SPECIAL_JSON_KEYS[path.name]
    if path.name in OPERATIONAL_FILES:
        return f"operational_json:{path.name}"
    return f"persistent_json:{path.name}"


def product_catalog_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with sqlite3.connect(path) as connection:
        return {
            "version": 1,
            "produkty": [list(row) for row in connection.execute("SELECT nazwa, dane FROM produkty")],
            "product_history": [list(row) for row in connection.execute("SELECT product_name, action, changed_at, changed_by, reason, old_data, new_data FROM product_history")],
            "archived_products": [list(row) for row in connection.execute("SELECT original_name, data, archived_at, archived_by, reason FROM archived_products")],
            "product_locks": [list(row) for row in connection.execute("SELECT product_name, locked_by, locked_at FROM product_locks")],
            "product_custom_fields": [list(row) for row in connection.execute("SELECT field_name, active FROM product_custom_fields")],
        }


def local_state() -> tuple[dict[str, Any], list[str]]:
    records: dict[str, Any] = {}
    skipped: list[str] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            records[key_for_file(path)] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            skipped.append(path.name)
    snapshot = product_catalog_snapshot(DATA_DIR / "baza_produktow.db")
    if snapshot is not None:
        records["product_catalog_sqlite_v1"] = snapshot

    # Zachowujemy także rekordy, których starego klucza ścieżkowego nie da się
    # już bezpiecznie przypisać do pliku. Nie są nadpisywane i można je później
    # świadomie przyporządkować; dzięki temu nic nie przepada.
    if STATE_DB.exists():
        with sqlite3.connect(STATE_DB) as connection:
            for state_key, serialized in connection.execute("SELECT state_key, payload FROM application_state"):
                if state_key.startswith("json_store:"):
                    target_key = "legacy_" + state_key
                else:
                    target_key = state_key
                try:
                    records.setdefault(target_key, json.loads(serialized))
                except json.JSONDecodeError:
                    skipped.append(f"SQLite:{state_key}")
    return records, skipped


def upsert(base_url: str, key: str, state_key: str, payload: Any) -> None:
    request_json(
        base_url, key, "POST", "application_state?on_conflict=state_key",
        {"state_key": state_key, "payload": payload, "updated_at": datetime.now(timezone.utc).isoformat()},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bezpiecznie migruje brakujące lokalne rekordy do Supabase.")
    parser.add_argument("--apply", action="store_true", help="Zapisz brakujące rekordy; bez tej flagi jest tylko raport.")
    args = parser.parse_args()
    base_url, key = configuration()
    cloud = cloud_state(base_url, key)
    local, skipped = local_state()
    missing = [(state_key, payload) for state_key, payload in sorted(local.items()) if state_key not in cloud]
    existing = sorted(state_key for state_key in local if state_key in cloud)

    print(f"Supabase: {len(cloud)} rekordów; lokalnie odnaleziono: {len(local)} rekordów.")
    print(f"Do dodania bez nadpisywania: {len(missing)}; pozostawione w chmurze: {len(existing)}.")
    for state_key, payload in missing:
        size = len(json.dumps(payload, ensure_ascii=False, default=str))
        print(f"  DODAJ  {state_key} ({size} B)")
    for state_key in existing:
        print(f"  POMIŃ  {state_key} (rekord istnieje już w Supabase)")
    for name in skipped:
        print(f"  BŁĄD   pominięto nieprawidłowy JSON: {name}")
    if not args.apply:
        print("Raport zakończony. Żadnych danych nie zmieniono. Dodaj --apply, aby zapisać wyłącznie brakujące rekordy.")
        return
    for state_key, payload in missing:
        upsert(base_url, key, state_key, payload)
    print(f"Migracja zakończona: dodano {len(missing)} rekordów. Żaden istniejący rekord Supabase nie został nadpisany.")


if __name__ == "__main__":
    main()
