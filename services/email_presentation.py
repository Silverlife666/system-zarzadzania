"""Stałe i czysta prezentacja danych dla modułu E-mail."""

from __future__ import annotations


def default_email_branding() -> dict:
    return {
        "company_name": "", "address": "", "phone": "", "website": "",
        "legal_footer": "Wiadomość firmowa. Prosimy nie przekazywać jej osobom nieuprawnionym.",
        "logo_b64": "", "logo_mime": "image/png", "signatures": {},
    }


EMAIL_TEMPLATES = {
    "Raport paletyzacji": ("Raport paletyzacji — {produkt}", "Dzień dobry,\n\nW załączeniu przekazujemy raport paletyzacji dla: {produkt}.\n\nPozdrawiamy,"),
    "Packing List": ("Packing List — {produkt}", "Dzień dobry,\n\nW załączeniu przesyłamy Packing List.\n\nPozdrawiamy,"),
    "Zamówienie do drukarni": ("Zamówienie do drukarni — {produkt}", "Dzień dobry,\n\nProsimy o realizację zamówienia. Dokumentacja znajduje się w załącznikach.\n\nPozdrawiamy,"),
    "Karta Pracy": ("Karta Pracy — {produkt}", "Dzień dobry,\n\nW załączeniu przesyłamy Kartę Pracy.\n\nPozdrawiamy,"),
    "Karta Techniczna TDS": ("Karta Techniczna (TDS) — {produkt}", "Dzień dobry,\n\nW załączeniu przesyłamy Kartę Techniczną produktu.\n\nPozdrawiamy,"),
    "PPWR / deklaracje": ("Dokumentacja PPWR — {produkt}", "Dzień dobry,\n\nW załączeniu przekazujemy raport PPWR oraz deklaracje.\n\nPozdrawiamy,"),
    "Reklamacja do drukarni": ("Reklamacja — {produkt}", "Dzień dobry,\n\nProsimy o analizę wskazanych niezgodności. Raport QA znajduje się w załączniku.\n\nPozdrawiamy,"),
    "Awizacja transportu": ("Awizacja transportu — {produkt}", "Dzień dobry,\n\nPrzekazujemy dane do awizacji transportu.\n\nPozdrawiamy,"),
    "Przypomnienie o terminie": ("Przypomnienie — {produkt}", "Dzień dobry,\n\nPrzypominamy o zbliżającym się terminie realizacji.\n\nPozdrawiamy,"),
    "Prośba o akceptację pliku": ("Prośba o akceptację pliku — {produkt}", "Dzień dobry,\n\nProsimy o akceptację załączonego pliku.\n\nPozdrawiamy,"),
}


def email_template_content(template_name: str, product: str, language: str = "Polski") -> tuple[str, str]:
    """Zwraca uzupełniony temat i treść, bez zależności od interfejsu."""
    subject, body = EMAIL_TEMPLATES.get(template_name, next(iter(EMAIL_TEMPLATES.values())))
    if language == "English":
        subject = subject.replace("Raport paletyzacji", "Palletisation report").replace("Zamówienie", "Order")
        body = body.replace("Dzień dobry", "Dear Sir or Madam").replace("Pozdrawiamy", "Kind regards").replace("W załączeniu", "Please find attached")
    return subject.format(produkt=product or "produkt"), body.format(produkt=product or "produkt")


def mask_history_addresses(rows: list[dict], *, is_administrator: bool) -> list[dict]:
    """Maskuje odbiorców dla ról bez dostępu do pełnych danych kontaktowych."""
    if is_administrator:
        return [dict(row) for row in rows]
    import re
    result = []
    for row in rows:
        masked = dict(row)
        for key in ("to", "cc", "bcc"):
            value = str(masked.get(key, ""))
            masked[key] = re.sub(r"(?<=.).(?=[^@]*@)", "•", value)
        result.append(masked)
    return result
