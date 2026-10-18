"""Minimalny, serwerowy magazyn stanu w Supabase.

Klucz ``service_role`` jest używany tylko przez proces Streamlit. Ten moduł
nie importuje Streamlit ani nie odczytuje sekretów samodzielnie, dzięki czemu
nie ma ryzyka przypadkowego przesłania klucza do przeglądarki.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from services.storage import SharedStateStore


def jsonb_safe(value: Any) -> Any:
    """PostgreSQL JSONB nie dopuszcza ``NaN`` ani wartości nieskończonych."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): jsonb_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonb_safe(item) for item in value]
    return value


class SupabaseStateStore(SharedStateStore):
    """Supabase jako źródło prawdy, SQLite/JSON jako bezpieczny fallback."""

    def __init__(self, database_path: str, default_directory: str, url: str, key: str):
        super().__init__(database_path, default_directory)
        self.base_url = url.rstrip("/") + "/rest/v1"
        self.key = key

    def _request(self, method: str, path: str, payload: Any | None = None) -> Any:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        data = None
        if payload is not None:
            data = json.dumps(jsonb_safe(payload), ensure_ascii=False, allow_nan=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}/{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ConnectionError("Nie udało się połączyć z magazynem Supabase.") from error

    def load(self, state_key: str, mirror_path: str, default: Any) -> Any:
        try:
            encoded_key = quote(state_key, safe="")
            rows = self._request("GET", f"application_state?state_key=eq.{encoded_key}&select=payload")
            if rows:
                return rows[0]["payload"]
            # Po skutecznym połączeniu brak rekordu oznacza brak danych w
            # chmurze. Nie wolno wtedy wskrzeszać starej kopii z katalogu
            # wdrożenia (np. skasowanych zleceń).
            return default
        except (ConnectionError, KeyError, TypeError):
            # Tylko rzeczywista awaria sieci pozwala użyć lokalnej kopii.
            return super().load(state_key, mirror_path, default)

    def save(self, state_key: str, mirror_path: str, data: Any) -> None:
        # Lokalna kopia pozostaje ostatnią linią obrony przy awarii sieci.
        super().save(state_key, mirror_path, data)
        payload = {
            "state_key": state_key,
            "payload": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._request(
                "POST",
                "application_state?on_conflict=state_key",
                payload,
            )
        except ConnectionError:
            # Zapis lokalny jest już wykonany; aplikacja może kontynuować pracę.
            pass
