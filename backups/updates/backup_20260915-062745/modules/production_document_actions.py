"""Adaptery generatorów dokumentów produkcyjnych do rejestru zlecenia.

Warstwa PDF pozostaje w ``services.production_documents``. Ten moduł łączy ją
z zależnościami aplikacji (czcionkami, nagłówkami oraz zapisem wersji).
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Callable

from services.production_documents import (
    build_eorder_bilingual_pdf,
    build_eorder_pdf,
    build_structured_document_pdf,
    build_worksheet_pdf,
)


def generate_tds_pdf(data: dict[str, Any], *, document_title: str, font_regular: str,
                     font_bold: str, attachment_image_bytes: bytes | None,
                     bct_flowables: tuple | list, canvasmaker: Any,
                     store_pdf: Callable[..., Any], order_id: str | None,
                     visual_attachments: list[dict[str, Any]] | None = None) -> BytesIO:
    pdf_bytes = build_structured_document_pdf(
        data, document_title=document_title, font_regular=font_regular, font_bold=font_bold,
        attachment_image_bytes=attachment_image_bytes, visual_attachments=visual_attachments or [], extra_flowables=bct_flowables,
        canvasmaker=canvasmaker,
    )
    store_pdf(document_title, pdf_bytes, f"{document_title}.pdf", {"source": "PDF TDS/Zamówienie"}, order_id=order_id)
    return BytesIO(pdf_bytes)


def generate_eorder(items: list[dict[str, Any]], meta: dict[str, Any], *, font_regular: str,
                    font_bold: str, logo_path: str, canvasmaker: Any,
                    store_pdf: Callable[..., Any], store_document: bool = True,
                    order_id: str | None = None) -> BytesIO:
    pdf_bytes = build_eorder_pdf(items, meta, font_regular=font_regular, font_bold=font_bold,
                                 logo_path=logo_path, canvasmaker=canvasmaker)
    if store_document:
        recipient = meta.get("recipient", {}) or {}
        store_pdf("E-Order", pdf_bytes, "e_order.pdf", {
            "order_no": meta.get("order_no", ""),
            "recipient": recipient.get("company") or recipient.get("name", ""),
            "response_status": meta.get("response_status", "wysłano"),
            "language": str(meta.get("lang", "pl")).lower(),
        }, order_id=order_id or meta.get("order_id"))
    return BytesIO(pdf_bytes)


def generate_bilingual_eorder(items: list[dict[str, Any]], meta: dict[str, Any], *, font_regular: str,
                              font_bold: str, canvasmaker: Any, store_pdf: Callable[..., Any],
                              order_id: str | None = None) -> BytesIO:
    pdf_bytes = build_eorder_bilingual_pdf(items, meta, font_regular=font_regular,
                                           font_bold=font_bold, canvasmaker=canvasmaker)
    store_pdf("E-Order", pdf_bytes, "e_order_pl_en.pdf", {
        "order_no": meta.get("order_no", ""),
        "recipient": (meta.get("recipient", {}) or {}).get("company", ""),
        "response_status": meta.get("response_status", "wysłano"), "language": "PL/EN",
    }, order_id=order_id or meta.get("order_id"))
    return BytesIO(pdf_bytes)


def generate_worksheet(items: list[dict[str, Any]], meta: dict[str, Any], *, font_regular: str,
                       font_bold: str, logo_path: str, bct_flowables: tuple | list, canvasmaker: Any,
                       store_pdf: Callable[..., Any], order_id: str | None = None) -> BytesIO:
    pdf_bytes = build_worksheet_pdf(items, meta, font_regular=font_regular, font_bold=font_bold,
                                    logo_path=logo_path, bct_flowables=bct_flowables, canvasmaker=canvasmaker)
    store_pdf("Karta Pracy", pdf_bytes, "karta_pracy.pdf", order_id=order_id or meta.get("order_id"))
    return BytesIO(pdf_bytes)
