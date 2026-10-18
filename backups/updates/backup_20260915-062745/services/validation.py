"""Walidacje niezależne od formularzy Streamlit."""

from __future__ import annotations

import re


def validate_ean_gtin(value: object) -> tuple[bool, str]:
    code = re.sub(r"\s", "", str(value or ""))
    if not code:
        return True, ""
    if not code.isdigit() or len(code) not in {8, 12, 13, 14}:
        return False, "EAN/GTIN musi mieć 8, 12, 13 albo 14 cyfr."
    checksum = sum((3 if position % 2 else 1) * int(digit) for position, digit in enumerate(reversed(code[:-1]), start=1))
    if (10 - checksum % 10) % 10 != int(code[-1]):
        return False, "Nieprawidłowa cyfra kontrolna EAN/GTIN."
    return True, ""


def validate_required_text(value: object, label: str, required: bool = False) -> tuple[bool, str]:
    text = str(value or "").strip()
    if required and not text:
        return False, f"Pole „{label}” jest wymagane."
    if text and (len(text) > 200 or re.search(r"[<>\\{}\[\]|\x00-\x1f]", text)):
        return False, f"Pole „{label}” zawiera niedozwolone znaki."
    return True, ""
