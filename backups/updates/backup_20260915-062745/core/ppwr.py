"""Niezależne od Streamlit obliczenia masy komponentów PPWR."""


PPWR_PACKAGING_FLAG = "Uwzględniać jako opakowanie PPWR"
NUMERIC_COLUMNS = ("Masa jednostkowa (g)", "Ilość / 1 SKU", "Ilość / 1 paletę")


def _number(value):
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _included(value):
    """Rozpoznaje flagę również po odczycie ze starszego pliku/CSV."""
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "nie", "no", "off"}
    return value is not False


def migrate_legacy_order_units(order_units, display_count, units_per_display):
    """Naprawia historyczny zapis, w którym liczbę displayów wpisano jako SKU.

    Zwraca ``(liczba_sku, czy_poprawiono)``. Migracja jest celowo wąska: działa
    wyłącznie, gdy zapisana liczba dokładnie odpowiada sumie displayów, a jeden
    display zawiera więcej niż jedną sztukę. Dzięki temu nie zmienia ręcznie
    wprowadzonych, faktycznych ilości SKU.
    """
    stored_units = _number(order_units)
    displays = _number(display_count)
    per_display = _number(units_per_display)
    if displays and per_display > 1 and stored_units == displays:
        return int(displays * per_display), True
    return int(stored_units), False


def calculate_ppwr_masses(records, units_per_pallet, pallets_per_order, packaging_flag=PPWR_PACKAGING_FLAG, units_per_order=None):
    """Normalizuje komponenty, pomija nieopakowania i sumuje masy PPWR.

    Brak flagi w starym rekordzie oznacza *uwzględniaj*, aby migracja nie
    zmieniała wcześniejszych kalkulacji.
    """
    units_per_pallet = _number(units_per_pallet)
    pallets_per_order = _number(pallets_per_order)
    units_per_order = _number(units_per_order)
    all_components, components = [], []
    redundant_pallet_quantities = []
    for raw in records or []:
        row = dict(raw or {})
        row[packaging_flag] = _included(row.get(packaging_flag, True))
        for column in NUMERIC_COLUMNS:
            row[column] = _number(row.get(column, 0))
        # Ta sama ilość nie może być podana równocześnie na SKU i na paletę.
        # Przykład: 1 kartonik/SKU przy 20 736 SKU/paletę już oznacza 20 736
        # kartoników/paletę. Drugi wpis 20 736 byłby podwójnym liczeniem.
        per_sku = row["Ilość / 1 SKU"]
        per_pallet = row["Ilość / 1 paletę"]
        if units_per_pallet and per_sku and per_pallet == per_sku * units_per_pallet:
            component_name = str(row.get("Komponent opakowania", "komponent") or "komponent")
            redundant_pallet_quantities.append(component_name)
            row["Ilość / 1 paletę"] = 0.0
            correction_note = "Automatycznie pominięto redundantną ilość / paletę (jest już ujęta w ilości / SKU)."
            prior_note = str(row.get("Kolor / druk / uwagi", "") or "").strip()
            row["Kolor / druk / uwagi"] = f"{prior_note} {correction_note}".strip()
        if units_per_pallet:
            mass_per_sku = row["Masa jednostkowa (g)"] * (
                row["Ilość / 1 SKU"] + row["Ilość / 1 paletę"] / units_per_pallet
            )
        else:
            mass_per_sku = row["Masa jednostkowa (g)"] * row["Ilość / 1 SKU"]
        row["Masa / 1 SKU (g)"] = mass_per_sku
        row["Masa / 1 paletę (kg)"] = mass_per_sku * units_per_pallet / 1000
        if units_per_order:
            # Komponenty jednostkowe liczymy od faktycznej liczby SKU, a elementy
            # transportowe (np. paleta, folia, etykieta paletowa) od liczby palet.
            row["Masa / zamówienie (kg)"] = row["Masa jednostkowa (g)"] * (
                row["Ilość / 1 SKU"] * units_per_order + row["Ilość / 1 paletę"] * pallets_per_order
            ) / 1000
        else:
            # Zgodność ze starszymi zleceniami bez podanej dokładnej liczby SKU.
            row["Masa / zamówienie (kg)"] = row["Masa / 1 paletę (kg)"] * pallets_per_order
        all_components.append(row)
        if row[packaging_flag]:
            components.append(row)

    totals = {
        "total_sku_g": sum(item["Masa / 1 SKU (g)"] for item in components),
        "total_pallet_kg": sum(item["Masa / 1 paletę (kg)"] for item in components),
        "total_order_kg": sum(item["Masa / zamówienie (kg)"] for item in components),
    }
    materials = {}
    for item in components:
        material = str(item.get("Materiał główny", "") or "Nieokreślony")
        bucket = materials.setdefault(material, {
            "Materiał główny": material, "Masa / 1 SKU (g)": 0.0,
            "Masa / 1 paletę (kg)": 0.0, "Masa / zamówienie (kg)": 0.0,
        })
        for column in ("Masa / 1 SKU (g)", "Masa / 1 paletę (kg)", "Masa / zamówienie (kg)"):
            bucket[column] += item[column]
    material_summary = []
    for item in materials.values():
        item["Udział / 1 SKU (%)"] = item["Masa / 1 SKU (g)"] / totals["total_sku_g"] * 100 if totals["total_sku_g"] else 0
        item["Udział / 1 paleta (%)"] = item["Masa / 1 paletę (kg)"] / totals["total_pallet_kg"] * 100 if totals["total_pallet_kg"] else 0
        item["Udział / zamówienie (%)"] = item["Masa / zamówienie (kg)"] / totals["total_order_kg"] * 100 if totals["total_order_kg"] else 0
        material_summary.append(item)
    return {
        "all_components": all_components,
        "components": components,
        "excluded_components_count": len(all_components) - len(components),
        "redundant_pallet_quantities": redundant_pallet_quantities,
        "units_per_order": units_per_order,
        "material_summary": material_summary,
        **totals,
    }
