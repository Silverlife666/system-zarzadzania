"""Generator PDF raportu rozliczenia pracy (moduł 24)."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_work_settlement_pdf(entries, order_id, operator, font_regular="Helvetica", font_bold="Helvetica-Bold", changeovers=None):
    """Zwraca raport PDF z zarejestrowanymi czynnościami produkcyjnymi."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("WorkSettlementTitle", parent=styles["Title"], fontName=font_bold, fontSize=18, leading=22)
    normal = ParagraphStyle("WorkSettlementNormal", parent=styles["Normal"], fontName=font_regular, fontSize=8, leading=10)
    header = ParagraphStyle("WorkSettlementHeader", parent=normal, fontName=font_bold, textColor=colors.white)
    story = [
        Paragraph("RAPORT ROZLICZENIA PRACY", title),
        Spacer(1, 5 * mm),
        Paragraph(f"Zlecenie: <b>{order_id}</b> &nbsp;&nbsp;&nbsp; Wygenerował: <b>{operator}</b>", normal),
        Spacer(1, 5 * mm),
    ]
    table_widths = [20 * mm, 28 * mm, 43 * mm, 24 * mm, 22 * mm, 19 * mm, 20 * mm, 19 * mm, 57 * mm]
    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B69")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])
    monthly_entries = {}
    for entry in entries:
        month = str(entry.get("date", "") or "")[:7] or "Bez daty"
        paper_name = str(entry.get("paper_name", "") or "Nieokreślony papier")
        monthly_entries.setdefault(month, {}).setdefault(paper_name, []).append(entry)
    if not monthly_entries:
        monthly_entries = {"Brak danych": {"Nieokreślony papier": []}}
    for month, papers in sorted(monthly_entries.items()):
        story.extend([Spacer(1, 3 * mm), Paragraph(f"MIESIĄC: {month}", ParagraphStyle("MonthTitle", parent=title, fontSize=13, leading=16)), Spacer(1, 2 * mm)])
        for paper_name, paper_entries in sorted(papers.items()):
            paper_type = str((paper_entries[0] if paper_entries else {}).get("paper_type", "Nieokreślony") or "Nieokreślony")
            story.extend([Paragraph(f"Papier: <b>{paper_name}</b> &nbsp;&nbsp; Rodzaj: {paper_type}", normal), Spacer(1, 2 * mm)])
            rows = [[Paragraph(label, header) for label in ("Data", "Pracownik", "Czynność", "Ilość wykonana", "Ilość odpadu", "Jednostka", "Zmiana", "Czas (min)", "Uwagi")]]
            for entry in paper_entries:
                rows.append([
                    Paragraph(str(entry.get("date", "")), normal), Paragraph(str(entry.get("employee", "")), normal),
                    Paragraph(str(entry.get("activity", "")), normal), Paragraph(str(entry.get("quantity", "")), normal),
                    Paragraph(str(entry.get("waste_quantity", 0)), normal), Paragraph(str(entry.get("unit", "")), normal),
                    Paragraph(str(entry.get("shift", "")), normal), Paragraph(str(entry.get("duration_minutes", 0)), normal),
                    Paragraph(str(entry.get("notes", "") or "—"), normal),
                ])
            if len(rows) == 1:
                rows.append([Paragraph("Brak zarejestrowanych czynności.", normal)] + [""] * 8)
            table = Table(rows, colWidths=table_widths, repeatRows=1)
            table.setStyle(table_style)
            story.extend([table, Spacer(1, 4 * mm)])
    story.append(Spacer(1, 6 * mm))
    paper_summaries = {}
    for item in entries:
        paper_name = str(item.get("paper_name", "") or "Nieokreślony papier")
        summary = paper_summaries.setdefault(paper_name, {"entries": 0, "quantities": {}, "waste": {}, "minutes": 0})
        unit = str(item.get("unit", "") or "bez jednostki")
        summary["entries"] += 1
        summary["quantities"][unit] = summary["quantities"].get(unit, 0) + float(item.get("quantity", 0) or 0)
        summary["waste"][unit] = summary["waste"].get(unit, 0) + float(item.get("waste_quantity", 0) or 0)
        summary["minutes"] += int(item.get("duration_minutes", 0) or 0)
    story.extend([Spacer(1, 5 * mm), Paragraph("PODSUMOWANIE WEDŁUG NAZWY PAPIERU", ParagraphStyle("PaperSummaryTitle", parent=title, fontSize=13, leading=16)), Spacer(1, 3 * mm)])
    if not paper_summaries:
        story.append(Paragraph("Brak wpisów do podsumowania.", normal))
    for paper_name, summary in sorted(paper_summaries.items()):
        quantity_text = ", ".join(f"{value:g} {unit}" for unit, value in summary["quantities"].items())
        waste_text = ", ".join(f"{value:g} {unit}" for unit, value in summary["waste"].items())
        summary_hours, summary_minutes = divmod(summary["minutes"], 60)
        story.extend([
            Paragraph(f"Nazwa papieru: <b>{paper_name}</b><br/>1. Liczba wpisów: <b>{summary['entries']}</b><br/>2. Ilość wykonana: <b>{quantity_text}</b><br/>3. Ilość odpadu: <b>{waste_text}</b><br/>4. Czas pracy: <b>{summary_hours} godz. {summary_minutes} min</b>", normal),
            Spacer(1, 4 * mm),
        ])

    changeovers = changeovers or []
    story.extend([Spacer(1, 8 * mm), Paragraph("PRZEZBROJENIA MASZYNY", ParagraphStyle("ChangeoverTitle", parent=title, fontSize=13, leading=16)), Spacer(1, 3 * mm)])
    changeover_rows = [[Paragraph(label, header) for label in ("Data", "Pracownik", "Maszyna", "Następne zlecenie", "Czas (min)", "Uwagi")]]
    for item in changeovers:
        changeover_rows.append([
            Paragraph(str(item.get("date", "")), normal), Paragraph(str(item.get("employee", "")), normal),
            Paragraph(str(item.get("machine", "")), normal), Paragraph(str(item.get("next_order", "")), normal),
            Paragraph(str(item.get("duration_minutes", 0)), normal), Paragraph(str(item.get("notes", "") or "—"), normal),
        ])
    if len(changeover_rows) == 1:
        changeover_rows.append([Paragraph("Brak zarejestrowanych przezbrojeń.", normal)] + [""] * 5)
    changeover_table = Table(changeover_rows, colWidths=[25 * mm, 38 * mm, 48 * mm, 50 * mm, 25 * mm, 85 * mm], repeatRows=1)
    changeover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7C2D12")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFF7ED"), colors.white]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(changeover_table)
    changeover_minutes = sum(int(item.get("duration_minutes", 0) or 0) for item in changeovers)
    changeover_hours, changeover_rest_minutes = divmod(changeover_minutes, 60)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Liczba przezbrojeń: <b>{len(changeovers)}</b> &nbsp;&nbsp;&nbsp; Łączny czas przezbrojeń: <b>{changeover_hours} godz. {changeover_rest_minutes} min</b>", normal))
    document.build(story)
    return buffer.getvalue()
