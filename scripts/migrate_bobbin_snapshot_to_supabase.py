"""Jednorazowo importuje eksport modułu 31 (np. z npoint) do Supabase.

Przykład (PowerShell):
  $env:SUPABASE_URL='https://<project>.supabase.co'
  $env:SUPABASE_SERVICE_ROLE_KEY='sb_secret_...'
  python scripts/migrate_bobbin_snapshot_to_supabase.py C:\\Users\\Adrian\\Desktop\\rozliczenie_bobin.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

STATE_KEY = "operational_json:rozliczenie_bobin.json"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Podaj ścieżkę do eksportu JSON modułu 31.")
    source = Path(sys.argv[1])
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("format") != "system-produkcji/bobbin-settlement" or payload.get("version") != 1:
        raise SystemExit("To nie jest prawidłowy eksport modułu 31 (format/version).")
    if not isinstance(payload.get("data"), dict) or not isinstance(payload.get("sync"), dict):
        raise SystemExit("Eksport nie zawiera sekcji data i sync.")
    url, key = os.environ.get("SUPABASE_URL", "").strip(), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise SystemExit("Ustaw SUPABASE_URL oraz SUPABASE_SERVICE_ROLE_KEY.")
    body = json.dumps({"state_key": STATE_KEY, "payload": payload, "updated_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False).encode()
    request = Request(url.rstrip("/") + "/rest/v1/application_state?on_conflict=state_key", body, method="POST", headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"})
    try:
        with urlopen(request, timeout=30):
            pass
    except HTTPError as error:
        raise SystemExit(f"Import nieudany: HTTP {error.code}: {error.read().decode(errors='replace')}")
    print(f"Zaimportowano {len(payload['data'].get('orders', []))} zleceń i {len(payload['data'].get('entries', []))} wpisów do {STATE_KEY}.")


if __name__ == "__main__":
    main()
