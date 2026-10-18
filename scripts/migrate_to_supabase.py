"""Jednorazowy import lokalnych danych aplikacji do Supabase.

Uruchom na komputerze z katalogu projektu:
  $env:SUPABASE_URL='https://...supabase.co'
  $env:SUPABASE_SERVICE_ROLE_KEY='sb_secret_...'
  python scripts/migrate_to_supabase.py
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "dane_aplikacji"


def jsonb_safe(value: object) -> object:
    """Zamienia NaN i nieskończoności na null, zgodny z PostgreSQL JSONB."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): jsonb_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonb_safe(item) for item in value]
    return value


def configuration() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise SystemExit("Ustaw SUPABASE_URL oraz SUPABASE_SERVICE_ROLE_KEY w zmiennych środowiskowych.")
    return url.rstrip("/") + "/rest/v1", key


def upsert(base_url: str, key: str, state_key: str, payload: object) -> None:
    body = json.dumps(
        {"state_key": state_key, "payload": jsonb_safe(payload), "updated_at": datetime.now(timezone.utc).isoformat()},
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    request = Request(
        f"{base_url}/application_state?on_conflict=state_key",
        data=body,
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        with urlopen(request, timeout=30):
            pass
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Nie udało się zapisać {state_key}: HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Nie udało się zapisać {state_key}: {error}") from error


def main() -> None:
    base_url, key = configuration()
    imported = 0
    state_db = DATA_DIR / "magazyn_stanu_aplikacji.db"
    if not state_db.exists():
        state_db = ROOT / "magazyn_stanu_aplikacji.db"
    if state_db.exists():
        with sqlite3.connect(state_db) as connection:
            for state_key, serialized in connection.execute("select state_key, payload from application_state"):
                upsert(base_url, key, state_key, json.loads(serialized))
                imported += 1

    # Pliki JSON są kopią bezpieczeństwa, więc zapisujemy je oddzielnie. Nie
    # nadpisują aktualnych kluczy aplikacji z centralnej SQLite.
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            upsert(base_url, key, f"migration:json:{path.name}", json.loads(path.read_text(encoding="utf-8")))
            imported += 1
        except json.JSONDecodeError:
            print(f"Pominięto nieprawidłowy JSON: {path.name}")

    db_path = DATA_DIR / "baza_produktow.db"
    if not db_path.exists():
        db_path = ROOT / "baza_produktow.db"
    if db_path.exists():
        with sqlite3.connect(db_path) as connection:
            snapshot = {
                "version": 1,
                "produkty": [list(row) for row in connection.execute("select nazwa, dane from produkty")],
                "product_history": [list(row) for row in connection.execute("select product_name, action, changed_at, changed_by, reason, old_data, new_data from product_history")],
                "archived_products": [list(row) for row in connection.execute("select original_name, data, archived_at, archived_by, reason from archived_products")],
                "product_locks": [list(row) for row in connection.execute("select product_name, locked_by, locked_at from product_locks")],
                "product_custom_fields": [list(row) for row in connection.execute("select field_name, active from product_custom_fields")],
            }
        upsert(base_url, key, "product_catalog_sqlite_v1", snapshot)
        imported += 1

    print(f"Import zakończony: {imported} zbiorów danych zapisano w Supabase.")


if __name__ == "__main__":
    main()
