"""Niezależna od Streamlit kontrola dostępności i podglądu PDF."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile


def inspect_pdf_visually(file_path: str, *, dpi: int = 140, which=shutil.which, run=subprocess.run) -> dict:
    """Rasteruje pierwszą stronę PDF przez Poppler i zwraca jej bajty oraz liczbę stron."""
    if not os.path.isfile(file_path):
        return {"ok": False, "message": "Plik nie istnieje na dysku."}
    renderer = which("pdftoppm")
    if not renderer:
        return {"ok": False, "message": "Brak narzędzia pdftoppm (Poppler). Zainstaluj Poppler i uruchom aplikację ponownie."}
    page_count = None
    info_tool = which("pdfinfo")
    if info_tool:
        try:
            info = run([info_tool, file_path], capture_output=True, text=True, timeout=20, check=False)
            match = re.search(r"^Pages:\s*(\d+)", info.stdout or "", flags=re.MULTILINE)
            page_count = int(match.group(1)) if match else None
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        with tempfile.TemporaryDirectory(prefix="pdf_preview_") as temporary_directory:
            output_prefix = os.path.join(temporary_directory, "page")
            result = run([renderer, "-f", "1", "-l", "1", "-r", str(dpi), "-singlefile", "-png", file_path, output_prefix], capture_output=True, text=True, timeout=45, check=False)
            preview_path = f"{output_prefix}.png"
            if result.returncode != 0 or not os.path.isfile(preview_path):
                error = (result.stderr or result.stdout or "Nie udało się zrasteryzować PDF.").strip()
                return {"ok": False, "message": error[:500]}
            with open(preview_path, "rb") as preview_file:
                preview = preview_file.read()
        return {"ok": True, "preview": preview, "pages": page_count, "message": "Pierwsza strona została wyrenderowana poprawnie."}
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "message": f"Błąd kontroli wizualnej: {error}"}
