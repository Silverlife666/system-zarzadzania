"""Ekran Streamlit generatora zleceń transportowych.

Plik nie importuje app.py: zależności trwałego zapisu są przekazywane przez router.
"""

from __future__ import annotations

from datetime import datetime
import json


def render_transport_screen(st, *, pandas, pallet_types, generate_pdf, get_current_order_id, load_archive, save_archive, update_snapshot, save_order_context):
    """Renderuje moduł transportowy i zapisuje dane przy aktywnym order_id."""
    st.subheader("📝 Generator Opisów i Zleceń Transportowych")
    st.markdown("Szybko przygotuj uporządkowane dane do systemu **Raben (`myRaben` / awizacja)** lub gotowy opis zlecenia na **Clicktrans**.")
    transport_result = st.session_state.get("transport_prefill", {})

    def number(value, default=0.0):
        try:
            return float(value or default)
        except (TypeError, ValueError):
            return float(default)

    dimensions = transport_result.get("Wymiary palety mm", []) if isinstance(transport_result, dict) else []
    if not isinstance(dimensions, (list, tuple)) or len(dimensions) < 3:
        pallet_name = str(transport_result.get("Paleta", "")).upper()
        pallet_data = next((data for name, data in pallet_types.items() if name in pallet_name or pallet_name in name), pallet_types["EURO"])
        dimensions = [pallet_data["L"], pallet_data["W"], number(transport_result.get("Wysokość palety mm"), 1600)]
    prefill_quantity = max(1, int(number(transport_result.get("Liczba palet"), 1)))
    prefill_weight = number(transport_result.get("Masa brutto całkowita kg"), 0)
    if prefill_weight <= 0:
        prefill_weight = number(transport_result.get("Masa brutto/paleta kg"), 100) * prefill_quantity
    signature = json.dumps({"order_id": transport_result.get("order_id", ""), "pallet": transport_result.get("Paleta", ""), "qty": prefill_quantity, "weight": prefill_weight, "dimensions": list(dimensions[:3])}, sort_keys=True)
    if transport_result and st.session_state.get("_transport_prefill_signature") != signature:
        st.session_state.update({"gen_qty": prefill_quantity, "gen_weight": prefill_weight, "gen_len": max(10.0, number(dimensions[0]) / 10), "gen_wid": max(10.0, number(dimensions[1]) / 10), "gen_hei": max(10.0, number(dimensions[2]) / 10), "_transport_prefill_signature": signature})
    if transport_result:
        st.success(f"Załadowano dane z paletyzacji: {transport_result.get('Produkt', '')} — {number(dimensions[0]):.0f} × {number(dimensions[1]):.0f} × {number(dimensions[2]):.0f} mm.")

    carrier = st.radio("Wybierz platformę docelową:", ["Raben (myRaben / Awizacja)", "Clicktrans (Giełda transportowa)"], horizontal=True, key="gen_carrier_choice")
    left, right = st.columns(2)
    with left:
        cargo_type = st.selectbox("Rodzaj ładunku", ["Palety EUR (1200x800)", "Palety Przemysłowe (1200x1000)", "Karton / Opakowania zbiorcze", "Towar niestandardowy"], key="gen_cargo_type")
        quantity = st.number_input("Liczba sztuk / palet", min_value=1, value=prefill_quantity, step=1, key="gen_qty")
        total_weight = st.number_input("Waga brutto całkowita (kg)", min_value=0.1, value=prefill_weight, step=10.0, key="gen_weight")
    with right:
        length_cm = st.number_input("Długość 1 sztuki / palety (cm)", min_value=10.0, value=number(dimensions[0], 1200) / 10, key="gen_len")
        width_cm = st.number_input("Szerokość 1 sztuki / palety (cm)", min_value=10.0, value=number(dimensions[1], 800) / 10, key="gen_wid")
        height_cm = st.number_input("Wysokość całkowita ładunku (cm)", min_value=10.0, value=number(dimensions[2], 1600) / 10, key="gen_hei")
    st.markdown("#### Wymagania i uwagi specjalne:")
    requirement_columns = st.columns(3)
    with requirement_columns[0]:
        tail_lift = st.checkbox("Wymagana winda (Tail lift)", value=False, key="gen_lift")
    with requirement_columns[1]:
        no_stacking = st.checkbox("Nie piętrować (Do not stack)", value=True, key="gen_nostack")
    with requirement_columns[2]:
        phone_notice = st.checkbox("Awizacja telefoniczna przed dostawą", value=True, key="gen_phone")
    notes = st.text_area("Dodatkowe uwagi dla kierowcy / przewoźnika", value="Proszę o kontakt telefoniczny przed dostawą. Towar wymaga ostrożnego rozładunku.", key="gen_notes")
    st.markdown("---")
    ldm = (length_cm * width_cm * quantity) / 24000.0
    if carrier.startswith("Raben"):
        st.markdown("### 📋 Podsumowanie danych do systemu myRaben / Awizacji:")
        st.info("Skopiuj poniższe dane bezpośrednio do formularza awizacji lub systemu bookingowego Rabena.")
        content = f"""DANE DO ZLECENIA / AWIZACJI (RABEN):
- Rodzaj ładunku: {cargo_type} x {quantity} szt.
- Waga brutto łączna: {total_weight} kg
- Wymiary 1 sztuki: {length_cm} x {width_cm} x {height_cm} cm
- Szacowane metry ładunkowe (LDM): {ldm:.2f} LDM
- Wymagania:
  * Winda samochodowa: {'TAK' if tail_lift else 'NIE'}
  * Piętrowanie: {'ZABRONIONE (Nie piętrować)' if no_stacking else 'Dozwolone'}
  * Awizacja telefoniczna: {'TAK' if phone_notice else 'NIE'}
- Uwagi: {notes}"""
    else:
        st.markdown("### 📋 Gotowy opis zlecenia do wklejenia na Clicktrans:")
        st.info("Gotowy tekst idealny do skopiowania przy wystawianiu zapytania lub aukcji transportowej.")
        content = f"""Dzień dobry,
Zlecę transport następującego ładunku:
- Rodzaj i ilość: {quantity}x {cargo_type}
- Wymiary sztuki/palety: {length_cm} x {width_cm} x {height_cm} cm
- Łączna waga brutto: {total_weight} kg

Szczegóły i wymagania:
- Załadunek / Rozładunek: {'Wymagana winda samochodowa (brak rampy)' if tail_lift else 'Standardowy załadunek / rozładunek'}
- {'Towar wrażliwy na nacisk - ABSOLUTNIE NIE PIĘTROWAC!' if no_stacking else ''}
- {'Wymagany kontakt telefoniczny przed realizacją.' if phone_notice else ''}

Dodatkowe informacje: {notes}

Proszę o oferty z uwzględnieniem powyższych parametrów."""
    st.code(content, language="text")
    order_id = get_current_order_id()
    document = {"order_id": order_id, "number": f"TR/{datetime.now().strftime('%Y')}/{order_id.replace('ORD-', '')}", "saved_at": datetime.now().isoformat(timespec="seconds"), "carrier": carrier, "cargo_type": cargo_type, "quantity": int(quantity), "total_weight": float(total_weight), "dimensions_cm": [float(length_cm), float(width_cm), float(height_cm)], "pallet_type": transport_result.get("Paleta", ""), "ldm": round(ldm, 2), "requirements": {"tail_lift": tail_lift, "no_stacking": no_stacking, "phone_notice": phone_notice}, "notes": notes, "content": content, "status": "robocze"}
    st.session_state["transport_document"] = document
    pdf_key = f"transport_pdf_{order_id}_{document['number']}"
    actions = st.columns(3)
    with actions[0]:
        if st.button("💾 Zapisz zlecenie transportowe do archiwum"):
            archive = [item for item in load_archive() if not (item.get("order_id") == order_id and item.get("number") == document["number"])]
            archive.append(document)
            save_archive(archive)
            st.session_state[pdf_key] = generate_pdf(document, save_to_order=True)
            update_snapshot("transport", document, order_id)
            save_order_context(order_id)
            st.success("Zlecenie transportowe i jego PDF zapisano dla aktywnego zlecenia.")
    with actions[1]:
        st.download_button("⬇️ Pobierz opis transportu TXT", content.encode("utf-8"), file_name=f"zlecenie_transportowe_{order_id}.txt", mime="text/plain")
    with actions[2]:
        if st.button("📄 Przygotuj PDF zlecenia", key="transport_pdf_generate"):
            st.session_state[pdf_key] = generate_pdf(document, save_to_order=True)
            st.success("PDF przygotowano i zapisano w Centrum zlecenia.")
        if st.session_state.get(pdf_key):
            st.download_button("⬇️ Pobierz PDF", st.session_state[pdf_key], file_name=f"zlecenie_transportowe_{document['number'].replace('/', '_')}.pdf", mime="application/pdf", key="transport_pdf_download")
    with st.expander("📚 Archiwum zleceń transportowych tego zlecenia", expanded=False):
        order_archive = [item for item in load_archive() if item.get("order_id") == order_id]
        if order_archive:
            st.dataframe(pandas.DataFrame([{key: item.get(key, "") for key in ("number", "saved_at", "carrier", "quantity", "total_weight", "ldm", "status")} for item in order_archive]), width="stretch", hide_index=True)
            selected = st.selectbox("Zapisane zlecenie", [item["number"] for item in order_archive], key="transport_archive_choice")
            selected_record = next(item for item in order_archive if item["number"] == selected)
            st.download_button("⬇️ Pobierz zapisany opis", selected_record.get("content", "").encode("utf-8"), file_name=f"{selected}.txt".replace("/", "_"), mime="text/plain", key="transport_archive_download")
            archived_pdf = generate_pdf(selected_record, save_to_order=False)
            st.download_button("⬇️ Pobierz PDF archiwalnego zlecenia", archived_pdf, file_name=f"{selected}.pdf".replace("/", "_"), mime="application/pdf", key="transport_archive_pdf_download")
        else:
            st.info("Brak zapisanych zleceń transportowych dla tego order_id.")
