"""Moduł 31: generator dużych etykiet magazynowych A4."""
from __future__ import annotations

from html import escape
from io import BytesIO

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas


INK = HexColor("#080C13")


def _fit_font_size(text: str, font_name: str, max_size: float, max_width: float) -> float:
    """Dobiera największy rozmiar, który mieści się w jednym wierszu."""
    if not text:
        return max_size
    size = max_size
    while size > 30 and pdfmetrics.stringWidth(text, font_name, size) > max_width:
        size -= 1
    return size


def build_warehouse_label_pdf(
    dimension: str,
    product: str,
    package_type: str,
    sku: str,
    font_regular: str,
    font_bold: str,
) -> bytes:
    """Tworzy pojedynczą, poziomą etykietę A4 gotową do druku."""
    buffer = BytesIO()
    width, height = landscape(A4)
    margin = 13 * mm
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdf.setTitle("Etykieta magazynowa A4")
    pdf.setFillColor(INK)

    # Nagłówek
    pdf.setFont(font_bold, 16)
    pdf.drawString(margin, height - 14 * mm, "IDENTYFIKACJA TOWARU")
    pdf.setFont(font_bold, 10)
    pdf.drawString(margin, height - 23 * mm, "MAGAZYN / LOGISTYKA")

    badge_text = (package_type or "STREFA MAGAZYNOWA").upper()
    badge_size = 13
    badge_width = max(70 * mm, pdfmetrics.stringWidth(badge_text, font_bold, badge_size) + 16 * mm)
    badge_x = width - margin - badge_width
    badge_y = height - 20 * mm
    pdf.setFillColor(INK)
    pdf.rect(badge_x, badge_y, badge_width, 14 * mm, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont(font_bold, badge_size)
    pdf.drawCentredString(badge_x + badge_width / 2, badge_y + 4.4 * mm, badge_text)

    pdf.setStrokeColor(INK)
    pdf.setLineWidth(1.4)
    pdf.line(margin, height - 33 * mm, width - margin, height - 33 * mm)

    # Wymiar jest najważniejszy: duży i optycznie wyśrodkowany.
    dimension_text = (dimension or "—").strip()
    dimension_size = _fit_font_size(dimension_text, font_bold, 126, width - 2 * margin)
    pdf.setFillColor(INK)
    pdf.setFont(font_bold, dimension_size)
    pdf.drawCentredString(width / 2, 94 * mm, dimension_text)

    # Dane pomocnicze na dole etykiety.
    box_y, box_height = 19 * mm, 43 * mm
    box_width = width - 2 * margin
    split_x = margin + box_width * 0.64
    pdf.setLineWidth(1.4)
    pdf.rect(margin, box_y, box_width, box_height, fill=0, stroke=1)
    pdf.line(split_x, box_y, split_x, box_y + box_height)
    pdf.setFont(font_bold, 10)
    pdf.drawString(margin + 6 * mm, box_y + box_height - 10 * mm, "OPIS TOWARU")
    pdf.drawString(split_x + 6 * mm, box_y + box_height - 10 * mm, "INDEKS / SKU")
    pdf.setFont(font_bold, 21)
    pdf.drawString(margin + 6 * mm, box_y + 16 * mm, (product or "—")[:54])
    sku_text = (sku or "—")[:28]
    sku_size = _fit_font_size(sku_text, font_bold, 21, width - split_x - 12 * mm)
    pdf.setFont(font_bold, sku_size)
    pdf.drawString(split_x + 6 * mm, box_y + 16 * mm, sku_text)
    pdf.save()
    return buffer.getvalue()


def _preview_html(dimension: str, product: str, package_type: str, sku: str) -> str:
    return f"""
    <style>
      .warehouse-preview {{ width:100%; aspect-ratio:1.414/1; box-sizing:border-box; padding:5%; color:#080c13; background:#fff; font-family:Arial,sans-serif; border:1px solid #d7dce5; container-type:inline-size; }}
      .warehouse-preview__top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; padding-bottom:3%; border-bottom:3px solid #080c13; }}
      .warehouse-preview__title {{ font-size:clamp(.8rem,1.8vw,1.25rem); font-weight:900; letter-spacing:.06em; }} .warehouse-preview__sub {{ margin-top:12px; font-size:clamp(.63rem,1.15vw,.82rem); font-weight:800; }}
      .warehouse-preview__badge {{ padding:10px 14px; background:#080c13; color:#fff; font-size:clamp(.65rem,1.4vw,1rem); font-weight:900; white-space:nowrap; }}
      .warehouse-preview__dimension {{ min-height:42%; display:flex; align-items:center; justify-content:center; text-align:center; font-size:min(9cqw,8.8rem); font-weight:900; line-height:1; letter-spacing:-.05em; white-space:nowrap; }}
      .warehouse-preview__details {{ display:grid; grid-template-columns:1.8fr 1fr; border:3px solid #080c13; }} .warehouse-preview__detail {{ padding:16px; min-height:65px; }} .warehouse-preview__detail + .warehouse-preview__detail {{ border-left:3px solid #080c13; }}
      .warehouse-preview__label {{ font-size:clamp(.6rem,1vw,.74rem); font-weight:900; letter-spacing:.08em; }} .warehouse-preview__value {{ margin-top:12px; font-size:clamp(1rem,2.1vw,1.35rem); font-weight:900; overflow-wrap:anywhere; }}
    </style>
    <div class="warehouse-preview"><div class="warehouse-preview__top"><div><div class="warehouse-preview__title">IDENTYFIKACJA TOWARU</div><div class="warehouse-preview__sub">MAGAZYN / LOGISTYKA</div></div><div class="warehouse-preview__badge">{escape(package_type or 'STREFA MAGAZYNOWA').upper()}</div></div>
    <div class="warehouse-preview__dimension">{escape(dimension or '—')}</div><div class="warehouse-preview__details"><div class="warehouse-preview__detail"><div class="warehouse-preview__label">OPIS TOWARU</div><div class="warehouse-preview__value">{escape(product or '—')}</div></div><div class="warehouse-preview__detail"><div class="warehouse-preview__label">INDEKS / SKU</div><div class="warehouse-preview__value">{escape(sku or '—')}</div></div></div></div>
    """


def render_warehouse_label_screen(st, deps: dict) -> None:
    st.title("🏷️ 31. Etykieta magazynowa A4")
    st.caption("Duży wymiar na środku, poziomy wydruk A4 i dane pomocnicze na dole.")
    left, right = st.columns([1, 1.6], gap="large")
    with left:
        dimension = st.text_input("Wymiar / wariant", value="470 x 180 x 305", key="warehouse_label_dimension")
        product = st.text_input("Opis towaru", value="Karton zbiorczy", key="warehouse_label_product")
        package_type = st.selectbox(
            "Typ / strefa", ["Strefa magazynowa", "Karton zbiorczy", "Paleta", "Pojemnik", "Regał"],
            key="warehouse_label_package_type",
        )
        sku = st.text_input("Indeks / SKU", value="", key="warehouse_label_sku")
        pdf = build_warehouse_label_pdf(
            dimension, product, package_type, sku,
            deps["font_regular"], deps["font_bold"],
        )
        st.download_button(
            "⬇️ Pobierz etykietę PDF A4", pdf, "etykieta_magazynowa_A4.pdf",
            "application/pdf", type="primary", use_container_width=True,
        )
        st.caption("Drukuj w orientacji poziomej, skala 100%, bez nagłówków i stopek przeglądarki.")
    with right:
        st.subheader("Podgląd na żywo")
        st.markdown(_preview_html(dimension, product, package_type, sku), unsafe_allow_html=True)
