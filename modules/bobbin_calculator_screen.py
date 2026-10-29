"""Kalkulator długości nawoju bobin papieru SWM."""

import json
import io
from datetime import datetime
from math import pi
from pathlib import Path


CORE_OUTER_DIAMETER_MM = 130.0
CALIBRATION_FILE = Path(__file__).resolve().parent.parent / "dane_aplikacji" / "bobbin_calibrations.json"
BOBBIN_INVENTORY_FILE = Path(__file__).resolve().parent.parent / "dane_aplikacji" / "inwentaryzacja_bobin.json"
SHEET_PAPER_INVENTORY_FILE = Path(__file__).resolve().parent.parent / "dane_aplikacji" / "magazyn_papieru_w_stosach.json"

# Punkty początkowe. Zapisana kalibracja dostawy zastępuje je tylko dla
# konkretnego papieru, a historia pozostaje w pliku JSON.
PAPER_VARIANTS = (
    {"name": "Różowy 14 gsm", "diameter": 365.0, "length": 5000.0},
    {"name": "Biały 14 gsm", "diameter": 365.0, "length": 5000.0},
    {"name": "Biały 12,5 gsm", "diameter": 280.0, "length": 3000.0},
    {"name": "Organic 13,5 gsm", "diameter": 295.0, "length": 5000.0},
    {"name": "Niebieski 14 gsm", "diameter": 359.0, "length": 5000.0},
    {"name": "Brązowy 14 gsm", "diameter": 362.0, "length": 5000.0},
)

BOBBIN_ARCHIVE_FORMAT = "system-zarzadzania-produkcja/bobbin-inventory"
BOBBIN_ARCHIVE_VERSION = 1


def _records_by_fingerprint(records):
    """Zwraca rekordy bez duplikatów; ID jest preferowanym identyfikatorem."""
    result, fingerprints = [], set()
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        fingerprint = str(record.get("id") or json.dumps(record, ensure_ascii=False, sort_keys=True, default=str))
        if fingerprint not in fingerprints:
            result.append(record)
            fingerprints.add(fingerprint)
    return result


