"""Moduł 28: stan po produkcji, zamówienie klienta i lista braków."""
from __future__ import annotations

import io
import json
from copy import deepcopy
from datetime import datetime

import pandas as pd


INPUT_COLUMNS = ["Pozycja", "Nazwa", "Rodzaj towaru", "Ilość"]


def _number(value):
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _rows(frame):
    result = []
    for row in frame.to_dict("records"):
        item = {column: str(row.get(column, "")).strip() for column in INPUT_COLUMNS[:3]}
        item["Ilość"] = _number(row.get("Ilość"))
        if any(item.values()):
            result.append(item)
    return result


def _summary(stock, order, executors, relations=(), fulfillments=None, planned=None, corrections=None, conversions=()):
    combined = {}
    for side, rows in (("stock", stock), ("order", order)):
        for item in rows:
            key = tuple(str(item.get(field, "")).strip().casefold() for field in INPUT_COLUMNS[:3])
            if not any(key):
                continue
            current = combined.setdefault(key, {field: str(item.get(field, "")).strip() for field in INPUT_COLUMNS[:3]} | {"Ilość na stanie": 0, "Ilość w zamówieniu": 0})
            current["Ilość na stanie" if side == "stock" else "Ilość w zamówieniu"] += _number(item.get("Ilość"))
    consumed, internally_produced = {}, {}
    for conversion in conversions or ():
        semi_key, finished_key = conversion.get("semi_key", ""), conversion.get("finished_key", "")
        semi = next((item for key, item in combined.items() if "|".join(key) == semi_key), None)
        finished = next((item for key, item in combined.items() if "|".join(key) == finished_key), None)
        if semi and finished:
            use = min(_number(conversion.get("consume")), semi["Ilość na stanie"])
            consumed[semi_key] = consumed.get(semi_key, 0) + use
            internally_produced[finished_key] = internally_produced.get(finished_key, 0) + max(0, use - _number(conversion.get("waste")))
    # Gotowy produkt może pokryć zapotrzebowanie na powiązany półprodukt.
    # Przelicznik oznacza: ile sztuk półproduktu zastępuje 1 sztuka gotowego produktu.
    covered_by_finished, planned_coverage = {}, {}
    for relation in relations or ():
        semi_key, finished_key = relation.get("semi_key", ""), relation.get("finished_key", "")
        semi = next((item for key, item in combined.items() if "|".join(key) == semi_key), None)
        finished = next((item for key, item in combined.items() if "|".join(key) == finished_key), None)
        if not semi or not finished:
            continue
        factor = max(float(relation.get("factor", 1) or 1), 0.0001)
        missing = max(semi["Ilość w zamówieniu"] - semi["Ilość na stanie"], 0)
        covered_by_finished[semi_key] = min(missing, int(finished["Ilość na stanie"] * factor))
        planned_coverage[semi_key] = int(_number((planned or {}).get(finished_key)) * factor)
        semi["_fulfillment"] = relation.get("fulfillment", "Zlecić półprodukt")
        semi["_finished_name"] = finished.get("Nazwa", "")
    output = []
    for key, item in combined.items():
        item_key = "|".join(key)
        actual_coverage = covered_by_finished.get(item_key, 0)
        # Pokrycie planem jest widoczne wyłącznie w prognozie, a nie w stanie faktycznym.
        planned_finished_coverage = planned_coverage.get(item_key, 0)
        current_coverage = min(actual_coverage, max(item["Ilość w zamówieniu"] - item["Ilość na stanie"], 0))
        item["Pokrycie gotowym produktem"] = current_coverage
        item["Zużycie do produkcji"] = consumed.get(item_key, 0)
        item["Produkcja wewnętrzna"] = internally_produced.get(item_key, 0)
        item["Planowana produkcja"] = _number((planned or {}).get(item_key))
        item["Korekta prognozy / odpad"] = int((corrections or {}).get(item_key, 0) or 0)
        item["Stan prognozowany"] = max(0, item["Ilość na stanie"] - item["Zużycie do produkcji"] + item["Produkcja wewnętrzna"] + item["Planowana produkcja"] + item["Korekta prognozy / odpad"])
        item["Ilość do zamówienia"] = max(item["Ilość w zamówieniu"] - item["Ilość na stanie"] - current_coverage, 0)
        item["Prognozowana różnica"] = item["Stan prognozowany"] + current_coverage + planned_finished_coverage - item["Ilość w zamówieniu"]
        item["Do zlecenia po planie"] = max(-item["Prognozowana różnica"], 0)
        item["Różnica"] = item["Ilość na stanie"] - item["Ilość w zamówieniu"]
        item["Wykonawca asortymentu"] = str(executors.get("|".join(key), ""))
        item["Sposób realizacji braku"] = (fulfillments or {}).get("|".join(key), item.pop("_fulfillment", "Decyzja ręczna"))
        item.pop("_finished_name", None)
        item["_key"] = item_key
        output.append(item)
    return sorted(output, key=lambda item: (item["Pozycja"], item["Nazwa"]))


