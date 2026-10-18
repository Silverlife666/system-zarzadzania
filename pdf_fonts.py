"""Wspólna rejestracja czcionki z polskimi znakami dla wszystkich modułów PDF (reportlab).

W głównym pliku aplikacji (tam, gdzie dziś definiowane są FONT_REGULAR i FONT_BOLD):

    from pdf_fonts import register_polish_fonts
    FONT_REGULAR, FONT_BOLD = register_polish_fonts(APP_DIR)

Każdy moduł, który używa FONT_REGULAR / FONT_BOLD, dostaje wtedy poprawne polskie litery.
Czcionki wyszukiwane są w: APP_DIR/fonts, folderze tego pliku/fonts, Windows (Arial, Segoe UI, Calibri, Tahoma),
Linux/macOS (Liberation, DejaVu) i matplotlib. Zalecane: skopiować LiberationSans-Regular.ttf i -Bold.ttf do APP_DIR/fonts.
"""
from pathlib import Path

POLISH = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
_PAIRS = [("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"), ("arial.ttf", "arialbd.ttf"), ("Arial.ttf", "Arial Bold.ttf"),
          ("segoeui.ttf", "segoeuib.ttf"), ("calibri.ttf", "calibrib.ttf"), ("tahoma.ttf", "tahomabd.ttf"), ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")]
_cache = {}


def _supports(name):
    from reportlab.pdfbase import pdfmetrics
    try:
        cmap = getattr(getattr(pdfmetrics.getFont(name), "face", None), "charToGlyph", None)
        return bool(cmap) and all(ord(c) in cmap for c in POLISH)
    except Exception:
        return False


def register_polish_fonts(app_dir=None, regular_name="AppSans", bold_name="AppSans-Bold"):
    """Zwraca (nazwa_zwykłej, nazwa_pogrubionej). Gdy nic nie znajdzie – ('Helvetica', 'Helvetica-Bold') i ostrzeżenie w konsoli."""
    key = str(app_dir)
    if key in _cache:
        return _cache[key]
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if _supports(regular_name) and _supports(bold_name):
        return _cache.setdefault(key, (regular_name, bold_name))
    dirs = ([Path(app_dir) / "fonts"] if app_dir else []) + [Path(__file__).resolve().parent / "fonts", Path("C:/Windows/Fonts"),
            Path("/usr/share/fonts/truetype/liberation"), Path("/usr/share/fonts/truetype/dejavu"), Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]
    try:
        import matplotlib
        dirs.append(Path(matplotlib.get_data_path()) / "fonts" / "ttf")
    except Exception:
        pass
    for d in dirs:
        for r, b in _PAIRS:
            if (d / r).is_file() and (d / b).is_file():
                try:
                    pdfmetrics.registerFont(TTFont(regular_name, str(d / r))); pdfmetrics.registerFont(TTFont(bold_name, str(d / b)))
                    if _supports(regular_name) and _supports(bold_name):
                        return _cache.setdefault(key, (regular_name, bold_name))
                except Exception:
                    continue
    print("[pdf_fonts] UWAGA: nie znaleziono czcionki z polskimi znakami – PDF-y będą bez polskich liter. Skopiuj LiberationSans-Regular.ttf i LiberationSans-Bold.ttf do folderu fonts.")
    return _cache.setdefault(key, ("Helvetica", "Helvetica-Bold"))
