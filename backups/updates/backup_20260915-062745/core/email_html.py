"""Bezpieczne budowanie podglądu wiadomości HTML."""

from __future__ import annotations

from html import escape


def _text_to_html(value: object) -> str:
    return escape(str(value or ""), quote=True).replace("\n", "<br>")


def render_email_html(
    body: object,
    signature: object,
    company_details: object,
    legal_footer: object,
    logo_html: str = "",
) -> str:
    """Zwraca podgląd, w którym pola wpisane przez użytkownika są tekstem, nie kodem HTML."""
    return (
        "<html><body style='font-family:Arial,sans-serif;color:#1f2937;max-width:680px;margin:auto;padding:18px;'>"
        f"{logo_html}<p>{_text_to_html(body)}</p>"
        f"<p>{_text_to_html(signature)}</p>"
        "<hr style='border:0;border-top:1px solid #d1d5db;'>"
        f"<small>{_text_to_html(company_details)}<br>{_text_to_html(legal_footer)}</small>"
        "</body></html>"
    )