def _pdf(rows, title, font_regular, font_bold):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    output = io.BytesIO(); styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=9*mm, rightMargin=9*mm, topMargin=9*mm, bottomMargin=9*mm)
    normal = ParagraphStyle("m28n", parent=styles["BodyText"], fontName=font_regular, fontSize=7, leading=8)
    header = ParagraphStyle("m28h", parent=normal, fontName=font_bold, textColor=colors.white)
    keys = ["Pozycja", "Nazwa", "Rodzaj towaru", "Ilość na stanie", "Zużycie do produkcji", "Produkcja wewnętrzna", "Planowana produkcja", "Korekta prognozy / odpad", "Stan prognozowany", "Ilość w zamówieniu", "Do zlecenia po planie", "Prognozowana różnica", "Sposób realizacji braku", "Wykonawca asortymentu"]
    data = [[Paragraph(key, header) for key in keys]] + [[Paragraph(str(row.get(key, "")), normal) for key in keys] for row in rows]
    table = Table(data, colWidths=[10*mm, 24*mm, 20*mm, 13*mm, 14*mm, 14*mm, 14*mm, 15*mm, 14*mm, 14*mm, 14*mm, 15*mm, 20*mm, 22*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")), ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#CBD5E1")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F4F8FB")]), ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    doc.build([Paragraph(title, ParagraphStyle("m28t", parent=styles["Title"], fontName=font_bold, fontSize=16)), Spacer(1, 5*mm), table]); return output.getvalue()


def _purchase_pdf(report, font_regular, font_bold):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    output = io.BytesIO(); styles = getSampleStyleSheet()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=10*mm, rightMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
    normal = ParagraphStyle("m28pn", parent=styles["BodyText"], fontName=font_regular, fontSize=8, leading=9)
    header = ParagraphStyle("m28ph", parent=normal, fontName=font_bold, textColor=colors.white)
    keys = ["Pozycja", "Asortyment", "Rodzaj towaru", "Ilość bazowa", "Korekta", "Ilość do zlecenia", "Zamówić jako", "Gdzie / wykonawca"]
    data = [[Paragraph(key, header) for key in keys]] + [[Paragraph(str(row.get(key, "")), normal) for key in keys] for row in report]
    table = Table(data, colWidths=[14*mm, 45*mm, 34*mm, 20*mm, 18*mm, 26*mm, 42*mm, 45*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")), ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#CBD5E1")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F4F8FB")]), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    document.build([Paragraph("Raport: co trzeba zamówić i gdzie", ParagraphStyle("m28pt", parent=styles["Title"], fontName=font_bold, fontSize=16)), Spacer(1, 5*mm), table])
    return output.getvalue()


def _combined_pdf(rows, purchase_report, font_regular, font_bold):
    """Kompaktowy raport: oba zestawienia na jednej stronie A4 poziomo."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    output = io.BytesIO(); styles = getSampleStyleSheet()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=5*mm, rightMargin=5*mm, topMargin=5*mm, bottomMargin=5*mm)
    title = ParagraphStyle("m28ct", parent=styles["Title"], fontName=font_bold, fontSize=12, leading=14)
    normal = ParagraphStyle("m28cn", parent=styles["BodyText"], fontName=font_regular, fontSize=7, leading=8.2, wordWrap="LTR")
    header = ParagraphStyle("m28ch", parent=normal, fontName=font_bold, textColor=colors.white, alignment=TA_CENTER, leading=8.5, wordWrap="LTR")
    # W raporcie jednoplanszowym zostają kolumny decyzyjne. Pełne dane są nadal w widoku systemu.
    summary_keys = ["Pozycja", "Nazwa", "Rodzaj towaru", "Ilość na stanie", "Produkcja wewnętrzna", "Planowana produkcja", "Ilość w zamówieniu", "Prognozowana różnica", "Wykonawca asortymentu"]
    widths = [16, 50, 35, 20, 23, 23, 20, 25, 45]
    summary_data = [[Paragraph(key, header) for key in summary_keys]] + [[Paragraph(str(row.get(key, "")), normal) for key in summary_keys] for row in rows]
    summary_table = Table(summary_data, colWidths=[value*mm for value in widths], repeatRows=1)
    summary_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")), ("GRID", (0,0), (-1,-1), .2, colors.HexColor("#CBD5E1")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ALIGN", (0,0), (-1,0), "CENTER"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F4F8FB")]), ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2), ("LEFTPADDING", (0,0), (-1,-1), 1.5), ("RIGHTPADDING", (0,0), (-1,-1), 1.5)]))
    purchase_keys = ["Pozycja", "Asortyment", "Rodzaj towaru", "Ilość bazowa", "Korekta", "Ilość do zlecenia", "Zamówić jako", "Gdzie / wykonawca"]
    purchase_data = [[Paragraph(key, header) for key in purchase_keys]] + [[Paragraph(str(row.get(key, "")), normal) for key in purchase_keys] for row in purchase_report]
    purchase_table = Table(purchase_data, colWidths=[20*mm, 43*mm, 32*mm, 19*mm, 17*mm, 24*mm, 40*mm, 42*mm], repeatRows=1)
    purchase_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")), ("GRID", (0,0), (-1,-1), .2, colors.HexColor("#CBD5E1")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ALIGN", (0,0), (-1,0), "CENTER"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F4F8FB")]), ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))
    document.build([Paragraph("Pełny raport stanu i zamówień", title), Spacer(1, 2*mm), summary_table, Spacer(1, 3*mm), Paragraph("Co trzeba zamówić i gdzie", ParagraphStyle("m28cs", parent=title, fontSize=8, leading=10)), Spacer(1, 1*mm), purchase_table])
    return output.getvalue()


def render_order_stock_screen(st, deps):
    load_json, save_json, archive_file = deps["load_json"], deps["save_json"], deps["archive_file"]
    state = st.session_state.setdefault("module_28_draft", {"stock": [], "order": [], "executors": {}, "relations": [], "fulfillments": {}, "planned": {}, "corrections": {}, "conversions": [], "purchase_adjustments": {}})
    state.setdefault("relations", [])
    state.setdefault("fulfillments", {})
    state.setdefault("planned", {})
    state.setdefault("corrections", {})
    state.setdefault("conversions", [])
    state.setdefault("purchase_adjustments", {})
    st.title("📋 28. Rozliczenie stanu i zamówienia")
    st.caption("Wprowadź stan po poprzednim zamówieniu/produkcji oraz zamówienie klienta. Braki są liczone jako max(zamówienie − stan, 0).")
    left, right = st.columns(2)
    for column, title, state_key, form_key in (
        (left, "Stan magazynowy / po produkcji", "stock", "m28_add_stock"),
        (right, "Zamówienie od klienta", "order", "m28_add_order"),
    ):
        with column:
            st.subheader(title)
            with st.form(form_key, clear_on_submit=True):
                position = st.text_input("Pozycja", key=f"{form_key}_position")
                name = st.text_input("Nazwa", key=f"{form_key}_name")
                product_type = st.text_input("Rodzaj towaru", key=f"{form_key}_type")
                quantity = st.number_input("Ilość", min_value=0, step=1, key=f"{form_key}_quantity")
                add = st.form_submit_button("➕ Dodaj pozycję", width="stretch")
            if add:
                if not (position.strip() or name.strip() or product_type.strip()):
                    st.error("Uzupełnij co najmniej pozycję, nazwę lub rodzaj towaru.")
                else:
                    state[state_key].append({"Pozycja": position.strip(), "Nazwa": name.strip(), "Rodzaj towaru": product_type.strip(), "Ilość": int(quantity)})
                    st.rerun()
            if state[state_key]:
                st.dataframe(pd.DataFrame(state[state_key], columns=INPUT_COLUMNS), hide_index=True, width="stretch")
                remove_index = st.selectbox("Usuń pozycję", range(len(state[state_key])), key=f"{form_key}_remove", format_func=lambda index: f"{state[state_key][index]['Pozycja']} · {state[state_key][index]['Nazwa']}")
                if st.button("🗑️ Usuń wybraną pozycję", key=f"{form_key}_remove_button"):
                    state[state_key].pop(remove_index)
                    st.rerun()
    base_rows = _summary(state["stock"], state["order"], state["executors"], fulfillments=state["fulfillments"], planned=state["planned"], corrections=state["corrections"], conversions=state["conversions"])
    if base_rows:
        st.subheader("Powiązanie: półprodukt ↔ gotowy produkt")
        st.caption("Np. „Kartonik do bletki” może zostać pokryty stanem „Gotowej bletki”.")
        choices = {f"{row['Pozycja']} · {row['Nazwa']} · {row['Rodzaj towaru']}": row["_key"] for row in base_rows}
        with st.form("m28_relation", clear_on_submit=True):
            semi_label = st.selectbox("Półprodukt, którego zamówienie można pokryć", list(choices))
            finished_label = st.selectbox("Gotowy produkt dostępny na stanie", list(choices), index=min(1, len(choices)-1))
            factor = st.number_input("Ile sztuk półproduktu zastępuje 1 gotowy produkt", min_value=0.01, value=1.0, step=0.01)
            fulfillment = st.selectbox("Jeśli pozostanie brak, zlecić podwykonawcy jako", ["Zlecić półprodukt", "Zlecić gotowy produkt", "Produkcja wewnętrzna", "Decyzja ręczna"])
            add_relation = st.form_submit_button("➕ Dodaj powiązanie")
        if add_relation:
            if semi_label == finished_label:
                st.error("Półprodukt i gotowy produkt muszą być różnymi pozycjami.")
            else:
                state["relations"] = [item for item in state["relations"] if item.get("semi_key") != choices[semi_label]]
                state["relations"].append({"semi_key": choices[semi_label], "finished_key": choices[finished_label], "semi_label": semi_label, "finished_label": finished_label, "factor": factor, "fulfillment": fulfillment})
                st.rerun()
        if state["relations"]:
            for index, relation in enumerate(state["relations"]):
                st.caption(f"Półprodukt: **{relation.get('semi_label', relation['semi_key'])}** ← gotowy produkt: **{relation.get('finished_label', relation['finished_key'])}** · przelicznik: {relation['factor']:g} · {relation['fulfillment']}")
                if st.button("Usuń powiązanie", key=f"m28_delete_relation_{index}"):
                    state["relations"].pop(index); st.rerun()
    if base_rows:
        st.subheader("Produkcja wewnętrzna z półproduktu")
        st.caption("Zużywa półprodukt, odejmuje odpad i automatycznie tworzy gotowy produkt.")
        plan_choices = {f"{row['Pozycja']} · {row['Nazwa']} · {row['Rodzaj towaru']}": row["_key"] for row in base_rows}
        with st.form("m28_conversion", clear_on_submit=True):
            semi = st.selectbox("Zużywany półprodukt", list(plan_choices), key="m28_conversion_semi")
            finished = st.selectbox("Powstający gotowy produkt", list(plan_choices), index=min(1, len(plan_choices)-1), key="m28_conversion_finished")
            consume = st.number_input("Zużycie półproduktu", min_value=0, step=1)
            waste = st.number_input("Odpad produkcyjny", min_value=0, step=1)
            move_order = st.checkbox("Przenieś zamówienie klienta z półproduktu na gotowy produkt", value=True)
            add_conversion = st.form_submit_button("➕ Zapisz produkcję wewnętrzną")
        if add_conversion:
            if semi == finished or consume <= 0 or waste > consume:
                st.error("Wybierz dwie różne pozycje; zużycie musi być dodatnie, a odpad nie może go przekraczać.")
            else:
                semi_key, finished_key = plan_choices[semi], plan_choices[finished]
                state["conversions"].append({"semi_key": semi_key, "finished_key": finished_key, "consume": int(consume), "waste": int(waste)})
                if move_order:
                    moved = 0
                    for item in state["order"]:
                        if "|".join(str(item.get(field, "")).strip().casefold() for field in INPUT_COLUMNS[:3]) == semi_key:
                            moved += _number(item.get("Ilość")); item["Ilość"] = 0
                    if moved:
                        finished_row = next(row for row in base_rows if row["_key"] == finished_key)
                        state["order"].append({"Pozycja": finished_row["Pozycja"], "Nazwa": finished_row["Nazwa"], "Rodzaj towaru": finished_row["Rodzaj towaru"], "Ilość": moved})
                st.rerun()
        st.subheader("Planowana produkcja / dostawa")
        with st.form("m28_plan", clear_on_submit=True):
            planned_label = st.selectbox("Asortyment", list(plan_choices), key="m28_plan_product")
            planned_quantity = st.number_input("Ilość planowana", min_value=0, step=1, key="m28_plan_quantity")
            add_plan = st.form_submit_button("➕ Dodaj plan produkcji / dostawy")
        if add_plan:
            state["planned"][plan_choices[planned_label]] = _number(state["planned"].get(plan_choices[planned_label])) + int(planned_quantity)
            st.rerun()
        with st.form("m28_correction", clear_on_submit=True):
            correction_label = st.selectbox("Pozycja do korekty prognozy", list(plan_choices), key="m28_correction_product")
            correction_quantity = st.number_input("Korekta prognozy / odpad (ujemna liczba = odpad)", value=0, step=1, key="m28_correction_quantity")
            add_correction = st.form_submit_button("➕ Zapisz korektę prognozy")
        if add_correction:
            key = plan_choices[correction_label]
            state["corrections"][key] = int(state["corrections"].get(key, 0) or 0) + int(correction_quantity)
            st.rerun()
    rows = _summary(state["stock"], state["order"], state["executors"], (), state["fulfillments"], state["planned"], state["corrections"], state["conversions"])
    st.subheader("Zestawienie do realizacji")
    if rows:
        executor_frame = pd.DataFrame(rows).drop(columns=["_key"])
        edited = st.data_editor(executor_frame, hide_index=True, disabled=[column for column in executor_frame.columns if column not in ("Wykonawca asortymentu", "Sposób realizacji braku")], key="m28_summary", column_config={"Sposób realizacji braku": st.column_config.SelectboxColumn(options=["Zlecić półprodukt", "Zlecić gotowy produkt", "Produkcja wewnętrzna", "Decyzja ręczna"], required=True)})
        for source, changed in zip(rows, edited.to_dict("records")):
            state["executors"][source["_key"]] = str(changed.get("Wykonawca asortymentu", "")).strip()
            state["fulfillments"][source["_key"]] = str(changed.get("Sposób realizacji braku", "Decyzja ręczna"))
        rows = _summary(state["stock"], state["order"], state["executors"], (), state["fulfillments"], state["planned"], state["corrections"], state["conversions"])
        shortage = sum(row["Ilość do zamówienia"] for row in rows)
        st.info(f"Pozycje z brakiem: **{sum(row['Ilość do zamówienia'] > 0 for row in rows)}** · Łącznie do zamówienia: **{shortage}**")
        st.subheader("Raport: co trzeba zamówić i gdzie")
        purchase_rows = [row for row in rows if row["Do zlecenia po planie"] > 0 or (row["Planowana produkcja"] > 0 and row["Sposób realizacji braku"].startswith("Zlecić"))]
        if purchase_rows:
            purchase_choices = {f"{row['Pozycja']} · {row['Nazwa']}": row["_key"] for row in purchase_rows}
            with st.form("m28_purchase_adjustment", clear_on_submit=True):
                adjustment_label = st.selectbox("Pozycja do korekty zamówienia", list(purchase_choices))
                adjustment = st.number_input("Dodatkowa ilość na odpad / uszkodzenia", min_value=0, step=1)
                add_adjustment = st.form_submit_button("➕ Dodaj korektę do zamówienia")
            if add_adjustment:
                key = purchase_choices[adjustment_label]
                state["purchase_adjustments"][key] = int(state["purchase_adjustments"].get(key, 0) or 0) + int(adjustment)
                st.rerun()
            purchase_report_rows = [{
                "Pozycja": row["Pozycja"],
                "Asortyment": row["Nazwa"],
                "Rodzaj towaru": row["Rodzaj towaru"],
                "Ilość bazowa": row["Planowana produkcja"] if row["Planowana produkcja"] > 0 else row["Do zlecenia po planie"],
                "Korekta": int(state["purchase_adjustments"].get(row["_key"], 0) or 0),
                "Ilość do zlecenia": (row["Planowana produkcja"] if row["Planowana produkcja"] > 0 else row["Do zlecenia po planie"]) + int(state["purchase_adjustments"].get(row["_key"], 0) or 0),
                "Zamówić jako": row["Sposób realizacji braku"],
                "Gdzie / wykonawca": row["Wykonawca asortymentu"] or "Nieprzypisano",
            } for row in purchase_rows]
            purchase_report = pd.DataFrame(purchase_report_rows)
            st.dataframe(purchase_report, hide_index=True, width="stretch")
            report_pdf = _purchase_pdf(purchase_report_rows, deps["font_regular"], deps["font_bold"])
            left_pdf, right_pdf = st.columns(2)
            with left_pdf:
                st.download_button("📄 Pobierz raport zakupowy PDF", report_pdf, "raport_do_zlecenia.pdf", "application/pdf", width="stretch")
            with right_pdf:
                st.download_button("📚 Pobierz pełny raport PDF", _combined_pdf(rows, purchase_report_rows, deps["font_regular"], deps["font_bold"]), "pelny_raport_stanu_i_zamowien.pdf", "application/pdf", width="stretch")
        else:
            st.success("Po uwzględnieniu planów nie ma pozycji do zlecenia.")
    else:
        st.info("Dodaj pozycje w jednej z tabel.")
    archive = load_json(archive_file, [])
    if not isinstance(archive, list): archive = []
    a, b, c = st.columns(3)
    with a:
        if st.button("💾 Zapisz do archiwum", width="stretch"):
            name = st.session_state.get("m28_archive_name", "") or f"Zestawienie {datetime.now():%Y-%m-%d %H:%M}"
            archive.insert(0, {"name": name, "created_at": datetime.now().isoformat(timespec="seconds"), "data": deepcopy(state)})
            save_json(archive_file, archive); st.success("Zapisano w archiwum.")
    with b:
        st.download_button("📄 Pobierz PDF", _pdf(rows, "Rozliczenie stanu i zamówienia", deps["font_regular"], deps["font_bold"]), "rozliczenie_stanu_i_zamowienia.pdf", "application/pdf", width="stretch", disabled=not rows)
    with c:
        st.download_button("⬇️ Eksportuj kopię archiwum", json.dumps({"type":"module-28-archive", "archive":archive}, ensure_ascii=False, indent=2).encode("utf-8"), "modul_28_archiwum.json", "application/json", width="stretch")
    st.text_input("Nazwa zapisu archiwalnego", key="m28_archive_name")
    uploaded = st.file_uploader("Importuj kopię archiwum (.json)", type=["json"], key="m28_import")
    if uploaded and st.button("Importuj archiwum"):
        try:
            data=json.loads(uploaded.getvalue().decode("utf-8")); incoming=data.get("archive", [])
            if not isinstance(incoming, list): raise ValueError
            save_json(archive_file, incoming + archive); st.success(f"Zaimportowano {len(incoming)} zapisów.")
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError): st.error("Nieprawidłowy plik kopii archiwum.")
    if archive:
        st.subheader("Archiwum")
        labels=[f"{item.get('name','Zapis')} · {item.get('created_at','')}" for item in archive]
        selected=st.selectbox("Zapis", range(len(archive)), format_func=lambda index: labels[index])
        if st.button("↩️ Przywróć wybrany zapis"):
            st.session_state["module_28_draft"] = deepcopy(archive[selected].get("data", state)); st.rerun()
