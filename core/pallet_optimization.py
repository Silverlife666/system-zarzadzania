"""Czysty algorytm porównywania wariantów paletyzacji."""

from __future__ import annotations

from math import ceil


def optimize_pallet_layout(*, carton_length, carton_width, carton_height, carton_mass, pallet, carton_quantity, max_height, max_weight, can_stack, can_rotate_vertical, layout_standard, layout_mixed, overhang_check, preferred_layout="Automatycznie najlepszy"):
    """Zwraca warianty, najlepszy układ i parametry masy bez zależności od Streamlit."""
    dimensions = [float(carton_length or 0), float(carton_width or 0), float(carton_height or 0), float(carton_mass or 0)]
    if min(dimensions) <= 0:
        raise ValueError("Wszystkie wymiary i masa kartonu muszą być większe od zera.")
    pallet = pallet or {}
    pallet_length, pallet_width, pallet_height = float(pallet.get("L", 0)), float(pallet.get("W", 0)), float(pallet.get("H", 0))
    pallet_weight = float(pallet.get("WEIGHT", 0) or 0)
    if min(pallet_length, pallet_width) <= 0:
        raise ValueError("Paleta musi mieć dodatnią długość i szerokość.")
    orientations = [
        ("Oryginalna", dimensions[0], dimensions[1], dimensions[2], False),
        ("Obrót 90°", dimensions[1], dimensions[0], dimensions[2], False),
        ("Mieszany / pionowy" if can_rotate_vertical else "Mieszany / zaawansowany", dimensions[0], dimensions[2] if can_rotate_vertical else dimensions[1], dimensions[1] if can_rotate_vertical else dimensions[2], True),
    ]
    variants = []
    for name, base_length, base_width, layer_height, advanced in orientations:
        layout = layout_mixed(pallet_length, pallet_width, base_length, base_width) if advanced else layout_standard(pallet_length, pallet_width, base_length, base_width)
        cartons_per_layer = len(layout)
        status, overhang = overhang_check(layout, pallet_length, pallet_width)
        height_layers = int(max(0, float(max_height) - pallet_height) // layer_height)
        weight_layers = int(max(0, float(max_weight) - pallet_weight) // (cartons_per_layer * dimensions[3])) if cartons_per_layer else 0
        full_layers = min(height_layers, weight_layers, 1 if not can_stack else 10**6)
        variants.append({"Nazwa": name, "Układ": layout, "Kartonów/warstwę": cartons_per_layer, "Pełnych warstw": full_layers, "Pojemność": cartons_per_layer * full_layers, "Status": status, "Wystawanie mm": round(float(overhang), 1), "Wysokość kartonu": layer_height})
    valid = [item for item in variants if item["Pojemność"] > 0]
    if not valid:
        raise ValueError("Żaden wariant nie spełnia jednocześnie ograniczeń wysokości i nośności.")
    if preferred_layout == "Oryginalnie":
        best = next((item for item in valid if item["Nazwa"] == "Oryginalna"), max(valid, key=lambda item: item["Pojemność"]))
    elif preferred_layout == "Obrót 90°":
        best = next((item for item in valid if item["Nazwa"] == "Obrót 90°"), max(valid, key=lambda item: item["Pojemność"]))
    else:
        best = max(valid, key=lambda item: item["Pojemność"])
    full_pallets, remainder = divmod(int(carton_quantity), best["Pojemność"])
    pallet_count = full_pallets + (1 if remainder else 0)
    last_cartons = remainder or best["Pojemność"]
    last_layers = int(ceil(last_cartons / best["Kartonów/warstwę"]))
    # Raport i wizualizacja dotyczą rzeczywiście ładowanej palety. Gdy zlecenie
    # nie wypełnia całej palety, nie wolno rysować ani mierzyć jej pojemności maksymalnej.
    report_cartons = best["Pojemność"] if full_pallets else last_cartons
    report_layers = best["Pełnych warstw"] if full_pallets else last_layers
    loaded_height = pallet_height + report_layers * best["Wysokość kartonu"]
    layout = best["Układ"]
    used_layout = layout[:min(report_cartons, len(layout))]
    cargo_length = max(item[0] + item[2] for item in used_layout) - min(item[0] for item in used_layout)
    cargo_width = max(item[1] + item[3] for item in used_layout) - min(item[1] for item in used_layout)
    cargo_dimensions = [round(cargo_length, 1), round(cargo_width, 1), round(report_layers * best["Wysokość kartonu"], 1)]
    gross_full = best["Pojemność"] * dimensions[3] + pallet_weight
    gross_last = last_cartons * dimensions[3] + pallet_weight
    gross_weight = gross_full if full_pallets else gross_last
    total_gross = full_pallets * gross_full + (gross_last if remainder else 0)
    footprint = best["Kartonów/warstwę"] * (dimensions[0] * dimensions[1]) / (pallet_length * pallet_width)
    stability = max(0, min(100, round(100 - max(0, loaded_height / min(pallet_length, pallet_width) - 1) * 55 - max(0, 1 - footprint) * 25)))
    warnings = []
    if loaded_height > float(max_height) or gross_weight > float(max_weight):
        warnings.append("Przekroczony limit wysokości lub nośności.")
    if best["Wystawanie mm"] > 0:
        warnings.append(f"Wykryto wystawanie poza obrys: {best['Wystawanie mm']} mm.")
    if stability < 60:
        warnings.append("Paleta wysoka lub niestabilna - wymagane dodatkowe zabezpieczenie.")
    return {"variants": variants, "best": best, "pallet_count": pallet_count, "last_cartons": last_cartons, "last_layers": last_layers, "report_cartons": report_cartons, "report_layers": report_layers, "cargo_dimensions": cargo_dimensions, "loaded_height": loaded_height, "gross_weight": gross_weight, "gross_last": gross_last, "total_gross_weight": total_gross, "stability": stability, "stability_text": "stabilna" if stability >= 80 else "wymaga zabezpieczenia" if stability >= 60 else "ryzykowna", "warnings": warnings}
