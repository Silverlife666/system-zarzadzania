"""Normalizacja numerów VAT przed zapytaniem do MF albo VIES."""

from __future__ import annotations

import re


def normalize_vat_identifier(raw_value: object, default_country: str = "PL") -> tuple[str, str]:
    """Zwraca kod kraju i VAT bez spacji, myślników ani prefiksu powtórzonego w numerze."""
    value = re.sub(r"[\s\-]", "", str(raw_value or "")).upper()
    match = re.fullmatch(r"([A-Z]{2})([A-Z0-9]+)", value)
    if match:
        return match.group(1), match.group(2)
    return default_country.upper(), value
