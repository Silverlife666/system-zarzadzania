"""Pomocnicze reguły e-maila i przekazywania załączników."""

from __future__ import annotations

import re
from typing import Iterable


EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def parse_email_addresses(*fields: str) -> tuple[list[str], list[str]]:
    addresses = [address.strip().lower() for field in fields for address in str(field or "").split(",") if address.strip()]
    invalid = [address for address in addresses if not EMAIL_PATTERN.fullmatch(address)]
    return addresses, invalid


def use_kdrive_for_attachments(delivery_mode: str, total_bytes: int, threshold_bytes: int = 25 * 1024 * 1024) -> bool:
    return delivery_mode == "Prześlij do kDrive i wstaw link" or (
        delivery_mode.startswith("Automatycznie") and total_bytes > threshold_bytes
    )


def prepare_email_delivery(to_value, cc_value, bcc_value, subject, body, attachment_names, total_bytes, delivery_mode, mode):
    """Ujednolica walidację i plan przekazania wiadomości.

    Nie wysyła e-maila ani nie odczytuje sekretów. Dzięki temu interfejs może
    bezpiecznie pokazać właściwy komunikat jeszcze przed połączeniem z SMTP.
    """
    addresses, invalid = parse_email_addresses(to_value, cc_value, bcc_value)
    errors = []
    if not str(to_value or "").strip() or not str(subject or "").strip() or not str(body or "").strip():
        errors.append("Uzupełnij odbiorcę, temat i treść.")
    if invalid:
        errors.append("Nieprawidłowe adresy: " + ", ".join(invalid))
    attachment_notice = ""
    if "załącz" in str(body or "").casefold() and not attachment_names:
        attachment_notice = "Treść wskazuje załącznik, ale nie dodano pliku."
    direct_large_warning = (
        delivery_mode == "Dołącz bezpośrednio do e-maila" and total_bytes > 25 * 1024 * 1024
    )
    status = "robocza" if mode == "Zapisz roboczą" else "oczekuje" if mode == "Podgląd" else "wysłana"
    return {
        "addresses": addresses,
        "invalid_addresses": invalid,
        "errors": errors,
        "attachment_notice": attachment_notice,
        "use_kdrive": use_kdrive_for_attachments(delivery_mode, total_bytes),
        "direct_large_warning": direct_large_warning,
        "status": status,
    }
