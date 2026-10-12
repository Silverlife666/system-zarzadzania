"""Czyste reguły wspólne dla dokumentów produkcyjnych (moduł 9).

Moduł nie zależy od Streamlit ani od generatorów PDF, dlatego może być objęty
testami regresji niezależnie od interfejsu.
"""

from math import ceil


def as_positive_int(value, default=0):
    """Konwertuje wartość formularza na nieujemną liczbę całkowitą."""
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def selected_ean(snapshot, packaging_level):
    """Dobiera EAN odpowiadający poziomowi Produkt / Display / Master Case."""
    snapshot = snapshot or {}
    levels = {
        "Produkt": snapshot.get("Produkt", {}).get("EAN produktu", ""),
        "Display": snapshot.get("Display", {}).get("EAN displaya", ""),
        "Master Case": snapshot.get("Master Case", {}).get("EAN Master Case", ""),
    }
    return str(levels.get(packaging_level, "") or "")


def default_order_header(order_id):
    """Tworzy spójny nagłówek nowego zlecenia."""
    return {
        "order_id": order_id,
        "order_number": order_id,
        "priority": "normalny",
        "document_status": "robocze",
        "language": "PL",
        "document_version": "v1",
        "delivery_date": "",
        "recipient": {},
        "delivery_address": {},
        "change_reason": "",
    }


def order_header_pdf_fields(order_header):
    """Zwraca pola nagłówka używane jednolicie w dokumentach PDF."""
    order_header = order_header or {}
    return {
        "Order ID": order_header.get("order_id", ""),
        "Numer zlecenia": order_header.get("order_number", ""),
        "Priorytet": order_header.get("priority", ""),
        "Status dokumentu": order_header.get("document_status", ""),
        "Język dokumentu": order_header.get("language", ""),
        "Wersja dokumentu": order_header.get("document_version", ""),
        "Planowana data dostawy": order_header.get("delivery_date", "") or "—",
        "Powód zmiany": order_header.get("change_reason", "") or "—",
    }


def validate_base_data(
    product_name, client, quantity, delivery_date="", require_client=True,
    require_delivery=False, location="Formularz", quantity_field="Ilość netto",
):
    """Waliduje podstawową pozycję i zwraca komunikaty ze wskazaniem pola."""
    errors = []
    prefix = f"{location} → " if location else ""
    if not str(product_name or "").strip():
        errors.append(prefix + "pole „Nazwa produktu” jest wymagane.")
    if require_client and not str(client or "").strip():
        errors.append(prefix + "pole „Klient / odbiorca” jest wymagane.")
    if as_positive_int(quantity) <= 0:
        errors.append(prefix + f"pole „{quantity_field}” musi być większe od zera.")
    if require_delivery and not str(delivery_date or "").strip():
        errors.append(prefix + "pole „Planowana data dostawy” jest wymagane.")
    return errors


def packaging_calculation(snapshot, packaging_level, quantity, cartons_per_pallet=0):
    """Przelicza ilość pozycji na Produkt, Display, Master Case i palety."""
    relations = (snapshot or {}).get("Relacje pakowania", {})
    pcs_per_box = max(1, as_positive_int(relations.get("Sztuk w pudełku"), 1))
    boxes_per_display = max(1, as_positive_int(relations.get("Pudełek w displayu"), 1))
    displays_per_mastercase = max(1, as_positive_int(relations.get("Displayów w Master Case"), 1))
    products_per_display = pcs_per_box * boxes_per_display
    products_per_mastercase = products_per_display * displays_per_mastercase
    factors = {"Produkt": 1, "Display": products_per_display, "Master Case": products_per_mastercase}
    product_equivalent = as_positive_int(quantity) * factors.get(packaging_level, 1)
    display_count = ceil(product_equivalent / products_per_display) if product_equivalent else 0
    mastercase_count = ceil(product_equivalent / products_per_mastercase) if product_equivalent else 0
    cartons_per_pallet = as_positive_int(cartons_per_pallet)
    pallet_count = ceil(mastercase_count / cartons_per_pallet) if cartons_per_pallet and mastercase_count else 0
    return {
        "sztuk_w_pudelku": pcs_per_box,
        "pudelek_w_displayu": boxes_per_display,
        "displayow_w_mastercase": displays_per_mastercase,
        "produktow_w_displayu": products_per_display,
        "produktow_w_mastercase": products_per_mastercase,
        "ilosc_ekwiwalent_produktu": product_equivalent,
        "displayow": display_count,
        "mastercase": mastercase_count,
        "kartonow_na_palecie": cartons_per_pallet,
        "palet": pallet_count,
    }


def packaging_pdf_fields(calculation):
    """Formatuje pola przelicznika do wspólnej sekcji w PDF."""
    return {
        "Sztuk w pudełku": calculation["sztuk_w_pudelku"],
        "Produktów w displayu": calculation["produktow_w_displayu"],
        "Produktów w Master Case": calculation["produktow_w_mastercase"],
        "Ilość na palecie": calculation["ilosc_ekwiwalent_produktu"],
        "Przeliczone displaye": calculation["displayow"],
        "Przeliczone Master Case": calculation["mastercase"],
        "Kartony na palecie": calculation["kartonow_na_palecie"] or "—",
        "Przeliczone palety": calculation["palet"] if calculation["kartonow_na_palecie"] else "—",
    }