def export_bobbin_archive(calibration_store, bobbin_inventory, sheet_inventory):
    """Tworzy przenośny eksport wszystkich trwałych danych modułu 16."""
    payload = {
        "format": BOBBIN_ARCHIVE_FORMAT,
        "version": BOBBIN_ARCHIVE_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "calibrations": load_calibration_store_from_value(calibration_store),
        "bobbin_inventory": load_bobbin_inventory_from_value(bobbin_inventory),
        "sheet_paper_inventory": load_sheet_paper_inventory_from_value(sheet_inventory),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def load_calibration_store_from_value(store):
    store = store if isinstance(store, dict) else {}
    return {
        "calibrations": _records_by_fingerprint(store.get("calibrations", [])),
        "active_ids": store.get("active_ids", {}) if isinstance(store.get("active_ids"), dict) else {},
    }


def load_bobbin_inventory_from_value(inventory):
    inventory = inventory if isinstance(inventory, dict) else {}
    return {"records": _records_by_fingerprint(inventory.get("records", []))}


def load_sheet_paper_inventory_from_value(inventory):
    inventory = inventory if isinstance(inventory, dict) else {}
    return {"movements": _records_by_fingerprint(inventory.get("movements", []))}


def parse_bobbin_archive(file_bytes):
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Plik importu nie jest poprawnym plikiem JSON UTF-8.") from error
    if not isinstance(payload, dict) or payload.get("format") != BOBBIN_ARCHIVE_FORMAT:
        raise ValueError("Wybrany plik nie jest eksportem modułu 16.")
    if payload.get("version") != BOBBIN_ARCHIVE_VERSION:
        raise ValueError("Ta wersja eksportu modułu 16 nie jest obsługiwana.")
    return (
        load_calibration_store_from_value(payload.get("calibrations")),
        load_bobbin_inventory_from_value(payload.get("bobbin_inventory")),
        load_sheet_paper_inventory_from_value(payload.get("sheet_paper_inventory")),
    )


def merge_bobbin_archive(current_store, current_bobbins, current_sheets, imported_store, imported_bobbins, imported_sheets):
    """Scala import jak moduł 24: nie usuwa lokalnych danych ani duplikatów."""
    def merge_records(current, incoming):
        merged = _records_by_fingerprint(current + incoming)
        return merged, len(merged) - len(_records_by_fingerprint(current))

    merged_calibrations, added_calibrations = merge_records(
        current_store.get("calibrations", []), imported_store.get("calibrations", []),
    )
    merged_bobbins, added_bobbins = merge_records(
        current_bobbins.get("records", []), imported_bobbins.get("records", []),
    )
    merged_movements, added_movements = merge_records(
        current_sheets.get("movements", []), imported_sheets.get("movements", []),
    )
    calibration_ids = {record.get("id") for record in merged_calibrations}
    active_ids = dict(current_store.get("active_ids", {}))
    active_ids.update({
        paper: record_id for paper, record_id in imported_store.get("active_ids", {}).items()
        if record_id in calibration_ids
    })
    return (
        {"calibrations": merged_calibrations, "active_ids": active_ids},
        {"records": merged_bobbins},
        {"movements": merged_movements},
        {"calibrations": added_calibrations, "bobbins": added_bobbins, "movements": added_movements},
    )


def thickness_from_calibration(outer_diameter_mm, length_m):
    annulus_area_mm2 = pi * ((outer_diameter_mm ** 2 - CORE_OUTER_DIAMETER_MM ** 2) / 4)
    return annulus_area_mm2 / (length_m * 1000)


def calculate_length_m(outer_diameter_mm, thickness_mm):
    annulus_area_mm2 = pi * ((outer_diameter_mm ** 2 - CORE_OUTER_DIAMETER_MM ** 2) / 4)
    return annulus_area_mm2 / thickness_mm * 0.001


def load_calibration_store(load_json=None):
    if load_json is not None:
        store = load_json(str(CALIBRATION_FILE), {"calibrations": [], "active_ids": {}})
    elif not CALIBRATION_FILE.exists():
        store = {"calibrations": [], "active_ids": {}}
    else:
        try:
            store = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            store = {"calibrations": [], "active_ids": {}}
    return load_calibration_store_from_value(store)


def save_calibration_store(store, save_json=None):
    if save_json is not None:
        save_json(str(CALIBRATION_FILE), store)
        return
    CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = CALIBRATION_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(CALIBRATION_FILE)


def load_bobbin_inventory(load_json=None):
    if load_json is not None:
        inventory = load_json(str(BOBBIN_INVENTORY_FILE), {"records": []})
    elif not BOBBIN_INVENTORY_FILE.exists():
        inventory = {"records": []}
    else:
        try:
            inventory = json.loads(BOBBIN_INVENTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            inventory = {"records": []}
    return load_bobbin_inventory_from_value(inventory)


def save_bobbin_inventory(inventory, save_json=None):
    if save_json is not None:
        save_json(str(BOBBIN_INVENTORY_FILE), inventory)
        return
    BOBBIN_INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = BOBBIN_INVENTORY_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_file.replace(BOBBIN_INVENTORY_FILE)


def load_sheet_paper_inventory(load_json=None):
    if load_json is not None:
        inventory = load_json(str(SHEET_PAPER_INVENTORY_FILE), {"movements": []})
    elif not SHEET_PAPER_INVENTORY_FILE.exists():
        inventory = {"movements": []}
    else:
        try:
            inventory = json.loads(SHEET_PAPER_INVENTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            inventory = {"movements": []}
    return load_sheet_paper_inventory_from_value(inventory)


def save_sheet_paper_inventory(inventory, save_json=None):
    if save_json is not None:
        save_json(str(SHEET_PAPER_INVENTORY_FILE), inventory)
        return
    SHEET_PAPER_INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = SHEET_PAPER_INVENTORY_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_file.replace(SHEET_PAPER_INVENTORY_FILE)


def sheet_paper_stock(movements):
    stock = {}
    for movement in movements:
        paper = str(movement.get("paper", "")).strip()
        paper_type = str(movement.get("paper_type", "")).strip()
        if not paper or not paper_type:
            continue
        key = (paper, paper_type)
        stock[key] = stock.get(key, 0) + int(movement.get("quantity_change", 0) or 0)
    return [
        {"paper": paper, "paper_type": paper_type, "quantity": quantity}
        for (paper, paper_type), quantity in sorted(stock.items())
        if quantity != 0
    ]


def bobbin_inventory_summary(records, reference_lengths=None):
    """Podsumowanie wg papieru; ekwiwalent liczony względem długości bobiny wzorcowej aktywnej kalibracji."""
    reference_lengths = reference_lengths or {}
    summary = {}
    for record in records:
        paper = record.get("paper", "Nieznany papier")
        row = summary.setdefault(paper, {"paper": paper, "pieces": 0, "meters": 0.0})
        row["pieces"] += int(record.get("quantity", 0) or 0)
        row["meters"] += float(record.get("meters", 0) or 0)
    result = []
    for row in sorted(summary.values(), key=lambda item: item["paper"]):
        reference_length = float(reference_lengths.get(row["paper"]) or DEFAULT_REFERENCE_LENGTH_M)
        result.append({**row, "reference_length": reference_length, "equivalent": row["meters"] / reference_length})
    return result


def build_bobbin_inventory_pdf(records, summary, font_regular="Helvetica", font_bold="Helvetica-Bold", calibrations=None):
    """Buduje raport trwałej inwentaryzacji bobin jako bajty PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm, topMargin=10 * mm, bottomMargin=10 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("bobbin_title", parent=styles["Title"], fontName=font_bold, fontSize=16, leading=20, textColor=colors.HexColor("#123B69"))
    normal = ParagraphStyle("bobbin_normal", parent=styles["BodyText"], fontName=font_regular, fontSize=8, leading=10)
    header = ParagraphStyle("bobbin_header", parent=normal, fontName=font_bold, textColor=colors.white)
    story = [
        Paragraph("Raport inwentaryzacji bobin SWM", title),
        Paragraph(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Tuleja wewnętrzna: 130 mm", normal),
        Spacer(1, 5 * mm),
    ]
    summary_rows = [[Paragraph(text, header) for text in ("Papier", "Suma sztuk", "Suma metrów", "Bobina wzorcowa [m]", "Ekwiwalent bobin wzorcowych")]]
    summary_rows.extend([
        [
            Paragraph(row["paper"], normal), str(row["pieces"]), f"{row['meters']:,.0f}".replace(",", " "),
            f"{row['reference_length']:,.0f}".replace(",", " "), f"{row['equivalent']:.2f}",
        ]
        for row in summary
    ])
    summary_table = Table(summary_rows, colWidths=[65 * mm, 30 * mm, 40 * mm, 40 * mm, 50 * mm], repeatRows=1)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B69")), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 1), (-1, -1), font_regular), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F9FC")]), ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([summary_table, Spacer(1, 6 * mm)])

    # Dane techniczne kalibracji użytej dla papierów z inwentaryzacji
    calibrations = calibrations or {}
    story.append(Paragraph("Dane techniczne kalibracji (aktywne w chwili generowania raportu)", ParagraphStyle(
        "bobbin_section", parent=normal, fontName=font_bold, fontSize=10, leading=13, textColor=colors.HexColor("#123B69"),
    )))
    story.append(Spacer(1, 2 * mm))
    calibration_rows = [[Paragraph(text, header) for text in (
        "Papier", "Źródło kalibracji", "Data", "Ø wzorcowa [mm]", "Długość wzorcowa [m]", "Grubość efektywna [µm]", "Tuleja Ø [mm]",
    )]]
    for row in summary:
        calibration = calibrations.get(row["paper"])
        if calibration:
            calibration_rows.append([
                Paragraph(row["paper"], normal), Paragraph(str(calibration.get("source", "-")), normal), str(calibration.get("date", "-")),
                f"{float(calibration.get('diameter_mm', 0)):.1f}",
                f"{float(calibration.get('reference_length_m', 0)):,.0f}".replace(",", " "),
                f"{float(calibration['thickness_mm']) * 1000:.3f}", f"{CORE_OUTER_DIAMETER_MM:.0f}",
            ])
        else:
            calibration_rows.append([Paragraph(row["paper"], normal), Paragraph("brak danych kalibracji", normal), "-", "-", "-", "-", f"{CORE_OUTER_DIAMETER_MM:.0f}"])
    calibration_table = Table(calibration_rows, colWidths=[50 * mm, 62 * mm, 24 * mm, 30 * mm, 33 * mm, 38 * mm, 25 * mm], repeatRows=1)
    calibration_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B69")), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 1), (-1, -1), font_regular), ("FONTSIZE", (0, 1), (-1, -1), 8), ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F9FC")]), ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([
        calibration_table, Spacer(1, 2 * mm),
        Paragraph(
            "Metoda: grubość efektywna = π · (D² − d²) / 4 / (L · 1000), gdzie D - średnica bobiny wzorcowej, d - średnica tulei, "
            "L - potwierdzona długość bobiny wzorcowej. Długość bobiny = π · (D² − d²) / 4 / grubość · 0,001. "
            "Ekwiwalent = suma metrów / długość bobiny wzorcowej danego papieru.", normal,
        ),
        Spacer(1, 6 * mm),
    ])

    detail_rows = [[Paragraph(text, header) for text in ("Data", "Papier", "Średnica [mm]", "Sztuki", "Metry / szt.", "Metry razem", "Użyta kalibracja")]]
    for record in records:
        detail_rows.append([
            Paragraph(str(record.get("created_at", ""))[:16].replace("T", " "), normal), Paragraph(str(record.get("paper", "")), normal),
            f"{float(record.get('outer_diameter_mm', 0)):.1f}", str(record.get("quantity", 0)),
            f"{float(record.get('meters_per_piece', 0)):,.0f}".replace(",", " "), f"{float(record.get('meters', 0)):,.0f}".replace(",", " "),
            Paragraph(str(record.get("calibration", "-")), normal),
        ])
    detail_table = Table(detail_rows, colWidths=[32 * mm, 50 * mm, 25 * mm, 18 * mm, 28 * mm, 28 * mm, 96 * mm], repeatRows=1)
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 1), (-1, -1), font_regular), ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F9FC")]), ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(detail_table)
    document.build(story)
    return output.getvalue()


DEFAULT_REFERENCE_LENGTH_M = 5000.0


def _record_reference_length(record, fallback=None):
    """Długość bobiny wzorcowej z rekordu kalibracji (length_m); w razie braku - wartość zapasowa."""
    try:
        length = float(record.get("length_m"))
        if length > 0:
            return length
    except (TypeError, ValueError):
        pass
    if fallback and fallback.get("reference_length_m"):
        return float(fallback["reference_length_m"])
    return DEFAULT_REFERENCE_LENGTH_M


def current_calibrations(store):
    calibrations = {
        variant["name"]: {
            "thickness_mm": thickness_from_calibration(variant["diameter"], variant["length"]),
            "reference_length_m": float(variant["length"]),
            "diameter_mm": float(variant["diameter"]),
            "source": "wartość domyślna",
            "date": "-",
            "reference": f"kalibracja: Ø{variant['diameter']:.0f} mm = {variant['length']:.0f} m",
        }
        for variant in PAPER_VARIANTS
    }
    records_by_id = {record.get("id"): record for record in store["calibrations"] if isinstance(record, dict)}
    for paper, record_id in store["active_ids"].items():
        record = records_by_id.get(record_id)
        if not record:
            continue
        try:
            thickness_mm = float(record["thickness_mm"])
        except (KeyError, TypeError, ValueError):
            continue
        if thickness_mm > 0:
            calibrations[paper] = {
                "thickness_mm": thickness_mm,
                "reference_length_m": _record_reference_length(record, calibrations.get(paper)),
                "diameter_mm": float(record.get("outer_diameter_mm") or calibrations.get(paper, {}).get("diameter_mm", 0) or 0),
                "source": f"dostawa: {record.get('delivery', 'bez opisu')}",
                "date": str(record.get("created_at", ""))[:10] or "-",
                "reference": f"dostawa: {record.get('delivery', 'bez opisu')} · {record.get('created_at', '')[:10]}",
            }
    return calibrations


def render_bobbin_calculator_screen(st, font_regular="Helvetica", font_bold="Helvetica-Bold", user_role="", load_json=None, save_json=None):
    st.subheader("🧻 Kalkulator bobin SWM")
    st.caption("Podaj tylko średnicę zewnętrzną bobiny. Tuleja wewnętrzna: 130 mm.")
    store = load_calibration_store(load_json)
    inventory = load_bobbin_inventory(load_json)
    sheet_inventory = load_sheet_paper_inventory(load_json)

    with st.expander("Wymiana danych z kopią JSON", expanded=False):
        st.caption("Eksport zawiera kalibracje, inwentaryzację bobin i magazyn papieru. Import scala dane i zapisuje je w Supabase.")
        transfer_left, transfer_right = st.columns(2)
        with transfer_left:
            st.download_button(
                "Eksportuj dane modułu 16",
                data=export_bobbin_archive(store, inventory, sheet_inventory),
                file_name=f"modul_16_bobiny_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="bobbin_archive_export",
                width="stretch",
            )
        with transfer_right:
            import_file = st.file_uploader(
                "Importuj kopię modułu 16", type=["json"], key="bobbin_archive_import",
            )
            if import_file is not None:
                try:
                    imported_store, imported_bobbins, imported_sheets = parse_bobbin_archive(import_file.getvalue())
                    st.caption(
                        f"Kalibracje: {len(imported_store['calibrations'])} · "
                        f"bobiny: {len(imported_bobbins['records'])} · "
                        f"ruchy magazynowe: {len(imported_sheets['movements'])}"
                    )
                    if st.button("Scal z bieżącymi danymi", key="bobbin_archive_import_confirm", width="stretch"):
                        store, inventory, sheet_inventory, stats = merge_bobbin_archive(
                            store, inventory, sheet_inventory,
                            imported_store, imported_bobbins, imported_sheets,
                        )
                        save_calibration_store(store, save_json)
                        save_bobbin_inventory(inventory, save_json)
                        save_sheet_paper_inventory(sheet_inventory, save_json)
                        st.success(
                            f"Dodano: kalibracje {stats['calibrations']} · bobiny {stats['bobbins']} · "
                            f"ruchy magazynowe {stats['movements']}."
                        )
                        st.rerun()
                except ValueError as error:
                    st.error(str(error))
        st.caption("Import nie usuwa ani nie zastępuje danych zapisanych już w aplikacji.")

    calibrations = current_calibrations(store)

    outer_diameter_mm = st.number_input(
        "Średnica zewnętrzna bobiny [mm]", min_value=130.0, value=365.0,
        step=1.0, format="%.1f", key="bobbin_outer_diameter_mm",
    )
    if outer_diameter_mm > CORE_OUTER_DIAMETER_MM:
        rows = []
        for paper, calibration in calibrations.items():
            length_m = calculate_length_m(outer_diameter_mm, calibration["thickness_mm"])
            rows.append({
                "Papier": paper,
                "Długość nawoju": f"{length_m:,.0f} m".replace(",", " "),
                "Grubość efektywna": f"{calibration['thickness_mm'] * 1000:.3f} µm",
                "Kalibracja aktywna": calibration["reference"],
            })
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Podaj średnicę większą niż 130 mm.")

    with st.expander("➕ Kalibracja nowej dostawy"):
        paper_options = list(calibrations) + ["➕ Dodaj nowy papier"]
        with st.form("new_bobbin_calibration"):
            selected_paper = st.selectbox("Papier", paper_options)
            new_paper = st.text_input("Nazwa nowego papieru") if selected_paper == "➕ Dodaj nowy papier" else ""
            delivery = st.text_input("Opis dostawy / numer partii", placeholder="np. dostawa 2026-09-01")
            calibration_diameter = st.number_input(
                "Średnica pełnej bobiny wzorcowej [mm]", min_value=130.1, value=365.0, step=1.0, format="%.1f",
            )
            known_length = st.number_input(
                "Potwierdzona długość bobiny wzorcowej [m]", min_value=1.0, value=5000.0, step=1.0, format="%.0f",
            )
            save_new = st.form_submit_button("Zapisz i ustaw jako aktywną", width="stretch")

        if save_new:
            paper = new_paper.strip() if selected_paper == "➕ Dodaj nowy papier" else selected_paper
            if not paper:
                st.error("Podaj nazwę nowego papieru.")
            else:
                record_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
                thickness_mm = thickness_from_calibration(calibration_diameter, known_length)
                store["calibrations"].append({
                    "id": record_id, "paper": paper, "delivery": delivery.strip() or "bez opisu",
                    "outer_diameter_mm": calibration_diameter, "length_m": known_length,
                    "thickness_mm": thickness_mm, "created_at": datetime.now().isoformat(timespec="seconds"),
                })
                store["active_ids"][paper] = record_id
                save_calibration_store(store, save_json)
                st.success(f"Zapisano aktywną kalibrację: {paper} — {thickness_mm * 1000:.3f} µm.")
                st.rerun()

    if store["calibrations"]:
        with st.expander("🗂️ Historia kalibracji"):
            records = sorted(store["calibrations"], key=lambda item: item.get("created_at", ""), reverse=True)
            st.dataframe([
                {
                    "Papier": record.get("paper", ""), "Dostawa": record.get("delivery", ""),
                    "Wzorzec": f"Ø{float(record.get('outer_diameter_mm', 0)):.1f} mm = {float(record.get('length_m', 0)):.0f} m",
                    "Grubość": f"{float(record.get('thickness_mm', 0)) * 1000:.3f} µm",
                    "Data": record.get("created_at", "")[:16].replace("T", " "),
                }
                for record in records
            ], width="stretch", hide_index=True)

            papers = sorted({record.get("paper") for record in records if record.get("paper")})
            history_paper = st.selectbox("Papier", papers, key="bobbin_history_paper")
            matching = [record for record in records if record.get("paper") == history_paper]
            selected_id = st.selectbox(
                "Ustaw aktywną kalibrację", [record["id"] for record in matching],
                format_func=lambda record_id: next(
                    f"{record.get('delivery', 'bez opisu')} · {record.get('created_at', '')[:16].replace('T', ' ')}"
                    for record in matching if record["id"] == record_id
                ),
            )
            if st.button("Ustaw wybraną kalibrację jako aktywną", width="stretch"):
                store["active_ids"][history_paper] = selected_id
                save_calibration_store(store, save_json)
                st.success("Zmieniono aktywną kalibrację.")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Inwentaryzacja bobin")
    st.caption("Dodawaj kolejne pozycje. Lista i podsumowanie są zapisywane trwale, niezależnie od sesji przeglądarki.")
    with st.form("add_bobbin_inventory_record", clear_on_submit=True):
        inventory_paper = st.selectbox("Papier", list(calibrations), key="bobbin_inventory_paper")
        inventory_diameter = st.number_input(
            "Średnica zewnętrzna [mm]", min_value=130.1, value=240.0, step=1.0, format="%.1f", key="bobbin_inventory_diameter",
        )
        inventory_quantity = st.number_input("Liczba sztuk", min_value=1, value=1, step=1, key="bobbin_inventory_quantity")
        add_inventory_record = st.form_submit_button("Dodaj bobiny do inwentaryzacji", width="stretch")
    if add_inventory_record:
        calibration = calibrations[inventory_paper]
        meters_per_piece = calculate_length_m(inventory_diameter, calibration["thickness_mm"])
        inventory["records"].append({
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"), "created_at": datetime.now().isoformat(timespec="seconds"),
            "paper": inventory_paper, "outer_diameter_mm": inventory_diameter, "quantity": int(inventory_quantity),
            "meters_per_piece": meters_per_piece, "meters": meters_per_piece * int(inventory_quantity),
            "calibration": calibration["reference"],
        })
        save_bobbin_inventory(inventory, save_json)
        st.success(f"Dodano {int(inventory_quantity)} szt. {inventory_paper}: {meters_per_piece:,.0f} m/szt.".replace(",", " "))
        st.rerun()

    inventory_records = inventory["records"]
    if inventory_records:
        reference_lengths = {name: item["reference_length_m"] for name, item in calibrations.items()}
        inventory_summary = bobbin_inventory_summary(inventory_records, reference_lengths)
        st.markdown("#### Podsumowanie według typu papieru")
        st.dataframe([
            {
                "Papier": row["paper"], "Suma sztuk": row["pieces"],
                "Suma metrów": f"{row['meters']:,.0f} m".replace(",", " "),
                "Bobina wzorcowa": f"{row['reference_length']:,.0f} m".replace(",", " "),
                "Ekwiwalent bobin wzorcowych": f"{row['equivalent']:.2f}",
            }
            for row in inventory_summary
        ], width="stretch", hide_index=True)
        with st.expander("Pozycje inwentaryzacji", expanded=False):
            st.dataframe([
                {
                    "Data": record.get("created_at", "")[:16].replace("T", " "), "Papier": record.get("paper", ""),
                    "Średnica [mm]": f"{float(record.get('outer_diameter_mm', 0)):.1f}", "Sztuki": record.get("quantity", 0),
                    "Metry / szt.": f"{float(record.get('meters_per_piece', 0)):,.0f}".replace(",", " "),
                    "Metry razem": f"{float(record.get('meters', 0)):,.0f}".replace(",", " "),
                }
                for record in inventory_records
            ], width="stretch", hide_index=True)
            if user_role == "Administrator":
                record_options = [record.get("id", str(index)) for index, record in enumerate(inventory_records)]
                selected_record_id = st.selectbox(
                    "Pozycja do usunięcia", record_options, key="bobbin_inventory_delete_record",
                    format_func=lambda record_id: next(
                        f"{record.get('paper', '')} · Ø{float(record.get('outer_diameter_mm', 0)):.1f} mm · "
                        f"{record.get('quantity', 0)} szt. · {record.get('created_at', '')[:16].replace('T', ' ')}"
                        for record in inventory_records if record.get("id", "") == record_id
                    ),
                )
                delete_column, clear_column = st.columns(2)
                with delete_column:
                    if st.button("Usuń wybraną pozycję", type="secondary", width="stretch"):
                        save_bobbin_inventory({
                            "records": [record for record in inventory_records if record.get("id", "") != selected_record_id]
                        }, save_json)
                        st.success("Usunięto pozycję z inwentaryzacji bobin.")
                        st.rerun()
                with clear_column:
                    if st.button("Wyczyść całą inwentaryzację", type="secondary", width="stretch"):
                        save_bobbin_inventory({"records": []}, save_json)
                        st.success("Wyczyszczono zapisaną inwentaryzację bobin.")
                        st.rerun()
            else:
                st.caption("Usuwanie pozycji jest dostępne tylko dla administratora.")
        report_pdf = build_bobbin_inventory_pdf(inventory_records, inventory_summary, font_regular, font_bold, calibrations)
        st.download_button(
            "📄 Pobierz raport PDF", report_pdf, "raport_inwentaryzacji_bobin.pdf", "application/pdf", width="stretch",
        )
    else:
        st.info("Inwentaryzacja jest pusta. Dodaj pierwszą pozycję powyżej.")

    st.markdown("---")
    st.subheader("📚 Magazyn papieru w stosach")
    st.caption("Stan jest liczony z zapisanych przyjęć i pobrań na produkcję.")
    sheet_stock_rows = sheet_paper_stock(sheet_inventory["movements"])

    intake_column, production_column = st.columns(2)
    with intake_column:
        with st.form("add_sheet_paper_stock", clear_on_submit=True):
            st.markdown("#### Dodaj do magazynu")
            intake_paper = st.text_input("Papier", placeholder="np. Biały 14 gsm", key="sheet_intake_paper")
            intake_type = st.text_input("Typ", placeholder="np. A4 / format / rodzaj cięcia", key="sheet_intake_type")
            intake_quantity = st.number_input("Ilość", min_value=1, value=1, step=1, key="sheet_intake_quantity")
            add_to_stock = st.form_submit_button("Dodaj do stanu", width="stretch")
        if add_to_stock:
            if not intake_paper.strip() or not intake_type.strip():
                st.error("Podaj papier i typ.")
            else:
                sheet_inventory["movements"].append({
                    "id": datetime.now().strftime("%Y%m%d%H%M%S%f"), "created_at": datetime.now().isoformat(timespec="seconds"),
                    "action": "Przyjęcie do magazynu", "paper": intake_paper.strip(), "paper_type": intake_type.strip(),
                    "quantity_change": int(intake_quantity), "project": "",
                })
                save_sheet_paper_inventory(sheet_inventory, save_json)
                st.success("Dodano papier do magazynu.")
                st.rerun()

    with production_column:
        st.markdown("#### Pobierz na produkcję")
        if sheet_stock_rows:
            stock_options = [f"{row['paper']} | {row['paper_type']}" for row in sheet_stock_rows]
            with st.form("remove_sheet_paper_stock", clear_on_submit=True):
                selected_stock = st.selectbox("Pozycja magazynowa", stock_options)
                selected_stock_row = sheet_stock_rows[stock_options.index(selected_stock)]
                production_quantity = st.number_input(
                    "Ilość do pobrania", min_value=1, max_value=int(selected_stock_row["quantity"]), value=1, step=1,
                )
                production_project = st.text_input("Projekt", placeholder="np. numer zlecenia / nazwa projektu")
                remove_from_stock = st.form_submit_button("Pobierz na produkcję", width="stretch")
            if remove_from_stock:
                if not production_project.strip():
                    st.error("Przy pobraniu na produkcję podaj projekt.")
                else:
                    sheet_inventory["movements"].append({
                        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"), "created_at": datetime.now().isoformat(timespec="seconds"),
                        "action": "Pobranie na produkcję", "paper": selected_stock_row["paper"], "paper_type": selected_stock_row["paper_type"],
                        "quantity_change": -int(production_quantity), "project": production_project.strip(),
                    })
                    save_sheet_paper_inventory(sheet_inventory, save_json)
                    st.success("Zapisano pobranie na produkcję.")
                    st.rerun()
        else:
            st.info("Najpierw dodaj papier do magazynu.")

    if sheet_stock_rows:
        st.markdown("#### Bieżący stan")
        st.dataframe([
            {"Papier": row["paper"], "Typ": row["paper_type"], "Ilość w magazynie": row["quantity"]}
            for row in sheet_stock_rows
        ], width="stretch", hide_index=True)
    else:
        st.info("Brak papieru w stosach na magazynie.")

    st.markdown("#### Ostatnie 30 wpisów")
    last_movements = sorted(sheet_inventory["movements"], key=lambda row: row.get("created_at", ""), reverse=True)[:30]
    if last_movements:
        st.dataframe([
            {
                "Data": movement.get("created_at", "")[:16].replace("T", " "), "Operacja": movement.get("action", ""),
                "Papier": movement.get("paper", ""), "Typ": movement.get("paper_type", ""),
                "Ilość": movement.get("quantity_change", 0), "Projekt": movement.get("project", "") or "—",
            }
            for movement in last_movements
        ], width="stretch", hide_index=True)
        if user_role == "Administrator":
            movement_options = [movement.get("id", str(index)) for index, movement in enumerate(last_movements)]
            selected_movement_id = st.selectbox(
                "Wpis do usunięcia", movement_options, key="sheet_inventory_delete_movement",
                format_func=lambda movement_id: next(
                    f"{movement.get('action', '')} · {movement.get('paper', '')} · {movement.get('paper_type', '')} · "
                    f"{movement.get('quantity_change', 0)} · {movement.get('created_at', '')[:16].replace('T', ' ')}"
                    for movement in last_movements if movement.get("id", "") == movement_id
                ),
            )
            delete_movement_column, clear_movements_column = st.columns(2)
            with delete_movement_column:
                if st.button("Usuń wybrany wpis magazynowy", type="secondary", width="stretch"):
                    save_sheet_paper_inventory({
                        "movements": [
                            movement for movement in sheet_inventory["movements"]
                            if movement.get("id", "") != selected_movement_id
                        ]
                    }, save_json)
                    st.success("Usunięto wpis magazynowy.")
                    st.rerun()
            with clear_movements_column:
                if st.button("Wyczyść historię i stan magazynu", type="secondary", width="stretch"):
                    save_sheet_paper_inventory({"movements": []}, save_json)
                    st.success("Wyczyszczono historię i stan magazynu papieru w stosach.")
                    st.rerun()
        else:
            st.caption("Usuwanie wpisów magazynowych jest dostępne tylko dla administratora.")
    else:
        st.caption("Nie ma jeszcze wpisów magazynowych.")

    with st.expander("Metoda obliczenia"):
        st.markdown(
            "Długość = π × ((średnica zewnętrzna² − 130²) / 4) / grubość × 0,001.  "
            "W obliczeniu 130 mm to zewnętrzna średnica tulei — miejsce, od którego zaczyna się papier."
        )
