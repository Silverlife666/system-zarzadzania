"""Czysta analiza PDF dla modułu Preflight DTP.

To kontrola pomocnicza przed drukiem, nie zastępuje preflightu RIP drukarni.
"""
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PROFILES = {
    "standard": {"label": "Standard drukowy — CMYK", "bleed_mm": 3.0, "min_dpi": 300, "max_tac": 300, "spots": "warning"},
    "cmyk_pantone": {"label": "CMYK + Pantone dozwolone", "bleed_mm": 3.0, "min_dpi": 300, "max_tac": 300, "spots": "info"},
}
MM_PER_POINT = 25.4 / 72.0


def _finding(severity: str, code: str, message: str, page: int | None = None) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message, "page": page}


def _box_mm(box: Any) -> dict[str, float]:
    return {"width": round(float(box.width) * MM_PER_POINT, 2), "height": round(float(box.height) * MM_PER_POINT, 2)}


def _has_embedded_font(font: Any) -> bool:
    try:
        font = font.get_object()
        descriptor = font.get("/FontDescriptor")
        if descriptor is None and font.get("/DescendantFonts"):
            descriptor = font["/DescendantFonts"][0].get_object().get("/FontDescriptor")
        descriptor = descriptor.get_object() if descriptor else {}
        return any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
    except Exception:
        return False


def _images_for_page(page: Any) -> list[dict[str, Any]]:
    images = []
    try:
        xobjects = page.get("/Resources", {}).get("/XObject", {}).get_object()
        for name, obj in xobjects.items():
            obj = obj.get_object()
            if obj.get("/Subtype") == "/Image":
                color = str(obj.get("/ColorSpace", "nieznana"))
                images.append({"name": str(name), "width": int(obj.get("/Width", 0)), "height": int(obj.get("/Height", 0)), "color_space": color})
    except Exception:
        pass
    return images


def analyze_pdf(file_bytes: bytes, file_name: str, profile_key: str = "standard") -> dict[str, Any]:
    """Zwraca bezpieczny, serializowalny raport analizy PDF."""
    profile_key = profile_key if profile_key in PROFILES else "standard"
    profile = PROFILES[profile_key]
    findings: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {"pages": 0, "spots": [], "has_rgb": False, "images": [], "fonts": 0, "embedded_fonts": 0, "has_text": False, "has_vectors": False, "boxes": []}
    raw = bytes(file_bytes or b"")
    base = {"checked_at": datetime.now().isoformat(timespec="seconds"), "file_name": str(file_name or "plik.pdf"), "sha256": hashlib.sha256(raw).hexdigest(), "profile": profile_key, "profile_label": profile["label"], "file_size": len(raw)}
    if not raw.startswith(b"%PDF"):
        findings.append(_finding("blocker", "invalid_pdf", "Plik nie jest prawidłowym dokumentem PDF."))
        return {**base, "overall_status": "blokada", "summary": {"blockers": 1, "warnings": 0, "info": 0}, "findings": findings, "metrics": metrics}
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted:
            findings.append(_finding("blocker", "encrypted", "PDF jest chroniony hasłem lub zaszyfrowany."))
            return {**base, "overall_status": "blokada", "summary": {"blockers": 1, "warnings": 0, "info": 0}, "findings": findings, "metrics": metrics}
        metrics["pdf_version"] = str(getattr(reader, "pdf_header", ""))
        metadata = reader.metadata or {}
        metrics["producer"] = str(metadata.get("/Producer", ""))
        metrics["creator"] = str(metadata.get("/Creator", ""))
        if b"PDF/X" not in raw and b"GTS_PDFX" not in raw:
            findings.append(_finding("warning", "pdfx_unknown", "Nie wykryto deklaracji PDF/X; potwierdź wymagania drukarni."))
        spots = sorted(set(match.decode("latin-1", "replace") for match in re.findall(rb"/Separation\s*/([^\s/\[\]()<>]+)", raw)))
        metrics["spots"] = spots
        rgb = b"/DeviceRGB" in raw or b"/CalRGB" in raw
        metrics["has_rgb"] = rgb
        if rgb:
            findings.append(_finding("blocker", "rgb", "Wykryto przestrzeń RGB. Przed drukiem przekonwertuj plik do CMYK."))
        if spots:
            findings.append(_finding(profile["spots"], "spot_colors", "Wykryto kolory dodatkowe: " + ", ".join(spots) + "."))
        if b"/SMask" in raw or b"/ca " in raw or b"/CA " in raw:
            findings.append(_finding("warning", "transparency", "Wykryto przezroczystości lub maski; sprawdź wynik po spłaszczeniu w RIP."))
        if b"/OCProperties" in raw:
            findings.append(_finding("warning", "layers", "Wykryto warstwy PDF."))
        if b"/AcroForm" in raw or b"/Annots" in raw:
            findings.append(_finding("warning", "annotations", "Wykryto formularze lub adnotacje PDF."))
        tac_values = [sum(float(value) for value in match) * 100 for match in re.findall(rb"([01](?:\.\d+)?)\s+([01](?:\.\d+)?)\s+([01](?:\.\d+)?)\s+([01](?:\.\d+)?)\s+k\b", raw)]
        if tac_values and max(tac_values) > profile["max_tac"]:
            findings.append(_finding("blocker", "tac", f"Wykryto stały kolor CMYK o sumie farb {max(tac_values):.0f}%, powyżej limitu {profile['max_tac']}%."))
        for index, page in enumerate(reader.pages, start=1):
            metrics["pages"] += 1
            media, trim, bleed = page.mediabox, page.trimbox, page.bleedbox
            box_data = {"page": index, "media": _box_mm(media), "trim": _box_mm(trim), "bleed": _box_mm(bleed)}
            metrics["boxes"].append(box_data)
            horizontal = (float(media.width) - float(trim.width)) * MM_PER_POINT / 2
            vertical = (float(media.height) - float(trim.height)) * MM_PER_POINT / 2
            if horizontal + 0.01 < profile["bleed_mm"] or vertical + 0.01 < profile["bleed_mm"]:
                findings.append(_finding("blocker", "bleed", f"Spad: {horizontal:.1f} mm poziomo / {vertical:.1f} mm pionowo; wymagane {profile['bleed_mm']:.0f} mm.", index))
            try:
                text = page.extract_text() or ""
                metrics["has_text"] = metrics["has_text"] or bool(text.strip())
            except Exception:
                pass
            try:
                contents = page.get_contents().get_data() if page.get_contents() else b""
                metrics["has_vectors"] = metrics["has_vectors"] or bool(re.search(rb"(?:\s|^)(?:m|l|c|re|S|f)(?:\s|$)", contents))
            except Exception:
                pass
            images = _images_for_page(page)
            for image in images:
                image["page"] = index
            metrics["images"].extend(images)
            try:
                fonts = page.get("/Resources", {}).get("/Font", {}).get_object()
                for _, font in fonts.items():
                    metrics["fonts"] += 1
                    metrics["embedded_fonts"] += int(_has_embedded_font(font))
            except Exception:
                pass
        if metrics["fonts"] and metrics["embedded_fonts"] < metrics["fonts"]:
            findings.append(_finding("blocker", "fonts", f"Osadzone fonty: {metrics['embedded_fonts']} z {metrics['fonts']}."))
        if not metrics["has_text"]:
            findings.append(_finding("warning", "no_text", "Nie wykryto edytowalnego tekstu; tekst może być zamieniony na krzywe lub obraz."))
        if not metrics["has_vectors"]:
            findings.append(_finding("warning", "no_vectors", "Nie wykryto obiektów wektorowych."))
        if metrics["images"]:
            findings.append(_finding("info", "image_dpi", "Rozdzielczość efektywna obrazów wymaga weryfikacji w RIP; nie jest zgadywana przez ten raport."))
    except Exception as error:
        findings.append(_finding("blocker", "read_error", f"Nie można odczytać PDF: {error}"))
    counts = {"blockers": sum(f["severity"] == "blocker" for f in findings), "warnings": sum(f["severity"] == "warning" for f in findings), "info": sum(f["severity"] == "info" for f in findings)}
    status = "blokada" if counts["blockers"] else ("ostrzezenia" if counts["warnings"] else "gotowy")
    return {**base, "overall_status": status, "summary": counts, "findings": findings, "metrics": metrics}


