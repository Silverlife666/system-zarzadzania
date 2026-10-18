"""Operacje trwałego zapisu wykonywane przez formularz dokumentów produkcyjnych."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from services.order_documents import as_positive_int


def save_order_header(order_header: dict[str, Any], *, load_registry: Callable[[], dict[str, Any]],
                      save_registry: Callable[[dict[str, Any]], None], user_name: str = "",
                      saved_at: str | None = None) -> dict[str, Any]:
    order_id = order_header["order_id"]
    registry, now = load_registry(), saved_at or datetime.now().isoformat(timespec="seconds")
    record = registry.setdefault(order_id, {"created_at": now, "updated_at": now, "order_status": "robocze", "documents": [], "order_history": []})
    previous_header = record.get("order_header", {})
    record["order_header"], record["updated_at"] = order_header, now
    if previous_header != order_header:
        record.setdefault("order_history", []).append({
            "at": now, "action": "zaktualizowano nagłówek zlecenia", "by": user_name,
            "from": previous_header, "to": order_header,
        })
    save_registry(registry)
    return order_header


def update_production_summary(order_id: str, production_meta: dict[str, Any], items: list[dict[str, Any]], *,
                              load_registry: Callable[[], dict[str, Any]], save_registry: Callable[[dict[str, Any]], None],
                              user_name: str = "", saved_at: str | None = None) -> dict[str, Any]:
    totals = {
        "planned": sum(as_positive_int(item.get("production_planned", item.get("qty_production", 0))) for item in items),
        "made": sum(as_positive_int(item.get("production_made", 0)) for item in items),
        "waste": sum(as_positive_int(item.get("production_waste", 0)) for item in items),
    }
    registry, now = load_registry(), saved_at or datetime.now().isoformat(timespec="seconds")
    record = registry.setdefault(order_id, {"created_at": now, "updated_at": now, "documents": [], "order_history": []})
    summary, previous = record.setdefault("summary", {}), record.setdefault("summary", {}).get("production", {})
    summary["production"] = {**production_meta, **totals, "updated_at": now}
    record["updated_at"] = now
    if previous != summary["production"]:
        record.setdefault("order_history", []).append({"at": now, "action": "zaktualizowano wykonanie Karty Pracy", "by": user_name, "to": summary["production"]})
    save_registry(registry)
    return summary["production"]
