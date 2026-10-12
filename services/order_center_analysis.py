"""Czyste kontrole jakości i przepływu danych dla Centrum zlecenia."""

from __future__ import annotations

from typing import Any, Callable


def end_to_end_checks(order_id: str, record: dict[str, Any], eorder_items: list[dict[str, Any]], requirements: list[str], checks: dict[str, bool], labels: dict[str, str], *, own_file: Callable[[str], bool], selected_ean: Callable[[dict[str, Any], str], str]) -> list[dict[str, str]]:
    """Zwraca czytelne scenariusze sprawdzające bez odczytu sesji i plików aplikacji."""
    record = record or {}
    header = record.get("order_header", {}) or {}
    results = [{
        "Scenariusz": "Nowe zlecenie i nagłówek", "Wynik": "OK" if header.get("order_number") else "BŁĄD",
        "Szczegóły": header.get("order_number") or "Brak numeru zlecenia w nagłówku.",
    }, {
        "Scenariusz": "Komplet dokumentów", "Wynik": "OK" if all(checks.get(key, False) for key in requirements) else "UWAGA",
        "Szczegóły": ", ".join(labels.get(key, key) for key in requirements if not checks.get(key, False)) or "Komplet zgodny z checklistą.",
    }]
    if record.get("source_order_id"):
        foreign = [item.get("file_path", "") for item in record.get("documents", []) if item.get("file_path") and not own_file(item["file_path"])]
        results.append({
            "Scenariusz": "Reprint nie współdzieli plików z oryginałem", "Wynik": "OK" if not foreign else "BŁĄD",
            "Szczegóły": "PDF-y są własne albo wymagają wygenerowania." if not foreign else "Wykryto obcą ścieżkę PDF.",
        })
    if eorder_items:
        invalid = []
        for index, item in enumerate(eorder_items, start=1):
            snapshot = item.get("catalog_snapshot", {}) or {}
            expected = selected_ean(snapshot, item.get("packaging_level", "Produkt")) if snapshot else ""
            if expected and item.get("ean_selected") != expected:
                invalid.append(str(index))
        results.append({
            "Scenariusz": "Wiele pozycji i EAN poziomu opakowania", "Wynik": "OK" if not invalid else "BŁĄD",
            "Szczegóły": f"Pozycji E-Order: {len(eorder_items)}." if not invalid else "Błędny EAN w pozycjach: " + ", ".join(invalid),
        })
    return results