def build_preflight_html(report: dict[str, Any]) -> bytes:
    rows = "".join(f"<tr><td>{html.escape(f['severity'])}</td><td>{html.escape(str(f.get('page') or '—'))}</td><td>{html.escape(f['message'])}</td></tr>" for f in report.get("findings", [])) or "<tr><td colspan='3'>Brak ustaleń.</td></tr>"
    return ("<meta charset='utf-8'><h1>Raport Preflight DTP</h1><p>Status: <b>" + html.escape(report.get("overall_status", "")) + "</b></p><p>Plik: " + html.escape(report.get("file_name", "")) + "</p><table border='1' cellpadding='6'><tr><th>Ważność</th><th>Strona</th><th>Wynik</th></tr>" + rows + "</table><p>Automatyczna kontrola techniczna nie zastępuje preflightu RIP ani akceptacji drukarni.</p>").encode("utf-8")


def build_preflight_pdf(report: dict[str, Any]) -> bytes:
    buffer = BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=30, rightMargin=30, topMargin=35, bottomMargin=35)
    styles = getSampleStyleSheet(); normal = ParagraphStyle("pf", parent=styles["BodyText"], fontSize=8, leading=10)
    story = [Paragraph("Raport Preflight DTP", styles["Title"]), Paragraph(f"Plik: {html.escape(report.get('file_name', ''))} · Status: <b>{html.escape(report.get('overall_status', ''))}</b>", normal), Spacer(1, 10)]
    data = [["Ważność", "Strona", "Wynik"]] + [[f["severity"], str(f.get("page") or "—"), f["message"]] for f in report.get("findings", [])]
    table = Table(data, colWidths=[72, 48, 345], repeatRows=1); table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONT", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("LEADING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)])); story += [table, Spacer(1, 10), Paragraph("Automatyczna kontrola techniczna nie zastępuje preflightu RIP ani akceptacji drukarni.", normal)]; doc.build(story); return buffer.getvalue()
