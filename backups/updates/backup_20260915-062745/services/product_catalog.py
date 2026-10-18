"""Pomocnicza logika kartoteki Produkt / Display / Master Case."""

from __future__ import annotations

from typing import Any


def normalize_product_record(data: dict[str, Any] | None) -> dict[str, Any]:
    """Ujednolica starsze i nowe kartoteki do Produkt / Display / Master Case."""
    data = dict(data or {})
    product = dict(data.get("Produkt") or {})
    display = dict(data.get("Display") or {})
    mastercase = dict(data.get("MasterCase") or {})
    product.setdefault("Dlugosc", data.get("Dlugosc", 0))
    product.setdefault("Szerokosc", data.get("Szerokosc", 0))
    product.setdefault("Wysokosc", data.get("Wysokosc", 0))
    if "Masa_netto_g" not in product:
        product["Masa_netto_g"] = float(product.get("Masa_netto_kg", data.get("Waga", 0)) or 0) * 1000
    product.setdefault("EAN", data.get("EAN", ""))
    display.setdefault("Pudelka_w_displayu", data.get("boxes_in_display", 1))
    # Od wersji 2 wagi displaya przechowujemy w gramach. Migrujemy stare rekordy
    # w pamięci; trwałą migrację wykonuje inicjalizacja bazy produktów.
    if "Masa_pustego_g" not in display and "Masa_pustego_kg" in display:
        display["Masa_pustego_g"] = float(display.get("Masa_pustego_kg") or 0) * 1000
    if "Masa_pelnego_g" not in display and "Masa_pelnego_kg" in display:
        display["Masa_pelnego_g"] = float(display.get("Masa_pelnego_kg") or 0) * 1000
    mastercase.setdefault("Dlugosc_zewnetrzna", data.get("Dlugosc", 0))
    mastercase.setdefault("Szerokosc_zewnetrzna", data.get("Szerokosc", 0))
    mastercase.setdefault("Wysokosc_zewnetrzna", data.get("Wysokosc", 0))
    mastercase.setdefault("Displayow_w_mastercase", data.get("displays_in_mc", 1))
    data["Produkt"], data["Display"], data["MasterCase"] = product, display, mastercase
    # Kompatybilność z kalkulatorami używającymi starszych pól płaskich.
    data["Dlugosc"] = product.get("Dlugosc", 0)
    data["Szerokosc"] = product.get("Szerokosc", 0)
    data["Wysokosc"] = product.get("Wysokosc", 0)
    data["Waga"] = float(product.get("Masa_netto_g", 0) or 0) / 1000
    data["EAN"] = product.get("EAN", "")
    return data


def product_ean_levels(data: dict[str, Any]) -> dict[str, str]:
    product = data.get("Produkt", {}) or {}
    display = data.get("Display", {}) or {}
    mastercase = data.get("MasterCase", {}) or {}
    values = {
        "Produkt": str(product.get("EAN", data.get("EAN Produkt", data.get("EAN", ""))) or "").strip(),
        "Display": str(display.get("EAN", data.get("EAN Display", "")) or "").strip(),
        "Master Case": str(mastercase.get("EAN", data.get("EAN Master Case", "")) or "").strip(),
    }
    return {level: ean for level, ean in values.items() if ean}


def build_catalog_snapshot(product_name: str, catalogue: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Tworzy trwały obraz Produkt / Display / Master Case dla dokumentów."""
    product_data = dict((catalogue or {}).get(product_name) or {})
    if not product_name or not product_data:
        return {}
    product = dict(product_data.get("Produkt") or {})
    display = dict(product_data.get("Display") or {})
    mastercase = dict(product_data.get("MasterCase") or {})
    product_view = {
        "Długość [mm]": product.get("Dlugosc", product_data.get("Dlugosc", "")),
        "Szerokość [mm]": product.get("Szerokosc", product_data.get("Szerokosc", "")),
        "Wysokość [mm]": product.get("Wysokosc", product_data.get("Wysokosc", "")),
        "Masa netto [g]": product.get("Masa_netto_g", ""),
        "EAN produktu": product.get("EAN", product_data.get("EAN", "")),
    }
    display_view = {
        "Długość [mm]": display.get("Dlugosc", ""), "Szerokość [mm]": display.get("Szerokosc", ""),
        "Wysokość [mm]": display.get("Wysokosc", ""), "Masa pustego displaya [g]": display.get("Masa_pustego_g", ""),
        "Masa pełnego displaya [g]": display.get("Masa_pelnego_g", ""), "EAN displaya": display.get("EAN", ""),
        "Pudełek w displayu": display.get("Pudelka_w_displayu", product_data.get("boxes_in_display", "")),
    }
    mastercase_view = {
        "Długość wewnętrzna [mm]": mastercase.get("Dlugosc_wewnetrzna", ""), "Szerokość wewnętrzna [mm]": mastercase.get("Szerokosc_wewnetrzna", ""),
        "Wysokość wewnętrzna [mm]": mastercase.get("Wysokosc_wewnetrzna", ""), "Długość zewnętrzna [mm]": mastercase.get("Dlugosc_zewnetrzna", ""),
        "Szerokość zewnętrzna [mm]": mastercase.get("Szerokosc_zewnetrzna", ""), "Wysokość zewnętrzna [mm]": mastercase.get("Wysokosc_zewnetrzna", ""),
        "Tara [kg]": mastercase.get("Tara_kg", ""), "Maks. masa brutto [kg]": mastercase.get("Masa_brutto_max_kg", ""),
        "EAN Master Case": mastercase.get("EAN", ""), "FEFCO": mastercase.get("FEFCO", ""),
        "Tektura / fala": " / ".join(str(value) for value in [mastercase.get("Tektura", ""), mastercase.get("Fala", "")] if value),
        "Displayów w Master Case": mastercase.get("Displayow_w_mastercase", product_data.get("displays_in_mc", "")),
    }
    return {
        "Nazwa produktu": product_name, "SKU": product_data.get("SKU", ""), "Klient": product_data.get("Klient", ""), "Producent": product_data.get("Producent", ""),
        "Produkt": product_view, "Display": display_view, "Master Case": mastercase_view,
        "Relacje pakowania": {"Sztuk w pudełku": product_data.get("pcs_in_box", ""), "Pudełek w displayu": display_view["Pudełek w displayu"], "Displayów w Master Case": mastercase_view["Displayów w Master Case"]},
        "Paleta": {"Domyślny typ palety": product_data.get("Typ_Palety", ""), "Limit wysokości [mm]": product_data.get("Max_Wysokosc", ""), "Limit masy [kg]": product_data.get("Max_Waga", "")},
    }


def ean_conflicts(product_name: str, data: dict[str, Any], catalogue: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    own = product_ean_levels(data)
    conflicts: dict[str, list[str]] = {}
    for existing_name, existing in catalogue.items():
        if existing_name == product_name:
            continue
        duplicated = sorted(set(own.values()) & set(product_ean_levels(existing).values()))
        if duplicated:
            conflicts[existing_name] = duplicated
    return conflicts
