"""Rozwijalny diagram procesu pakowania dla raportu PPWR."""
import base64
from xml.sax.saxutils import escape

import pandas as pd



def render_ppwr_packing_diagram(st, ppwr_positions, order, get_current_order_id, canonical_column_name):
    """Wyświetla dynamiczny schemat pakowania zbudowany z pozycji bieżącego PPWR."""
    if isinstance(ppwr_positions, pd.DataFrame):
        positions = ppwr_positions.to_dict(orient="records")
    else:
        positions = list(ppwr_positions or [])
    if not positions:
        return

    active_order_id = str((order or {}).get("order_id") or get_current_order_id())
    image_state_key = f"ppwr_diagram_images_{active_order_id}"
    diagram_images = st.session_state.setdefault(image_state_key, {})
    step_state_key = f"ppwr_diagram_steps_{active_order_id}"
    diagram_steps = st.session_state.setdefault(step_state_key, {})

    def component_name(position):
        return str(position.get("Komponent opakowania") or "Pozycja PPWR").strip()

    def component_type(name):
        normalized = canonical_column_name(name)
        type_rules = (
            ("etykieta", ("etykiet", "label")),
            ("display", ("display",)),
            ("karton", ("karton", "box", "master case", "mastercase")),
            ("paleta", ("palet", "pallet")),
            ("folia_stretch", ("stretch",)),
            ("folia", ("folia", "film")),
            ("tasma", ("tasma", "tape")),
            ("narozniki", ("naroznik", "corner")),
            ("przekladka", ("przeklad", "separator")),
        )
        for type_name, tokens in type_rules:
            if any(token in normalized for token in tokens):
                return type_name
        return normalized or "pozostale"

    image_types = []
    for position in positions:
        detected_type = component_type(component_name(position))
        if detected_type != "etykieta" and detected_type not in image_types:
            image_types.append(detected_type)

    with st.expander("🖼️ Obrazy elementów diagramu", expanded=False):
        st.caption(
            "Dodaj jeden obraz dla danego typu komponentu. Zostanie użyty we wszystkich "
            "odpowiadających mu pozycjach bieżącego PPWR."
        )
        for image_type in image_types:
            uploaded_image = st.file_uploader(
                f"Obraz: {image_type.replace('_', ' ')}",
                type=["png", "jpg", "jpeg", "gif", "webp"],
                key=f"ppwr_diagram_upload_{active_order_id}_{image_type}",
            )
            if uploaded_image is not None:
                diagram_images[image_type] = {
                    "bytes": uploaded_image.getvalue(),
                    "name": uploaded_image.name,
                }

    with st.expander("📷 Zdjęcia kolejnych etapów procesu", expanded=False):
        st.caption(
            "Do raportu PDF każde zdjęcie jest przypisane do konkretnego etapu, tak jak w diagramie procesu. "
            "Starsze zdjęcia według typu komponentu pozostają jako rozwiązanie zapasowe."
        )
        for number, position in enumerate(positions[:24], start=1):
            name = component_name(position)
            uploaded_step_image = st.file_uploader(
                f"Etap {number:02d}: {name}", type=["png", "jpg", "jpeg", "webp"],
                key=f"ppwr_diagram_step_upload_{active_order_id}_{number}",
            )
            if uploaded_step_image is not None:
                diagram_steps[str(number)] = {
                    "bytes": uploaded_step_image.getvalue(),
                    "name": uploaded_step_image.name,
                }
            elif str(number) not in diagram_steps and component_type(name) in diagram_images:
                diagram_steps[str(number)] = diagram_images[component_type(name)]
        if len(positions) > 24:
            st.info("Dalsze etapy także trafią do kolejnych stron PDF; dla etapów powyżej 24 można na razie użyć zdjęć przypisanych według typu komponentu.")

    order_header = (order or {}).get("order_header", {}) or {}
    order_number = str(
        order_header.get("order_number")
        or (order or {}).get("order_number")
        or active_order_id
        or "—"
    )
    product_name = str(
        (order or {}).get("product_name")
        or (order or {}).get("Produkt")
        or st.session_state.get("ppwr_product_name")
        or "—"
    )
    sku = str(
        (order or {}).get("sku")
        or (order or {}).get("EAN")
        or st.session_state.get("ppwr_sku")
        or "—"
    )

    def render_position_card(position, diagram_index, ppwr_number):
        name = component_name(position)
        detected_type = component_type(name)
        material = str(position.get("Materiał główny") or "Materiał nieokreślony").strip()
        if detected_type == "etykieta":
            visual = f"""
                <div style="height:162px;border:1px solid #bfdbfe;border-radius:10px;overflow:hidden;background:#fff">
                  <div style="background:#123b69;color:#fff;font-size:12px;font-weight:800;letter-spacing:.08em;padding:10px 12px">ETYKIETA ZLECENIA</div>
                  <div style="padding:12px;color:#0f172a;line-height:1.35">
                    <div style="font-size:10px;color:#64748b">NR ZLECENIA</div><div style="font-size:13px;font-weight:800">{escape(order_number)}</div>
                    <div style="font-size:10px;color:#64748b;margin-top:7px">PRODUKT</div><div style="font-size:13px;font-weight:800">{escape(product_name)}</div>
                    <div style="font-size:10px;color:#64748b;margin-top:7px">SKU / EAN: <b>{escape(sku)}</b></div>
                  </div>
                </div>"""
        elif str(diagram_index) in diagram_steps or detected_type in diagram_images:
            image = diagram_steps.get(str(diagram_index), diagram_images.get(detected_type, {}))
            image_name = str(image.get("name", "")).lower()
            image_type = "image/png" if image_name.endswith(".png") else "image/webp" if image_name.endswith(".webp") else "image/jpeg"
            encoded_image = base64.b64encode(image["bytes"]).decode("ascii")
            visual = f"<div style='height:162px;border-radius:10px;overflow:hidden;background:#f8fafc'><img src='data:{image_type};base64,{encoded_image}' style='width:100%;height:162px;object-fit:contain;display:block'></div>"
        else:
            visual = "<div style='height:162px;border:1px dashed #94a3b8;border-radius:10px;display:flex;align-items:center;justify-content:center;background:#f8fafc;color:#64748b;font-size:13px'>Dodaj zdjęcie w sekcji powyżej</div>"
        stage_title = f"ETAP {ppwr_number:02d}" if ppwr_number is not None else "POZA PPWR"
        stage_kind = "PPWR" if ppwr_number is not None else "TOWAR / PRZESYŁKA"
        stage_color = "#123b69" if ppwr_number is not None else "#7c2d12"
        st.markdown(
            f"""
            <div style="border:1px solid #cbd5e1;border-radius:14px;overflow:hidden;background:#fff;box-shadow:0 2px 8px rgba(15,23,42,.08);margin-bottom:6px">
              <div style="display:flex;justify-content:space-between;align-items:center;background:{stage_color};color:#fff;padding:9px 12px">
                <span style="font-size:11px;font-weight:700;letter-spacing:.08em">{stage_title}</span><span style="font-size:11px;opacity:.85">{stage_kind}</span>
              </div>
              <div style="padding:10px">{visual}
                <div style="font-size:15px;font-weight:800;color:#0f172a;line-height:1.25;margin:12px 0 8px">{escape(name)}</div>
                <span style="display:inline-block;border-radius:999px;background:#e8f0f8;color:#123b69;padding:4px 8px;font-size:11px;font-weight:700">{escape(material)}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("## Diagram pakowania PPWR")
    st.caption(f"Schemat dla zlecenia {order_number}. Pozycje poza PPWR pozostają w przebiegu, lecz nie dostają numeru etapu.")
    visual_positions = []
    ppwr_number = 0
    for diagram_index, position in enumerate(positions, start=1):
        included = position.get("Uwzględniać jako opakowanie PPWR", True)
        if isinstance(included, str):
            included = included.strip().lower() not in {"false", "0", "nie", "no", "off"}
        if included is not False:
            ppwr_number += 1
            visual_positions.append((position, diagram_index, ppwr_number))
        else:
            visual_positions.append((position, diagram_index, None))
    cards_per_row = 4
    for row_start in range(0, len(visual_positions), cards_per_row):
        row = visual_positions[row_start:row_start + cards_per_row]
        column_widths = []
        for index in range(len(row)):
            column_widths.append(5)
            if index < len(row) - 1:
                column_widths.append(1)
        columns = st.columns(column_widths, vertical_alignment="center")
        column_index = 0
        for offset, (position, diagram_index, ppwr_number) in enumerate(row):
            with columns[column_index]:
                render_position_card(position, diagram_index, ppwr_number)
            column_index += 1
            if offset < len(row) - 1:
                columns[column_index].markdown(
                    "<div style='font-size:32px;text-align:center;color:#123b69'>→</div>",
                    unsafe_allow_html=True,
                )
                column_index += 1
        if row_start + cards_per_row < len(visual_positions):
            st.markdown(
                "<div style='font-size:30px;text-align:center;color:#123b69;line-height:1'>↓</div>",
                unsafe_allow_html=True,
            )