def order_data_quality(record: dict[str, Any], context: dict[str, Any], *, selected_ean: Callable[[dict[str, Any], str], str], positive_int: Callable[[Any], int], file_exists: Callable[[str], bool]) -> list[dict[str, str]]:
    """Wyszukuje braki danych między E-Order, Packing List, BCT i dokumentami."""
    record, context = record or {}, context or {}
    header = record.get("order_header", {}) or context.get("tab9_order_header", {}) or {}
    issues: list[dict[str, str]] = []
    def add(area: str, severity: str, message: str, fix: str) -> None:
        issues.append({"Obszar": area, "Poziom": severity, "Problem": message, "Zalecenie": fix})
    if not header.get("order_number"):
        add("Nagłówek", "BŁĄD", "Brak numeru zamówienia.", "Otwórz moduł 9 i zapisz nagłówek zlecenia.")
    if not header.get("delivery_date"):
        add("Nagłówek", "UWAGA", "Brak planowanej daty dostawy.", "Uzupełnij termin w module 9 lub E-Order.")
    snapshot = record.get("shared_snapshot", {}) or context.get("order_snapshot", {}) or {}
    expected_sections = {"paletyzacja", "packing_list", "tds", "eorder", "karta_pracy"}
    for section in sorted(expected_sections - set((snapshot.get("sections", {}) or {}).keys())):
        add("Integracje", "INFO", f"Brak migawki: {section}.", "Nie jest to błąd, jeżeli moduł nie jest potrzebny; zapisz dane w odpowiednim module, aby je połączyć.")
    packing = context.get("packing_document", {}) or {}
    for index, item in enumerate(packing.get("items", []), start=1):
        level = item.get("Poziom opakowania", "")
        expected = {"Produkt": item.get("EAN produktu", ""), "Display": item.get("EAN displaya", ""), "Master Case": item.get("EAN Master Case", "")}.get(level, "")
        if level not in {"Produkt", "Display", "Master Case"}:
            add("Packing List", "BŁĄD", f"Pozycja {index} nie ma prawidłowego poziomu opakowania.", "Wybierz Produkt, Display lub Master Case.")
        elif expected and str(item.get("EAN/GTIN", "")) != str(expected):
            add("Packing List", "BŁĄD", f"Pozycja {index} ma EAN niezgodny z poziomem {level}.", "Przywróć EAN z kartoteki dla wybranego poziomu.")
        if not str(item.get("LOT", "")).strip():
            add("Packing List", "UWAGA", f"Pozycja {index} nie ma numeru LOT.", "Uzupełnij numer partii przed wysyłką.")
    for index, item in enumerate(context.get("e_order_items", []) or [], start=1):
        snapshot_item = item.get("catalog_snapshot", {}) or {}
        expected = selected_ean(snapshot_item, item.get("packaging_level", "Produkt")) if snapshot_item else ""
        if expected and item.get("ean_selected") != expected:
            add("E-Order", "BŁĄD", f"Pozycja {index} używa niewłaściwego EAN.", "Wybierz EAN zgodny z poziomem opakowania.")
        if positive_int(item.get("qty_shipping", item.get("qty_net", 0))) <= 0:
            add("E-Order", "BŁĄD", f"Pozycja {index} ma ilość wysyłki równą zero.", "Uzupełnij ilość netto lub wysyłki.")
    bct = context.get("bct_last_result", {}) or {}
    if bct and bct.get("approval") != "zatwierdzony":
        add("BCT", "UWAGA", f"BCT ma status: {bct.get('approval', 'brak')}.", "Zatwierdź konstrukcję przed produkcją lub wysyłką.")
    for document in record.get("documents", []):
        path = document.get("file_path", "")
        if path and not file_exists(path):
            add("Dokumenty", "BŁĄD", f"Brak pliku na dysku: {document.get('type', 'Dokument')}.", "Wygeneruj dokument ponownie albo popraw ścieżkę.")
    return issues


def order_flow_map(snapshot: dict[str, Any], documents: list[dict[str, Any]], bct_result: dict[str, Any]) -> list[dict[str, str]]:
    """Buduje małą mapę, pokazującą które etapy procesu mają zapisane dane."""
    sections = set(((snapshot or {}).get("sections", {}) or {}).keys())
    document_names = [str(item.get("type", "")).lower() for item in (documents or [])]
    return [
        {"Etap": "Baza Produkt / Display / Master Case", "Status": "✅" if sections & {"tds", "paletyzacja", "mastercase"} else "⏳", "Źródło / wynik": "Kartoteka, TDS lub wynik Box Rightsizing"},
        {"Etap": "Paletyzacja / Box Rightsizing", "Status": "✅" if "paletyzacja" in sections else "⏳", "Źródło / wynik": "Palety, masa, LDM"},
        {"Etap": "BCT", "Status": "✅" if bct_result else "⏳", "Źródło / wynik": "Wytrzymałość i limit warstw"},
        {"Etap": "TDS / E-Order / Karta Pracy", "Status": "✅" if sections & {"tds", "eorder", "karta_pracy"} else "⏳", "Źródło / wynik": "Specyfikacja i produkcja"},
        {"Etap": "Packing List / Transport", "Status": "✅" if "packing_list" in sections or "transport" in sections or "zlecenie transportowe" in document_names else "⏳", "Źródło / wynik": "Palety, odbiorca i dostawa"},
        {"Etap": "PPWR / QA / E-mail", "Status": "✅" if any("ppwr" in item or "qa" in item for item in document_names) else "⏳", "Źródło / wynik": "Zgodność, kontrola i wysyłka"},
    ]
