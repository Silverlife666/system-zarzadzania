"""Widok modułu 11: walidacja QA po impozycji."""
import json
import smtplib
from datetime import datetime
from email.message import EmailMessage
from io import BytesIO

import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.qa import evaluate_qa_metrics, parse_ignored_regions
from services.qa_files import image_slider_html, inspect_pdf_separations, render_validation_bytes



def render_qa_screen(st, deps):
    pd = deps["pd"]
    load_database = deps["load_database"]
    save_database = deps["save_database"]
    store_order_pdf = deps["store_order_pdf"]
    FONT_BOLD = deps["font_bold"]
    FONT_REGULAR = deps["font_regular"]
    st.title("✅ Walidacja zamówień z drukarni")
    qa_db = load_database()
    st.caption("Kontrola QA po impozycji: porównanie projektu źródłowego z wyciętym użytkiem z arkusza montażowego.")
    st.info(
        "Wskaż położenie formatu netto użytku na arkuszu. Znaczniki pasowania, linie cięcia i spady "
        "nie powinny znaleźć się w wycinanym obszarze porównania."
    )

    upload_col_source, upload_col_sheet = st.columns(2)
    allowed_types = ["pdf", "jpg", "jpeg", "png", "tif", "tiff", "gif"]
    with upload_col_source:
        source_file = st.file_uploader(
            "1. Projekt źródłowy", type=allowed_types, key="print_qa_source_file",
            help="PDF, JPG, PNG, TIFF lub GIF z projektem zaakceptowanym do druku.",
        )
    with upload_col_sheet:
        imposed_file = st.file_uploader(
            "2. Arkusz montażowy z drukarni", type=allowed_types, key="print_qa_imposed_file",
            help="PDF, JPG, PNG, TIFF lub GIF z arkuszem po impozycji.",
        )

    if source_file is not None and imposed_file is not None:
        with st.expander("🎨 Kontrola separacji CMYK / Pantone", expanded=False):
            source_separations = inspect_pdf_separations(source_file.getvalue(), source_file.name)
            imposed_separations = inspect_pdf_separations(imposed_file.getvalue(), imposed_file.name)
            separation_table = pd.DataFrame([
                {"Plik": "Projekt źródłowy", "Typ": source_separations["type"], "CMYK / DeviceN": source_separations["cmyk"], "Pantone / spot": ", ".join(source_separations["pantone"]) or "brak"},
                {"Plik": "Arkusz montażowy", "Typ": imposed_separations["type"], "CMYK / DeviceN": imposed_separations["cmyk"], "Pantone / spot": ", ".join(imposed_separations["pantone"]) or "brak"},
            ])
            st.dataframe(separation_table, width="stretch", hide_index=True)
            if source_separations["pantone"] != imposed_separations["pantone"]:
                st.warning("Wykryto różnicę w deklarowanych separacjach dodatkowych / Pantone.")

    clicked_use_point = None
    if imposed_file is not None:
        try:
            from streamlit_image_coordinates import streamlit_image_coordinates
            preview_for_click = render_validation_bytes(imposed_file.getvalue(), imposed_file.name, 1, 150)
            with st.expander("🖱️ Wskaż użytek kliknięciem", expanded=False):
                st.caption("Kliknij lewy górny róg formatu netto. Rozmiar użytku zostanie pobrany z projektu źródłowego.")
                clicked_use_point = streamlit_image_coordinates(preview_for_click, key="print_qa_click_use")
                if clicked_use_point:
                    st.session_state["print_qa_clicked_use"] = clicked_use_point
                    st.success(f"Wybrano punkt: X={clicked_use_point['x']}, Y={clicked_use_point['y']}.")
        except ImportError:
            st.caption("Klikanie użytku wymaga opcjonalnego pakietu `streamlit-image-coordinates`; dostępne są tryby siatki i ręczne współrzędne.")
        except Exception as error:
            st.caption(f"Podgląd klikalny jest chwilowo niedostępny: {error}")

    st.markdown("### Ustawienia walidacji")
    set_col1, set_col2, set_col3 = st.columns(3)
    with set_col1:
        render_dpi = st.selectbox("Rozdzielczość rasteryzacji", [150, 200, 300, 600], index=2, key="print_qa_dpi")
        source_page = st.number_input("Strona projektu źródłowego", min_value=1, value=1, step=1, key="print_qa_source_page")
        imposed_page = st.number_input("Strona arkusza montażowego", min_value=1, value=1, step=1, key="print_qa_imposed_page")
    with set_col2:
        crop_mode = st.selectbox(
            "Sposób wskazania użytku",
            ["Cały arkusz (jeden użytek)", "Kliknięty użytek", "Siatka użytków", "Zaawansowane współrzędne px"],
            key="print_qa_crop_mode",
        )
        rotation = st.selectbox("Obrót użytku z arkusza", [0, 90, 180, 270], key="print_qa_rotation")
    with set_col3:
        ssim_threshold = st.slider("Czułość różnic SSIM", min_value=1, max_value=100, value=15, key="print_qa_ssim_threshold")

    grid_columns = grid_rows = selected_column = selected_row = trim_margin_px = 0
    crop_x = crop_y = crop_width = crop_height = 0
    if crop_mode == "Siatka użytków":
        st.caption("Podaj układ na arkuszu. Aplikacja sama wytnie wskazany użytek; jedno odsunięcie pomija spad i linie cięcia.")
        grid_col1, grid_col2, grid_col3, grid_col4, grid_col5 = st.columns(5)
        with grid_col1:
            grid_columns = st.number_input("Kolumny użytków", min_value=1, value=1, step=1, key="print_qa_grid_columns")
        with grid_col2:
            grid_rows = st.number_input("Wiersze użytków", min_value=1, value=1, step=1, key="print_qa_grid_rows")
        with grid_col3:
            selected_column = st.number_input("Wybierz kolumnę", min_value=1, max_value=int(grid_columns), value=1, step=1, key="print_qa_selected_column")
        with grid_col4:
            selected_row = st.number_input("Wybierz wiersz", min_value=1, max_value=int(grid_rows), value=1, step=1, key="print_qa_selected_row")
        with grid_col5:
            trim_margin_px = st.number_input("Odsunięcie od spadu / linii cięcia (px)", min_value=0, value=0, step=1, key="print_qa_trim_margin")
    elif crop_mode == "Zaawansowane współrzędne px":
        with st.expander("Ręczne wyznaczenie formatu netto", expanded=True):
            st.caption("Użyj tylko dla niestandardowego montażu. Wartości odnoszą się do obrazu po rasteryzacji.")
            crop_col1, crop_col2, crop_col3, crop_col4 = st.columns(4)
            with crop_col1:
                crop_x = st.number_input("X od lewej (px)", min_value=0, value=0, step=1, key="print_qa_crop_x")
            with crop_col2:
                crop_y = st.number_input("Y od góry (px)", min_value=0, value=0, step=1, key="print_qa_crop_y")
            with crop_col3:
                crop_width = st.number_input("Szerokość (px; 0 = do prawej)", min_value=0, value=0, step=1, key="print_qa_crop_width")
            with crop_col4:
                crop_height = st.number_input("Wysokość (px; 0 = do dołu)", min_value=0, value=0, step=1, key="print_qa_crop_height")

    with st.expander("Zaawansowane reguły QA", expanded=False):
        qa_col1, qa_col2, qa_col3 = st.columns(3)
        with qa_col1:
            validate_all_uses = st.checkbox(
                "Waliduj wszystkie użytki z siatki", value=False, disabled=crop_mode != "Siatka użytków", key="print_qa_all_uses"
            )
            alignment_tolerance = st.slider("Tolerancja automatycznego przesunięcia (px)", 0, 30, 5, key="print_qa_alignment")
        with qa_col2:
            min_ssim = st.slider("Minimalny SSIM dla statusu OK", 0.800, 1.000, 0.980, 0.001, key="print_qa_min_ssim")
            max_mismatch = st.slider("Maksymalna różnica pikseli (%)", 0.0, 100.0, 2.0, 0.1, key="print_qa_max_mismatch")
            max_delta_e = st.slider("Maksymalna średnia Delta E", 0.0, 100.0, 5.0, 0.1, key="print_qa_max_delta_e")
        with qa_col3:
            ignored_regions_text = st.text_area(
                "Maski ignorowane (x,y,szer,wys; ...)", value="", key="print_qa_ignored_regions",
                help="Współrzędne odnoszą się do obrazu projektu po dopasowaniu. Przykład: 10,10,200,60; 800,20,120,80",
            )
            run_ocr = st.checkbox("Porównaj tekst OCR", value=False, key="print_qa_ocr")
            run_barcodes = st.checkbox("Sprawdź kody EAN/QR", value=False, key="print_qa_barcodes")
        qa_operator = st.text_input("Osoba walidująca", value=st.session_state.get("user_name", ""), key="print_qa_operator")
        qa_comment = st.text_area("Komentarz QA", value="", key="print_qa_comment")

    if st.button("✨ Wykryj automatycznie kandydatów na użytki", key="print_qa_detect_uses"):
        if imposed_file is None:
            st.warning("Najpierw wgraj arkusz montażowy z drukarni.")
        else:
            try:
                import cv2
                detection_image = render_validation_bytes(imposed_file.getvalue(), imposed_file.name, int(imposed_page), 150)
                detection_gray = cv2.cvtColor(detection_image, cv2.COLOR_RGB2GRAY)
                detection_edges = cv2.Canny(detection_gray, 50, 150)
                contours, _ = cv2.findContours(detection_edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                candidates = []
                min_area = detection_image.shape[0] * detection_image.shape[1] * 0.01
                for contour in contours:
                    x, y, width, height = cv2.boundingRect(contour)
                    if width * height >= min_area and width > 40 and height > 40:
                        candidates.append((x, y, width, height))
                candidates = sorted(set(candidates), key=lambda item: item[2] * item[3], reverse=True)[:24]
                preview = detection_image.copy()
                for index, (x, y, width, height) in enumerate(candidates, start=1):
                    cv2.rectangle(preview, (x, y), (x + width, y + height), (0, 255, 0), 3)
                    cv2.putText(preview, str(index), (x + 5, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                st.session_state["print_qa_detected_uses"] = candidates
                st.image(preview, caption="Zielone prostokąty: wykryte kandydaty na format netto", width="stretch")
                st.caption("Wykrywanie jest propozycją — wybierz potem właściwy użytek w trybie siatki lub współrzędnych zaawansowanych.")
            except Exception as error:
                st.warning(f"Nie udało się wykryć kandydatów na użytki: {error}")

    if st.button("🔍 Uruchom walidację QA po impozycji", type="primary", key="print_qa_run"):
        if source_file is None or imposed_file is None:
            st.error("Wgraj oba pliki: projekt źródłowy i arkusz montażowy.")
        else:
            try:
                import cv2
                from skimage.metrics import structural_similarity

                source_image = render_validation_bytes(source_file.getvalue(), source_file.name, int(source_page), int(render_dpi))
                imposed_image = render_validation_bytes(imposed_file.getvalue(), imposed_file.name, int(imposed_page), int(render_dpi))
                imposed_height, imposed_width = imposed_image.shape[:2]
                if crop_mode == "Cały arkusz (jeden użytek)":
                    crop_x_int, crop_y_int = 0, 0
                    crop_width_int, crop_height_int = imposed_width, imposed_height
                elif crop_mode == "Kliknięty użytek":
                    selected_point = st.session_state.get("print_qa_clicked_use")
                    if not selected_point:
                        raise ValueError("Otwórz „Wskaż użytek kliknięciem” i kliknij lewy górny róg użytku.")
                    # Punkt pochodzi z podglądu 150 DPI, a walidacja działa w wybranym DPI.
                    crop_x_int = int(selected_point["x"] * int(render_dpi) / 150)
                    crop_y_int = int(selected_point["y"] * int(render_dpi) / 150)
                    crop_width_int, crop_height_int = source_image.shape[1], source_image.shape[0]
                elif crop_mode == "Siatka użytków":
                    cell_width = imposed_width / int(grid_columns)
                    cell_height = imposed_height / int(grid_rows)
                    crop_x_int = int((int(selected_column) - 1) * cell_width + int(trim_margin_px))
                    crop_y_int = int((int(selected_row) - 1) * cell_height + int(trim_margin_px))
                    crop_width_int = int(cell_width - 2 * int(trim_margin_px))
                    crop_height_int = int(cell_height - 2 * int(trim_margin_px))
                else:
                    crop_x_int, crop_y_int = int(crop_x), int(crop_y)
                    crop_width_int = int(crop_width) or (imposed_width - crop_x_int)
                    crop_height_int = int(crop_height) or (imposed_height - crop_y_int)
                crop_right = crop_x_int + crop_width_int
                crop_bottom = crop_y_int + crop_height_int

                if (
                    crop_width_int <= 0 or crop_height_int <= 0 or crop_x_int >= imposed_width or crop_y_int >= imposed_height
                    or crop_right > imposed_width or crop_bottom > imposed_height
                ):
                    st.error(
                        f"Wskazany format netto wychodzi poza arkusz ({imposed_width} × {imposed_height} px po rasteryzacji)."
                    )
                else:
                    imposed_crop = imposed_image[crop_y_int:crop_bottom, crop_x_int:crop_right]
                    if rotation == 90:
                        imposed_crop = cv2.rotate(imposed_crop, cv2.ROTATE_90_CLOCKWISE)
                    elif rotation == 180:
                        imposed_crop = cv2.rotate(imposed_crop, cv2.ROTATE_180)
                    elif rotation == 270:
                        imposed_crop = cv2.rotate(imposed_crop, cv2.ROTATE_90_COUNTERCLOCKWISE)

                    source_height, source_width = source_image.shape[:2]
                    imposed_crop = cv2.resize(imposed_crop, (source_width, source_height), interpolation=cv2.INTER_AREA)
                    source_gray = cv2.cvtColor(source_image, cv2.COLOR_RGB2GRAY)
                    orientation_candidates = {
                        "zgodna orientacja": imposed_crop,
                        "odbicie lustrzane poziome": cv2.flip(imposed_crop, 1),
                        "odbicie lustrzane pionowe": cv2.flip(imposed_crop, 0),
                        "awers / rewers (obrót 180°)": cv2.rotate(imposed_crop, cv2.ROTATE_180),
                    }
                    orientation_scores = {
                        name: structural_similarity(source_gray, cv2.cvtColor(candidate, cv2.COLOR_RGB2GRAY))
                        for name, candidate in orientation_candidates.items()
                    }
                    best_orientation = max(orientation_scores, key=orientation_scores.get)
                    if best_orientation != "zgodna orientacja":
                        imposed_crop = orientation_candidates[best_orientation]
                    imposed_gray = cv2.cvtColor(imposed_crop, cv2.COLOR_RGB2GRAY)
                    # Korekta niewielkiego przesunięcia po RIP-ie / impozycji.
                    shift, _ = cv2.phaseCorrelate(np.float32(source_gray), np.float32(imposed_gray))
                    shift_x = int(np.clip(round(shift[0]), -alignment_tolerance, alignment_tolerance))
                    shift_y = int(np.clip(round(shift[1]), -alignment_tolerance, alignment_tolerance))
                    if alignment_tolerance and (shift_x or shift_y):
                        imposed_crop = cv2.warpAffine(
                            imposed_crop, np.float32([[1, 0, shift_x], [0, 1, shift_y]]),
                            (source_width, source_height), borderMode=cv2.BORDER_REPLICATE,
                        )
                        imposed_gray = cv2.cvtColor(imposed_crop, cv2.COLOR_RGB2GRAY)
                    absolute_difference = cv2.absdiff(source_image, imposed_crop)
                    ssim_score, ssim_map = structural_similarity(source_gray, imposed_gray, full=True)
                    ssim_difference = ((1.0 - ssim_map) * 255).astype(np.uint8)
                    _, difference_mask = cv2.threshold(
                        ssim_difference, int(ssim_threshold), 255, cv2.THRESH_BINARY
                    )
                    absolute_gray = cv2.cvtColor(absolute_difference, cv2.COLOR_RGB2GRAY)
                    _, absolute_mask = cv2.threshold(absolute_gray, 12, 255, cv2.THRESH_BINARY)
                    difference_mask = cv2.bitwise_or(difference_mask, absolute_mask)
                    ignored_regions, invalid_ignored_regions = parse_ignored_regions(ignored_regions_text)
                    for raw_region in invalid_ignored_regions:
                        st.warning(f"Pominięto nieprawidłową maskę: {raw_region}")
                    for x, y, width, height in ignored_regions:
                        difference_mask[max(y, 0):max(y, 0) + height, max(x, 0):max(x, 0) + width] = 0
                    highlighted_difference = imposed_crop.copy()
                    highlighted_difference[difference_mask > 0] = [255, 0, 0]
                    mismatch_percent = float((difference_mask > 0).mean() * 100)
                    source_lab = cv2.cvtColor(source_image, cv2.COLOR_RGB2LAB).astype(np.float32)
                    imposed_lab = cv2.cvtColor(imposed_crop, cv2.COLOR_RGB2LAB).astype(np.float32)
                    mean_delta_e = float(np.linalg.norm(source_lab - imposed_lab, axis=2).mean())
                    qa_assessment = evaluate_qa_metrics(
                        ssim_score, mismatch_percent, mean_delta_e,
                        min_ssim=min_ssim, max_mismatch=max_mismatch, max_delta_e=max_delta_e,
                    )
                    qa_status = qa_assessment["status"]

                    (st.success if qa_status == "ZATWIERDZONE" else st.warning)(f"Wynik QA: {qa_status}")
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    metric_col1.metric("SSIM", f"{ssim_score:.4f}")
                    metric_col2.metric("Różniące się piksele", f"{mismatch_percent:.2f}%")
                    metric_col3.metric("Średnia Delta E", f"{mean_delta_e:.2f}")
                    metric_col4.metric("Korekta przesunięcia", f"{shift_x}, {shift_y} px")
                    st.caption(f"Format netto: {crop_width_int} × {crop_height_int} px | Maski ignorowane: {len(ignored_regions)}")
                    st.caption(f"Najlepsza orientacja: **{best_orientation}**")
                    if qa_status != "ZATWIERDZONE":
                        st.warning("Wykryto istotne różnice strukturalne. Sprawdź zaznaczenia na czerwono.")
                        for reason in qa_assessment["reasons"]:
                            st.caption(f"• {reason}")
                    else:
                        st.info("Obrazy są strukturalnie bardzo podobne. Różnice mogą wynikać z rasteryzacji lub profilu koloru.")

                    image_col1, image_col2, image_col3 = st.columns(3)
                    with image_col1:
                        st.image(source_image, caption="Projekt źródłowy", width="stretch")
                    with image_col2:
                        st.image(imposed_crop, caption="Użytek wycięty z arkusza", width="stretch")
                    with image_col3:
                        st.image(highlighted_difference, caption="Różnice — czerwone", width="stretch")
                    with st.expander("↔️ Porównanie przed / po", expanded=False):
                        st.components.v1.html(
                            image_slider_html(source_image, imposed_crop),
                            height=520, scrolling=False,
                        )

                    qa_annotations = []
                    with st.expander("✍️ Komentarze bezpośrednio na obrazie", expanded=False):
                        annotation_comment = st.text_area("Opis zaznaczonego błędu", key="print_qa_annotation_comment")
                        try:
                            from streamlit_drawable_canvas import st_canvas
                            from PIL import Image
                            canvas_result = st_canvas(
                                fill_color="rgba(255, 0, 0, 0.20)", stroke_width=3, stroke_color="#ff0000",
                                background_image=Image.fromarray(highlighted_difference), drawing_mode="rect",
                                height=min(source_height, 700), width=min(source_width, 900), key="print_qa_annotation_canvas",
                            )
                            if canvas_result.json_data and annotation_comment:
                                qa_annotations = canvas_result.json_data.get("objects", [])
                                for annotation in qa_annotations:
                                    annotation["comment"] = annotation_comment
                                st.caption(f"Dodano adnotacje: {len(qa_annotations)}.")
                        except ImportError:
                            st.info("Do zaznaczania obszarów na obrazie zainstaluj `streamlit-drawable-canvas`. Opis można nadal dodać w komentarzu QA.")

                    ocr_result = "Nie uruchomiono"
                    barcode_result = "Nie uruchomiono"
                    if run_ocr:
                        try:
                            import pytesseract
                            source_text = pytesseract.image_to_string(source_image, lang="pol+eng").strip()
                            imposed_text = pytesseract.image_to_string(imposed_crop, lang="pol+eng").strip()
                            ocr_result = "ZGODNE" if source_text == imposed_text else "RÓŻNICE W TEKŚCIE"
                        except Exception as error:
                            ocr_result = f"Niedostępne: {error}"
                    if run_barcodes:
                        try:
                            from pyzbar.pyzbar import decode
                            source_codes = sorted(item.data.decode("utf-8", errors="replace") for item in decode(source_image))
                            imposed_codes = sorted(item.data.decode("utf-8", errors="replace") for item in decode(imposed_crop))
                            barcode_result = "ZGODNE" if source_codes == imposed_codes else f"RÓŻNICE: źródło={source_codes}, arkusz={imposed_codes}"
                        except Exception as error:
                            barcode_result = f"Niedostępne: {error}"

                    if validate_all_uses and crop_mode == "Siatka użytków":
                        batch_rows = []
                        cell_width = imposed_width / int(grid_columns)
                        cell_height = imposed_height / int(grid_rows)
                        for batch_row in range(int(grid_rows)):
                            for batch_col in range(int(grid_columns)):
                                x = int(batch_col * cell_width + int(trim_margin_px))
                                y = int(batch_row * cell_height + int(trim_margin_px))
                                w = int(cell_width - 2 * int(trim_margin_px))
                                h = int(cell_height - 2 * int(trim_margin_px))
                                cell = imposed_image[y:y + h, x:x + w]
                                cell = cv2.resize(cell, (source_width, source_height), interpolation=cv2.INTER_AREA)
                                cell_ssim = structural_similarity(source_gray, cv2.cvtColor(cell, cv2.COLOR_RGB2GRAY))
                                cell_diff = cv2.absdiff(source_image, cell)
                                cell_mismatch = float((cv2.cvtColor(cell_diff, cv2.COLOR_RGB2GRAY) > 12).mean() * 100)
                                batch_rows.append({
                                    "Użytek": f"R{batch_row + 1} / K{batch_col + 1}",
                                    "SSIM": round(float(cell_ssim), 4),
                                    "Różnice (%)": round(cell_mismatch, 2),
                                    "Status": evaluate_qa_metrics(
                                        cell_ssim, cell_mismatch, min_ssim=min_ssim, max_mismatch=max_mismatch,
                                    )["status"],
                                })
                        st.markdown("#### Wyniki wszystkich użytków")
                        st.dataframe(pd.DataFrame(batch_rows), width="stretch", hide_index=True)

                    result_record = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "operator": qa_operator,
                        "comment": qa_comment,
                        "source_file": source_file.name,
                        "imposed_file": imposed_file.name,
                        "dpi": int(render_dpi),
                        "crop_mode": crop_mode,
                        "ssim": round(float(ssim_score), 6),
                        "mismatch_percent": round(mismatch_percent, 4),
                        "mean_delta_e": round(mean_delta_e, 4),
                        "status": qa_status,
                        "ocr": ocr_result,
                        "barcodes": barcode_result,
                        "annotations": qa_annotations,
                    }
                    # Wynik należy do aktywnego order_id i zostanie zapisany przez
                    # wspólny mechanizm kontekstu przy kolejnym odświeżeniu modułu.
                    st.session_state["print_qa_last_result"] = result_record
                    st.markdown("#### Kontrole dodatkowe")
                    st.write(f"**OCR:** {ocr_result}  \\n**EAN / QR:** {barcode_result}")

                    from PIL import Image
                    diff_png_buffer = BytesIO()
                    Image.fromarray(highlighted_difference).save(diff_png_buffer, format="PNG")
                    diff_png_bytes = diff_png_buffer.getvalue()
                    qa_pdf_buffer = BytesIO()
                    qa_pdf_doc = SimpleDocTemplate(qa_pdf_buffer, pagesize=A4, leftMargin=35, rightMargin=35, topMargin=40, bottomMargin=40)
                    qa_pdf_styles = getSampleStyleSheet()
                    qa_pdf_title = ParagraphStyle("QATitle", parent=qa_pdf_styles["Heading1"], fontName=FONT_BOLD, fontSize=16, textColor=colors.HexColor("#123B66"), spaceAfter=10)
                    qa_pdf_body = ParagraphStyle("QABody", parent=qa_pdf_styles["Normal"], fontName=FONT_REGULAR, fontSize=8.5, leading=11)
                    qa_table = Table([
                        [Paragraph("Status", qa_pdf_body), Paragraph(qa_status, qa_pdf_body)],
                        [Paragraph("SSIM", qa_pdf_body), Paragraph(f"{ssim_score:.4f}", qa_pdf_body)],
                        [Paragraph("Różnice pikselowe", qa_pdf_body), Paragraph(f"{mismatch_percent:.2f}%", qa_pdf_body)],
                        [Paragraph("Średnia Delta E", qa_pdf_body), Paragraph(f"{mean_delta_e:.2f}", qa_pdf_body)],
                        [Paragraph("Projekt / arkusz", qa_pdf_body), Paragraph(f"{source_file.name} / {imposed_file.name}", qa_pdf_body)],
                        [Paragraph("Operator / komentarz", qa_pdf_body), Paragraph(f"{qa_operator or '-'} / {qa_comment or '-'}", qa_pdf_body)],
                    ], colWidths=[150, 360])
                    qa_table.setStyle(TableStyle([
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F0F8")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]))
                    qa_report_image = RLImage(BytesIO(diff_png_bytes))
                    qa_report_image._restrictSize(450, 450)
                    qa_pdf_doc.build([
                        Paragraph("RAPORT QA PO IMPOZYCJI", qa_pdf_title), qa_table, Spacer(1, 12),
                        Paragraph("Mapa różnic — czerwone piksele wymagają weryfikacji.", qa_pdf_body), qa_report_image,
                    ])
                    qa_pdf_bytes = qa_pdf_buffer.getvalue()
                    export_json = json.dumps(result_record, ensure_ascii=False, indent=2).encode("utf-8")
                    export_csv = pd.DataFrame([result_record]).to_csv(index=False).encode("utf-8-sig")
                    export_col1, export_col2, export_col3, export_col4, export_col5 = st.columns(5)
                    with export_col1:
                        st.download_button("🖼️ Pobierz PNG różnic", diff_png_bytes, "qa_roznice.png", "image/png", key="qa_png_export")
                    with export_col2:
                        st.download_button("⬇️ Pobierz JSON", export_json, "qa_wynik.json", "application/json", key="qa_json_export")
                    with export_col3:
                        st.download_button("⬇️ Pobierz CSV", export_csv, "qa_wynik.csv", "text/csv", key="qa_csv_export")
                    with export_col4:
                        st.download_button("📄 Pobierz raport QA PDF", qa_pdf_bytes, "raport_QA.pdf", "application/pdf", key="qa_pdf_export")
                        if st.button("💾 Zapisz raport QA w Centrum zlecenia", key="store_qa_pdf"):
                            store_order_pdf("Raport QA drukarni", qa_pdf_bytes, "raport_QA.pdf")
                            st.success("Raport QA zapisano w Centrum zlecenia.")
                    with export_col5:
                        if st.button("💾 Zapisz wynik w historii", key="qa_save_history"):
                            qa_db["print_qa_history"].append(result_record)
                            save_database(qa_db)
                            st.success("Wynik walidacji zapisano w historii.")
                    with st.expander("✉️ E-mail reklamacyjny do drukarni", expanded=False):
                        complaint_recipient = st.text_input("E-mail drukarni", key="qa_complaint_recipient")
                        complaint_subject = st.text_input(
                            "Temat", value=f"QA: wymagane wyjaśnienie — {imposed_file.name}", key="qa_complaint_subject"
                        )
                        complaint_body = st.text_area(
                            "Treść", value=(
                                "Dzień dobry,\n\nprosimy o wyjaśnienie różnic wykrytych podczas kontroli QA po impozycji. "
                                f"Wynik: {qa_status}; SSIM: {ssim_score:.4f}; różnice pikselowe: {mismatch_percent:.2f}%.\n\n"
                                "W załącznikach przesyłamy raport QA oraz mapę różnic."
                            ), key="qa_complaint_body"
                        )
                        if st.button("📤 Wyślij e-mail reklamacyjny", key="qa_send_complaint"):
                            smtp_server = st.secrets.get("SMTP_SERVER", "")
                            smtp_port = st.secrets.get("SMTP_PORT", 465)
                            sender_email = st.secrets.get("SENDER_EMAIL", "")
                            sender_password = st.secrets.get("SENDER_PASSWORD", "")
                            if not all([complaint_recipient, smtp_server, sender_email, sender_password]):
                                st.error("Uzupełnij adres drukarni oraz konfigurację SMTP w pliku secrets.toml.")
                            else:
                                try:
                                    message = EmailMessage()
                                    message["From"] = sender_email
                                    message["To"] = complaint_recipient
                                    message["Subject"] = complaint_subject
                                    message.set_content(complaint_body)
                                    message.add_attachment(qa_pdf_bytes, maintype="application", subtype="pdf", filename="raport_QA.pdf")
                                    message.add_attachment(diff_png_bytes, maintype="image", subtype="png", filename="mapa_roznic.png")
                                    with smtplib.SMTP_SSL(smtp_server, int(smtp_port)) as smtp:
                                        smtp.login(sender_email, sender_password)
                                        smtp.send_message(message)
                                    st.success("E-mail reklamacyjny z raportem i mapą różnic został wysłany.")
                                except Exception as error:
                                    st.error(f"Nie udało się wysłać e-maila: {error}")
                    with st.expander("Szczegóły techniczne kontroli"):
                        st.write(
                            "Porównanie łączy różnicę pikselową `cv2.absdiff` z SSIM, aby ograniczyć fałszywe alarmy "
                            "spowodowane niewielką zmianą tonu lub profilem kolorów RIP."
                        )
            except ImportError as error:
                st.error(
                    "Brakuje biblioteki potrzebnej do walidacji: "
                    f"{error}. Zainstaluj: pymupdf, pillow, opencv-python i scikit-image."
                )
            except Exception as error:
                st.error(f"Nie udało się wykonać walidacji: {error}")

    st.markdown("---")
    st.markdown("### 📁 Historia walidacji QA")
    if qa_db["print_qa_history"]:
        history_dataframe = pd.DataFrame(qa_db["print_qa_history"])
        st.dataframe(history_dataframe.sort_values("timestamp", ascending=False), width="stretch", hide_index=True)
        if st.button("🗑️ Wyczyść historię walidacji", key="qa_clear_history"):
            qa_db["print_qa_history"] = []
            save_database(qa_db)
            st.rerun()
    else:
        st.caption("Brak zapisanych wyników QA.")


