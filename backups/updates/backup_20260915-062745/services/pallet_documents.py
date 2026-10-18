"""Etykiety paletowe i odczyt kodu QR poza warstwą Streamlit."""

from __future__ import annotations

from io import BytesIO
import json


def build_pallet_labels_pdf(result, ean, delivery_place, *, canvas, colors, mm, qr_widget, drawing_class, render_pdf, font_regular="Helvetica", font_bold="Helvetica-Bold"):
    """Tworzy po jednej etykiecie QR dla każdej palety wskazanej w wyniku."""
    result = result or {}
    buffer = BytesIO()
    width, height = 100 * mm, 150 * mm
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    total = max(0, int(result.get("Liczba palet", 0) or 0))
    for number in range(1, total + 1):
        pdf.setFillColor(colors.HexColor("#123B69")); pdf.rect(0, height - 24 * mm, width, 24 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white); pdf.setFont(font_bold, 15); pdf.drawString(8 * mm, height - 14 * mm, "ETYKIETA PALETOWA")
        pdf.setFillColor(colors.HexColor("#111827")); pdf.setFont(font_bold, 12); pdf.drawString(8 * mm, height - 33 * mm, f"PALETA {number} Z {total}")
        y = height - 42 * mm
        fields = [("Produkt", result.get("Produkt", "")), ("EAN", ean or "Brak"), ("Paleta", result.get("Paleta", "")), ("Masa brutto", f"{result.get('Masa brutto/paleta kg', 0)} kg"), ("Wysokość", f"{result.get('Wysokość palety mm', 0)} mm"), ("Miejsce dostawy", delivery_place or "Do uzupełnienia")]
        for label, value in fields:
            pdf.setFillColor(colors.HexColor("#64748B")); pdf.setFont(font_regular, 7); pdf.drawString(8 * mm, y, label.upper())
            pdf.setFillColor(colors.HexColor("#111827")); pdf.setFont(font_bold, 9); pdf.drawString(8 * mm, y - 4 * mm, str(value)[:52]); y -= 12 * mm
        payload = json.dumps({"produkt": result.get("Produkt", ""), "ean": ean, "paleta": number, "z": total}, ensure_ascii=False)
        code = qr_widget(payload); bounds = code.getBounds(); source_width, source_height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        size = 38 * mm; drawing = drawing_class(size, size, transform=[size / source_width, 0, 0, size / source_height, 0, 0]); drawing.add(code); render_pdf.draw(drawing, pdf, width - 48 * mm, 8 * mm)
        pdf.setFillColor(colors.HexColor("#64748B")); pdf.setFont(font_regular, 6.5); pdf.drawString(8 * mm, 11 * mm, "Wygenerowano przez Kalkulator - sekcja 4"); pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def decode_qr_bytes(data: bytes, *, cv2_module, numpy_module):
    """Zwraca pierwszy wykryty QR albo komunikat gotowy do pokazania użytkownikowi."""
    image_array = numpy_module.frombuffer(data, dtype=numpy_module.uint8)
    image = cv2_module.imdecode(image_array, cv2_module.IMREAD_COLOR)
    if image is None:
        return None, "Nie udało się odczytać obrazu."
    value, _, _ = cv2_module.QRCodeDetector().detectAndDecode(image)
    if not value:
        return None, "Nie wykryto czytelnego kodu QR. Zrób zdjęcie na wprost, w dobrym świetle."
    return value, None
