"""Generowanie PDF-ów harmonogramu produkcji bez zależności od Streamlit."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_production_schedule_pdf(rows, *, title, period_label, font_regular="Helvetica", font_bold="Helvetica-Bold"):
    """Buduje czytelny, podzielony na dni PDF harmonogramu produkcji."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=32, bottomMargin=38,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ScheduleTitle", parent=styles["Heading1"], fontName=font_bold, fontSize=18, leading=22,
        textColor=colors.white,
    )
    kicker_style = ParagraphStyle("ScheduleKicker", parent=styles["Normal"], fontName=font_bold, fontSize=8, leading=10, textColor=colors.HexColor("#BFDBFE"))
    metric_label_style = ParagraphStyle("ScheduleMetricLabel", parent=styles["Normal"], fontName=font_bold, fontSize=7, leading=9, textColor=colors.HexColor("#64748B"))
    metric_value_style = ParagraphStyle("ScheduleMetricValue", parent=styles["Normal"], fontName=font_bold, fontSize=11, leading=14, textColor=colors.HexColor("#0F172A"))
    text_style = ParagraphStyle("ScheduleText", parent=styles["Normal"], fontName=font_regular, fontSize=8, leading=10, textColor=colors.HexColor("#1E293B"))
    header_style = ParagraphStyle("ScheduleHeader", parent=text_style, fontName=font_bold, textColor=colors.white, alignment=0)
    day_style = ParagraphStyle("ScheduleDay", parent=text_style, fontName=font_bold, fontSize=9, leading=12, textColor=colors.HexColor("#123B69"))

    header = Table(
        [[
            [Paragraph("KALKULATOR PRODUKCJI", kicker_style), Paragraph(escape(title), title_style)],
            Paragraph("HARMONOGRAM", ParagraphStyle("ScheduleBadge", parent=kicker_style, alignment=2, fontSize=9, textColor=colors.white)),
        ]],
        colWidths=[document.width - 150, 150],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#123B69")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 16), ("RIGHTPADDING", (0, 0), (-1, -1), 16),
    ]))
    metrics = Table([[
        [Paragraph("OKRES", metric_label_style), Paragraph(escape(period_label), metric_value_style)],
        [Paragraph("ZAPLANOWANE ZADANIA", metric_label_style), Paragraph(str(len(rows)), metric_value_style)],
        [Paragraph("WYGENEROWANO", metric_label_style), Paragraph(datetime.now().strftime("%d.%m.%Y %H:%M"), metric_value_style)],
    ]], colWidths=[document.width * 0.48, document.width * 0.25, document.width * 0.27])
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story = [header, Spacer(1, 12), metrics, Spacer(1, 14)]

    headers = ["DATA", "ZMIANA", "PRACOWNIK", "ZADANIE", "UWAGI", "ZLECENIE"]
    table_rows = [[Paragraph(header, header_style) for header in headers]]
    day_rows, previous_date = [], None
    polish_days = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
    for row in rows:
        row_date = str(row.get("date", ""))
        if row_date != previous_date:
            try:
                parsed_date = date.fromisoformat(row_date)
                day_label = f"{polish_days[parsed_date.weekday()]} | {parsed_date.strftime('%d.%m.%Y')}"
            except ValueError:
                day_label = row_date or "Bez daty"
            day_rows.append(len(table_rows))
            table_rows.append([Paragraph(escape(day_label), day_style), "", "", "", "", ""])
            previous_date = row_date
        table_rows.append([
            Paragraph(escape(row_date or "-"), text_style),
            Paragraph(escape(str(row.get("shift", "-"))), text_style),
            Paragraph(escape(str(row.get("employee", "-"))), text_style),
            Paragraph(escape(str(row.get("task", "-"))), text_style),
            Paragraph(escape(str(row.get("notes", "") or "-")), text_style),
            Paragraph(escape(str(row.get("order_id", "") or "-")), text_style),
        ])
    if len(table_rows) == 1:
        story.append(Paragraph("Brak zadań w wybranym okresie.", text_style))
    else:
        table = Table(table_rows, colWidths=[76, 122, 110, 205, 150, 113], repeatRows=1)
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#0F2F55")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
        task_row_index = 0
        for index in range(1, len(table_rows)):
            if index in day_rows:
                table_style.extend([("SPAN", (0, index), (-1, index)), ("BACKGROUND", (0, index), (-1, index), colors.HexColor("#DBEAFE")), ("LINEABOVE", (0, index), (-1, index), 0.6, colors.HexColor("#93C5FD"))])
            else:
                table_style.extend([("BACKGROUND", (0, index), (-1, index), colors.HexColor("#F8FAFC") if task_row_index % 2 == 0 else colors.white), ("LINEBELOW", (0, index), (-1, index), 0.35, colors.HexColor("#E2E8F0"))])
                task_row_index += 1
        table.setStyle(TableStyle(table_style))
        story.append(table)

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(doc.leftMargin, 24, A4[1] - doc.rightMargin, 24)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.setFont(font_regular, 7)
        canvas.drawString(doc.leftMargin, 13, "Kalkulator produkcji | Harmonogram operacyjny")
        canvas.drawRightString(A4[1] - doc.rightMargin, 13, f"Strona {canvas.getPageNumber()}")
        canvas.restoreState()

    document.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return buffer.getvalue()
