"""Budowanie wiadomości SMTP bez zależności od Streamlit."""

from __future__ import annotations

from email.message import EmailMessage


def _attachment_payload(attachment):
    data = attachment.getvalue() if hasattr(attachment, "getvalue") else attachment.get("data", b"")
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("Załącznik nie zawiera danych binarnych.")
    name = getattr(attachment, "name", "") or (attachment.get("name", "") if isinstance(attachment, dict) else "") or "zalacznik"
    mime = getattr(attachment, "type", "") or (attachment.get("mime", "") if isinstance(attachment, dict) else "") or "application/octet-stream"
    maintype, _, subtype = str(mime).partition("/")
    return bytes(data), str(name), maintype or "application", subtype or "octet-stream"


def build_smtp_message(subject, sender, to_value, cc_value, plain_body, *, html_body="", logo_bytes=None, logo_mime="image/png", attachments=()):
    """Tworzy gotową wiadomość z HTML/logo i dowolnymi załącznikami."""
    message = EmailMessage()
    message["Subject"] = str(subject)
    message["From"] = str(sender)
    message["To"] = str(to_value)
    if str(cc_value or "").strip():
        message["Cc"] = str(cc_value)
    message.set_content(str(plain_body))
    if html_body:
        message.add_alternative(str(html_body), subtype="html")
        if logo_bytes:
            main, _, sub = str(logo_mime or "image/png").partition("/")
            message.get_payload()[-1].add_related(bytes(logo_bytes), maintype=main or "image", subtype=sub or "png", cid="<logo>")
    for attachment in attachments or ():
        data, name, maintype, subtype = _attachment_payload(attachment)
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return message
