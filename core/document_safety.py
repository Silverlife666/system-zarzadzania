"""Walidacja ścieżek i kompletności dokumentów zleceń."""

from __future__ import annotations

import os
from collections.abc import Iterable


def is_path_in_directory(file_path: str, directory: str) -> bool:
    """Sprawdza, czy ścieżka nie wychodzi poza katalog aplikacji."""
    if not file_path or not directory:
        return False
    try:
        root = os.path.normcase(os.path.abspath(directory))
        candidate = os.path.normcase(os.path.abspath(file_path))
        return os.path.commonpath([root, candidate]) == root
    except (TypeError, ValueError):
        return False


def document_file_is_ready(file_path: str, order_directories: str | Iterable[str]) -> bool:
    """Dokument jest gotowy wyłącznie wtedy, gdy istnieje w katalogu zlecenia lub jego archiwum."""
    directories = [order_directories] if isinstance(order_directories, str) else list(order_directories)
    return os.path.isfile(file_path) and any(is_path_in_directory(file_path, directory) for directory in directories)
