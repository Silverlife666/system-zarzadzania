import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import io
import os
import time
import json
import base64
import hashlib
import smtplib
import re
import shutil
import zipfile
import subprocess
import tempfile
import secrets
from datetime import datetime, timedelta
from email.message import EmailMessage
from xml.sax.saxutils import escape

from core.document_safety import document_file_is_ready, is_path_in_directory
from core.email_html import render_email_html
from core.packaging import packaging_level_quantities as calculate_packaging_level_quantities
from core.vat import normalize_vat_identifier
from core.pallets import layout_for_orientation, mixed_layout_for_orientation, overhang_status
from core.bct import calculate_bct
from core.ppwr import calculate_ppwr_masses, migrate_legacy_order_units
from core.qa import evaluate_qa_metrics, parse_ignored_regions
from modules.order_center_dashboard import render_order_center_dashboard
from modules.order_center_actions import render_order_center_actions
from modules.order_center_documents import render_order_center_document_files
from modules.order_center_statuses import render_order_center_document_statuses
from modules.order_center_screen import render_order_center_screen
from modules.production_planner import render_production_planner
from modules.form_widgets import render_existing_includable_field, render_includable_field, render_section_master_checkbox
from modules.transport_screen import render_transport_screen
from modules.email_screen import render_email_screen
from modules.pallet_optimization_screen import render_pallet_optimization_screen
from modules.ppwr_screen import render_ppwr_screen
from modules.ppwr_diagram import render_ppwr_packing_diagram
from modules.qa_screen import render_qa_screen
from modules.user_admin_screen import render_user_admin_screen
from modules.catalog_import_screen import render_catalog_import_screen
from modules.palletization_screen import render_palletization_screen
from modules.module6_screen import render_module_six
from modules.module7_screen import render_module_seven
from modules.module8_screen import render_module_eight
from modules.inventory_screen import render_inventory_screen
from modules.order_stock_screen import render_order_stock_screen
from modules.bobbin_calculator_screen import render_bobbin_calculator_screen
from modules.material_library_screen import render_material_library_screen
from modules.client_portal_screen import render_client_portal_screen
from modules.client_commercial_screen import render_client_commercial_screen
from modules.integrations_screen import render_integrations_screen
from modules.update_screen import render_update_screen
from modules.project_archive_screen import render_project_archive_screen
from modules.artwork_approval_screen import render_artwork_approval_screen
from modules.generators_screen import render_generators_screen
from modules.client_product_card_screen import render_client_product_card_screen
from modules.work_settlement_screen import render_work_settlement_screen
from modules.work_settlement_archive_screen import render_work_settlement_archive_screen
from modules.bobbin_settlement_screen import render_bobbin_settlement_screen
from modules.preorder_screen import render_preorder_screen
from modules.preflight_dtp_screen import render_preflight_dtp_screen
from modules.backup_center_screen import render_backup_center_screen
from modules.warehouse_label_screen import render_warehouse_label_screen
from services.update_manager import read_version

from modules.production_documents_full_screen import render_tab9_screen
from modules.production_document_actions import (
    generate_bilingual_eorder, generate_eorder, generate_tds_pdf, generate_worksheet,
)
from modules.production_document_form_data import (
    apply_approval_validation as production_apply_approval_validation,
    project_file_payload as production_project_file_payload,
    project_pdf_fields as production_project_pdf_fields,
    requires_strict_approval as production_requires_strict_approval,
    validate_eorder as production_validate_eorder,
    validate_packaging_relations as production_validate_packaging_relations,
    validate_worksheet as production_validate_worksheet,
)
from modules.production_document_form_actions import (
    save_order_header as production_save_order_header,
    update_production_summary as production_update_production_summary,
)
from modules.production_documents_screen import (
    apply_catalog_selection,
    prepare_production_documents_state,
    render_catalog_selector,
    render_catalog_snapshot_preview,
    render_tds_materials_section,
    render_tds_quantities_section,
    render_tds_artwork_section,
    render_tds_specification_section,
    restore_production_document_state,
    render_tds_form_intro,
    render_order_header_form,
    render_production_documents_intro,
)
from services.order_copy import copy_order_context, create_order_copy_record
from services.ppwr_documents import build_ppwr_mass_specification_pdf
import modules.module8_screen as _legacy_ppwr_document_generators

# Zachowujemy bezpośrednie referencje do oryginalnych generatorów. Kontekst
# zgodności uzupełnia globals modułu legacy, więc odczyt funkcji przez atrybut
# modułu mógł zostać nadpisany przez poniższe wrappery i wywoływać rekurencję.
_legacy_generate_ppwr_mass_specification_pdf = _legacy_ppwr_document_generators.generate_ppwr_mass_specification_pdf
_legacy_generate_eu_declaration_of_conformity_pdf = _legacy_ppwr_document_generators.generate_eu_declaration_of_conformity_pdf
_legacy_generate_production_date_declaration_pdf = _legacy_ppwr_document_generators.generate_production_date_declaration_pdf


def _ppwr_generator_context():
    """Udostępnia generatorom PPWR współdzielone czcionki, PDF i rejestr dokumentów."""
    protected_names = {
        "generate_ppwr_mass_specification_pdf",
        "generate_eu_declaration_of_conformity_pdf",
        "generate_production_date_declaration_pdf",
    }
    _legacy_ppwr_document_generators.__dict__.update(
        {name: value for name, value in globals().items() if name not in protected_names}
    )




def generate_ppwr_mass_specification_pdf(metadata, components, material_summary, language="en", store_document=False):
    _ppwr_generator_context()
    return _legacy_generate_ppwr_mass_specification_pdf(
        metadata, components, material_summary, language=language, store_document=store_document,
    )


def generate_eu_declaration_of_conformity_pdf(issuer, customer, products, confirmations, language="en", store_document=False):
    _ppwr_generator_context()
    return _legacy_generate_eu_declaration_of_conformity_pdf(
        issuer, customer, products, confirmations, language=language, store_document=store_document,
    )


def generate_production_date_declaration_pdf(issuer, customer, products, cutoff_date, language="en", store_document=False):
    _ppwr_generator_context()
    return _legacy_generate_production_date_declaration_pdf(
        issuer, customer, products, cutoff_date, language=language, store_document=store_document,
    )
from services.document_bundle import build_order_documents_zip, order_document_files
from services.document_storage import clear_pdf_version_history, store_pdf_version
from services.order_context import UNSERIALIZABLE_CONTEXT as SERVICE_UNSERIALIZABLE_CONTEXT, deserialize_context_value, serialize_context_value
from services.order_registry import derive_order_lifecycle, generate_short_order_id, new_order_record, register_document_record
from services.storage import SharedStateStore
from services.supabase_storage import CloudStorageUnavailable, SupabaseStateStore
from services.validation import validate_ean_gtin, validate_required_text
from services.email_service import prepare_email_delivery
from services.document_generation import bct_document_rows
from services.product_catalog import build_catalog_snapshot as service_build_catalog_snapshot, ean_conflicts, normalize_product_record as normalize_catalog_product_record
from services.navigation import (
    available_modules as navigation_available_modules,
    available_navigation_groups,
    group_for_module_id,
    group_for_module_label,
    module_label_for_id,
)
from services.user_access import apply_role_permissions, build_role_permissions, save_user_access_config, update_user_credentials
from services.production_planning import empty_production_plan, normalize_production_plan
from services.production_documents import (
    DeepLTranslationError,
    build_eorder_bilingual_pdf,
    build_eorder_pdf,
    build_structured_document_pdf,
    build_worksheet_pdf,
    printer_copy_data,
    printer_copy_data_en,
    printer_copy_translation_rows,
    worksheet_item_data,
)
from services.smtp_message import build_smtp_message
from services.qa_files import image_slider_html, inspect_pdf_separations, render_validation_bytes
from services.bct_documents import build_bct_report_pdf, build_bct_text_document_pdf
from services.email_attachments import load_order_pdf_attachments
from services.ppwr_documents import (
    build_ppwr_mass_specification_pdf, format_ppwr_number,
    ppwr_deepl_translation_overrides, ppwr_translation_rows,
)
from services.order_center_analysis import (
    end_to_end_checks as service_end_to_end_checks,
    order_data_quality as service_order_data_quality,
    order_flow_map as service_order_flow_map,
)
from services.pdf_visual import inspect_pdf_visually as service_inspect_pdf_visually
from services.order_requirements import requirement_status as service_requirement_status
from services.transport_documents import build_transport_order_pdf
from services.packing_documents import build_basic_packing_list_pdf, build_packing_list_pdf
from services.pallet_documents import build_pallet_labels_pdf, decode_qr_bytes
from services.mastercase_documents import build_mastercase_2d_pdf
from services.pallet_layout_documents import build_pallet_layout_2d_pdf
from services.email_presentation import EMAIL_TEMPLATES, default_email_branding, email_template_content, mask_history_addresses
from services.order_documents import (
    as_positive_int as order_as_positive_int,
    default_order_header as service_default_order_header,
    order_header_pdf_fields as service_order_header_pdf_fields,
    packaging_calculation as service_packaging_calculation,
    packaging_pdf_fields as service_packaging_pdf_fields,
    selected_ean as service_selected_ean,
    validate_base_data as service_validate_base_data,
)

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import plotly.graph_objects as go

from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

def bct_pdf_section():
    result = st.session_state.get("bct_last_result") or st.session_state.get("bct_for_tds") or {}
    if not result:
        return []
    style = ParagraphStyle("BCTPdfSection", parent=getSampleStyleSheet()["Normal"], fontName=FONT_REGULAR, fontSize=8, leading=10)
    values = bct_document_rows(result)
    table=Table(values,colWidths=[150,350]); table.setStyle(TableStyle([("SPAN",(0,0),(-1,0)),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#123B69")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,-1),FONT_REGULAR),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#CBD5E1")),("PADDING",(0,0),(-1,-1),5)]))
    return [Spacer(1,10), table]


def get_bct_palletization_gate(order_id, layers, gross_mass_kg, loaded_height_mm):
    """Zwraca informacyjną ocenę BCT bez blokowania przepływu między modułami."""
    bct_result = st.session_state.get("bct_for_palletization") or st.session_state.get("bct_last_result") or {}
    if not isinstance(bct_result, dict) or not bct_result:
        return {"blocked": False, "status": "brak analizy BCT (informacyjnie)", "reasons": ["Brak analizy BCT dla bieżącego zlecenia."], "result": {}}
    result_order_id = str(bct_result.get("order_id", "")).strip()
    if result_order_id and result_order_id != str(order_id):
        return {"blocked": False, "status": "BCT z innego zlecenia (informacyjnie)", "reasons": ["Analiza BCT nie należy do aktywnego zlecenia."], "result": bct_result}

    def number(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    reasons = []
    if str(bct_result.get("approval", "")).strip().lower() != "zatwierdzony":
        reasons.append("Analiza BCT nie ma statusu „zatwierdzony”.")
    max_layers = int(number(bct_result.get("max_safe_layers")))
    max_pallet_mass = number(bct_result.get("max_safe_pallet_mass_kg"))
    max_height = number(bct_result.get("max_safe_pallet_height_mm"))
    if max_layers > 0 and int(layers) > max_layers:
        reasons.append(f"Liczba warstw {int(layers)} przekracza limit BCT: {max_layers}.")
    if max_pallet_mass > 0 and number(gross_mass_kg) > max_pallet_mass:
        reasons.append(f"Masa palety {number(gross_mass_kg):.1f} kg przekracza limit BCT: {max_pallet_mass:.1f} kg.")
    if max_height > 0 and number(loaded_height_mm) > max_height:
        reasons.append(f"Wysokość palety {number(loaded_height_mm):.0f} mm przekracza zatwierdzony limit BCT: {max_height:.0f} mm.")
    return {
        "blocked": False,
        "status": "uwaga BCT" if reasons else "zgodne z zatwierdzonym BCT",
        "reasons": reasons,
        "result": bct_result,
    }
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF



#nowy kod#


# Rejestracja czcionki obsługującej polskie znaki
@st.cache_resource
def register_polish_fonts():
    """Rejestruje czcionkę z polskimi znakami. Kolejność: folder fonts/ aplikacji, Windows, Linux, czcionka DejaVu dołączona do matplotlib."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        (os.path.join(here, "fonts", "LiberationSans-Regular.ttf"), os.path.join(here, "fonts", "LiberationSans-Bold.ttf")),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    try:
        mpl_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")  # matplotlib jest zawsze w aplikacji
        candidates.append((os.path.join(mpl_dir, "DejaVuSans.ttf"), os.path.join(mpl_dir, "DejaVuSans-Bold.ttf")))
    except Exception:
        pass
    for regular, bold in candidates:
        if os.path.exists(regular):
            try:
                pdfmetrics.registerFont(TTFont('PolishFont', regular))
                pdfmetrics.registerFont(TTFont('PolishFont-Bold', bold if os.path.exists(bold) else regular))
                return 'PolishFont', 'PolishFont-Bold'
            except Exception:
                pass
    print("UWAGA: nie znaleziono czcionki z polskimi znakami - PDF-y będą bez polskich liter.")
    return 'Helvetica', 'Helvetica-Bold'


FONT_REGULAR, FONT_BOLD = register_polish_fonts()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DATA_DIR = os.path.join(APP_DIR, "dane_aplikacji")
os.makedirs(APP_DATA_DIR, exist_ok=True)


def application_storage_path(file_name):
    """Zwraca ścieżkę we wspólnym magazynie danych i migruje starszy plik bez nadpisywania."""
    target_path = os.path.join(APP_DATA_DIR, file_name)
    legacy_candidates = [os.path.join(APP_DIR, file_name), os.path.abspath(file_name)]
    if os.path.exists(target_path):
        return target_path
    legacy_path = next((path for path in legacy_candidates if path != target_path and os.path.isfile(path)), "")
    if not legacy_path:
        return target_path
    try:
        # Dla SQLite używamy mechanizmu backup, aby poprawnie obsłużyć bazę
        # pracującą wcześniej w trybie WAL; zwykłe kopiowanie pliku mogłoby
        # pominąć ostatnie zatwierdzone dane.
        if file_name.lower().endswith(".db"):
            with sqlite3.connect(legacy_path) as source_db, sqlite3.connect(target_path) as target_db:
                source_db.backup(target_db)
        else:
            shutil.copy2(legacy_path, target_path)
    except (OSError, sqlite3.Error):
        # Nie kasujemy ani nie nadpisujemy starego pliku, gdy migracja się nie uda.
        pass
    return target_path


def application_storage_directory(directory_name):
    """Zwraca katalog danych i kopiuje do niego starsze dokumenty bez usuwania oryginału."""
    target_path = os.path.join(APP_DATA_DIR, directory_name)
    legacy_path = os.path.join(APP_DIR, directory_name)
    if not os.path.isdir(target_path) and os.path.isdir(legacy_path):
        try:
            shutil.copytree(legacy_path, target_path)
        except OSError:
            pass
    os.makedirs(target_path, exist_ok=True)
    return target_path


# Wszystkie dane robocze i dokumenty są teraz skupione w katalogu dane_aplikacji.
# Istniejące pliki z katalogu głównego są kopiowane przy pierwszym użyciu.
DB_FILE = application_storage_path("print_db.json")
DOCUMENT_REGISTRY_FILE = application_storage_path("rejestr_dokumentow.json")
DOCUMENT_FILES_DIR = application_storage_directory("dokumenty_zlecen")
DOCUMENT_ARCHIVE_DIR = application_storage_directory("archiwum_dokumentow_zlecen")
ORDER_CONTEXT_FILE = application_storage_path("konteksty_zlecen.json")
USER_WORKSPACE_FILE = application_storage_path("ustawienia_przestrzeni_uzytkownikow.json")
PRODUCTION_PLANNER_FILE = application_storage_path("plan_produkcji.json")
INVENTORY_SESSIONS_FILE = application_storage_path("sesje_inwentaryzacji.json")
ORDER_STOCK_ARCHIVE_FILE = application_storage_path("archiwum_rozliczenia_stanu_zamowienia.json")
WORK_SETTLEMENT_ARCHIVE_FILE = application_storage_path("archiwum_rozliczen_pracy.json")
PREORDER_ARCHIVE_FILE = application_storage_path("archiwum_preorderow.json")
APP_STATE_DB = application_storage_path("magazyn_stanu_aplikacji.db")
_supabase_url = str(st.secrets.get("supabase", {}).get("url", "")).strip()
_supabase_key = str(st.secrets.get("supabase", {}).get("key", "")).strip()
# Streamlit Community Cloud uruchamia repozytorium pod /mount/src. Zmienna
# STREAMLIT_SHARING_MODE nie jest obecna we wszystkich obrazach, więc sama nie
# może być jedyną blokadą przed uruchomieniem lokalnego fallbacku w chmurze.
_is_streamlit_cloud = bool(os.environ.get("STREAMLIT_SHARING_MODE")) or os.path.normpath(APP_DIR).startswith(os.path.normpath("/mount/src"))
if not (_supabase_url and _supabase_key) and _is_streamlit_cloud:
    st.error(
        "Brak konfiguracji Supabase w Settings → Secrets. Dodaj sekcję [supabase] z url i key, "
        "a następnie zrestartuj aplikację. Dane nie zostaną zapisane lokalnie."
    )
    st.stop()
SHARED_STATE_STORE = (
    SupabaseStateStore(APP_STATE_DB, APP_DATA_DIR, _supabase_url, _supabase_key)
    if _supabase_url and _supabase_key
    else SharedStateStore(APP_STATE_DB, APP_DATA_DIR)
)
EORDER_LOGO_PATH = os.path.join(APP_DIR, "logo1.jpg")
WORKSHEET_LOGO_PATH = os.path.join(APP_DIR, "logo2.jpg")


def _state_storage_connection():
    connection = sqlite3.connect(APP_STATE_DB)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS application_state (
        state_key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_epoch REAL NOT NULL
        )"""
    )
    return connection


def _atomic_write_json(path, data):
    """Zapis odporny na przerwanie procesu: najpierw plik tymczasowy, potem podmiana."""
    SHARED_STATE_STORE.atomic_write_json(path, data)


def load_shared_state(state_key, mirror_path, default):
    """Odczytuje dane z centralnej SQLite i jednokrotnie/migrująco synchronizuje starszy JSON."""
    try:
        return SHARED_STATE_STORE.load(state_key, mirror_path, default)
    except CloudStorageUnavailable as error:
        st.error(str(error))
        st.stop()


def save_shared_state(state_key, mirror_path, data):
    """Zapisuje centralnie w SQLite oraz zostawia bezpieczną kopię JSON do eksportu i zgodności."""
    try:
        SHARED_STATE_STORE.save(state_key, mirror_path, data)
    except CloudStorageUnavailable as error:
        st.error(str(error))
        st.stop()


def load_persistent_json(path, default):
    """Odczytuje pomocniczy słownik/listę z centralnej SQLite i kopii JSON.

    Szablony, biblioteki i archiwa pozostają eksportowalnymi plikami JSON,
    lecz źródłem trwałego stanu jest wspólny magazyn aplikacji.
    """
    normalized_path = os.path.normcase(os.path.abspath(path))
    state_key = "json_store:" + hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()
    value = load_shared_state(state_key, path, default)
    return value if isinstance(value, type(default)) else default


def save_persistent_json(path, data):
    """Zapisuje dane pomocnicze atomowo i centralnie."""
    normalized_path = os.path.normcase(os.path.abspath(path))
    state_key = "json_store:" + hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()
    save_shared_state(state_key, path, data)


def load_operational_json(path, default):
    """Trwałe dane operacyjne o stabilnym kluczu, niezależnym od ścieżki hosta."""
    state_key = "operational_json:" + os.path.basename(os.fspath(path))
    value = load_shared_state(state_key, os.fspath(path), default)
    return value if isinstance(value, type(default)) else default


def save_operational_json(path, data):
    state_key = "operational_json:" + os.path.basename(os.fspath(path))
    save_shared_state(state_key, os.fspath(path), data)


# Klucze z tych modułów są przechowywane osobno dla każdego zlecenia.
# Dzięki temu otwarcie innego order_id nie miesza wyników paletyzacji, BCT,
# PPWR, Packing List ani QA z aktualnie oglądanym zleceniem.
ORDER_CONTEXT_MODULES = {2, 4, 5, 6, 7, 8, 9, 10, 11, 24, 26}
ORDER_CONTEXT_KEYS = {
    "pal_calc_result", "pal_calc_last", "sug_layout_result", "sug_layout_session",
    "packing_document", "transport_prefill", "transport_document", "bct_last_result", "bct_for_order",
    "bct_for_tds", "bct_for_ppwr", "bct_for_palletization", "bct_for_packing_list",
    "email_auto_attachment", "order_data", "order_snapshot", "tds_items", "tab9_order_header", "saved_specification",
    "e_order_items", "work_sheet_items", "box_rightsizing_result",
}
ORDER_CONTEXT_PREFIXES = ("calc_", "sug_", "packing_", "rs_", "bct_", "ppwr_", "print_qa_", "qa_", "eo_", "ws_")
# Klucze kontrolek (zwłaszcza przycisków) nie są danymi zlecenia. Streamlit nie
# pozwala przywracać wartości przycisku przez session_state, dlatego nie wolno
# ich utrwalać ani odtwarzać przy zmianie zlecenia.
ORDER_CONTEXT_TRANSIENT_PREFIXES = (
    "ppwr_add_option_", "ppwr_remove_option_", "ppwr_new_option_", "ppwr_selected_dictionary",
    "ppwr_diagram_upload_", "ppwr_diagram_step_upload_", "ppwr_components_editor_",
    "ppwr_component_library_editor",
    "ppwr_save_", "ppwr_add_", "ppwr_remove_", "ppwr_load_", "ppwr_delete_", "ppwr_move_",
    "ppwr_translate_", "ppwr_download_", "ppwr_appendix_uploader_", "ppwr_manual_translation_editor_",
    "ppwr_declaration_items_editor",
)
_UNSERIALIZABLE_CONTEXT = SERVICE_UNSERIALIZABLE_CONTEXT

ORDER_REQUIREMENT_LABELS = {
    "tds": "TDS / Zamówienie",
    "eorder": "E-Order",
    "worksheet": "Karta Pracy",
    "packing_list": "Packing List",
    "bct": "Raport BCT (zatwierdzony)",
    "ppwr": "Raport PPWR",
    "declaration_compliance": "Deklaracja zgodności PPWR",
    "declaration_production_date": "Deklaracja daty produkcji",
    "qa": "Raport QA drukarni",
}
ORDER_REQUIREMENT_PROFILES = {
    "Standard produkcyjny": ["ppwr", "qa"],
    "Zlecenie do drukarni": ["tds", "eorder", "worksheet", "qa"],
    "Wysyłka": ["packing_list"],
    "PPWR": ["ppwr", "declaration_compliance", "declaration_production_date"],
    "Własny": [],
}


def _serialize_order_context_value(value):
    """Konwertuje bezpieczne wartości sesji na format JSON; pomija np. uploady plików."""
    return serialize_context_value(value)


def _deserialize_order_context_value(value):
    return deserialize_context_value(value)


def load_order_contexts():
    data = load_shared_state("order_contexts", ORDER_CONTEXT_FILE, {})
    return data if isinstance(data, dict) else {}


def save_order_context(order_id=None):
    """Zapisuje bieżące dane robocze modułów do trwałego kontekstu order_id."""
    context_order_id = order_id or st.session_state.get("order_id")
    if not context_order_id:
        return
    context = {}
    for key, value in st.session_state.items():
        if (key in ORDER_CONTEXT_KEYS or key.startswith(ORDER_CONTEXT_PREFIXES)) and not key.startswith(ORDER_CONTEXT_TRANSIENT_PREFIXES):
            encoded = _serialize_order_context_value(value)
            if encoded is not _UNSERIALIZABLE_CONTEXT:
                context[key] = encoded
    contexts = load_order_contexts()
    contexts[context_order_id] = {"updated_at": datetime.now().isoformat(timespec="seconds"), "data": context}
    save_shared_state("order_contexts", ORDER_CONTEXT_FILE, contexts)


def restore_order_context(order_id):
    """Wczytuje zapisany kontekst do sesji zanim zostanie wyrenderowany moduł."""
    saved = load_order_contexts().get(order_id, {}).get("data", {})
    # Nowe albo starsze zlecenie może nie mieć części danych. Usuwamy wtedy
    # odpowiadające im wartości poprzedniego zlecenia, aby nie pokazać ich omyłkowo.
    for key in list(st.session_state.keys()):
        is_context_key = (key in ORDER_CONTEXT_KEYS or key.startswith(ORDER_CONTEXT_PREFIXES)) and not key.startswith(ORDER_CONTEXT_TRANSIENT_PREFIXES)
        if is_context_key and key not in saved:
            del st.session_state[key]
    for key, value in saved.items():
        restored_value = _deserialize_order_context_value(value)
        # Przycisk Streamlit przechowuje wartość bool. Stare konteksty zleceń mogły
        # zawierać taki stan, którego nie wolno przypisać do widgetu po odświeżeniu.
        if key.startswith(ORDER_CONTEXT_TRANSIENT_PREFIXES):
            continue
        if key.startswith("ppwr_") and isinstance(restored_value, bool):
            continue
        st.session_state[key] = restored_value
    st.session_state["_loaded_order_context_id"] = order_id


def activate_order_context(order_id):
    """Bezpiecznie przełącza zlecenie: najpierw zapisuje poprzednie, potem ładuje wybrane."""
    previous_order_id = st.session_state.get("order_id")
    if previous_order_id and previous_order_id != order_id:
        save_order_context(previous_order_id)
    st.session_state["order_id"] = order_id
    restore_order_context(order_id)
    save_active_order_for_user(order_id)


def load_user_workspace_preferences():
    """Zwraca wyłącznie niesensytywne ustawienia widoku danego użytkownika."""
    data = load_persistent_json(USER_WORKSPACE_FILE, {})
    return data if isinstance(data, dict) else {}


def save_active_order_for_user(order_id):
    """Pamięta ostatnio wybrane zlecenie po ponownym, poprawnym zalogowaniu."""
    user_name = str(st.session_state.get("user_name") or "").strip()
    if not user_name or not order_id:
        return
    preferences = load_user_workspace_preferences()
    preferences[user_name] = {
        **(preferences.get(user_name, {}) if isinstance(preferences.get(user_name), dict) else {}),
        "active_order_id": str(order_id),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_persistent_json(USER_WORKSPACE_FILE, preferences)


def create_new_order():
    """Zakłada puste zlecenie wraz z trwałym wpisem w Centrum zlecenia."""
    registry = load_document_registry()
    new_order_id = generate_short_order_id(datetime.now().strftime("%y%m%d"), registry, secrets.token_hex)
    now = datetime.now().isoformat(timespec="seconds")
    registry[new_order_id] = new_order_record(now, st.session_state.get("user_name", ""))
    save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)
    activate_order_context(new_order_id)
    return new_order_id


def delete_order_permanently(order_id, delete_files=True):
    """Usuwa wpis zlecenia i - po potwierdzeniu - wyłącznie jego pliki aplikacji."""
    registry = load_document_registry()
    if order_id not in registry:
        raise ValueError("Wybrane zlecenie nie istnieje w rejestrze.")

    removed_paths = []
    if delete_files:
        for root_path in (DOCUMENT_FILES_DIR, DOCUMENT_ARCHIVE_DIR):
            order_directory = os.path.abspath(os.path.join(root_path, order_id))
            if not _is_path_in_directory(order_directory, root_path):
                raise ValueError("Nieprawidłowa ścieżka katalogu zlecenia.")
            if os.path.isdir(order_directory):
                shutil.rmtree(order_directory)
                removed_paths.append(order_directory)

    del registry[order_id]
    save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)

    contexts = load_order_contexts()
    if order_id in contexts:
        del contexts[order_id]
        save_shared_state("order_contexts", ORDER_CONTEXT_FILE, contexts)
    return removed_paths


def synchronize_order_context():
    """Utrwala edycje w aktualnym module bez potrzeby dodatkowego przycisku Zapisu."""
    active_order_id = get_current_order_id()
    if st.session_state.get("_loaded_order_context_id") != active_order_id:
        restore_order_context(active_order_id)
    else:
        save_order_context(active_order_id)


def get_current_order_id():
    if "order_id" not in st.session_state:
        registry = load_document_registry()
        user_name = str(st.session_state.get("user_name") or "").strip()
        preferences = load_user_workspace_preferences()
        saved_order_id = str(
            (preferences.get(user_name, {}) if isinstance(preferences.get(user_name), dict) else {}).get("active_order_id")
            or ""
        )
        if saved_order_id in registry:
            st.session_state["order_id"] = saved_order_id
        elif registry:
            st.session_state["order_id"] = max(
                registry,
                key=lambda order_id: registry.get(order_id, {}).get("updated_at", ""),
            )
        else:
            st.session_state["order_id"] = generate_short_order_id(
                datetime.now().strftime("%y%m%d"), registry, secrets.token_hex,
            )
    current_order_id = st.session_state["order_id"]
    user_name = str(st.session_state.get("user_name") or "").strip()
    if user_name:
        preferences = load_user_workspace_preferences()
        user_preferences = preferences.get(user_name, {})
        saved_order_id = str(
            (user_preferences if isinstance(user_preferences, dict) else {}).get("active_order_id") or ""
        )
        if saved_order_id != current_order_id:
            save_active_order_for_user(current_order_id)
    return current_order_id


def update_order_snapshot(section, payload, order_id=None):
    """Utrwala wspólną migawkę danych, aby moduły korzystały z tego samego źródła."""
    order_id = order_id or get_current_order_id()
    snapshot = st.session_state.get("order_snapshot", {})
    if snapshot.get("order_id") != order_id:
        snapshot = {"order_id": order_id, "sections": {}}
    snapshot.setdefault("sections", {})[section] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "data": _serialize_order_context_value(payload),
    }
    snapshot["updated_at"] = datetime.now().isoformat(timespec="seconds")
    st.session_state["order_snapshot"] = snapshot
    registry = load_document_registry()
    record = registry.setdefault(order_id, {"created_at": snapshot["updated_at"], "documents": []})
    record["shared_snapshot"] = snapshot
    record["updated_at"] = snapshot["updated_at"]
    save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)
    return snapshot

def load_document_registry():
    data = load_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, {})
    return data if isinstance(data, dict) else {}

def register_document(document_type, metadata=None, status="wygenerowany", file_name="", file_path="", approved_by="", order_id=None):
    """Tworzy lub aktualizuje jeden wpis dokumentu zamiast dopisywać duplikaty."""
    order_id = order_id or get_current_order_id()
    registry = load_document_registry()
    record = registry.setdefault(order_id, {"created_at": datetime.now().isoformat(timespec="seconds"), "documents": []})
    now = datetime.now().isoformat(timespec="seconds")
    record["updated_at"] = now
    record["documents"] = register_document_record(
        record.setdefault("documents", []), document_type, now, metadata=metadata, status=status,
        file_name=file_name, file_path=file_path, approved_by=approved_by,
        operator=st.session_state.get("user_name", ""),
    )
    save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)
    update_order_lifecycle_status(order_id)
    return order_id

def store_order_pdf(document_type, pdf_bytes, file_name, metadata=None, order_id=None):
    """Zapisuje PDF wyłącznie w katalogu wskazanego zlecenia i wersjonuje jego wpis."""
    order_id = order_id or get_current_order_id()
    order_dir = os.path.join(DOCUMENT_FILES_DIR, order_id)
    registry = load_document_registry()
    record = registry.setdefault(order_id, {"created_at": datetime.now().isoformat(timespec="seconds"), "documents": []})
    now = datetime.now().isoformat(timespec="seconds")
    record["documents"], file_path, _changed = store_pdf_version(
        record.setdefault("documents", []), document_type, pdf_bytes, file_name, order_dir,
        metadata=metadata, operator=st.session_state.get("user_name", ""), timestamp=now,
    )
    record["updated_at"] = now
    save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)
    update_order_lifecycle_status(order_id)
    return file_path


def get_order_document_file_path(order_id, document_type, file_name=""):
    """Zwraca zapisany plik dokumentu wyłącznie z katalogu wskazanego zlecenia."""
    record = load_document_registry().get(order_id, {})
    candidates = [item for item in record.get("documents", []) if item.get("type") == document_type]
    if file_name:
        candidates = [item for item in candidates if item.get("file_name") == file_name] or candidates
    for item in reversed(candidates):
        path = item.get("file_path", "")
        if path and _is_path_in_directory(path, os.path.join(DOCUMENT_FILES_DIR, order_id)) and os.path.isfile(path):
            return path
    return ""


def restore_order_pdf_version(order_id, document_index, version_path):
    """Przywraca wskazaną wersję jako nową bieżącą wersję dokumentu."""
    own_order_directory = os.path.join(DOCUMENT_FILES_DIR, order_id)
    if not _is_path_in_directory(version_path, own_order_directory) or not os.path.isfile(version_path):
        raise ValueError("Wybrana wersja PDF nie istnieje albo nie należy do tego zlecenia.")
    registry = load_document_registry()
    document = registry.get(order_id, {}).get("documents", [])[document_index]
    with open(version_path, "rb") as file:
        restored_bytes = file.read()
    store_order_pdf(
        document.get("type", "Dokument"), restored_bytes,
        document.get("document_key") or document.get("file_name") or "dokument.pdf",
        {**document.get("metadata", {}), "restored_from": version_path}, order_id=order_id,
    )
    registry = load_document_registry()
    updated_document = registry[order_id]["documents"][document_index]
    updated_document.setdefault("history", []).append({
        "at": datetime.now().isoformat(timespec="seconds"), "action": "przywrócono wcześniejszą wersję PDF",
        "by": st.session_state.get("user_name", ""), "source_file_path": version_path,
        "status": updated_document.get("status", "wygenerowany"),
    })
    save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)


def _is_path_in_directory(file_path, directory):
    """Zgodna wstecznie nazwa dla wspólnej walidacji ścieżek dokumentów."""
    return is_path_in_directory(file_path, directory)


def _is_managed_document_path(file_path):
    """Pozwala usuwać wyłącznie pliki utworzone lub zarchiwizowane przez aplikację."""
    return _is_path_in_directory(file_path, DOCUMENT_FILES_DIR) or _is_path_in_directory(file_path, DOCUMENT_ARCHIVE_DIR)


def archive_order_pdf_file(order_id, file_path):
    """Przenosi plik PDF z bieżącego katalogu zlecenia do katalogu archiwalnego."""
    if not _is_path_in_directory(file_path, DOCUMENT_FILES_DIR) or not os.path.isfile(file_path):
        raise ValueError("Można archiwizować wyłącznie istniejący plik PDF utworzony przez aplikację.")
    target_dir = os.path.join(DOCUMENT_ARCHIVE_DIR, order_id)
    os.makedirs(target_dir, exist_ok=True)
    base_name = os.path.basename(file_path)
    target_path = os.path.join(target_dir, base_name)
    if os.path.exists(target_path):
        stem, extension = os.path.splitext(base_name)
        target_path = os.path.join(target_dir, f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{extension}")
    shutil.move(file_path, target_path)
    return target_path


def delete_order_pdf_file(file_path):
    """Nieodwracalnie usuwa tylko dokument zapisany w katalogu aplikacji."""
    if not _is_managed_document_path(file_path) or not os.path.isfile(file_path):
        raise ValueError("Można usunąć wyłącznie istniejący plik PDF utworzony przez aplikację.")
    os.remove(file_path)


def _legacy_inspect_pdf_visually(file_path, dpi=140):
    """Rasteruje pierwszą stronę PDF do PNG oraz odczytuje liczbę stron przez Poppler."""
    if not os.path.isfile(file_path):
        return {"ok": False, "message": "Plik nie istnieje na dysku."}
    pdf_renderer = shutil.which("pdftoppm")
    if not pdf_renderer:
        return {"ok": False, "message": "Brak narzędzia pdftoppm (Poppler). Zainstaluj Poppler i uruchom aplikację ponownie."}
    page_count = None
    pdf_info = shutil.which("pdfinfo")
    if pdf_info:
        try:
            info = subprocess.run([pdf_info, file_path], capture_output=True, text=True, timeout=20, check=False)
            match = re.search(r"^Pages:\s*(\d+)", info.stdout, flags=re.MULTILINE)
            page_count = int(match.group(1)) if match else None
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        with tempfile.TemporaryDirectory(prefix="pdf_preview_") as temp_dir:
            output_prefix = os.path.join(temp_dir, "page")
            render = subprocess.run(
                [pdf_renderer, "-f", "1", "-l", "1", "-r", str(dpi), "-singlefile", "-png", file_path, output_prefix],
                capture_output=True, text=True, timeout=45, check=False,
            )
            preview_path = f"{output_prefix}.png"
            if render.returncode != 0 or not os.path.isfile(preview_path):
                error = (render.stderr or render.stdout or "Nie udało się zrasteryzować PDF.").strip()
                return {"ok": False, "message": error[:500]}
            with open(preview_path, "rb") as image_file:
                preview_bytes = image_file.read()
        return {"ok": True, "preview": preview_bytes, "pages": page_count, "message": "Pierwsza strona została wyrenderowana poprawnie."}
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "message": f"Błąd kontroli wizualnej: {error}"}


def inspect_pdf_visually(file_path, dpi=140):
    """Zgodny wstecznie punkt wejścia do testowalnej kontroli PDF."""
    return service_inspect_pdf_visually(file_path, dpi=dpi)

def register_order_email(status, recipient, subject, attachment_names):
    order_id = st.session_state.get("email_order_bundle", {}).get("order_id") or get_current_order_id()
    registry = load_document_registry()
    record = registry.setdefault(order_id, {"created_at": datetime.now().isoformat(timespec="seconds"), "documents": []})
    record.setdefault("email_history", []).append({"at": datetime.now().isoformat(timespec="seconds"), "recipient": recipient, "subject": subject, "documents": attachment_names, "status": status, "by": st.session_state.get("user_name", "")})
    record["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)
    update_order_lifecycle_status(order_id)


def _legacy_get_order_requirement_status(order_id, record=None):
    """Zwraca faktyczną kompletność dokumentów wymaganą dla danego zlecenia."""
    registry = load_document_registry()
    record = record or registry.get(order_id, {})
    requirements = record.get("required_documents") or ORDER_REQUIREMENT_PROFILES["Standard produkcyjny"]
    documents = record.get("documents", [])
    def document_ready(key):
        terms = {
            "tds": ("tds", "zamówienie", "zamowienie"), "eorder": ("e-order", "eorder"),
            "worksheet": ("karta pracy",), "packing_list": ("packing list",),
            "ppwr": ("raport ppwr", "mass specification ppwr"),
            "declaration_compliance": ("deklaracja zgodności", "deklaracja zgodnosci"),
            "declaration_production_date": ("deklaracja daty produkcji",), "qa": ("raport qa",),
        }[key]
        # PPWR, deklaracje i QA są dokumentami kontrolnymi; samo wygenerowanie
        # pliku nie oznacza ich zatwierdzenia. Pozostałe dokumenty operacyjne
        # mogą być uznane za gotowe po wygenerowaniu.
        required_statuses = {"zatwierdzony", "zatwierdzone", "wysłany", "wysłane"} if key in {
            "ppwr", "declaration_compliance", "declaration_production_date", "qa"
        } else {"wygenerowany", "zatwierdzony", "zatwierdzone", "wysłany", "wysłane"}
        return any(
            any(term in str(document.get("type", "")).lower() for term in terms)
            and str(document.get("status", "")).strip().lower() in required_statuses
            and document_file_is_ready(
                document.get("file_path", ""), os.path.join(DOCUMENT_FILES_DIR, order_id)
            )
            for document in documents
        )
    context = load_order_contexts().get(order_id, {}).get("data", {})
    bct_context = _deserialize_order_context_value(context.get("bct_last_result", {}))
    bct_approved = str((bct_context or {}).get("approval", "")).strip().lower() == "zatwierdzony"
    if not bct_approved:
        bct_approved = any(
            "bct" in str(document.get("type", "")).lower()
            and str(document.get("metadata", {}).get("approval", "")).lower() == "zatwierdzony"
            for document in documents
        )
    checks = {
        "tds": document_ready("tds"),
        "eorder": document_ready("eorder"),
        "worksheet": document_ready("worksheet"),
        "packing_list": document_ready("packing_list"),
        "bct": bct_approved,
        "ppwr": document_ready("ppwr"),
        "declaration_compliance": document_ready("declaration_compliance"),
        "declaration_production_date": document_ready("declaration_production_date"),
        "qa": document_ready("qa"),
    }
    return requirements, checks


def get_order_requirement_status(order_id, record=None):
    """Pobiera dane aplikacji, a reguły kompletności wykonuje w serwisie."""
    record = record or load_document_registry().get(order_id, {})
    context = _decoded_order_context(order_id) if "_decoded_order_context" in globals() else {
        key: _deserialize_order_context_value(value)
        for key, value in load_order_contexts().get(order_id, {}).get("data", {}).items()
    }
    terms_by_key = {
        "tds": ("tds", "zamówienie", "zamowienie"), "eorder": ("e-order", "eorder"),
        "worksheet": ("karta pracy",), "packing_list": ("packing list",),
        "ppwr": ("raport ppwr", "mass specification ppwr"),
        "declaration_compliance": ("deklaracja zgodności", "deklaracja zgodnosci"),
        "declaration_production_date": ("deklaracja daty produkcji",), "qa": ("raport qa",),
    }
    controlled = {"ppwr", "declaration_compliance", "declaration_production_date", "qa"}
    def document_ready(key, documents):
        statuses = {"zatwierdzony", "zatwierdzone", "wysłany", "wysłane"} if key in controlled else {"wygenerowany", "zatwierdzony", "zatwierdzone", "wysłany", "wysłane"}
        return any(
            any(term in str(document.get("type", "")).lower() for term in terms_by_key[key])
            and str(document.get("status", "")).strip().lower() in statuses
            and document_file_is_ready(document.get("file_path", ""), os.path.join(DOCUMENT_FILES_DIR, order_id))
            for document in documents
        )
    return service_requirement_status(
        record, context, ORDER_REQUIREMENT_PROFILES["Standard produkcyjny"], document_ready=document_ready,
    )


def save_order_delivery_data(order_id, recipient, address, delivery_date):
    """Przechowuje jednego odbiorcę i termin wspólne dla dokumentów zlecenia."""
    registry = load_document_registry()
    now = datetime.now().isoformat(timespec="seconds")
    record = registry.setdefault(order_id, {"created_at": now, "documents": [], "order_history": []})
    delivery_data = {
        "recipient": {key: str(recipient.get(key, "")).strip() for key in ("name", "company", "email")},
        "address": {key: str(address.get(key, "")).strip() for key in ("street", "postal_code", "city", "country")},
        "delivery_date": str(delivery_date or ""),
    }
    if record.get("delivery") != delivery_data:
        record["delivery"] = delivery_data
        header = record.setdefault("order_header", tab9_default_order_header(order_id))
        header["delivery_date"] = delivery_data["delivery_date"]
        header["recipient"] = delivery_data["recipient"]
        header["delivery_address"] = delivery_data["address"]
        record.setdefault("order_history", []).append({
            "at": now, "action": "zaktualizowano wspólne dane dostawy", "by": st.session_state.get("user_name", ""),
        })
        record["updated_at"] = now
        registry[order_id] = record
        save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)
    return delivery_data


def _legacy_get_order_end_to_end_checks(order_id, record=None):
    """Szybka kontrola czterech scenariuszy końcowych bez generowania nowych dokumentów."""
    registry = load_document_registry()
    record = record or registry.get(order_id, {})
    context = load_order_contexts().get(order_id, {}).get("data", {})
    header = record.get("order_header", {})
    eorder_items = _deserialize_order_context_value(context.get("e_order_items", [])) or []
    requirements, checks = get_order_requirement_status(order_id, record)
    results = []
    results.append({
        "Scenariusz": "Nowe zlecenie i nagłówek",
        "Wynik": "OK" if header.get("order_number") else "BŁĄD",
        "Szczegóły": header.get("order_number") or "Brak numeru zlecenia w nagłówku.",
    })
    results.append({
        "Scenariusz": "Komplet dokumentów",
        "Wynik": "OK" if all(checks.get(key, False) for key in requirements) else "UWAGA",
        "Szczegóły": ", ".join(ORDER_REQUIREMENT_LABELS[key] for key in requirements if not checks.get(key, False)) or "Komplet zgodny z checklistą.",
    })
    if record.get("source_order_id"):
        own_directory = os.path.join(DOCUMENT_FILES_DIR, order_id)
        shared_files = [
            item.get("file_path", "") for item in record.get("documents", [])
            if item.get("file_path") and not _is_path_in_directory(item["file_path"], own_directory)
        ]
        results.append({
            "Scenariusz": "Reprint nie współdzieli plików z oryginałem",
            "Wynik": "OK" if not shared_files else "BŁĄD",
            "Szczegóły": "PDF-y są własne albo wymagają wygenerowania." if not shared_files else "Wykryto obcą ścieżkę PDF.",
        })
    if eorder_items:
        invalid_eans = []
        for index, item in enumerate(eorder_items, start=1):
            snapshot = item.get("catalog_snapshot", {})
            expected = tab9_selected_ean(snapshot, item.get("packaging_level", "Produkt")) if snapshot else ""
            if expected and item.get("ean_selected") != expected:
                invalid_eans.append(str(index))
        results.append({
            "Scenariusz": "Wiele pozycji i EAN poziomu opakowania",
            "Wynik": "OK" if not invalid_eans else "BŁĄD",
            "Szczegóły": f"Pozycji E-Order: {len(eorder_items)}." if not invalid_eans else "Błędny EAN w pozycjach: " + ", ".join(invalid_eans),
        })
    return results


def _legacy_get_order_data_quality(order_id, record=None):
    """Zbiera czytelne błędy danych i brakujące połączenia między modułami."""
    registry = load_document_registry()
    record = record or registry.get(order_id, {})
    context = load_order_contexts().get(order_id, {}).get("data", {})
    get_context = lambda key, default=None: _deserialize_order_context_value(context.get(key, default))
    header = record.get("order_header", {}) or get_context("tab9_order_header", {}) or {}
    issues = []
    def add(area, severity, message, fix):
        issues.append({"Obszar": area, "Poziom": severity, "Problem": message, "Zalecenie": fix})

    if not header.get("order_number"):
        add("Nagłówek", "BŁĄD", "Brak numeru zamówienia.", "Otwórz moduł 9 i zapisz nagłówek zlecenia.")
    if not header.get("delivery_date"):
        add("Nagłówek", "UWAGA", "Brak planowanej daty dostawy.", "Uzupełnij termin w module 9 lub E-Order.")
    snapshot = record.get("shared_snapshot", {}) or get_context("order_snapshot", {}) or {}
    expected_sections = {"paletyzacja", "packing_list", "tds", "eorder", "karta_pracy"}
    available_sections = set((snapshot.get("sections", {}) or {}).keys())
    for section in sorted(expected_sections - available_sections):
        add("Integracje", "INFO", f"Brak migawki: {section}.", "Nie jest to błąd, jeżeli moduł nie jest potrzebny; zapisz dane w odpowiednim module, aby je połączyć.")

    packing = get_context("packing_document", {}) or {}
    for index, item in enumerate(packing.get("items", []), start=1):
        level = item.get("Poziom opakowania", "")
        expected_ean = {"Produkt": item.get("EAN produktu", ""), "Display": item.get("EAN displaya", ""), "Master Case": item.get("EAN Master Case", "")}.get(level, "")
        if level not in {"Produkt", "Display", "Master Case"}:
            add("Packing List", "BŁĄD", f"Pozycja {index} nie ma prawidłowego poziomu opakowania.", "Wybierz Produkt, Display lub Master Case.")
        elif expected_ean and str(item.get("EAN/GTIN", "")) != str(expected_ean):
            add("Packing List", "BŁĄD", f"Pozycja {index} ma EAN niezgodny z poziomem {level}.", "Przywróć EAN z kartoteki dla wybranego poziomu.")
        if not str(item.get("LOT", "")).strip():
            add("Packing List", "UWAGA", f"Pozycja {index} nie ma numeru LOT.", "Uzupełnij numer partii przed wysyłką.")

    for index, item in enumerate(get_context("e_order_items", []) or [], start=1):
        snapshot_item = item.get("catalog_snapshot", {})
        expected_ean = tab9_selected_ean(snapshot_item, item.get("packaging_level", "Produkt")) if snapshot_item else ""
        if expected_ean and item.get("ean_selected") != expected_ean:
            add("E-Order", "BŁĄD", f"Pozycja {index} używa niewłaściwego EAN.", "Wybierz EAN zgodny z poziomem opakowania.")
        if tab9_as_positive_int(item.get("qty_shipping", item.get("qty_net", 0))) <= 0:
            add("E-Order", "BŁĄD", f"Pozycja {index} ma ilość wysyłki równą zero.", "Uzupełnij ilość netto lub wysyłki.")

    bct = get_context("bct_last_result", {}) or {}
    if bct and bct.get("approval") != "zatwierdzony":
        add("BCT", "UWAGA", f"BCT ma status: {bct.get('approval', 'brak')}.", "Zatwierdź konstrukcję przed produkcją lub wysyłką.")
    for document in record.get("documents", []):
        path = document.get("file_path", "")
        if path and not os.path.isfile(path):
            add("Dokumenty", "BŁĄD", f"Brak pliku na dysku: {document.get('type', 'Dokument')}.", "Wygeneruj dokument ponownie albo popraw ścieżkę.")
    return issues


def _legacy_get_order_flow_map(order_id, record=None):
    """Zwraca stan przepływu danych między modułami dla czytelnej mapy procesu."""
    registry = load_document_registry()
    record = record or registry.get(order_id, {})
    context = load_order_contexts().get(order_id, {}).get("data", {})
    get_context = lambda key, default=None: _deserialize_order_context_value(context.get(key, default))
    snapshot = record.get("shared_snapshot", {}) or get_context("order_snapshot", {}) or {}
    sections = set((snapshot.get("sections", {}) or {}).keys())
    documents = [str(item.get("type", "")).lower() for item in record.get("documents", [])]
    return [
        {"Etap": "Baza Produkt / Display / Master Case", "Status": "✅" if any(section in sections for section in {"tds", "paletyzacja", "mastercase"}) else "⏳", "Źródło / wynik": "Kartoteka, TDS lub wynik Box Rightsizing"},
        {"Etap": "Paletyzacja / Box Rightsizing", "Status": "✅" if "paletyzacja" in sections else "⏳", "Źródło / wynik": "Palety, masa, LDM"},
        {"Etap": "BCT", "Status": "✅" if get_context("bct_last_result", {}) else "⏳", "Źródło / wynik": "Wytrzymałość i limit warstw"},
        {"Etap": "TDS / E-Order / Karta Pracy", "Status": "✅" if any(section in sections for section in {"tds", "eorder", "karta_pracy"}) else "⏳", "Źródło / wynik": "Specyfikacja i produkcja"},
        {"Etap": "Packing List / Transport", "Status": "✅" if "packing_list" in sections or "transport" in sections or "zlecenie transportowe" in documents else "⏳", "Źródło / wynik": "Palety, odbiorca i dostawa"},
        {"Etap": "PPWR / QA / E-mail", "Status": "✅" if any("ppwr" in item or "qa" in item for item in documents) else "⏳", "Źródło / wynik": "Zgodność, kontrola i wysyłka"},
    ]


def _decoded_order_context(order_id):
    raw_context = load_order_contexts().get(order_id, {}).get("data", {})
    return {key: _deserialize_order_context_value(value) for key, value in raw_context.items()}


def get_order_end_to_end_checks(order_id, record=None):
    """Warstwa aplikacji dla czystych kontroli Centrum zlecenia."""
    record = record or load_document_registry().get(order_id, {})
    context = _decoded_order_context(order_id)
    requirements, checks = get_order_requirement_status(order_id, record)
    own_directory = os.path.join(DOCUMENT_FILES_DIR, order_id)
    return service_end_to_end_checks(
        order_id, record, context.get("e_order_items", []) or [], requirements, checks, ORDER_REQUIREMENT_LABELS,
        own_file=lambda path: _is_path_in_directory(path, own_directory), selected_ean=tab9_selected_ean,
    )


def get_order_data_quality(order_id, record=None):
    record = record or load_document_registry().get(order_id, {})
    return service_order_data_quality(
        record, _decoded_order_context(order_id), selected_ean=tab9_selected_ean,
        positive_int=tab9_as_positive_int, file_exists=os.path.isfile,
    )


def get_order_flow_map(order_id, record=None):
    record = record or load_document_registry().get(order_id, {})
    context = _decoded_order_context(order_id)
    snapshot = record.get("shared_snapshot", {}) or context.get("order_snapshot", {}) or {}
    return service_order_flow_map(snapshot, record.get("documents", []), context.get("bct_last_result", {}) or {})


def build_order_audit_report(order_id, record=None):
    registry = load_document_registry()
    record = record or registry.get(order_id, {})
    lifecycle = update_order_lifecycle_status(order_id)
    return {
        "order_id": order_id, "generated_at": datetime.now().isoformat(timespec="seconds"),
        "order_status": lifecycle.get("status"), "lifecycle_reason": lifecycle.get("reason"),
        "header": record.get("order_header", {}), "requirements": lifecycle.get("requirement_checks", {}),
        "data_quality": get_order_data_quality(order_id, record), "flow": get_order_flow_map(order_id, record),
        "documents": record.get("documents", []), "history": record.get("order_history", []), "email_history": record.get("email_history", []),
    }


def update_order_lifecycle_status(order_id):
    """Wyznacza etap zlecenia z dokumentów, zatwierdzenia BCT i historii wysyłki."""
    registry = load_document_registry()
    record = registry.get(order_id)
    if not record:
        return {"bct_approved": False, "ppwr_ready": False, "qa_ready": False, "email_sent": False, "status": "robocze"}

    documents = record.get("documents", [])
    requirements, requirement_checks = get_order_requirement_status(order_id, record)
    bct_approved = requirement_checks["bct"]
    ppwr_ready = requirement_checks["ppwr"]
    qa_ready = requirement_checks["qa"]
    email_sent = any(str(item.get("status", "")).lower() == "wysłana" for item in record.get("email_history", []))
    missing_requirements = [
        ORDER_REQUIREMENT_LABELS[key] for key in requirements if not requirement_checks.get(key, False)
    ]

    current_status = record.get("order_status", "robocze")
    if record.get("manual_status_override"):
        return {
            "bct_approved": bct_approved, "ppwr_ready": ppwr_ready, "qa_ready": qa_ready,
            "email_sent": email_sent, "requirements": requirements, "requirement_checks": requirement_checks,
            "missing_requirements": missing_requirements, "status": current_status,
            "reason": "status ustawiony ręcznie",
        }
    target_status, reason = derive_order_lifecycle(
        current_status, bool(documents), missing_requirements, email_sent
    )

    if target_status != current_status:
        now = datetime.now().isoformat(timespec="seconds")
        record.setdefault("order_history", []).append({
            "at": now,
            "action": "automatyczna zmiana statusu zlecenia",
            "by": "system",
            "from": current_status,
            "to": target_status,
            "reason": reason,
        })
        record["order_status"] = target_status
        record["updated_at"] = now
        registry[order_id] = record
        save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry)
    return {
        "bct_approved": bct_approved,
        "ppwr_ready": ppwr_ready,
        "qa_ready": qa_ready,
        "email_sent": email_sent,
        "requirements": requirements,
        "requirement_checks": requirement_checks,
        "missing_requirements": missing_requirements,
        "status": target_status,
        "reason": reason,
    }

def load_database():
    """Ładuje bazę danych z pliku JSON lub tworzy domyślną."""
    default_data = {
        "products": [
            "Rolls", "Bletka", "Cones", "Filtry kartonowe", "Filtry Acetatowe", 
            "Filtry z klejem", "Zestaw imprezowy", "Filtry smakowe", "Mieszanka", 
            "Młynek", "Tacka 3 w 1", "Cover KSS"
        ],
        "other_criteria": [
            "bez filtra", "z filtrem", "3 pcs", "6 pcs", "12 pcs", "32 pcs", 
            "800 pcs", "Filtry na gotowo", "Filtry bletka", "Filtry Rolls"
        ],
        "dimensions": [
            "-", "Emburn (53x20)", "BS_Style (49x22)", "King Size (108x25)", 
            "1 i ¼ (76 × 43)", "60x18", "57x23"
        ],
        "filter_colors": [
            "Biały", "Eko", "Czarny", "3 kolor", "Niebieski", "Różowy", 
            "Oliwkowy", "Fioletowy", "Inny"
        ],
        "box_paper_colors": [
            "Biały 12,5 gsm", "Biały 14 gsm", "Unbleached", "Hemp", "Różowy", 
            "Niebieski", "Zielony", "Inny", "Sekwencja Pink/Blue/Pink"
        ],
        "print_types": [
            "Offset Biały", "Offset Druk", "Cyfra Druk", "Brak", "Stock_Sklep"
        ],
        "orders_clients": [
            "Sklep", "Hempowo", "Zam. mailowe"
        ],
        "grammages": [
            "-", "120", "130", "140", "150", "160", "170", "180", "190", 
            "200", "210", "220", "230", "240", "250", "260", "270", "280", 
            "290", "300", "160/140"
        ],
        "print_covers": [
            "Brak zadruku", "Dwustronnie – całość (C1, C2, C3, C4)", 
            "Zewnątrz – pełen przód i tył (C1 + C4)", "Wewnątrz – pełen przód i tył (C2 + C3)", 
            "Zewnątrz (C1 + C4) + przód wewnątrz (C2)", "Zewnątrz (C1 + C4) + tył wewnątrz (C3)", 
            "Jednostronnie – tylko przód zewnątrz (C1)", "Jednostronnie – tylko przód wewnątrz (C2)", 
            "Jednostronnie – tylko tył wewnątrz (C3)", "Jednostronnie – tylko tył zewnątrz (C4)", 
            "Front obustronnie (C1 + C2)", "Tył obustronnie (C3 + C4)", "Obustronnie (C1 + C2)"
        ],
        "color_spaces": [
            "CMYK", "Patone", "HKS", "Multicolor", "RAL", "NCS", "Toyo", 
            "DIC", "ECG", "Hexachrome", "LAB", "HEX", "RGB", "C+K+Pantone 203c"
        ],
        "press_combinations": [
            "-", "0/0", "0/1", "0/2", "0/3", "0/4", "1/0", "1/1", "1/2", "1/3", "1/4",
            "2/0", "2/1", "2/2", "2/3", "2/4", "3/0", "3/1", "3/2", "3/3", "3/4",
            "4/0", "4/1", "4/2", "4/3", "4/4"
        ],
        "varnishes": [
            "brak", "błysk lakier", "mat lakier", "soft lakier", "błysk folia", 
            "mat folia", "soft folia", "Folia Anti-Scratch", "Hotstamping", 
            "UV wybiórczy", "UV puchnacy", "Holo"
        ],
        "foil_options": [
            "Tak", "Nie", "Tak – Zewnątrz + Wewnątrz", "Tak – Zewnątrz", 
            "Tak – Wewnątrz", "Tak – Awers", "Tak – Rewers", "Tak – Awers + Rewers"
        ],
        "perforations": ["Brak", "1", "2", "3", "4", "5"],
        "yes_no": ["TAK", "NIE"],
        "display_prints": ["1/0", "2/0", "3/0", "4/0", "Inne"],
        "ppwr_component_names": ["Box / paper", "Laminacja boxa", "Pusty display", "Paleta drewniana", "Folia stretch"],
        "ppwr_packaging_levels": ["Sprzedażowe / primary", "Wtórne / secondary", "Transportowe / pallet"],
        "ppwr_main_materials": ["Paper", "Plastics", "Wood", "Metal", "Glass", "Other"],
        "ppwr_raw_materials": ["Paper / cardboard", "PP film", "LDPE / other plastic", "Wood", "Aluminium", "Steel", "Glass", "Other"],
        "ppwr_colour_notes": ["CMYK", "transparent", "brak", "bez druku"],
        "ppwr_templates": {},
        "ppwr_templates_initialized": False,
        "ppwr_component_library": [
            {
                "Komponent opakowania": "Box / paper",
                "Poziom opakowania": "Sprzedażowe / primary",
                "Materiał główny": "Paper",
                "Surowiec": "Paper / cardboard",
                "Masa jednostkowa (g)": 2.13,
                "Ilość / 1 SKU": 1.0,
                "Ilość / 1 paletę": 0.0,
                "Kolor / druk / uwagi": "CMYK",
            },
            {
                "Komponent opakowania": "Laminacja boxa",
                "Poziom opakowania": "Sprzedażowe / primary",
                "Materiał główny": "Plastics",
                "Surowiec": "PP film",
                "Masa jednostkowa (g)": 0.30,
                "Ilość / 1 SKU": 1.0,
                "Ilość / 1 paletę": 0.0,
                "Kolor / druk / uwagi": "transparent",
            },
            {
                "Komponent opakowania": "Pusty display",
                "Poziom opakowania": "Wtórne / secondary",
                "Materiał główny": "Paper",
                "Surowiec": "Paper / cardboard",
                "Masa jednostkowa (g)": 18.66,
                "Ilość / 1 SKU": 0.0,
                "Ilość / 1 paletę": 72.0,
                "Kolor / druk / uwagi": "CMYK",
            },
            {
                "Komponent opakowania": "Paleta drewniana",
                "Poziom opakowania": "Transportowe / pallet",
                "Materiał główny": "Wood",
                "Surowiec": "Wood",
                "Masa jednostkowa (g)": 8500.0,
                "Ilość / 1 SKU": 0.0,
                "Ilość / 1 paletę": 1.0,
                "Kolor / druk / uwagi": "",
            },
            {
                "Komponent opakowania": "Folia stretch",
                "Poziom opakowania": "Transportowe / pallet",
                "Materiał główny": "Plastics",
                "Surowiec": "LDPE / other plastic",
                "Masa jednostkowa (g)": 700.0,
                "Ilość / 1 SKU": 0.0,
                "Ilość / 1 paletę": 1.0,
                "Kolor / druk / uwagi": "transparent",
            },
        ],
        "orders": [],
        "technical_cards": [],
        "print_qa_history": [],
        "e_orders": [],
        "work_sheets": []
    }
    
    data = load_shared_state("application_dictionary", DB_FILE, default_data)
    if not isinstance(data, dict):
        return default_data
    for key in default_data:
        data.setdefault(key, default_data[key])
    return data

def save_database(data):
    """Zapisuje słowniki aplikacji centralnie w SQLite z kopią JSON do eksportu."""
    try:
        save_shared_state("application_dictionary", DB_FILE, data)
    except Exception as e:
        st.error(f"Błąd zapisu bazy danych: {e}")

class NumberedCanvas(canvas.Canvas):
    """Niestandardowa klasa Canvas obsługująca dynamiczny numer stron ('Strona X z Y') oraz profesjonalny nagłówek i stopkę."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        primary_color = colors.HexColor('#1E3A8A')  # Ciemny granat
        text_color = colors.HexColor('#64748B')     # Stonowany szary
        line_color = colors.HexColor('#CBD5E1')     # Jasnoszara linia
        
        # Nagłówek
        self.setFont(FONT_BOLD, 8)
        self.setFillColor(primary_color)
        self.drawString(30, A4[1] - 25, "SPECYFIKACJA TECHNICZNA ZAMÓWIENIA")
        
        self.setFont(FONT_REGULAR, 8)
        self.setFillColor(text_color)
        self.drawRightString(A4[0] - 30, A4[1] - 25, datetime.now().strftime('%Y-%m-%d'))
        
        self.setStrokeColor(line_color)
        self.setLineWidth(0.75)
        self.line(30, A4[1] - 30, A4[0] - 30, A4[1] - 30)
        
        # Stopka
        self.line(30, 35, A4[0] - 30, 35)
        self.drawString(30, 22, "System Zarządzania Produkcją - made by Adrian")
        
        page_text = f"Strona {self._pageNumber} z {page_count}"
        self.drawRightString(A4[0] - 30, 22, page_text)
        
        self.restoreState()

class NumberedCanvasLandscape(canvas.Canvas):
    """Niestandardowa klasa Canvas dla układu poziomego (E-Order / Karta Pracy) z numeracją stron."""
    HEADER_LABEL = "DOKUMENTY ZAMÓWIENIA / E-ORDER"
    LOGO_PATH = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        width, height = landscape(A4)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages, width, height)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count, width, height):
        self.saveState()
        primary_color = colors.HexColor('#1E3A8A')
        text_color = colors.HexColor('#64748B')
        line_color = colors.HexColor('#CBD5E1')
        
        self.setFont(FONT_BOLD, 8)
        self.setFillColor(primary_color)
        self.drawString(30, height - 25, self.HEADER_LABEL)
        
        if self.LOGO_PATH and os.path.isfile(self.LOGO_PATH):
            self.drawImage(
                self.LOGO_PATH,
                width - 130,
                height - 25,
                width=500,
                height=100,
                preserveAspectRatio=True,
                mask='auto'
            )
        else:
            self.setFont(FONT_REGULAR, 8)
            self.setFillColor(text_color)
            self.drawRightString(width - 30, height - 25, datetime.now().strftime('%Y-%m-%d'))
        
        self.setStrokeColor(line_color)
        self.setLineWidth(0.75)
        self.line(30, height - 30, width - 30, height - 30)
        
        self.line(30, 30, width - 30, 30)
        self.drawString(30, 18, "System Zarządzania Produkcją - made by Adrian")
        page_text = f"Strona {self._pageNumber} z {page_count}"
        self.drawRightString(width - 30, 18, page_text)
        self.restoreState()


class NumberedCanvasPortrait(NumberedCanvas):
    """Nagłówek i stopka dla dokumentów A4 w orientacji pionowej."""
    HEADER_LABEL = "DOCUMENT"
    FOOTER_LABEL = "System Zarządzania Produkcją - made by Adrian"
    PAGE_LABEL = "Strona"

    def draw_page_decorations(self, page_count):
        self.saveState()
        width, height = self._pagesize
        primary_color = colors.HexColor('#1E3A8A')
        text_color = colors.HexColor('#64748B')
        line_color = colors.HexColor('#CBD5E1')

        self.setFont(FONT_BOLD, 8)
        self.setFillColor(primary_color)
        self.drawString(30, height - 25, self.HEADER_LABEL)
        self.setFont(FONT_REGULAR, 8)
        self.setFillColor(text_color)
        self.drawRightString(width - 30, height - 25, datetime.now().strftime('%Y-%m-%d'))

        self.setStrokeColor(line_color)
        self.setLineWidth(0.75)
        self.line(30, height - 30, width - 30, height - 30)
        self.line(30, 35, width - 30, 35)
        self.drawString(30, 22, self.FOOTER_LABEL)
        self.drawRightString(width - 30, 22, f"{self.PAGE_LABEL} {self._pageNumber} of {page_count}" if self.PAGE_LABEL == "Page" else f"{self.PAGE_LABEL} {self._pageNumber} z {page_count}")
        self.restoreState()


class EOrderCanvas(NumberedCanvasLandscape):
    HEADER_LABEL = "DOKUMENTY ZAMÓWIENIA / E-ORDER"
    LOGO_PATH = None


class WorksheetCanvas(NumberedCanvasLandscape):
    HEADER_LABEL = "KARTA PRACY"
    LOGO_PATH = None


class PPWRCanvas(NumberedCanvasLandscape):
    HEADER_LABEL = "PPWR MASS AND MATERIAL SPECIFICATION"
    LOGO_PATH = None


class EUDeclarationCanvas(NumberedCanvasPortrait):
    HEADER_LABEL = "EU DECLARATION OF CONFORMITY - PPWR"
    LOGO_PATH = None


class ProductionDateCanvas(NumberedCanvasPortrait):
    HEADER_LABEL = "DECLARATION OF PACKAGING PRODUCTION DATE"
    LOGO_PATH = None


class TransportOrderCanvas(NumberedCanvasPortrait):
    """Jednolity nagłówek i stopka dla profesjonalnego zlecenia transportowego."""
    HEADER_LABEL = "ZLECENIE TRANSPORTOWE / TRANSPORT ORDER"
    LOGO_PATH = None

def generate_pdf(data_to_print, attachment_image_bytes=None, attachment_image_name="", document_title="ZAMÓWIENIE", order_id=None, include_bct=True, visual_attachments=None):
    """Generuje profesjonalny plik PDF w pamięci i zwraca jego zawartość bajtową."""
    return generate_tds_pdf(data_to_print, document_title=document_title, font_regular=FONT_REGULAR,
        font_bold=FONT_BOLD, attachment_image_bytes=attachment_image_bytes,
        bct_flowables=bct_pdf_section() if include_bct else [], canvasmaker=NumberedCanvas,
        store_pdf=store_order_pdf, order_id=order_id, visual_attachments=visual_attachments)

#e-order#

def _legacy_generate_eorder_pdf(items_list, meta_info, store_document=True, order_id=None):
    """Generuje dokument PDF dla Elektronicznego Potwierdzenia Zamówienia (E-Order) w układzie poziomym z obsługą języków (PL/EN)."""
    
    # Pobieranie języka z meta_info (domyślnie 'pl')
    lang = meta_info.get("lang", "pl").lower()
    if lang not in ["pl", "en"]:
        lang = "pl"

    # Słownik tłumaczeń
    translations = {
        "pl": {
            "title": "E-Order – Elektroniczne Potwierdzenie Zamówienia",
            "order_date": "Data zamówienia",
            "delivery_date": "Data dostawy",
            "order_no": "Nr zlecenia",
            "priority": "Priorytet",
            "version": "Wersja",
            "recipient": "Odbiorca",
            "delivery_address": "Adres dostawy",
            "response": "Status odpowiedzi",
            "confirmation": "Potwierdzenie terminu i ilości",
            "reprint": "Reprint",
            "reprint_yes": "TAK",
            "reprint_no": "NIE",
            "headers": [
                "Poz.", "Klient",  "Nazwa towaru lub usługi", "Produkt", "Inne kryteria", 
                "Kolor filtrów", "Wymiar filtrów", "Kolor papieru", 
                "Ilość netto", "Ilość w display", "Ilość w karton", "Kartony na palecie", "Displaye na palecie"
            ]
        },
        "en": {
            "title": "E-Order – Electronic Order Confirmation",
            "order_date": "Order date",
            "delivery_date": "Delivery date",
            "order_no": "Order No.",
            "priority": "Priority",
            "version": "Version",
            "recipient": "Recipient",
            "delivery_address": "Delivery address",
            "response": "Response status",
            "confirmation": "Delivery date and quantity confirmation",
            "reprint": "Reprint",
            "reprint_yes": "YES",
            "reprint_no": "NO",
            "headers": [
                "Pos.", "Customer", "Product or service name", "Product", "Other criteria", 
                "Filter color", "Dimensions Filter Tips", "Box paper color",  
                "Net quantity", "Qty in display", "Qty in carton", "Cartons on palette", "Displays on palette"
            ]
        }
    }
    
    t_text = translations[lang]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4), 
        rightMargin=30, 
        leftMargin=30, 
        topMargin=45, 
        bottomMargin=40
    )
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'EOrderTitle', parent=styles['Heading1'], fontName=FONT_BOLD, fontSize=16, spaceAfter=6, textColor=colors.HexColor('#1E3A8A')
    )
    meta_style = ParagraphStyle(
        'EOrderMeta', parent=styles['Normal'], fontName=FONT_REGULAR, fontSize=9, leading=14, textColor=colors.HexColor('#0F172A')
    )
    th_style = ParagraphStyle(
        'EOrderTH', parent=styles['Normal'], fontName=FONT_BOLD, fontSize=8, leading=10, textColor=colors.white
    )
    td_style = ParagraphStyle(
        'EOrderTD', parent=styles['Normal'], fontName=FONT_REGULAR, fontSize=8, leading=10, textColor=colors.HexColor('#1E3A8A')
    )

    delivery_date = meta_info.get("delivery_date", "")
    order_date = meta_info.get("order_date", datetime.now().strftime('%d.%m.%Y'))
    order_no = meta_info.get("order_no", "14/2026")
    priority = meta_info.get("priority", "normalny")
    document_version = meta_info.get("document_version", "v1")
    production_meta = meta_info.get("production_meta", {}) or {}
    recipient = meta_info.get("recipient", {}) or {}
    delivery_address = meta_info.get("delivery_address", {}) or {}
    response_status = meta_info.get("response_status", "wysłano")
    confirmation_note = meta_info.get("confirmation_note", "")
    
    # Tłumaczenie wartości reprintu (TAK/NIE -> YES/NO)
    raw_reprint = str(meta_info.get("reprint", "NIE")).upper()
    reprint_val = t_text["reprint_yes"] if raw_reprint in ["TAK", "YES", "TRUE"] else t_text["reprint_no"]
    
    meta_text = (
        f"<b>{t_text['order_date']}:</b> {order_date} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>{t_text['delivery_date']}:</b> {delivery_date} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>{t_text['order_no']}:</b> {order_no} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>{t_text['reprint']}:</b> {reprint_val} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>{t_text['priority']}:</b> {escape(str(priority))} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>{t_text['version']}:</b> {escape(str(document_version))}"
    )
    eorder_header = [
        Paragraph(t_text["title"], title_style),
        Spacer(1, 2),
        Paragraph(meta_text, meta_style)
    ]
    if os.path.isfile(EORDER_LOGO_PATH):
        logo = RLImage(EORDER_LOGO_PATH, width=100, height=32)
        header_table = Table([[eorder_header, logo]], colWidths=[doc.width - 110, 110])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
    else:
        for element in eorder_header:
            story.append(element)
    recipient_name = recipient.get("company") or recipient.get("name") or "—"
    recipient_email = recipient.get("email", "")
    address_parts = [
        delivery_address.get("street", ""),
        " ".join(part for part in [delivery_address.get("postal_code", ""), delivery_address.get("city", "")] if part),
        delivery_address.get("country", ""),
    ]
    address_label = ", ".join(part for part in address_parts if part) or "—"
    recipient_details = (
        f"<b>{t_text['recipient']}:</b> {escape(str(recipient_name))}"
        f"{(' (' + escape(str(recipient_email)) + ')') if recipient_email else ''}<br/>"
        f"<b>{t_text['delivery_address']}:</b> {escape(str(address_label))}<br/>"
        f"<b>{t_text['response']}:</b> {escape(str(response_status))} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>{t_text['confirmation']}:</b> {escape(str(confirmation_note or '—'))}"
    )
    story.append(Spacer(1, 4))
    story.append(Paragraph(recipient_details, meta_style))
    story.append(Spacer(1, 10))

    headers = [Paragraph(h, th_style) for h in t_text["headers"]]
    
    table_data = [headers]
    
    for idx, item in enumerate(items_list, 1):
        sku = str(item.get("sku", "")).strip()
        selected_ean = str(item.get("ean_selected", "")).strip()
        selected_level = str(item.get("packaging_level", "Produkt")).strip()
        lot_number = str(item.get("lot_number", "")).strip()
        qty_with_buffer = item.get("qty_with_buffer", "")
        qty_production = item.get("qty_production", "")
        qty_shipping = item.get("qty_shipping", "")
        product_label = escape(str(item.get("product_name", "-")))
        if sku or selected_ean:
            identifier = " | ".join(part for part in [
                f"SKU: {escape(sku)}" if sku else "",
                f"EAN {escape(selected_level)}: {escape(selected_ean)}" if selected_ean else "",
            ] if part)
            product_label += f"<br/><font size=7>{identifier}</font>"
        if lot_number or qty_with_buffer or qty_production or qty_shipping:
            planning = " | ".join(part for part in [
                f"LOT: {escape(lot_number)}" if lot_number else "",
                f"Z zapasem: {qty_with_buffer}" if qty_with_buffer else "",
                f"Produkcja: {qty_production}" if qty_production else "",
                f"Wysyłka: {qty_shipping}" if qty_shipping else "",
            ] if part)
            product_label += f"<br/><font size=7>{planning}</font>"
        packaging = item.get("packaging_calculation", {})
        if packaging:
            product_label += (
                f"<br/><font size=7>Pakowanie: {packaging.get('displayow', 0)} displaye | "
                f"{packaging.get('mastercase', 0)} MC | {packaging.get('palet', 0)} palet</font>"
            )
        row = [
            Paragraph(str(idx), td_style),
            Paragraph(str(item.get("order_channel", "-")), td_style),
            Paragraph(product_label, td_style),
            Paragraph(str(item.get("product_type", "-")), td_style),
            Paragraph(str(item.get("other_criteria", "-")), td_style),
            Paragraph(str(item.get("filter_color", "-")), td_style),
            Paragraph(str(item.get("dimensions", "-")), td_style),
            Paragraph(str(item.get("box_paper_color", "-")), td_style),
            Paragraph(str(item.get("qty_net", 0)), td_style),
            Paragraph(str(item.get("qty_display_pieces", 0)), td_style),
            Paragraph(str(item.get("qty_carton", 0)), td_style),
            Paragraph(str(item.get("qty_cartons_palette", 0)), td_style),
            Paragraph(str(item.get("qty_displays_palette", 0)), td_style)
        ]
        table_data.append(row)

    col_widths = [25, 50, 85, 80, 55, 60, 65, 60, 60, 60, 60, 60, 60]

    
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]
    
    for i in range(1, len(table_data)):
        bg = colors.HexColor('#F8FAFC') if i % 2 == 1 else colors.white
        t_style.append(('BACKGROUND', (0, i), (-1, i), bg))
        
    t.setStyle(TableStyle(t_style))
    story.append(t)
    
    doc.build(story, canvasmaker=EOrderCanvas)
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    if store_document:
        store_order_pdf("E-Order", pdf_bytes, "e_order.pdf", {
            "order_no": order_no,
            "recipient": recipient_name,
            "response_status": response_status,
            "language": lang,
        }, order_id=order_id or meta_info.get("order_id"))
    return BytesIO(pdf_bytes)


def generate_eorder_pdf(items_list, meta_info, store_document=True, order_id=None):
    """Warstwa aplikacji: zapisuje wynik generatora E-Order w rejestrze dokumentów."""
    return generate_eorder(items_list, meta_info, font_regular=FONT_REGULAR, font_bold=FONT_BOLD,
        logo_path=EORDER_LOGO_PATH if os.path.isfile(EORDER_LOGO_PATH) else "", canvasmaker=EOrderCanvas,
        store_pdf=store_order_pdf, store_document=store_document, order_id=order_id)


def generate_eorder_bilingual_pdf(items_list, meta_info, order_id=None):
    """Generuje natywny dwujęzyczny E-Order bez zależności od pypdf, PyPDF2 ani pdfunite."""
    return generate_bilingual_eorder(items_list, meta_info, font_regular=FONT_REGULAR, font_bold=FONT_BOLD,
        canvasmaker=EOrderCanvas, store_pdf=store_order_pdf, order_id=order_id)

##

def _legacy_generate_worksheet_pdf(items_list, meta_info, order_id=None):
    """Generuje dokument PDF dla Karty Pracy w układzie poziomym ze wszystkimi wymaganymi kolumnami i logotypem."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4), 
        rightMargin=20, 
        leftMargin=20, 
        topMargin=45, 
        bottomMargin=40
    )
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'WS_Title', parent=styles['Heading1'], fontName=FONT_BOLD, fontSize=16, spaceAfter=4, textColor=colors.HexColor('#1E3A8A')
    )
    meta_style = ParagraphStyle(
        'WS_Meta', parent=styles['Normal'], fontName=FONT_REGULAR, fontSize=9, leading=14, textColor=colors.HexColor('#0F172A')
    )
    th_style = ParagraphStyle(
        'WS_TH', parent=styles['Normal'], fontName=FONT_BOLD, fontSize=7, leading=9, textColor=colors.white
    )
    td_style = ParagraphStyle(
        'WS_TD', parent=styles['Normal'], fontName=FONT_REGULAR, fontSize=7, leading=9, textColor=colors.HexColor('#1E3A8A')
    )

    title_p = Paragraph("KARTA PRACY – ZBIORCZE ZESTAWIENIE PRODUKCYJNE", title_style)
    
    order_date = meta_info.get("order_date", datetime.now().strftime('%d.%m.%Y'))
    order_no = meta_info.get("order_no", "14/2026")
    priority = meta_info.get("priority", "normalny")
    document_version = meta_info.get("document_version", "v1")
    production_meta = meta_info.get("production_meta", {}) or {}
    
    meta_text = (
        f"<b>Data:</b> {order_date} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Nr zlecenia:</b> {order_no} "
        f"&nbsp;&nbsp;|&nbsp;&nbsp; <b>Priorytet:</b> {escape(str(priority))} "
        f"&nbsp;&nbsp;|&nbsp;&nbsp; <b>Wersja:</b> {escape(str(document_version))}"
    )
    meta_p = Paragraph(meta_text, meta_style)
    
    header_content = [title_p, Spacer(1, 2), meta_p]
    
    if os.path.isfile(WORKSHEET_LOGO_PATH):
        logo = RLImage(WORKSHEET_LOGO_PATH, width=282, height=52)
        header_table = Table([[header_content, logo]], colWidths=[doc.width - 110, 110])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
    else:
        for element in header_content:
            story.append(element)

    production_details = " | ".join(part for part in [
        f"<b>Nr produkcyjny:</b> {escape(str(production_meta.get('production_order_no', '—')))}",
        f"<b>Stanowisko / maszyna:</b> {escape(str(production_meta.get('machine', '—')))}",
        f"<b>Operator:</b> {escape(str(production_meta.get('operator', '—')))}",
        f"<b>Zmiana:</b> {escape(str(production_meta.get('shift', '—')))}",
        f"<b>Czas planowany:</b> {escape(str(production_meta.get('planned_time_hours', '—')))} h",
    ])
    story.append(Paragraph(production_details, meta_style))
            
    story.append(Spacer(1, 10))

    headers = [
        Paragraph("Poz.", th_style),
        Paragraph("Klient", th_style),
        Paragraph("Nazwa towaru lub usługi", th_style),
        Paragraph("Inne kryteria", th_style),
        Paragraph("Display", th_style),
        Paragraph("Kolor papieru", th_style),
        Paragraph("Kolor filtrów", th_style),
        Paragraph("Wymiar", th_style),
        Paragraph("Ilość netto", th_style),
        Paragraph("Ilość box", th_style),
        Paragraph("Ilość cover", th_style),
        Paragraph("Ilość display", th_style),
        Paragraph("Uwagi do zamówienia", th_style),
        Paragraph("Wystawiony dokument Faktura", th_style)
    ]
    
    table_data = [headers]
    
    for idx, item in enumerate(items_list, 1):
        worksheet_data = worksheet_item_data(item)
        order_values = worksheet_data["order_values"]
        row = [
            Paragraph(str(idx), td_style),
            Paragraph(str(order_values[0]), td_style), Paragraph(worksheet_data["product_label"], td_style),
            *[Paragraph(str(value), td_style) for value in order_values[1:]],
        ]
        table_data.append(row)

    col_widths = [22, 55, 95, 55, 50, 55, 55, 50, 45, 45, 45, 45, 90, 94]
    
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
    ]
    
    for i in range(1, len(table_data)):
        bg = colors.HexColor('#F8FAFC') if i % 2 == 1 else colors.white
        t_style.append(('BACKGROUND', (0, i), (-1, i), bg))
        
    t.setStyle(TableStyle(t_style))
    story.append(t)

    production_rows = [[
        Paragraph("REALIZACJA PRODUKCJI", th_style), "", "", "", ""
    ], [
        Paragraph("Poz.", th_style), Paragraph("Plan", th_style), Paragraph("Wykonano", th_style),
        Paragraph("Odpady", th_style), Paragraph("Przyczyna odpadu", th_style),
    ]]
    for idx, item in enumerate(items_list, 1):
        production_values = worksheet_item_data(item)["production_values"]
        production_rows.append([
            Paragraph(str(idx), td_style),
            *[Paragraph(str(value), td_style) for value in production_values],
        ])
    production_table = Table(production_rows, colWidths=[35, 80, 80, 70, doc.width - 265], repeatRows=2)
    production_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor('#123B69')),
        ("TEXTCOLOR", (0, 0), (-1, 1), colors.white), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ("VALIGN", (0, 0), (-1, -1), 'MIDDLE'), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([Spacer(1, 10), production_table])
    
    story.extend(bct_pdf_section())
    doc.build(story, canvasmaker=WorksheetCanvas)
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    store_order_pdf("Karta Pracy", pdf_bytes, "karta_pracy.pdf", order_id=order_id or meta_info.get("order_id"))
    return BytesIO(pdf_bytes)


def generate_worksheet_pdf(items_list, meta_info, order_id=None):
    """Warstwa aplikacji dla Karty Pracy; wspólny generator nie zna rejestru ani sesji."""
    return generate_worksheet(items_list, meta_info, font_regular=FONT_REGULAR, font_bold=FONT_BOLD,
        logo_path=WORKSHEET_LOGO_PATH if os.path.isfile(WORKSHEET_LOGO_PATH) else "",
        bct_flowables=bct_pdf_section(), canvasmaker=WorksheetCanvas, store_pdf=store_order_pdf,
        order_id=order_id)


def render_field(label, widget_type, options=None, default_value="", key_prefix=""):
    """Pomocnicza funkcja renderująca pole formularza z przypisanym checkboxem."""
    return render_includable_field(label, widget_type, options, default_value, key_prefix)

def render_master_checkbox(label, keys_list, master_key):
    """Renderuje checkbox zarządzający całą podsekcją."""
    return render_section_master_checkbox(label, keys_list, master_key)


def _legacy_build_tab9_catalog_snapshot(product_name):
    """Zwraca trwały obraz kartoteki Produkt / Display / Master Case dla modułu 9."""
    if not product_name:
        return {}
    product_data = wczytaj_produkty_z_db().get(product_name, {})
    if not product_data:
        return {}

    product = product_data.get("Produkt", {}) if isinstance(product_data.get("Produkt"), dict) else {}
    display = product_data.get("Display", {}) if isinstance(product_data.get("Display"), dict) else {}
    mastercase = product_data.get("MasterCase", {}) if isinstance(product_data.get("MasterCase"), dict) else {}

    # Dane starszych pozycji pozostają obsługiwane jako bezpieczny fallback.
    product = {
        "Długość [mm]": product.get("Dlugosc", product_data.get("Dlugosc", "")),
        "Szerokość [mm]": product.get("Szerokosc", product_data.get("Szerokosc", "")),
        "Wysokość [mm]": product.get("Wysokosc", product_data.get("Wysokosc", "")),
        "Masa netto [kg]": product.get("Masa_netto_kg", product_data.get("Waga", "")),
        "EAN produktu": product.get("EAN", product_data.get("EAN", "")),
    }
    display = {
        "Długość [mm]": display.get("Dlugosc", ""),
        "Szerokość [mm]": display.get("Szerokosc", ""),
        "Wysokość [mm]": display.get("Wysokosc", ""),
        "Masa pustego displaya [g]": display.get("Masa_pustego_g", ""),
        "Masa pełnego displaya [g]": display.get("Masa_pelnego_g", ""),
        "EAN displaya": display.get("EAN", ""),
        "Pudełek w displayu": display.get("Pudelka_w_displayu", product_data.get("boxes_in_display", "")),
    }
    mastercase = {
        "Długość wewnętrzna [mm]": mastercase.get("Dlugosc_wewnetrzna", ""),
        "Szerokość wewnętrzna [mm]": mastercase.get("Szerokosc_wewnetrzna", ""),
        "Wysokość wewnętrzna [mm]": mastercase.get("Wysokosc_wewnetrzna", ""),
        "Długość zewnętrzna [mm]": mastercase.get("Dlugosc_zewnetrzna", ""),
        "Szerokość zewnętrzna [mm]": mastercase.get("Szerokosc_zewnetrzna", ""),
        "Wysokość zewnętrzna [mm]": mastercase.get("Wysokosc_zewnetrzna", ""),
        "Tara [kg]": mastercase.get("Tara_kg", ""),
        "Maks. masa brutto [kg]": mastercase.get("Masa_brutto_max_kg", ""),
        "EAN Master Case": mastercase.get("EAN", ""),
        "FEFCO": mastercase.get("FEFCO", ""),
        "Tektura / fala": " / ".join(str(v) for v in [mastercase.get("Tektura", ""), mastercase.get("Fala", "")] if v),
        "Displayów w Master Case": mastercase.get("Displayow_w_mastercase", product_data.get("displays_in_mc", "")),
    }
    relations = {
        "Sztuk w pudełku": product_data.get("pcs_in_box", ""),
        "Pudełek w displayu": display["Pudełek w displayu"],
        "Displayów w Master Case": mastercase["Displayów w Master Case"],
    }
    return {
        "Nazwa produktu": product_name,
        "SKU": product_data.get("SKU", ""),
        "Klient": product_data.get("Klient", ""),
        "Producent": product_data.get("Producent", ""),
        "Produkt": product,
        "Display": display,
        "Master Case": mastercase,
        "Relacje pakowania": relations,
        "Paleta": {
            "Domyślny typ palety": product_data.get("Typ_Palety", ""),
            "Limit wysokości [mm]": product_data.get("Max_Wysokosc", ""),
            "Limit masy [kg]": product_data.get("Max_Waga", ""),
        },
    }


def build_tab9_catalog_snapshot(product_name):
    """Aktywna ścieżka katalogowa dla dokumentów; szczegóły są w services."""
    return service_build_catalog_snapshot(product_name, wczytaj_produkty_z_db())


def tab9_selected_ean(snapshot, packaging_level):
    """Dobiera EAN zgodny z poziomem pozycji dokumentu."""
    return service_selected_ean(snapshot, packaging_level)


def tab9_catalog_product_image(snapshot):
    """Pobiera zdjęcie zapisane w kartotece bez umieszczania go w tabelach TDS."""
    product_name = (snapshot or {}).get("Nazwa produktu", "")
    image = wczytaj_produkty_z_db().get(product_name, {}).get("Zdjecie", {})
    return image if isinstance(image, dict) and image.get("b64") else {}


def tab9_tds_catalog_sections(snapshot, packaging_level):
    if not snapshot:
        return {}
    return {
        "TDS: identyfikacja": {
            "Nazwa produktu": snapshot.get("Nazwa produktu", ""),
            "SKU": snapshot.get("SKU", ""),
            "Klient": snapshot.get("Klient", ""),
            "Producent": snapshot.get("Producent", ""),
            "EAN produktu": tab9_selected_ean(snapshot, "Produkt") or "—",
            "EAN displaya": tab9_selected_ean(snapshot, "Display") or "—",
            "EAN Master Case": tab9_selected_ean(snapshot, "Master Case") or "—",
            "Poziom pozycji": packaging_level,
            "EAN pozycji": tab9_selected_ean(snapshot, packaging_level) or "—",
        },
        "TDS: Produkt": snapshot.get("Produkt", {}),
        "TDS: Display": snapshot.get("Display", {}),
        "TDS: Master Case": snapshot.get("Master Case", {}),
        "TDS: Paleta": snapshot.get("Paleta", {}),
        "TDS: relacje pakowania": snapshot.get("Relacje pakowania", {}),
    }


TAB9_DOCUMENT_STATUSES = ["robocze", "do akceptacji", "zatwierdzone", "w produkcji", "wysłane", "zamknięte"]
TAB9_ORDER_PRIORITIES = ["normalny", "pilne", "reklamacja", "reprint"]
TAB9_DOCUMENT_LANGUAGES = ["PL", "EN", "PL/EN"]


def tab9_default_order_header(order_id):
    return service_default_order_header(order_id)


def save_tab9_order_header(order_header):
    """Zapisuje nagłówek zamówienia w kontekście oraz Centrum zlecenia."""
    result = production_save_order_header(
        order_header, load_registry=load_document_registry,
        save_registry=lambda registry: save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry),
        user_name=st.session_state.get("user_name", ""),
    )
    st.session_state["tab9_order_header"] = result
    save_order_context(order_header["order_id"])


def tab9_order_header_pdf_fields(order_header):
    return service_order_header_pdf_fields(order_header)


def tab9_validate_base_data(
    product_name, client, quantity, delivery_date="", require_client=True, require_delivery=False,
    location="Formularz", quantity_field="Ilość netto",
):
    """Zwraca błędy wraz z dokładnym miejscem pola wymagającego poprawy."""
    return service_validate_base_data(
        product_name, client, quantity, delivery_date, require_client, require_delivery,
        location, quantity_field,
    )


def tab9_validate_packaging_relations(snapshot, qty_display_pieces, qty_carton, qty_cartons_palette, qty_displays_palette):
    return production_validate_packaging_relations(snapshot, qty_display_pieces, qty_carton, qty_cartons_palette, qty_displays_palette)


def tab9_validate_eorder(items, recipient, delivery_date):
    return production_validate_eorder(items, recipient, delivery_date)


def tab9_validate_worksheet(items):
    """Walidacja Karty Pracy przed zapisem i wygenerowaniem PDF."""
    return production_validate_worksheet(items)


def tab9_requires_strict_approval(*statuses):
    """Przy zatwierdzaniu ostrzeżenia danych pakowania stają się blokadą."""
    return production_requires_strict_approval(*statuses)


def tab9_apply_approval_validation(errors, warnings, *statuses):
    return production_apply_approval_validation(errors, warnings, *statuses)


def tab9_as_positive_int(value, default=0):
    return order_as_positive_int(value, default)


def tab9_packaging_calculation(snapshot, packaging_level, quantity, cartons_per_pallet=0):
    """Przelicza wybraną ilość na wszystkie poziomy opakowania."""
    return service_packaging_calculation(snapshot, packaging_level, quantity, cartons_per_pallet)


def tab9_packaging_pdf_fields(calculation):
    return service_packaging_pdf_fields(calculation)


def tab9_project_file_payload(uploaded_file, existing_payload=None):
    """Zapisuje projekt z historią wersji, kontrolą sumy SHA-256 i autorem wgrania."""
    return production_project_file_payload(
        uploaded_file, existing_payload, uploaded_by=st.session_state.get("user_name", ""),
    )


def tab9_project_pdf_fields(project_info):
    return production_project_pdf_fields(project_info)


def update_order_production_summary(order_id, production_meta, items):
    """Przekazuje zbiorcze wykonanie Karty Pracy do Centrum zlecenia."""
    return production_update_production_summary(
        order_id, production_meta, items, load_registry=load_document_registry,
        save_registry=lambda registry: save_shared_state("document_registry", DOCUMENT_REGISTRY_FILE, registry),
        user_name=st.session_state.get("user_name", ""),
    )


def render_tab9():
    return render_tab9_screen(st, globals())
st.set_page_config(
    page_title="System Zarządzania Produkcją",
    page_icon="📦",
    layout="wide"
)


# ==========================================
# 1. BAZA UŻYTKOWNIKÓW (TUTAJ DODAJESZ USERÓW)
# ==========================================
# Dane logowania są przechowywane w .streamlit/pass.toml
# Przykład:
# [users.admin]
# password = "..."
# role = "Administrator"
#
# [users.user1]
# password = "..."
# role = "Użytkownik"
from pathlib import Path
import tomllib

PASS_FILE = Path(__file__).resolve().parent / ".streamlit" / "pass.toml"

if not PASS_FILE.exists():
    st.error(f"Brak pliku danych logowania: {PASS_FILE}")
    st.stop()

with open(PASS_FILE, "rb") as f:
    PASS_DATA = tomllib.load(f)

USERS = PASS_DATA.get("users", {})



# ==========================================
# 2. INICJALIZACJA STANU SESJI
# ==========================================
SESSION_IDLE_SECONDS = 15 * 60
SESSION_FILE = application_storage_path("active_sessions.json")


def _load_active_sessions():
    data = load_shared_state("active_sessions_v1", SESSION_FILE, {})
    return data if isinstance(data, dict) else {}


def _save_active_sessions(sessions):
    save_shared_state("active_sessions_v1", SESSION_FILE, sessions)


def _restore_persistent_session():
    token = st.query_params.get("session")
    if not token:
        return False
    sessions = _load_active_sessions()
    record = sessions.get(token, {})
    try:
        last_seen = datetime.fromisoformat(record.get("last_seen", ""))
    except (TypeError, ValueError):
        last_seen = None
    if not record or not last_seen or (datetime.now() - last_seen).total_seconds() >= SESSION_IDLE_SECONDS:
        sessions.pop(token, None)
        _save_active_sessions(sessions)
        return False
    username = record.get("username")
    if username not in USERS or USERS[username].get("role") != record.get("role"):
        return False
    record["last_seen"] = datetime.now().isoformat(timespec="seconds")
    sessions[token] = record
    _save_active_sessions(sessions)
    st.session_state.update({"authenticated": True, "user_name": username, "user_role": record["role"], "persistent_session_token": token})
    return True


def _start_persistent_session(username):
    token = secrets.token_urlsafe(32)
    sessions = _load_active_sessions()
    sessions[token] = {"username": username, "role": USERS[username]["role"], "last_seen": datetime.now().isoformat(timespec="seconds")}
    _save_active_sessions(sessions)
    st.query_params["session"] = token
    st.session_state["persistent_session_token"] = token


def _end_persistent_session():
    token = st.session_state.get("persistent_session_token") or st.query_params.get("session")
    sessions = _load_active_sessions()
    sessions.pop(token, None)
    _save_active_sessions(sessions)
    if "session" in st.query_params:
        del st.query_params["session"]

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None
if "user_name" not in st.session_state:
    st.session_state["user_name"] = None

if not st.session_state["authenticated"] and not st.session_state.get("_explicitly_logged_out"):
    # Komponent ciasteczek zwraca wartość asynchronicznie po pierwszym renderze.
    # Jednorazowy rerun pozwala odebrać cookie także po F5, zanim pokażemy formularz logowania.
    if not st.session_state.get("_cookie_manager_initialized"):
        st.session_state["_cookie_manager_initialized"] = True
        st.rerun()
    _restore_persistent_session()


# ==========================================
# 3. LOGOWANIE DO SYSTEMU (Gdy użytkownik NIE JEST zalogowany)
# ==========================================
if not st.session_state["authenticated"]:
    st.title("🏭 System Zarządzania Produkcją")
    st.caption("Zaloguj się, aby pracować ze zleceniami, dokumentacją i produkcją.")
    
    with st.form("login_form"):
        username = st.text_input("Użytkownik")
        password = st.text_input("Hasło", type="password")
        submit_button = st.form_submit_button("Zaloguj się")
        
        if submit_button:
            # Sprawdzanie w słowniku USERS
            if username in USERS and USERS[username]["password"] == password:
                st.session_state["authenticated"] = True
                st.session_state["user_role"] = USERS[username]["role"]
                st.session_state["user_name"] = username
                st.session_state["_explicitly_logged_out"] = False
                _start_persistent_session(username)
                st.rerun()
            else:
                st.error("Nieprawidłowy login lub hasło")
                
    # ZATRZYMANIE SKRYPTU - Nic poniżej tej linii się nie wykona dla niezalogowanych
    if not st.session_state["authenticated"]:
        st.stop()


# ==========================================
# 4. GŁÓWNA CZĘŚĆ SYSTEMU
# (Poniższy kod wykona się TYLKO gdy ktoś jest zalogowany)
# ==========================================
st.title("🏭 System Zarządzania Produkcją")
st.caption(f"Witaj, **{st.session_state['user_name']}**. Wybierz zlecenie i obszar pracy w panelu po lewej stronie.")

# ==========================================
# 5. NAWIGACJA I MENU MODUŁÓW
# Uprawnienia definiujemy przy każdym module.
# Dzięki temu dodanie nowego modułu wymaga zmiany tylko tutaj.
# ==========================================
MODULE_OPTIONS = {
    "📥 1. Baza produktów": {"id": 1, "roles": ["Administrator", "Manager"]},
    "📐 2. Paletyzacja": {"id": 2, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "📧 3. E-mail": {"id": 3, "roles": ["Administrator"]},
    "💡 4. Optymalizacja palety": {"id": 4, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "🖨️ 5. Transport": {"id": 5, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "📋 6. Packing List": {"id": 6, "roles": ["Administrator", "Manager"]},
    "📦 7. Box Rightsizing": {"id": 7, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "⚖️ 8. Analiza BCT kartonu": {"id": 8, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "📦 9. Zlecenie produkcyjne / TDS": {"id": 9, "roles": ["Administrator"]},
    "📊 10. Mass Specification PPWR": {"id": 10, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "✅ 11. Walidacja zamówień z drukarni": {"id": 11, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "📁 12. Centrum zlecenia": {"id": 12, "roles": ["Administrator", "Manager"]},
    "🏭 13. Planowanie produkcji": {"id": 13, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "🗂️ 14. Archiwum projektów graficznych": {"id": 14, "roles": ["Administrator", "Manager"]},
    "📦 15. Inwentaryzacja": {"id": 15, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "🧻 16. Kalkulator bobin SWM": {"id": 16, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "📚 17. Biblioteka materiałów": {"id": 17, "roles": ["Administrator", "Manager"]},
    "🌐 18. Portal klienta": {"id": 18, "roles": ["Administrator", "Manager"]},
    "🤝 19. Relacje handlowe": {"id": 19, "roles": ["Administrator", "Manager"]},
    "🔌 20. Integracje": {"id": 20, "roles": ["Administrator", "Manager"]},
    "✅ 21. Akceptacja artworków przez klienta": {"id": 21, "roles": ["Administrator", "Manager"]},
    "🧰 22. Generatory": {"id": 22, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "🪪 23. Karta produktu dla klienta": {"id": 23, "roles": ["Administrator", "Manager"]},
    "🧾 24. Rozliczenie pracy": {"id": 24, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "📝 25. Pre-Order": {"id": 25, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "🖨️ 26. Preflight DTP": {"id": 26, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "🛡️ 27. Centrum kopii bezpieczeństwa": {"id": 27, "roles": ["Administrator"]},
    "📋 28. Rozliczenie stanu i zamówienia": {"id": 28, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "⚙️ 29. Panel użytkowników": {"id": 29, "roles": ["Administrator"]},
    "🔄 30. Aktualizacje": {"id": 30, "roles": ["Administrator"]},
    "🧻 31. Rozliczenie bobin": {"id": 31, "roles": ["Administrator", "Manager", "Użytkownik"]},
    "🏷️ 32. Etykieta magazynowa A4": {"id": 32, "roles": ["Administrator", "Manager", "Użytkownik"]},
}

ROLE_PERMISSIONS = build_role_permissions(
    USERS, MODULE_OPTIONS, PASS_DATA.get("role_permissions", {}),
)
MODULE_OPTIONS = apply_role_permissions(MODULE_OPTIONS, ROLE_PERMISSIONS)

MODULE_GROUPS = {
    "📋 Zlecenie i dane": [1, 9, 12, 14, 21, 23],
    "📦 Konstrukcja i paletyzacja": [7, 8, 2, 4],
    "🚚 Logistyka i wysyłka": [6, 5, 3, 32],
    "✅ Zgodność i jakość": [10, 11, 26],
    "🏭 Planowanie produkcji": [13, 24, 25],
    "📦 Inwentaryzacja": [15, 28],
    "🧻 Kalkulatory": [16, 22],
    "📚 Materiały i klient": [17, 18, 19, 20],
    "⚙️ Administracja": [27, 29, 30],
}

# ==================== BAZA DANYCH I FUNKCJE POMOCNICZE ====================
# Baza produktów jest przechowywana razem z aplikacją, niezależnie od sposobu jej uruchomienia.
DB_FILENAME = application_storage_path("baza_produktow.db")
PRODUCT_CATALOG_SNAPSHOT_FILE = application_storage_path(".product_catalog_snapshot.json")



def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produkty (
            nazwa TEXT PRIMARY KEY,
            dane TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT, action TEXT,
            changed_at TEXT, changed_by TEXT, reason TEXT, old_data TEXT, new_data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS archived_products (
            original_name TEXT PRIMARY KEY, data TEXT, archived_at TEXT, archived_by TEXT, reason TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_locks (
            product_name TEXT PRIMARY KEY, locked_by TEXT, locked_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_custom_fields (
            field_name TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1
        )
    ''')
    cursor.execute('SELECT COUNT(*) FROM produkty')
    if cursor.fetchone()[0] == 0:
        domyslne = {
            'Produkt Ritual': {
                'Dlugosc': 200.0, 'Szerokosc': 470.0, 'Wysokosc': 280.0, 
                'Waga': 8.0, 'EAN': '5056134535500', 'Typ_Palety': 'EURO',
                'Max_Wysokosc': 2000.0, 'Max_Waga': 500.0,
                'displays_in_mc': 24, 'boxes_in_display': 16, 'pcs_in_box': 1
            },
            'Box Standardowy': {
                'Dlugosc': 600.0, 'Szerokosc': 400.0, 'Wysokosc': 300.0, 
                'Waga': 12.0, 'EAN': '5909876543210', 'Typ_Palety': 'EURO',
                'Max_Wysokosc': 1900.0, 'Max_Waga': 1000.0,
                'displays_in_mc': 1, 'boxes_in_display': 1, 'pcs_in_box': 1
            }
        }
        for k, v in domyslne.items():
            cursor.execute('INSERT OR REPLACE INTO produkty (nazwa, dane) VALUES (?, ?)', (k, json.dumps(v)))
        conn.commit()
    conn.close()

def current_operator():
    return st.session_state.get("user_name", "System")

def add_product_history(conn, product_name, action, old_data=None, new_data=None, reason=""):
    conn.execute(
        '''INSERT INTO product_history (product_name, action, changed_at, changed_by, reason, old_data, new_data)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (product_name, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), current_operator(), reason.strip(),
         json.dumps(old_data or {}, ensure_ascii=False), json.dumps(new_data or {}, ensure_ascii=False)),
    )

def get_product_custom_fields():
    init_db()
    with sqlite3.connect(DB_FILENAME) as conn:
        return [row[0] for row in conn.execute("SELECT field_name FROM product_custom_fields WHERE active = 1 ORDER BY field_name")]

def product_archive_backup_if_due():
    """Tworzy lokalną kopię SQLite najczęściej raz na 24 godziny."""
    if not os.path.exists(DB_FILENAME):
        return
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(DB_FILENAME)), "backups_bazy_produktow")
    os.makedirs(backup_dir, exist_ok=True)
    last_marker = os.path.join(backup_dir, ".last_backup.txt")
    try:
        last_run = float(open(last_marker, "r", encoding="utf-8").read()) if os.path.exists(last_marker) else 0
    except (OSError, ValueError):
        last_run = 0
    if time.time() - last_run >= 24 * 60 * 60:
        backup_path = os.path.join(backup_dir, f"baza_produktow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        shutil.copy2(DB_FILENAME, backup_path)
        with open(last_marker, "w", encoding="utf-8") as marker:
            marker.write(str(time.time()))


def _product_catalog_snapshot():
    """Eksportuje SQLite katalogu do formatu możliwego do zapisania w Supabase."""
    with sqlite3.connect(DB_FILENAME) as conn:
        return {
            "version": 1,
            "produkty": [list(row) for row in conn.execute("SELECT nazwa, dane FROM produkty")],
            "product_history": [list(row) for row in conn.execute("SELECT product_name, action, changed_at, changed_by, reason, old_data, new_data FROM product_history")],
            "archived_products": [list(row) for row in conn.execute("SELECT original_name, data, archived_at, archived_by, reason FROM archived_products")],
            "product_locks": [list(row) for row in conn.execute("SELECT product_name, locked_by, locked_at FROM product_locks")],
            "product_custom_fields": [list(row) for row in conn.execute("SELECT field_name, active FROM product_custom_fields")],
        }


def sync_product_catalog_to_cloud():
    """Zapisuje katalog w centralnym magazynie; lokalna SQLite pozostaje cachem."""
    save_shared_state("product_catalog_sqlite_v1", PRODUCT_CATALOG_SNAPSHOT_FILE, _product_catalog_snapshot())


def restore_product_catalog_from_cloud():
    """Odtwarza cache SQLite z Supabase po starcie instancji Streamlit."""
    snapshot = load_shared_state("product_catalog_sqlite_v1", PRODUCT_CATALOG_SNAPSHOT_FILE, None)
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
        sync_product_catalog_to_cloud()
        return
    try:
        with sqlite3.connect(DB_FILENAME) as conn:
            for table in ("produkty", "product_history", "archived_products", "product_locks", "product_custom_fields"):
                conn.execute(f"DELETE FROM {table}")
            conn.executemany("INSERT INTO produkty (nazwa, dane) VALUES (?, ?)", snapshot.get("produkty", []))
            conn.executemany(
                "INSERT INTO product_history (product_name, action, changed_at, changed_by, reason, old_data, new_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
                snapshot.get("product_history", []),
            )
            conn.executemany(
                "INSERT INTO archived_products (original_name, data, archived_at, archived_by, reason) VALUES (?, ?, ?, ?, ?)",
                snapshot.get("archived_products", []),
            )
            conn.executemany("INSERT INTO product_locks (product_name, locked_by, locked_at) VALUES (?, ?, ?)", snapshot.get("product_locks", []))
            conn.executemany("INSERT INTO product_custom_fields (field_name, active) VALUES (?, ?)", snapshot.get("product_custom_fields", []))
    except (sqlite3.Error, TypeError, ValueError):
        # Nie usuwamy lokalnej kopii przy uszkodzonym lub niepełnym imporcie.
        init_db()

init_db()
restore_product_catalog_from_cloud()
product_archive_backup_if_due()

def wczytaj_produkty_z_db():
    init_db()
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('SELECT nazwa, dane FROM produkty')
    rows = cursor.fetchall()
    conn.close()
    # Starsze kartoteki miały tylko pojedynczy EAN i wymiary kartonu na poziomie
    # głównym. Ujednolicamy je przy odczycie, aby każdy moduł widział trzy poziomy.
    return {row[0]: normalize_product_record(json.loads(row[1])) for row in rows}


def normalize_product_record(data):
    """Zapewnia wspólny format Produkt / Display / Master Case dla nowych i starych kartotek."""
    return normalize_catalog_product_record(data)


def product_ean_levels(data):
    """Zwraca trzy EAN-y z nazwą poziomu; pomija puste wartości."""
    data = normalize_product_record(data)
    result = {}
    for level, value in {
        "produkt": data["Produkt"].get("EAN", ""),
        "display": data["Display"].get("EAN", ""),
        "master_case": data["MasterCase"].get("EAN", ""),
    }.items():
        code = safe_ean(value)
        if code and code != "Brak":
            result[level] = code
    return result


PACKAGING_LEVEL_OPTIONS = ["Produkt", "Display", "Master Case"]


def get_packaging_level_physical(data, level="Master Case"):
    """Zwraca wymiary, masę i EAN dokładnie tego poziomu opakowania.

    Płaskie pola starszych kartotek są nadal obsługiwane jako bezpieczny
    fallback, ale nowe obliczenia nie muszą już traktować produktu jako kartonu.
    """
    raw_data = dict(data or {})
    normalized = normalize_product_record(raw_data)
    product = normalized.get("Produkt", {}) or {}
    display = normalized.get("Display", {}) or {}
    mastercase = normalized.get("MasterCase", {}) or {}

    def number(value, default=0.0):
        try:
            return float(value or default)
        except (TypeError, ValueError):
            return float(default)

    level = level if level in PACKAGING_LEVEL_OPTIONS else "Master Case"
    product_mass = number(product.get("Masa_netto_g")) / 1000
    boxes_per_display = max(1, int(number(display.get("Pudelka_w_displayu", normalized.get("boxes_in_display", 1)), 1)))
    displays_per_mastercase = max(1, int(number(mastercase.get("Displayow_w_mastercase", normalized.get("displays_in_mc", 1)), 1)))
    pieces_per_box = max(1, int(number(normalized.get("pcs_in_box", 1), 1)))
    display_mass = number(display.get("Masa_pelnego_g")) / 1000
    if display_mass <= 0:
        display_mass = number(display.get("Masa_pustego_g")) / 1000 + product_mass * boxes_per_display * pieces_per_box

    if level == "Produkt":
        payload = {
            "Dlugosc": number(product.get("Dlugosc")), "Szerokosc": number(product.get("Szerokosc")),
            "Wysokosc": number(product.get("Wysokosc")), "Waga": product_mass,
            "EAN": safe_ean(product.get("EAN", "")), "label": "Produkt",
        }
    elif level == "Display":
        payload = {
            "Dlugosc": number(display.get("Dlugosc")), "Szerokosc": number(display.get("Szerokosc")),
            "Wysokosc": number(display.get("Wysokosc")), "Waga": display_mass,
            "EAN": safe_ean(display.get("EAN", "")), "label": "Display",
        }
    else:
        has_nested_mastercase = isinstance(raw_data.get("MasterCase"), dict)
        mastercase_mass = number(mastercase.get("Masa_brutto_kg"))
        if mastercase_mass <= 0 and (raw_data.get("source_type") or raw_data.get("Nazwa") == "Master Case z Box Rightsizing"):
            mastercase_mass = number(raw_data.get("Waga"))
        if mastercase_mass <= 0:
            mastercase_mass = display_mass * displays_per_mastercase + number(mastercase.get("Tara_kg"))
        if mastercase_mass <= 0 and not has_nested_mastercase:
            mastercase_mass = number(raw_data.get("Waga"))
        payload = {
            "Dlugosc": number(mastercase.get("Dlugosc_zewnetrzna", raw_data.get("Dlugosc", 0))),
            "Szerokosc": number(mastercase.get("Szerokosc_zewnetrzna", raw_data.get("Szerokosc", 0))),
            "Wysokosc": number(mastercase.get("Wysokosc_zewnetrzna", raw_data.get("Wysokosc", 0))),
            "Waga": mastercase_mass, "EAN": safe_ean(mastercase.get("EAN", "")), "label": "Master Case",
        }
    payload["EAN"] = "" if payload["EAN"] == "Brak" else payload["EAN"]
    payload["relacje"] = {
        "displays_per_mastercase": displays_per_mastercase,
        "boxes_per_display": boxes_per_display,
        "pieces_per_box": pieces_per_box,
    }
    return payload


def packaging_level_quantities(quantity, level, relations=None):
    """Przelicza ilość wybranego poziomu na Produkt / Display / Master Case.

    ``quantity`` zawsze oznacza poziom wybrany przez użytkownika w formularzu,
    dzięki czemu liczba produktów nie jest mylona z liczbą kartonów.
    """
    return calculate_packaging_level_quantities(quantity, level, relations)


def validate_product_ean_uniqueness(product_name, data):
    """Sprawdza EAN-y produktu, displaya i Master Case w całej aktywnej bazie."""
    own_eans = product_ean_levels(data)
    duplicated_inside = [code for code in set(own_eans.values()) if list(own_eans.values()).count(code) > 1]
    if duplicated_inside:
        raise ValueError(f"Ten sam EAN nie może należeć do dwóch poziomów jednej kartoteki: {', '.join(duplicated_inside)}.")
    conflicts_by_product = ean_conflicts(product_name, data, wczytaj_produkty_z_db())
    if conflicts_by_product:
        existing_name, conflicts = next(iter(conflicts_by_product.items()))
        raise ValueError(f"Kod EAN {', '.join(conflicts)} jest już przypisany do produktu: {existing_name}.")

def zapisz_produkt_w_db(nazwa, dane):
    """Zapisuje kartotekę i pilnuje unikalności wszystkich trzech EAN-ów."""
    nazwa = str(nazwa).strip()
    dane = normalize_product_record(dane)
    validate_product_ean_uniqueness(nazwa, dane)
    conn = sqlite3.connect(DB_FILENAME)
    try:
        old_row = conn.execute('SELECT dane FROM produkty WHERE nazwa = ?', (nazwa,)).fetchone()
        old_data = json.loads(old_row[0]) if old_row else {}
        conn.execute('INSERT OR REPLACE INTO produkty (nazwa, dane) VALUES (?, ?)', (nazwa, json.dumps(dane, ensure_ascii=False)))
        add_product_history(conn, nazwa, "utworzenie" if not old_row else "aktualizacja", old_data, dane)
        conn.commit()
    finally:
        conn.close()
    sync_product_catalog_to_cloud()

def usun_produkt_z_db(nazwa):
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM produkty WHERE nazwa = ?', (nazwa,))
    conn.commit()
    conn.close()
    sync_product_catalog_to_cloud()

def archive_product(nazwa, reason=""):
    with sqlite3.connect(DB_FILENAME) as conn:
        row = conn.execute('SELECT dane FROM produkty WHERE nazwa = ?', (nazwa,)).fetchone()
        if not row:
            raise ValueError("Produkt nie istnieje w aktywnej bazie.")
        product_data = json.loads(row[0])
        conn.execute(
            'INSERT OR REPLACE INTO archived_products (original_name, data, archived_at, archived_by, reason) VALUES (?, ?, ?, ?, ?)',
            (nazwa, json.dumps(product_data, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), current_operator(), reason.strip()),
        )
        conn.execute('DELETE FROM produkty WHERE nazwa = ?', (nazwa,))
        conn.execute('DELETE FROM product_locks WHERE product_name = ?', (nazwa,))
        add_product_history(conn, nazwa, "archiwizacja", product_data, {}, reason)
    sync_product_catalog_to_cloud()

def restore_archived_product(nazwa):
    with sqlite3.connect(DB_FILENAME) as conn:
        row = conn.execute('SELECT data FROM archived_products WHERE original_name = ?', (nazwa,)).fetchone()
        if not row:
            raise ValueError("Nie znaleziono produktu w archiwum.")
        if conn.execute('SELECT 1 FROM produkty WHERE nazwa = ?', (nazwa,)).fetchone():
            raise ValueError("Nie można przywrócić: produkt o tej nazwie już istnieje.")
        product_data = json.loads(row[0])
        conn.execute('INSERT INTO produkty (nazwa, dane) VALUES (?, ?)', (nazwa, json.dumps(product_data, ensure_ascii=False)))
        conn.execute('DELETE FROM archived_products WHERE original_name = ?', (nazwa,))
        add_product_history(conn, nazwa, "przywrócenie", {}, product_data)
    sync_product_catalog_to_cloud()

def update_product_in_db(old_name, new_name, new_data, reason=""):
    new_name = str(new_name).strip()
    new_data = normalize_product_record(new_data)
    validate_product_ean_uniqueness(old_name, new_data)
    with sqlite3.connect(DB_FILENAME) as conn:
        row = conn.execute('SELECT dane FROM produkty WHERE nazwa = ?', (old_name,)).fetchone()
        if not row:
            raise ValueError("Produkt nie istnieje lub został już zmieniony.")
        if old_name != new_name and conn.execute('SELECT 1 FROM produkty WHERE nazwa = ?', (new_name,)).fetchone():
            raise ValueError("Produkt o podanej nazwie już istnieje.")
        old_data = json.loads(row[0])
        if old_name != new_name:
            conn.execute('DELETE FROM produkty WHERE nazwa = ?', (old_name,))
            conn.execute('DELETE FROM product_locks WHERE product_name = ?', (old_name,))
        conn.execute('INSERT OR REPLACE INTO produkty (nazwa, dane) VALUES (?, ?)', (new_name, json.dumps(new_data, ensure_ascii=False)))
        add_product_history(conn, new_name, "aktualizacja", old_data, new_data, reason)
    sync_product_catalog_to_cloud()

def get_product_history(nazwa):
    with sqlite3.connect(DB_FILENAME) as conn:
        rows = conn.execute(
            'SELECT action, changed_at, changed_by, reason, old_data, new_data FROM product_history WHERE product_name = ? ORDER BY id DESC',
            (nazwa,),
        ).fetchall()
    return [
        {"Akcja": item[0], "Data": item[1], "Użytkownik": item[2], "Uzasadnienie": item[3], "Przed": json.loads(item[4]), "Po": json.loads(item[5])}
        for item in rows
    ]

PRODUCT_LOCK_TIMEOUT = timedelta(minutes=30)


def product_lock_database_paths():
    """Zwraca aktywną oraz starszą bazę, jeśli pozostała po migracji danych."""
    paths = [DB_FILENAME]
    legacy_path = os.path.join(APP_DIR, "baza_produktow.db")
    if legacy_path != DB_FILENAME and os.path.isfile(legacy_path):
        paths.append(legacy_path)
    return paths


def remove_expired_product_locks():
    """Usuwa tylko blokady, których czas bezczynności przekroczył 30 minut."""
    expired_locks = []
    for database_path in product_lock_database_paths():
        with sqlite3.connect(database_path) as conn:
            rows = conn.execute('SELECT product_name, locked_at FROM product_locks').fetchall()
            database_expired_locks = []
            for product_name, locked_at in rows:
                try:
                    lock_age = datetime.now() - datetime.strptime(locked_at, "%Y-%m-%d %H:%M:%S")
                except (TypeError, ValueError):
                    # Nie usuwamy wpisu o nieprawidłowej dacie automatycznie.
                    continue
                if lock_age > PRODUCT_LOCK_TIMEOUT:
                    database_expired_locks.append(product_name)
            if database_expired_locks:
                conn.executemany(
                    'DELETE FROM product_locks WHERE product_name = ?',
                    [(product_name,) for product_name in database_expired_locks],
                )
                expired_locks.extend(database_expired_locks)
    if expired_locks:
        sync_product_catalog_to_cloud()
    return expired_locks


def remove_all_product_locks():
    """Usuwa wszystkie blokady edycji produktów i zwraca ich liczbę."""
    deleted_count = 0
    for database_path in product_lock_database_paths():
        with sqlite3.connect(database_path) as conn:
            deleted_count += conn.execute('DELETE FROM product_locks').rowcount
    if deleted_count:
        sync_product_catalog_to_cloud()
    return deleted_count


def acquire_product_lock(nazwa):
    with sqlite3.connect(DB_FILENAME) as conn:
        current = conn.execute('SELECT locked_by, locked_at FROM product_locks WHERE product_name = ?', (nazwa,)).fetchone()
        if current:
            try:
                lock_age = (datetime.now() - datetime.strptime(current[1], "%Y-%m-%d %H:%M:%S")).total_seconds()
            except (TypeError, ValueError):
                lock_age = 0
            if lock_age > PRODUCT_LOCK_TIMEOUT.total_seconds():
                conn.execute('DELETE FROM product_locks WHERE product_name = ?', (nazwa,))
                current = None
        if current and current[0] != current_operator():
            return False, current[0]
        conn.execute('INSERT OR REPLACE INTO product_locks (product_name, locked_by, locked_at) VALUES (?, ?, ?)',
                     (nazwa, current_operator(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    sync_product_catalog_to_cloud()
    return True, current_operator()

def release_product_lock(nazwa):
    with sqlite3.connect(DB_FILENAME) as conn:
        conn.execute('DELETE FROM product_locks WHERE product_name = ? AND locked_by = ?', (nazwa, current_operator()))
    sync_product_catalog_to_cloud()

if 'database_products' not in st.session_state:
    st.session_state['database_products'] = wczytaj_produkty_z_db()

def get_product_by_ean(search_value):
    try:
        db = wczytaj_produkty_z_db()
        matched = []
        sought = safe_ean(search_value)
        for nazwa, dane in db.items():
            eans = product_ean_levels(dane)
            if sought in eans.values():
                row_data = {'nazwa': nazwa}
                row_data.update(dane)
                row_data["Poziom EAN"] = next(level for level, code in eans.items() if code == sought)
                matched.append(row_data)
        return pd.DataFrame(matched)
    except Exception as e:
        return pd.DataFrame()


def get_products_by_name(search_value):
    try:
        query = str(search_value).strip().casefold()
        if not query:
            return pd.DataFrame()

        matched = []
        for nazwa, dane in wczytaj_produkty_z_db().items():
            if query in str(nazwa).casefold():
                row_data = {'nazwa': nazwa}
                row_data.update(dane)
                matched.append(row_data)
        return pd.DataFrame(matched)
    except Exception:
        return pd.DataFrame()



# ==================== BAZA TYPÓW PALET ====================
PALLET_TYPES = {
    'EURO': {'L': 1200, 'W': 800, 'H': 152.4, 'WEIGHT': 15},
    'PRZEMYSŁOWA': {'L': 1200, 'W': 1000, 'H': 150, 'WEIGHT': 25},
    'PÓŁPALETA': {'L': 800, 'W': 600, 'H': 120, 'WEIGHT': 8}
}
CUSTOM_PALLETS_FILE = application_storage_path("biblioteka_wlasnych_palet.json")
TRANSPORT_ARCHIVE_FILE = application_storage_path("archiwum_zlecen_transportowych.json")
MASTERCASE_TEMPLATE_FILE = application_storage_path("szablony_mastercase.json")


def load_custom_pallets():
    """Trwała biblioteka własnych palet, dostępna po restarcie aplikacji."""
    return load_persistent_json(CUSTOM_PALLETS_FILE, {})


def save_custom_pallets(pallets):
    save_persistent_json(CUSTOM_PALLETS_FILE, pallets)


def all_available_pallets():
    return {**PALLET_TYPES, **load_custom_pallets()}


def load_transport_archive():
    return load_persistent_json(TRANSPORT_ARCHIVE_FILE, [])


def save_transport_archive(records):
    save_persistent_json(TRANSPORT_ARCHIVE_FILE, records)


def load_mastercase_templates():
    return load_persistent_json(MASTERCASE_TEMPLATE_FILE, {})


def save_mastercase_templates(templates):
    save_persistent_json(MASTERCASE_TEMPLATE_FILE, templates)

def safe_int(val, default=0):
    if pd.isna(val): return default
    try: return int(float(val))
    except (ValueError, TypeError): return default

def safe_float(val, default=0.0):
    if pd.isna(val): return default
    try: return float(val)
    except (ValueError, TypeError): return default

def safe_ean(val):
    if pd.isna(val): return "Brak"
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s

def validate_ean(value):
    """Zwraca (oczyszczony_kod, komunikat_błędu). Pusty EAN jest dopuszczalny."""
    ean = safe_ean(value)
    if not ean or ean == "Brak":
        return "", None
    valid, error = validate_ean_gtin(ean)
    return ean, error or None

def validate_product_text(value, label, required=False):
    text = str(value or "").strip()
    if text and len(text) > 120:
        return text, f"Pole „{label}” jest za długie (maksymalnie 120 znaków)."
    valid, error = validate_required_text(text, label, required=required)
    return text, error or None

def canonical_column_name(label):
    return str(label).strip().casefold().replace("ł", "l").replace("ó", "o").replace("ś", "s").replace("ć", "c").replace("ż", "z").replace("ź", "z").replace("ą", "a").replace("ę", "e").replace("ń", "n").replace("_", " ").replace("-", " ")

def safe_product_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return datetime.now().date()

@st.cache_data(show_spinner=False)
def build_import_template_xlsx():
    """Tworzy prosty, edytowalny szablon importu paletyzacji."""
    template = pd.DataFrame([{
        "Nazwa": "Przykładowy karton", "Dlugosc": 400, "Szerokosc": 300,
        "Wysokosc": 250, "Waga": 4.5, "EAN": "5056134535500",
        "EAN_Produkt": "5901234123457", "EAN_Display": "5901234123464", "EAN_MasterCase": "5901234123471",
        "Produkt_Dlugosc": 200, "Produkt_Szerokosc": 120, "Produkt_Wysokosc": 80, "Produkt_Masa_netto_kg": 0.25,
        "Display_Dlugosc": 400, "Display_Szerokosc": 300, "Display_Wysokosc": 240,
        "Display_Masa_pustego_kg": 0.35, "Display_Masa_pelnego_kg": 4.35,
        "MC_Dlugosc_wewnetrzna": 610, "MC_Szerokosc_wewnetrzna": 410, "MC_Wysokosc_wewnetrzna": 290,
        "MC_Dlugosc_zewnetrzna": 620, "MC_Szerokosc_zewnetrzna": 420, "MC_Wysokosc_zewnetrzna": 300,
        "MC_Tara_kg": 0.6, "MC_Masa_brutto_max_kg": 15, "MC_FEFCO": "0201", "MC_Tektura": "5-warstwowa", "MC_Fala": "BC",
        "Typ_Palety": "EURO", "Max_Wysokosc": 2000, "Max_Waga": 500,
        "displays_in_mc": 1, "boxes_in_display": 1, "pcs_in_box": 1,
        "SKU": "SKU-001", "Producent": "Przykładowy producent",
        "Klient": "Przykładowy klient", "Aktywny": "Tak",
        "Data_ostatniej_weryfikacji": datetime.now().date().isoformat(),
    }])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        template.to_excel(writer, index=False, sheet_name="Import produktów")
    return output.getvalue()

def generuj_uklad_warstwy(L_pal, W_pal, l_pud, w_pud):
    if l_pud <= 0 or w_pud <= 0: return []
    L_pal, W_pal = int(L_pal), int(W_pal)
    l_pud, w_pud = int(l_pud), int(w_pud)
    najlepszy_uklad = []
    max_sztuk = -1

    def ocen_i_zapisz(uklad):
        nonlocal max_sztuk, najlepszy_uklad
        if len(uklad) > max_sztuk:
            max_sztuk = len(uklad)
            najlepszy_uklad = uklad

    def szukaj(L, W, l, w, swap=False):
        if l <= 0 or w <= 0: return
        nx, ny = L // l, W // w
        uklad = []
        for ix in range(nx):
            for iy in range(ny): uklad.append((iy * w, ix * l, w, l) if swap else (ix * l, iy * w, l, w))
        ocen_i_zapisz(uklad)
        for k in range(1, int(L // l) + 1):
            x1 = k * l; x2 = L - x1
            uklad = []
            for ix in range(k):
                for iy in range(W // w): uklad.append((iy * w, ix * l, w, l) if swap else (ix * l, iy * w, l, w))
            for ix in range(x2 // w):
                for iy in range(W // l): uklad.append((iy * l, x1 + ix * w, l, w) if swap else (x1 + ix * w, iy * l, w, l))
            ocen_i_zapisz(uklad)

    szukaj(L_pal, W_pal, l_pud, w_pud, swap=False)
    szukaj(W_pal, L_pal, l_pud, w_pud, swap=True)
    
    if najlepszy_uklad:
        kolumny = {}
        for rect in najlepszy_uklad:
            x, y, dx, dy = rect
            x_key = round(x, 1)
            if x_key not in kolumny: kolumny[x_key] = []
            kolumny[x_key].append(rect)
            
        pionowo_wycentrowany = []
        for x_key, kolumna in kolumny.items():
            min_y_k = min(r[1] for r in kolumna)
            max_y_k = max(r[1] + r[3] for r in kolumna)
            wys_kolumny = max_y_k - min_y_k
            offset_y = (W_pal - wys_kolumny) / 2.0 - min_y_k
            for x, y, dx, dy in kolumna:
                pionowo_wycentrowany.append((x, y + offset_y, dx, dy))
                
        min_x = min(r[0] for r in pionowo_wycentrowany)
        max_x = max(r[0] + r[2] for r in pionowo_wycentrowany)
        szer_ukladu = max_x - min_x
        offset_x = (L_pal - szer_ukladu) / 2.0 - min_x
        
        wycentrowany_uklad = []
        for x, y, dx, dy in pionowo_wycentrowany:
            wycentrowany_uklad.append((x + offset_x, y, dx, dy))
        return wycentrowany_uklad
    return najlepszy_uklad

# Nowa funkcja dla Tab 4: generuje układ dla sztywno określonej orientacji (bez automatycznego zamieniania)
def generuj_uklad_dla_orientacji(L_pal, W_pal, l_pud, w_pud):
    return layout_for_orientation(L_pal, W_pal, l_pud, w_pud)

def sprawdz_pattern_i_overhang(uklad, L_pal, W_pal):
    if not uklad:
        return "Brak układu", 0.0
    return overhang_status(uklad, L_pal, W_pal)

def stworz_wykres_mini(dl, szer, uklad, pal_data, tytul):
    fig, ax = plt.subplots(figsize=(4, 3), facecolor='#FFFFFF')
    p_len, p_wid = pal_data['L'], pal_data['W']
    
    ax.set_title(tytul, fontsize=9, fontweight='bold')
    ax.set_facecolor('#F8F9FA'); ax.grid(True, linestyle='--', alpha=0.5, color='#CBD5E0')
    paleta_gora = patches.Rectangle((0, 0), p_len, p_wid, linewidth=1.5, edgecolor='#C05621', facecolor='#ED8936', alpha=0.3)
    ax.add_patch(paleta_gora)
    
    for i, rect in enumerate(uklad):
        x, y, dx, dy = rect
        box = patches.Rectangle((x, y), dx, dy, linewidth=1, edgecolor='#1A202C', facecolor='#3182CE', alpha=0.85)
        ax.add_patch(box)
        ax.text(x+dx/2, y+dy/2, f"#{i+1}", color='#FFFFFF', fontsize=6, fontweight='bold', ha='center', va='center')
        
    ax.set_xlim([-50, p_len + 50]); ax.set_ylim([-50, p_wid + 50]); ax.set_aspect('equal')
    ax.set_xlabel("Długość [mm]", fontsize=7); ax.set_ylabel("Szerokość [mm]", fontsize=7)
    plt.tight_layout()
    return fig

def stworz_wykres(dl, szer, wys, uklad, warstwy, max_h, szt_warstwa, pal_data, cartons_to_show=None):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), facecolor='#F8F9FA')
    p_len, p_wid, p_h = pal_data['L'], pal_data['W'], pal_data['H']

    top_cartons = min(len(uklad), int(cartons_to_show)) if cartons_to_show is not None else len(uklad)
    ax1.set_title(f"Rzut z góry (załadowano: {top_cartons} / {szt_warstwa} miejsc)", fontsize=10, fontweight='bold')
    ax1.set_facecolor('#FFFFFF'); ax1.grid(True, linestyle='--', alpha=0.5, color='#CBD5E0')
    paleta_gora = patches.Rectangle((0, 0), p_len, p_wid, linewidth=2, edgecolor='#C05621', facecolor='#ED8936', alpha=0.3)
    ax1.add_patch(paleta_gora)
    for i, rect in enumerate(uklad[:top_cartons]):
        x, y, dx, dy = rect
        box = patches.Rectangle((x, y), dx, dy, linewidth=1.2, edgecolor='#1A202C', facecolor='#3182CE', alpha=0.85)
        ax1.add_patch(box)
        ax1.text(x+dx/2, y+dy/2, f"#{i+1}", color='#FFFFFF', fontsize=7, fontweight='bold', ha='center', va='center')
    ax1.set_xlim([-50, p_len + 50]); ax1.set_ylim([-50, p_wid + 50]); ax1.set_aspect('equal')
    ax1.set_xlabel("Długość [mm]"); ax1.set_ylabel("Szerokość [mm]")

    ax2.set_title(f"Przekrój pionowy ({warstwy} warstw)", fontsize=10, fontweight='bold')
    ax2.set_facecolor('#FFFFFF'); ax2.grid(True, linestyle='--', alpha=0.5, color='#CBD5E0')
    paleta_bok = patches.Rectangle((0, 0), p_len, p_h, linewidth=2, edgecolor='#C05621', facecolor='#ED8936', alpha=0.9)
    ax2.add_patch(paleta_bok)
    
    remaining_cartons = int(cartons_to_show) if cartons_to_show is not None else len(uklad) * warstwy
    for l_idx in range(warstwy):
        z = p_h + l_idx * wys
        boxes_in_layer = min(len(uklad), remaining_cartons)
        for rect in uklad[:boxes_in_layer]:
            x, y, dx, dy = rect
            box = patches.Rectangle((x, z), dx, wys, linewidth=1, edgecolor='#1A202C', facecolor='#3182CE', alpha=0.85)
            ax2.add_patch(box)
        remaining_cartons -= boxes_in_layer
            
    total_h = p_h + warstwy * wys
    ax2.axhline(y=total_h, color='#E53E3E', linestyle='--', linewidth=2)
    ax2.set_xlim([-50, p_len + 50]); ax2.set_ylim([-50, max(max_h + 100, total_h + 150)])
    ax2.set_ylabel("Wysokość całkowita [mm]")
    ax2.set_xlabel("Długość [mm]")
    
    plt.tight_layout()
    return fig

def stworz_wykres_3d(dl, szer, wys, uklad, warstwy, pal_data):
    fig = go.Figure()
    p_len, p_wid, p_h = pal_data['L'], pal_data['W'], pal_data['H']
    
    fig.add_trace(go.Mesh3d(
        x=[0, p_len, p_len, 0, 0, p_len, p_len, 0],
        y=[0, 0, p_wid, p_wid, 0, 0, p_wid, p_wid],
        z=[0, 0, 0, 0, p_h, p_h, p_h, p_h],
        color='#ED8936', opacity=0.8, name='Paleta'
    ))
    
    for l_idx in range(warstwy):
        z_base = p_h + l_idx * wys
        for rect in uklad:
            x, y, dx, dy = rect
            bx = [x, x+dx, x+dx, x, x, x+dx, x+dx, x]
            by = [y, y, y+dy, y+dy, y, y, y+dy, y+dy]
            bz = [z_base, z_base, z_base, z_base, z_base+wys, z_base+wys, z_base+wys, z_base+wys]
            
            fig.add_trace(go.Mesh3d(
                x=bx, y=by, z=bz,
                color='#3182CE', opacity=0.85,
                alphahull=0, name='Pudełko'
            ))
            
    fig.update_layout(
        title="Interaktywny model 3D palety",
        scene=dict(
            xaxis_title='Długość [mm]',
            yaxis_title='Szerokość [mm]',
            zaxis_title='Wysokość [mm]',
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=40)
    )
    return fig

def generuj_pdf_raport(nazwa, dane_slownik, img_buffer=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    font_name, font_bold = FONT_REGULAR, FONT_BOLD
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName=font_bold, fontSize=15, textColor=colors.HexColor('#1A202C'), spaceAfter=8)
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontName=font_name, fontSize=8, textColor=colors.HexColor('#2D3748'))
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontName=font_bold, fontSize=8, textColor=colors.HexColor('#1A202C'))

    story.append(Paragraph(f"Karta Paletyzacji: {nazwa}", title_style))
    
    if img_buffer is not None:
        story.append(RLImage(img_buffer, width=400, height=160))
        story.append(Spacer(1, 6))
    else:
        story.append(Spacer(1, 8))
    
    table_data = [[Paragraph("Parametr", cell_bold), Paragraph("Wartość", cell_bold)]]
    for klucz, val in dane_slownik.items():
        table_data.append([Paragraph(klucz, cell_bold), Paragraph(str(val), cell_style)])
        
    t = Table(table_data, colWidths=[200, 340])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor('#ED8936')),
        ('TEXTCOLOR', (0,0), (1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7FAFC')])
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

def wykonaj_obliczenia_i_wyswietl(nazwa, dl, szer, wys, waga, ean, pal_typ, max_total_h, max_total_weight, disp_mc, boxes_disp, pcs_box, key_suffix):
    if dl <= 0 or szer <= 0 or wys <= 0:
        return
        
    if pal_typ not in PALLET_TYPES: 
        pal_typ = "EURO"
    pal_data = PALLET_TYPES[pal_typ]
    
    uklad = generuj_uklad_warstwy(pal_data['L'], pal_data['W'], dl, szer)
    szt_warstwa = len(uklad)
    if szt_warstwa == 0:
        st.error(f"Nie można wyliczyć układu dla produktu: {nazwa}")
        return
    
    dzielnik_waga = szt_warstwa * waga
    limit_w_wagi = int((max_total_weight - pal_data['WEIGHT']) // dzielnik_waga) if dzielnik_waga > 0 else 999
    limit_w_h = int((max_total_h - pal_data['H']) // wys) if wys > 0 else 1
    
    warstwy = max(1, min(limit_w_h, limit_w_wagi))
    razem_pakietow = szt_warstwa * warstwy
    wys_mm = round(pal_data['H'] + warstwy * wys, 1)
    waga_kg = round(razem_pakietow * waga, 2)
    waga_brutto_calkowita = round(waga_kg + pal_data['WEIGHT'], 2)
    
    szt_w_mc = disp_mc * boxes_disp * pcs_box
    pcs_pal = razem_pakietow * szt_w_mc
    pudelek_pal = razem_pakietow * boxes_disp * disp_mc
    displays_pal = razem_pakietow * disp_mc
    
    min_baza = min(pal_data['L'], pal_data['W'])
    wsp_stabilnosci = (wys_mm / min_baza) if min_baza > 0 else 0

    dane_raportu = {
        "Kod EAN-13": ean,
        "Wymiary jednostki": f"{int(dl)}L × {int(szer)}W × {int(wys)}H mm",
        "Typ palety": pal_typ,
        "Wymiary palety": f"{pal_data['L']}L × {pal_data['W']}W × {pal_data['H']}H mm",
        "Wymiary całkowite z paletą": f"{pal_data['L']}L × {pal_data['W']}W × {wys_mm}H mm (Limit: {max_total_h} mm)",
        "Waga całkowita": f"{waga_kg} kg (z paletą: {waga_brutto_calkowita} kg | Limit: {max_total_weight} kg)",
        "Wysokość całkowita": f"{wys_mm} mm",
        "Sztuk na warstwie": str(szt_warstwa),
        "Liczba warstw": f"{warstwy} (Układ kolumnowy)",
        "Łączna liczba paczek": str(razem_pakietow),
        "Kontrola obrysu": "OK (W obrysie palety)",
        "Wskaźnik stabilności": f"{wsp_stabilnosci:.2f} — " + ("Stabilna (< 2.0)" if wsp_stabilnosci <= 2.0 else "Wysoka (> 2.0)"),
        "Displays w Master Case": str(disp_mc),
        "Pudełek w displayu": str(boxes_disp),
        "Sztuk w Master Case": str(szt_w_mc),
        "Sztuk na palecie": str(pcs_pal),
        "Pudełek na palecie": str(pudelek_pal),
        "Displays na palecie": str(displays_pal)
    }

    fig = stworz_wykres(dl, szer, wys, uklad, warstwy, max_total_h, szt_warstwa, pal_data)
    
    pdf_img_buf = io.BytesIO()
    fig.savefig(pdf_img_buf, format="png", dpi=200, bbox_inches='tight')
    pdf_img_buf.seek(0)

    with st.expander(f"📦 Raport produktu: **{nazwa}** (Paleta: {pal_typ}, Sztuk na palecie: {pcs_pal})", expanded=True):
        pdf_buffer = generuj_pdf_raport(nazwa, dane_raportu, pdf_img_buf)
        st.download_button(
            label="📄 Pobierz oficjalny raport PDF (z wizualizacją 2D)",
            data=pdf_buffer,
            file_name=f"raport_paletyzacji_{nazwa}.pdf",
            mime="application/pdf",
            key=f"pdf_{key_suffix}"
        )
        
        col1, col2 = st.columns([1, 1.2])
        with col1:
            st.markdown("#### 📋 Szczegółowe parametry")
            st.dataframe(pd.DataFrame(list(dane_raportu.items()), columns=["Parametr", "Wartość"]), width="stretch", hide_index=True)
        with col2:
            st.markdown("#### 🎨 Wizualizacja i Modele")
            tab_2d, tab_3d = st.tabs(["Wizualizacja 2D", "Model 3D (Plotly)"])
            with tab_2d:
                st.pyplot(fig)
                
                buf_img = io.BytesIO()
                fig.savefig(buf_img, format="png", bbox_inches='tight', dpi=300)
                buf_img.seek(0)
                st.download_button(
                    label="📥 Pobierz wykres 2D (PNG)",
                    data=buf_img,
                    file_name=f"wykres_2d_{nazwa}.png",
                    mime="image/png",
                    key=f"img_2d_{key_suffix}"
                )
            with tab_3d:
                fig_3d = stworz_wykres_3d(dl, szer, wys, uklad, warstwy, pal_data)
                st.plotly_chart(fig_3d, width="stretch")

# ==================== PASEK BOCZNY (SIDEBAR) ====================
# Panel jest ułożony zgodnie z przebiegiem pracy: zlecenie → konstrukcja →
# logistyka → dokumenty i jakość. Dzięki temu użytkownik nie musi pamiętać
# numerów wszystkich modułów ani przełączać kontekstu zlecenia w wielu miejscach.
role = st.session_state["user_role"]
available_options = navigation_available_modules(MODULE_OPTIONS, role)

if not available_options:
    st.sidebar.error("Brak modułów dostępnych dla tej roli.")
    st.stop()

st.sidebar.title("🏭 Produkcja")
st.sidebar.caption("System Zarządzania Produkcją")
st.sidebar.markdown(
    f"👤 **{st.session_state['user_name']}**  \n🎭 {role}"
)

with st.sidebar.expander("📁 Aktywne zlecenie", expanded=True):
    order_registry = load_document_registry()
    active_order_id = get_current_order_id()
    order_ids = [active_order_id] + [order_id for order_id in order_registry if order_id != active_order_id]
    order_ids = sorted(set(order_ids), key=lambda order_id: order_registry.get(order_id, {}).get("updated_at", ""), reverse=True)

    def sidebar_order_label(order_id):
        order_record = order_registry.get(order_id, {})
        header = order_record.get("order_header", {}) or {}
        order_number = header.get("order_number", "")
        status = order_record.get("order_status", "nowe")
        return f"{order_number or order_id} · {status}"

    selected_order_id = st.selectbox(
        "Pracujesz na", options=order_ids, format_func=sidebar_order_label,
        index=order_ids.index(active_order_id), key=f"sidebar_active_order_{active_order_id}",
    )
    if selected_order_id != active_order_id:
        activate_order_context(selected_order_id)
        st.rerun()
    st.caption(f"ID: {active_order_id}")
    if st.button("➕ Nowe zlecenie", width="stretch", key="sidebar_create_order"):
        create_new_order()
        st.success("Utworzono nowe zlecenie.")
        st.rerun()
    if 12 in available_options.values() and st.button("📁 Otwórz Centrum zlecenia", width="stretch", key="sidebar_open_order_center"):
        st.session_state["main_module_selector"] = module_label_for_id(MODULE_OPTIONS, 12)
        st.session_state["sidebar_module_nonce"] = st.session_state.get("sidebar_module_nonce", 0) + 1
        st.rerun()

st.sidebar.markdown("---")
pending_module_id = st.session_state.pop("pending_module_id", None)
if pending_module_id is not None:
    pending_label = module_label_for_id(MODULE_OPTIONS, pending_module_id)
    if pending_label in available_options:
        # Wykonuje się przed utworzeniem widgetów menu: dzięki temu ich
        # zapamiętany stan nie nadpisze docelowego ekranu po operacji zlecenia.
        st.session_state["main_module_selector"] = pending_label
        # Wymusza świeży klucz listy, aby zapamiętany wybór nie nadpisał
        # programowego przekierowania po operacji zlecenia.
        st.session_state["sidebar_module_nonce"] = st.session_state.get("sidebar_module_nonce", 0) + 1
current_module_label = st.session_state.get("main_module_selector")
if current_module_label not in available_options:
    remembered_module = (load_user_workspace_preferences().get(st.session_state.get("user_name", ""), {}) or {}).get("active_module_label")
    current_module_label = remembered_module if remembered_module in available_options else None
module_labels = list(available_options)
module_index = module_labels.index(current_module_label) if current_module_label in module_labels else 0
selected_module_label = st.sidebar.selectbox(
    "Moduł", options=module_labels, index=module_index,
    key=f"sidebar_module_{st.session_state.get('sidebar_module_nonce', 0)}",
)
st.session_state["main_module_selector"] = selected_module_label
preferences = load_user_workspace_preferences()
user_preferences = preferences.get(st.session_state["user_name"], {})
preferences[st.session_state["user_name"]] = {
    **(user_preferences if isinstance(user_preferences, dict) else {}),
    "active_module_label": selected_module_label,
    "updated_at": datetime.now().isoformat(timespec="seconds"),
}
save_persistent_json(USER_WORKSPACE_FILE, preferences)
selected_module = available_options[selected_module_label]

# Dodatkowa kontrola uprawnień przed uruchomieniem modułu.
selected_module_config = next(
    (data for data in MODULE_OPTIONS.values() if data["id"] == selected_module),
    None
)
if selected_module_config is None or role not in selected_module_config["roles"]:
    st.error("⛔ Nie masz uprawnień do tego modułu.")
    st.stop()

# Moduły operacyjne pracują zawsze na jednym, aktywnym order_id. Przy zmianie
# modułu zapisujemy najnowszą edycję (również tę wykonaną tuż przed kliknięciem
# pozycji w menu), a po wejściu odtwarzamy dane wybranego zlecenia.
previous_module = st.session_state.get("_previous_selected_module")
if previous_module in ORDER_CONTEXT_MODULES and previous_module != selected_module:
    save_order_context()
if selected_module in ORDER_CONTEXT_MODULES:
    synchronize_order_context()
st.session_state["_previous_selected_module"] = selected_module


with st.sidebar.expander("🔍 Wyszukiwanie produktu", expanded=False):
    search_ean_input = st.text_input(
        "EAN / GTIN", placeholder="Wpisz lub zeskanuj kod", key="sidebar_search_ean"
    )
    search_name_input = st.text_input(
        "Nazwa, SKU, klient lub producent", placeholder="Wpisz szukaną wartość", key="sidebar_search_name"
    )
    if search_ean_input:
        result_df = get_product_by_ean(search_ean_input)
        if not result_df.empty:
            product = result_df.iloc[0]
            st.success(f"Znaleziono: {product['nazwa']}")
            st.caption(f"Poziom EAN: {product.get('Poziom EAN', '—')} | masa: {product.get('Waga', 0)} kg")
        else:
            st.warning("Brak produktu o tym EAN.")
    elif search_name_input:
        name_results_df = get_products_by_name(search_name_input)
        if not name_results_df.empty:
            st.success(f"Wyniki: {len(name_results_df)}")
            for _, product in name_results_df.head(5).iterrows():
                st.caption(f"**{product['nazwa']}** · {product.get('SKU', '—')} · {product.get('EAN', '—')}")
        else:
            st.warning("Brak produktu lub kartonu o tej nazwie.")

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Wyloguj", width="stretch", key="logout_button"):
    _end_persistent_session()
    st.session_state["_explicitly_logged_out"] = True
    st.session_state["authenticated"] = False
    st.session_state["user_role"] = None
    st.session_state["user_name"] = None
    st.rerun()

st.sidebar.markdown("---")
sidebar_version = read_version(Path(APP_DIR))
st.sidebar.caption("🔄 Wersja systemu")
st.sidebar.markdown(f"**{sidebar_version['version']}** · build `{sidebar_version['build_id']}`")
st.sidebar.caption(f"Ostatnia aktualizacja: {sidebar_version['updated_at'] or 'brak danych'}")
data_backup_files = list((Path(APP_DIR) / "dane_aplikacji" / "data_exports").glob("backup_danych_*.zip"))
if data_backup_files:
    latest_data_backup = max(data_backup_files, key=lambda path: path.stat().st_mtime)
    backup_time = datetime.fromtimestamp(latest_data_backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    st.sidebar.caption(f"Ostatni backup danych: {backup_time}")
else:
    st.sidebar.caption("Ostatni backup danych: brak")



# --- FUNKCJE BUFORUJĄCE PRZETWARZANIE PLIKÓW ---
@st.cache_data(show_spinner="Czytanie struktury pliku...")
def get_excel_sheets(file_bytes, file_name):
    engine = "odf" if file_name.endswith(".ods") else None
    # io.BytesIO przekształca bajty na obiekt plikopodobny
    xls = pd.ExcelFile(io.BytesIO(file_bytes), engine=engine)
    return xls.sheet_names


@st.cache_data(show_spinner="Wczytywanie i czyszczenie danych...")
def process_data(file_bytes, file_name, file_ext, header_row, sheet_name=None):
    file_obj = io.BytesIO(file_bytes)
    
    if file_ext == "csv":
        df = pd.read_csv(file_obj, header=header_row, sep=None, engine="python")
    else:
        engine = "odf" if file_ext == "ods" else None
        df = pd.read_excel(file_obj, sheet_name=sheet_name, header=header_row, engine=engine)

    # Czyszczenie spacji z nazw kolumn
    df.columns = [str(col).strip() for col in df.columns]

    # Usuwanie całkowicie pustych kolumn i zliczanie duplikatów
    initial_cols = len(df.columns)
    df = df.dropna(axis=1, how='all')
    dropped_cols = initial_cols - len(df.columns)
    duplicates_count = df.duplicated().sum()

    return df, dropped_cols, duplicates_count

def upload_email_attachments_to_kdrive(attachments):
    """Wysyła jeden plik lub paczkę ZIP do kDrive i zwraca link zgodny z polityką udostępniania."""
    try:
        import requests
        token = st.secrets["KDRIVE_API_TOKEN"]
        drive_id = st.secrets["KDRIVE_DRIVE_ID"]
        directory_id = st.secrets["KDRIVE_DIRECTORY_ID"]
    except (KeyError, FileNotFoundError):
        raise ValueError("Brak konfiguracji KDRIVE_API_TOKEN, KDRIVE_DRIVE_ID lub KDRIVE_DIRECTORY_ID w secrets.toml.")
    if len(attachments) == 1:
        upload_name, upload_bytes, upload_mime = attachments[0].name, attachments[0].getvalue(), attachments[0].type or "application/octet-stream"
    else:
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
            for attachment in attachments:
                archive.writestr(attachment.name, attachment.getvalue())
        upload_name, upload_bytes, upload_mime = f"zalaczniki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip", bundle.getvalue(), "application/zip"
    headers = {"Authorization": f"Bearer {token}"}
    # Bezpieczny domyślny wariant nie publikuje plików poza polityką folderu.
    # Dla linku dostępnego publicznie ustaw świadomie KDRIVE_LINK_RIGHT="public"
    # w secrets.toml. kDrive dopuszcza też wariant chroniony hasłem.
    kdrive_link_right = str(st.secrets.get("KDRIVE_LINK_RIGHT", "inherit")).strip().lower()
    if kdrive_link_right not in {"inherit", "public", "password"}:
        raise ValueError("KDRIVE_LINK_RIGHT może mieć wartość: inherit, public albo password.")
    upload_response = requests.post(
        f"https://api.infomaniak.com/3/drive/{drive_id}/upload",
        headers={**headers, "Content-Type": upload_mime, "Content-Length": str(len(upload_bytes))},
        params={"directory_id": str(directory_id), "file_name": upload_name, "total_size": str(len(upload_bytes)), "conflict": "rename"},
        data=upload_bytes, timeout=180,
    )
    if not upload_response.ok:
        raise ValueError(f"kDrive upload ({upload_response.status_code}): {upload_response.text[:500]}")
    upload_data = upload_response.json().get("data", {})
    file_id = upload_data.get("id")
    if not file_id:
        raise ValueError("kDrive nie zwrócił identyfikatora przesłanego pliku.")
    share_response = requests.post(
        f"https://api.infomaniak.com/2/drive/{drive_id}/files/{file_id}/link",
        headers={**headers, "Content-Type": "application/json"}, json={"right": kdrive_link_right}, timeout=60,
    )
    if not share_response.ok:
        raise ValueError(f"kDrive link ({share_response.status_code}): {share_response.text[:500]}")
    share_data = share_response.json().get("data", {})
    share_url = share_data.get("url") or share_data.get("link") or share_data.get("sharelink", {}).get("url")
    if not share_url:
        raise ValueError("Plik przesłano, ale kDrive nie zwrócił linku udostępnienia. Sprawdź uprawnienia tokenu do tworzenia linków.")
    return {"name": upload_name, "size": len(upload_bytes), "url": share_url, "file_id": file_id}


# --- TAB 1: BAZA, ERP & ODS ---
# --- TAB 2: PALETYZACJA ---
# --- TAB 3: E-MAIL ---
def generuj_pdf_etykiety_paletowe(wynik, ean, miejsce_dostawy, store_document=False):
    """Kompatybilny punkt wejścia do generatora etykiet paletowych."""
    pdf_bytes = build_pallet_labels_pdf(
        wynik, ean, miejsce_dostawy, canvas=canvas, colors=colors, mm=mm,
        qr_widget=qr.QrCodeWidget, drawing_class=Drawing, render_pdf=renderPDF,
        font_regular=FONT_REGULAR, font_bold=FONT_BOLD,
    )
    if store_document:
        store_order_pdf("Etykiety paletowe", pdf_bytes, "etykiety_paletowe.pdf")
    return pdf_bytes


def odczytaj_kod_qr(plik_obrazu):
    """Kompatybilny punkt wejścia do usługi dekodowania QR."""
    try:
        import cv2
        return decode_qr_bytes(plik_obrazu.getvalue(), cv2_module=cv2, numpy_module=np)
    except ImportError:
        return None, "Brakuje biblioteki OpenCV. Zainstaluj pakiet opencv-python."
    except Exception as error:
        return None, f"Nie udało się odczytać QR: {error}"


def generuj_pdf_instrukcje_ukladania(result, zabezpieczenia, store_document=False):
    """Tworzy instrukcję; do Centrum zlecenia zapisuje ją tylko na żądanie."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=38, rightMargin=38, topMargin=42, bottomMargin=42
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "PalletInstructionTitle", parent=styles["Title"], fontName=FONT_BOLD,
        fontSize=20, leading=24, textColor=colors.HexColor("#123B69"), spaceAfter=5,
    )
    subtitle = ParagraphStyle(
        "PalletInstructionSubtitle", parent=styles["Normal"], fontName=FONT_REGULAR,
        fontSize=9, leading=12, textColor=colors.HexColor("#5B6470"), spaceAfter=14,
    )
    heading = ParagraphStyle(
        "PalletInstructionHeading", parent=styles["Heading2"], fontName=FONT_BOLD,
        fontSize=12, leading=15, textColor=colors.HexColor("#123B69"), spaceBefore=12, spaceAfter=6,
    )
    body = ParagraphStyle(
        "PalletInstructionBody", parent=styles["Normal"], fontName=FONT_REGULAR,
        fontSize=9.5, leading=13,
    )
    small = ParagraphStyle(
        "PalletInstructionSmall", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#5B6470"),
    )

    def footer(pdf_canvas, pdf_doc):
        pdf_canvas.saveState()
        pdf_canvas.setStrokeColor(colors.HexColor("#D7DEE8"))
        pdf_canvas.line(38, 28, A4[0] - 38, 28)
        pdf_canvas.setFont(FONT_REGULAR, 7.5)
        pdf_canvas.setFillColor(colors.HexColor("#5B6470"))
        pdf_canvas.drawString(38, 17, "Instrukcja operacyjna - przygotowana przez Kalkulator")
        pdf_canvas.drawRightString(A4[0] - 38, 17, f"Strona {pdf_doc.page}")
        pdf_canvas.restoreState()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    product_name = escape(str(result["Produkt"]))
    pallet_name = escape(str(result["Paleta"]))
    orientation_name = escape(str(result["Orientacja"]))
    story = [
        Paragraph("INSTRUKCJA UKŁADANIA PALETY", title),
        Paragraph(f"Dokument operacyjny dla magazynu | Wygenerowano: {now}", subtitle),
    ]
    product_table = Table([
        [Paragraph("PRODUKT", small), Paragraph("PALETA", small), Paragraph("ORIENTACJA KARTONU", small)],
        [Paragraph(product_name, body), Paragraph(pallet_name, body), Paragraph(orientation_name, body)],
    ], colWidths=[170, 130, 189])
    product_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D4E3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [product_table, Spacer(1, 12), Paragraph("Parametry docelowe", heading)]

    parameters = [
        ["Kartonów na warstwę", str(result["Kartonów/warstwę"]), "Pełnych warstw", str(result["Pełnych warstw"])],
        ["Pojemność pełnej palety", str(result["Pojemność palety"]), "Liczba palet", str(result["Liczba palet"])],
        ["Ostatnia paleta", f"{result['Kartonów na ostatniej palecie']} kart. / {result['Warstw na ostatniej palecie']} warstw", "Wysokość", f"{result['Wysokość palety mm']} mm"],
        ["Masa brutto", f"{result['Masa brutto/paleta kg']} kg", "Stabilność", f"{result['Stabilność /100']} / 100"],
    ]
    parameter_table = Table(parameters, colWidths=[132, 112, 132, 113])
    parameter_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#5B6470")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#5B6470")),
        ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
        ("FONTNAME", (1, 0), (1, -1), FONT_BOLD),
        ("FONTNAME", (3, 0), (3, -1), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [parameter_table, Paragraph("Kolejność wykonywania", heading)]
    security_text = escape(", ".join(zabezpieczenia) if zabezpieczenia else "brak dodatkowych zabezpieczeń")
    steps = [
        "Sprawdź stan palety: powierzchnia musi być sucha, czysta, bez uszkodzonych desek i wystających elementów.",
        f"Ustaw pierwszą warstwę: <b>{result['Kartonów/warstwę']} kart.</b>, orientacja: <b>{orientation_name}</b>. Kartony ustawiaj równo do krawędzi palety.",
        f"Buduj kolejne warstwy do maksymalnie <b>{result['Pełnych warstw']}</b> pełnych warstw. Zachowaj równą płaszczyznę każdej warstwy.",
        f"Na ostatniej palecie przygotuj <b>{result['Kartonów na ostatniej palecie']} kart.</b> w maksymalnie <b>{result['Warstw na ostatniej palecie']}</b> warstwach.",
        f"Zastosuj zabezpieczenia: <b>{security_text}</b>. Folia i narożniki nie mogą zasłaniać etykiety logistycznej.",
        f"Przed przekazaniem do wysyłki potwierdź wysokość do <b>{result['Wysokość palety mm']} mm</b> oraz masę brutto do <b>{result['Masa brutto/paleta kg']} kg</b>.",
    ]
    for number, step in enumerate(steps, 1):
        story.append(Paragraph(f"<b>{number}.</b> {step}", body))
        story.append(Spacer(1, 4))

    story += [Paragraph("Kontrola końcowa", heading)]
    checks = [
        "Liczba kartonów i warstw zgodna z instrukcją.",
        "Paleta stabilna; ładunek nie wystaje poza jej obrys.",
        "Zabezpieczenia założone, etykieta logistyczna widoczna.",
        "Paleta oznaczona numerem zlecenia / miejscem docelowym.",
    ]
    check_table = Table([[Paragraph(f"□  {item}", body)] for item in checks], colWidths=[489])
    check_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8D4E3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ]))
    story += [check_table, Spacer(1, 16)]
    story += [Paragraph("Wykonał: ______________________________    Data / godzina: ______________________________", body)]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    pdf_bytes = buffer.getvalue()
    product_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(result.get("Produkt", "produkt"))).strip("_") or "produkt"
    if store_document:
        store_order_pdf("Instrukcja paletyzacji", pdf_bytes, f"instrukcja_ukladania_{product_name}.pdf")
    return pdf_bytes




# --- TAB 4: OPTYMALIZACJA UKŁADU KARTONÓW NA PALECIE ---

# Zachowane wyłącznie na czas porównania z nowym ekranem; nie jest wykonywane.


# --- TAB 5: GENERATOR OPISÓW I ZLECEŃ TRANSPORTOWYCH ---
def _legacy_generuj_pdf_zlecenie_transportowe(document, save_to_order=True):
    """Buduje profesjonalne zlecenie transportowe i opcjonalnie zapisuje je przy order_id."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=34, rightMargin=34, topMargin=46, bottomMargin=46,
        title=f"Zlecenie transportowe {document.get('number', '')}",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TransportTitle", parent=styles["Title"], fontName=FONT_BOLD, fontSize=18,
        leading=22, textColor=colors.HexColor("#123B69"), spaceAfter=10,
    )
    heading = ParagraphStyle(
        "TransportHeading", parent=styles["Heading2"], fontName=FONT_BOLD, fontSize=11,
        textColor=colors.HexColor("#123B69"), spaceBefore=12, spaceAfter=6,
    )
    body = ParagraphStyle(
        "TransportBody", parent=styles["Normal"], fontName=FONT_REGULAR, fontSize=9,
        leading=13, textColor=colors.HexColor("#1F2937"),
    )
    bold = ParagraphStyle("TransportBold", parent=body, fontName=FONT_BOLD)
    requirements = document.get("requirements", {}) or {}
    dimensions = document.get("dimensions_cm", [0, 0, 0])
    dimensions = (list(dimensions) + [0, 0, 0])[:3]
    number = str(document.get("number", "—"))
    status = str(document.get("status", "robocze"))
    story = [
        Paragraph("ZLECENIE TRANSPORTOWE / TRANSPORT ORDER", title),
        Paragraph(
            f"<b>Nr / No.:</b> {escape(number)} &nbsp;&nbsp;&nbsp; "
            f"<b>Status:</b> {escape(status)} &nbsp;&nbsp;&nbsp; "
            f"<b>Data:</b> {escape(str(document.get('saved_at', ''))[:10])}", body,
        ),
        Spacer(1, 12),
    ]
    shipment_rows = [
        [Paragraph("<b>Przewoźnik / Carrier</b>", bold), Paragraph(escape(str(document.get("carrier", "—"))), body)],
        [Paragraph("<b>Rodzaj ładunku / Cargo</b>", bold), Paragraph(escape(str(document.get("cargo_type", "—"))), body)],
        [Paragraph("<b>Ilość / Quantity</b>", bold), Paragraph(str(document.get("quantity", 0)), body)],
        [Paragraph("<b>Waga brutto / Gross weight</b>", bold), Paragraph(f"{float(document.get('total_weight', 0)):.2f} kg", body)],
        [Paragraph("<b>Wymiary 1 sztuki / Dimensions</b>", bold), Paragraph(f"{dimensions[0]:.1f} × {dimensions[1]:.1f} × {dimensions[2]:.1f} cm", body)],
        [Paragraph("<b>Metry ładunkowe / LDM</b>", bold), Paragraph(f"{float(document.get('ldm', 0)):.2f}", body)],
    ]
    shipment_table = Table(shipment_rows, colWidths=[190, 330])
    shipment_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF1FB")),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#C8D4E3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [Paragraph("Dane ładunku / Shipment data", heading), shipment_table, Spacer(1, 12)]
    requirement_rows = [
        [Paragraph("<b>Winda samochodowa / Tail lift</b>", bold), Paragraph("TAK / YES" if requirements.get("tail_lift") else "NIE / NO", body)],
        [Paragraph("<b>Piętrowanie / Stacking</b>", bold), Paragraph("ZABRONIONE / DO NOT STACK" if requirements.get("no_stacking") else "DOZWOLONE / ALLOWED", body)],
        [Paragraph("<b>Awizacja telefoniczna / Phone notice</b>", bold), Paragraph("TAK / YES" if requirements.get("phone_notice") else "NIE / NO", body)],
    ]
    requirement_table = Table(requirement_rows, colWidths=[250, 270])
    requirement_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#FFF7E8")),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#E6CF9C")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [Paragraph("Wymagania przewozu / Transport requirements", heading), requirement_table, Spacer(1, 12)]
    notes = str(document.get("notes", "")).strip() or "Brak dodatkowych uwag / No additional notes."
    story += [
        Paragraph("Uwagi dla przewoźnika / Carrier notes", heading),
        Paragraph(escape(notes).replace("\n", "<br/>"), body), Spacer(1, 22),
        Paragraph("Zlecił / Ordered by: ______________________________", body), Spacer(1, 16),
        Paragraph("Potwierdzenie przewoźnika / Carrier confirmation: ______________________________", body),
    ]
    doc.build(story, canvasmaker=TransportOrderCanvas)
    pdf_bytes = buffer.getvalue()
    if save_to_order:
        safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", number)
        store_order_pdf(
            "Zlecenie transportowe", pdf_bytes, f"zlecenie_transportowe_{safe_number}.pdf",
            {"number": number, "carrier": document.get("carrier", ""), "ldm": document.get("ldm", 0), "weight_kg": document.get("total_weight", 0)},
            order_id=document.get("order_id") or get_current_order_id(),
        )
    return pdf_bytes


def generuj_pdf_zlecenie_transportowe(document, save_to_order=True):
    """Warstwa aplikacji: wspólny generator tworzy PDF, aplikacja go wersjonuje."""
    pdf_bytes = build_transport_order_pdf(
        document, font_regular=FONT_REGULAR, font_bold=FONT_BOLD, canvasmaker=TransportOrderCanvas,
    )
    if save_to_order:
        number = str((document or {}).get("number", "—"))
        safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", number)
        store_order_pdf(
            "Zlecenie transportowe", pdf_bytes, f"zlecenie_transportowe_{safe_number}.pdf",
            {"number": number, "carrier": document.get("carrier", ""), "ldm": document.get("ldm", 0), "weight_kg": document.get("total_weight", 0)},
            order_id=document.get("order_id") or get_current_order_id(),
        )
    return pdf_bytes



# Zachowane wyłącznie na czas porównania z nowym ekranem; nie jest wykonywane.

def _legacy_generuj_pdf_packing_list(df_pack):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    font_name, font_bold = FONT_REGULAR, FONT_BOLD
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName=font_bold, fontSize=14, textColor=colors.HexColor('#1A202C'), spaceAfter=12)
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontName=font_name, fontSize=9, textColor=colors.HexColor('#2D3748'))
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontName=font_bold, fontSize=9, textColor=colors.HexColor('#1A202C'))

    story.append(Paragraph("Zbiorcza Lista Pakowania (Packing List)", title_style))
    story.append(Spacer(1, 10))
    
    table_data = [[Paragraph(str(col), cell_bold) for col in df_pack.columns]]
    for _, row in df_pack.iterrows():
        table_data.append([Paragraph(str(val), cell_style) for val in row])
        
    num_cols = len(df_pack.columns)
    col_width = 520 / num_cols if num_cols > 0 else 520
    col_widths = [col_width] * num_cols
    
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ED8936')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7FAFC')])
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer


def generuj_pdf_packing_list(df_pack):
    """Kompatybilny zwrot BytesIO dla starszego widoku Packing List."""
    return BytesIO(build_basic_packing_list_pdf(df_pack, font_regular=FONT_REGULAR, font_bold=FONT_BOLD))

PACKING_LIST_ARCHIVE_FILE = application_storage_path("archiwum_packing_list.json")

def _load_packing_archive():
    return load_persistent_json(PACKING_LIST_ARCHIVE_FILE, [])

def _save_packing_archive(archive):
    save_persistent_json(PACKING_LIST_ARCHIVE_FILE, archive)

def _legacy_generuj_pdf_packing_list_prof(document, store_document=False):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=30, rightMargin=30, topMargin=34, bottomMargin=34)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PLTitle", parent=styles["Title"], fontName=FONT_BOLD, fontSize=18, textColor=colors.HexColor("#123B69"))
    normal = ParagraphStyle("PLNormal", parent=styles["Normal"], fontName=FONT_REGULAR, fontSize=8, leading=10)
    bold = ParagraphStyle("PLBold", parent=normal, fontName=FONT_BOLD)
    labels = {"PL": ("LISTA PAKOWANIA", "Nadawca", "Odbiorca", "Podsumowanie", "Podpis wydającego", "Podpis odbierającego"), "EN": ("PACKING LIST", "Sender", "Recipient", "Summary", "Released by", "Received by")}
    language = document.get("language", "PL")
    title_text = " / ".join([labels[x][0] for x in (["PL", "EN"] if language == "PL/EN" else [language])])
    story = [Paragraph(title_text, title), Spacer(1, 7), Paragraph(f"<b>Nr:</b> {escape(document['number'])} &nbsp;&nbsp; <b>Status:</b> {escape(document['status'])} &nbsp;&nbsp; <b>Data utworzenia:</b> {escape(document['created_at'])}", normal), Spacer(1, 9)]
    header = [[Paragraph(f"<b>{labels['PL'][1]} / {labels['EN'][1]}</b><br/>{escape(document.get('sender',''))}", normal), Paragraph(f"<b>{labels['PL'][2]} / {labels['EN'][2]}</b><br/>{escape(document.get('recipient',''))}<br/>{escape(document.get('delivery_place',''))}", normal)]]
    t = Table(header, colWidths=[260, 275]); t.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,colors.HexColor("#C8D4E3")),("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F8FAFC")),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),8)])); story += [t, Spacer(1,10)]
    columns = ["Produkt / SKU", "EAN-y poziomów / LOT", "Szt.", "Kart.", "Paleta", "Masa kg"]
    rows = [[Paragraph(x, bold) for x in columns]]
    for item in document["items"]:
        eans = (
            f"Produkt: {escape(str(item.get('EAN produktu', '—') or '—'))}<br/>"
            f"Display: {escape(str(item.get('EAN displaya', '—') or '—'))}<br/>"
            f"Master Case: {escape(str(item.get('EAN Master Case', '—') or '—'))}<br/>"
            f"Poziom: {escape(str(item.get('Poziom opakowania', '—')))} | użyty: {escape(str(item.get('EAN/GTIN','')))}<br/>"
            f"LOT: {escape(str(item.get('LOT','')))}"
        )
        rows.append([Paragraph(f"{escape(str(item.get('Produkt','')))}<br/>{escape(str(item.get('SKU','')))}", normal), Paragraph(eans, normal), str(item.get("Sztuki",0)), str(item.get("Kartony",0)), escape(str(item.get("Paleta",""))), str(item.get("Masa kg",0))])
    table = Table(rows, colWidths=[120,180,42,42,80,60], repeatRows=1); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#123B69")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,-1),FONT_REGULAR),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#D7DEE8")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("PADDING",(0,0),(-1,-1),5)])); story += [table, Spacer(1,10)]
    summary = document.get("summary", {}); story += [Paragraph(f"<b>{labels['PL'][3]} / {labels['EN'][3]}:</b> palety: {summary.get('pallets',0)} | kartony: {summary.get('cartons',0)} | sztuki: {summary.get('pieces',0)} | kg: {summary.get('weight',0)} | m³: {summary.get('m3',0)} | LDM: {summary.get('ldm',0)}", normal), Spacer(1,25), Paragraph(f"{labels['PL'][4]} / {labels['EN'][4]}: ____________________ &nbsp;&nbsp;&nbsp; {labels['PL'][5]} / {labels['EN'][5]}: ____________________", normal)]
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    pdf_name = f"packing_list_{str(document.get('number', 'draft')).replace('/', '_')}.pdf"
    if store_document:
        store_order_pdf("Packing List", pdf_bytes, pdf_name, {"number": document.get("number", "")}, order_id=document.get("order_id") or get_current_order_id())
    return pdf_bytes


def generuj_pdf_packing_list_prof(document, store_document=False):
    """Warstwa aplikacji do wersjonowania Packing List po wygenerowaniu PDF."""
    pdf_bytes = build_packing_list_pdf(document, font_regular=FONT_REGULAR, font_bold=FONT_BOLD)
    if store_document:
        pdf_name = f"packing_list_{str(document.get('number', 'draft')).replace('/', '_')}.pdf"
        store_order_pdf(
            "Packing List", pdf_bytes, pdf_name, {"number": document.get("number", "")},
            order_id=document.get("order_id") or get_current_order_id(),
        )
    return pdf_bytes


def generuj_pdf_etykiety_packing(document):
    buffer = BytesIO(); pdf = canvas.Canvas(buffer, pagesize=(100*mm, 100*mm))
    for pallet in document.get("pallets", []):
        pdf.setFillColor(colors.HexColor("#123B69")); pdf.rect(0, 82*mm, 100*mm, 18*mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white); pdf.setFont(FONT_BOLD, 14); pdf.drawString(7*mm, 89*mm, "PALETA " + str(pallet.get("Paleta","")))
        pdf.setFillColor(colors.black); pdf.setFont(FONT_BOLD, 10); pdf.drawString(7*mm, 75*mm, str(pallet.get("Produkt", ""))[:44])
        pdf.setFont(FONT_REGULAR, 9); pdf.drawString(7*mm, 68*mm, f"Kartony: {pallet.get('Kartony',0)}  |  Status: {pallet.get('Status','oczekuje')}")
        widget=qr.QrCodeWidget(str(pallet.get("QR",""))); bounds=widget.getBounds(); size=42*mm; drawing=Drawing(size,size,transform=[size/(bounds[2]-bounds[0]),0,0,size/(bounds[3]-bounds[1]),0,0]); drawing.add(widget); renderPDF.draw(drawing,pdf,51*mm,13*mm)
        pdf.setFont(FONT_REGULAR,7); pdf.drawString(7*mm, 10*mm, document.get("number", "")); pdf.showPage()
    pdf.save(); return buffer.getvalue()

# --- TAB 6: PACKING LIST ---

# Wspólne pomocniki BCT: moduł 8 używa ich przy zapisie archiwum i generowaniu PDF.
BCT_LIBRARY_FILE = application_storage_path("biblioteka_tektur_bct.json")
BCT_ARCHIVE_FILE = application_storage_path("archiwum_bct.json")
BCT_TEMPLATE_FILE = application_storage_path("szablony_kartonow_bct.json")

def bct_load_json(path, default):
    return load_persistent_json(path, default)

def bct_save_json(path, data):
    save_persistent_json(path, data)

def generuj_pdf_raport_bct(result, store_document=False):
    pdf_bytes = build_bct_report_pdf(result, font_regular=FONT_REGULAR, font_bold=FONT_BOLD)
    if store_document:
        store_order_pdf("Raport BCT", pdf_bytes, "raport_bct.pdf", {"approval": result.get("approval", "roboczy")})
    return pdf_bytes

def generuj_pdf_bct_dokument(title_text, lines):
    return build_bct_text_document_pdf(title_text, lines, font_regular=FONT_REGULAR, font_bold=FONT_BOLD)

# --- MODUŁ 11: WALIDACJA ZAMÓWIEŃ Z DRUKARNI ---


# --- REJESTR WIDOKÓW APLIKACJI ---
# Renderowanie uruchamiamy dopiero po zdefiniowaniu wszystkich funkcji i stałych,
# aby każdy ekran otrzymał kompletny kontekst zależności.
def _render_module_1():
    render_catalog_import_screen(st, globals())


def _render_module_2():
    render_palletization_screen(st, globals())


def _render_module_3():
    render_email_screen(st, {
        "pd": pd, "load_database": load_database, "save_database": save_database,
        "current_operator": current_operator, "get_current_order_id": get_current_order_id,
        "document_files_dir": DOCUMENT_FILES_DIR, "document_file_is_ready": document_file_is_ready,
        "upload_kdrive": upload_email_attachments_to_kdrive, "register_order_email": register_order_email,
        "render_email_html": render_email_html, "secrets": st.secrets,
    })


def _render_module_4():
    render_pallet_optimization_screen(st, {
        "pd": pd, "np": np, "load_products": wczytaj_produkty_z_db,
        "storage_path": application_storage_path, "load_json": load_persistent_json, "save_json": save_persistent_json,
        "load_custom_pallets": load_custom_pallets, "pallet_types": PALLET_TYPES,
        "packaging_levels": PACKAGING_LEVEL_OPTIONS, "get_physical": get_packaging_level_physical,
        "ean_levels": product_ean_levels, "catalog_snapshot": build_tab9_catalog_snapshot,
        "layout": generuj_uklad_dla_orientacji, "layout_mixed": generuj_uklad_warstwy,
        "overhang": sprawdz_pattern_i_overhang, "bct_gate": get_bct_palletization_gate,
        "current_order_id": get_current_order_id, "update_snapshot": update_order_snapshot,
        "save_context": save_order_context, "mini_chart": stworz_wykres_mini, "full_chart": stworz_wykres,
        "build_layout_pdf": build_pallet_layout_2d_pdf, "store_order_pdf": store_order_pdf,
        "font_regular": FONT_REGULAR, "font_bold": FONT_BOLD,
        "read_qr": odczytaj_kod_qr, "labels_pdf": generuj_pdf_etykiety_paletowe,
    })


def _render_module_5():
    render_transport_screen(
        st, pandas=pd, pallet_types=PALLET_TYPES, generate_pdf=generuj_pdf_zlecenie_transportowe,
        get_current_order_id=get_current_order_id, load_archive=load_transport_archive,
        save_archive=save_transport_archive, update_snapshot=update_order_snapshot,
        save_order_context=save_order_context,
    )


def _render_module_10():
    render_ppwr_screen(st, {
        "pd": pd, "datetime": datetime, "calculate_ppwr_masses": calculate_ppwr_masses,
        "migrate_legacy_order_units": migrate_legacy_order_units,
        "format_ppwr_number": format_ppwr_number, "get_current_order_id": get_current_order_id,
        "load_document_registry": load_document_registry, "deserialize_order_context_value": _deserialize_order_context_value,
        "update_order_snapshot": update_order_snapshot, "save_order_context": save_order_context,
        "load_database": load_database, "save_database": save_database,
        "generate_ppwr_mass_specification_pdf": generate_ppwr_mass_specification_pdf,
        "generate_eu_declaration_of_conformity_pdf": generate_eu_declaration_of_conformity_pdf,
        "generate_production_date_declaration_pdf": generate_production_date_declaration_pdf,
        "normalize_vat_identifier": normalize_vat_identifier, "load_products": wczytaj_produkty_z_db,
        "ppwr_deepl_translation_overrides": ppwr_deepl_translation_overrides,
        "ppwr_translation_rows": ppwr_translation_rows,
        "deepl_api_key": st.secrets.get("DEEPL_API_KEY", ""),
        "deepl_translation_error": DeepLTranslationError,
        "render_packing_diagram": lambda ppwr_positions, order: render_ppwr_packing_diagram(
            st, ppwr_positions, order, get_current_order_id, canonical_column_name,
        ),
    })


def _render_module_12():
    render_order_center_screen(st, {
        "pd": pd, "json": json, "os": os, "secrets": secrets, "datetime": datetime,
        "get_current_order_id": get_current_order_id, "load_document_registry": load_document_registry,
        "create_new_order": create_new_order, "render_dashboard": render_order_center_dashboard,
        "load_order_contexts": load_order_contexts, "update_order_lifecycle_status": update_order_lifecycle_status,
        "activate_order_context": activate_order_context, "order_requirement_profiles": ORDER_REQUIREMENT_PROFILES,
        "order_requirement_labels": ORDER_REQUIREMENT_LABELS, "save_shared_state": save_shared_state,
        "document_registry_file": DOCUMENT_REGISTRY_FILE, "module_label_for_id": module_label_for_id,
        "module_options": MODULE_OPTIONS, "group_for_module_id": group_for_module_id, "module_groups": MODULE_GROUPS,
        "get_order_flow_map": get_order_flow_map, "get_order_data_quality": get_order_data_quality,
        "build_order_audit_report": build_order_audit_report, "get_order_end_to_end_checks": get_order_end_to_end_checks,
        "render_document_statuses": render_order_center_document_statuses, "render_document_files": render_order_center_document_files,
        "store_order_pdf": store_order_pdf,
        "document_files_dir": DOCUMENT_FILES_DIR, "document_archive_dir": DOCUMENT_ARCHIVE_DIR,
        "restore_order_pdf_version": restore_order_pdf_version, "archive_order_pdf_file": archive_order_pdf_file,
        "delete_order_pdf_file": delete_order_pdf_file, "clear_pdf_version_history": clear_pdf_version_history,
        "inspect_pdf_visually": inspect_pdf_visually, "is_path_in_directory": is_path_in_directory,
        "generate_short_order_id": generate_short_order_id, "create_order_copy_record": create_order_copy_record,
        "copy_order_context": copy_order_context, "order_context_file": ORDER_CONTEXT_FILE,
        "render_actions": render_order_center_actions, "delete_order_permanently": delete_order_permanently,
    })


def _render_module_13():
    production_plan = load_persistent_json(PRODUCTION_PLANNER_FILE, empty_production_plan())

    def save_production_plan(plan):
        save_persistent_json(PRODUCTION_PLANNER_FILE, normalize_production_plan(plan))

    render_production_planner(
        production_plan,
        save_plan=save_production_plan,
        active_order_id=get_current_order_id(),
        font_regular=FONT_REGULAR,
        font_bold=FONT_BOLD,
    )


MODULE_RENDERERS = {
    1: _render_module_1,
    2: _render_module_2,
    3: _render_module_3,
    4: _render_module_4,
    5: _render_module_5,
    6: lambda: render_module_six(st, globals()),
    7: lambda: render_module_seven(st, globals()),
    8: lambda: render_module_eight(st, globals()),
    9: render_tab9,
    10: _render_module_10,
    11: lambda: render_qa_screen(st, {
        "pd": pd, "load_database": load_database, "save_database": save_database,
        "store_order_pdf": store_order_pdf, "font_bold": FONT_BOLD, "font_regular": FONT_REGULAR,
    }),
    12: _render_module_12,
    13: _render_module_13,
    14: lambda: render_project_archive_screen(st),
    15: lambda: render_inventory_screen(st, {
        "load_json": load_persistent_json,
        "save_json": save_persistent_json,
        "inventory_file": INVENTORY_SESSIONS_FILE,
        "load_products": wczytaj_produkty_z_db,
        "current_operator": current_operator,
        "font_regular": FONT_REGULAR,
        "font_bold": FONT_BOLD,
    }),
    28: lambda: render_order_stock_screen(st, {"load_json": load_persistent_json, "save_json": save_persistent_json, "archive_file": ORDER_STOCK_ARCHIVE_FILE, "font_regular": FONT_REGULAR, "font_bold": FONT_BOLD}),
    16: lambda: render_bobbin_calculator_screen(
        st, font_regular=FONT_REGULAR, font_bold=FONT_BOLD, user_role=role,
        load_json=load_operational_json, save_json=save_operational_json,
    ),
    17: lambda: render_material_library_screen(st, {"pd": pd, "datetime": datetime, "load_database": load_database, "save_database": save_database}),
    18: lambda: render_client_portal_screen(st, {"pd": pd, "datetime": datetime, "secrets": secrets, "load_database": load_database, "save_database": save_database, "load_document_registry": load_document_registry}),
    19: lambda: render_client_commercial_screen(st, {"pd": pd, "datetime": datetime, "secrets": secrets, "load_database": load_database, "save_database": save_database, "font_regular": FONT_REGULAR, "font_bold": FONT_BOLD}),
    20: lambda: render_integrations_screen(st, {"pd": pd, "datetime": datetime, "secrets": secrets, "load_database": load_database, "save_database": save_database, "load_products": wczytaj_produkty_z_db, "save_product": zapisz_produkt_w_db}),
    21: lambda: render_artwork_approval_screen(st),
    22: lambda: render_generators_screen(st, {"load_database": load_database, "save_database": save_database, "font_regular": FONT_REGULAR, "font_bold": FONT_BOLD}),
    23: lambda: render_client_product_card_screen(st, {"pd": pd, "get_current_order_id": get_current_order_id, "load_document_registry": load_document_registry, "load_database": load_database, "save_database": save_database, "update_order_snapshot": update_order_snapshot, "save_order_context": save_order_context, "font_regular": FONT_REGULAR, "font_bold": FONT_BOLD}),
    # Moduł 24 jest niezależnym archiwum pracy. Stały klucz operacyjny nie
    # zależy od ścieżki serwera ani od istnienia zlecenia w Centrum zleceń.
    24: lambda: render_work_settlement_archive_screen(st, {"pd": pd, "get_current_order_id": get_current_order_id, "current_operator": current_operator, "store_order_pdf": store_order_pdf, "font_regular": FONT_REGULAR, "font_bold": FONT_BOLD, "archive_file": WORK_SETTLEMENT_ARCHIVE_FILE, "load_json": load_operational_json, "save_json": save_operational_json, "load_order_contexts": load_order_contexts, "deserialize_context": _deserialize_order_context_value}),
    25: lambda: render_preorder_screen(st, {"pd": pd, "font_regular": FONT_REGULAR, "font_bold": FONT_BOLD, "logo_path": os.path.join(APP_DIR, "logo1.jpg"), "archive_file": PREORDER_ARCHIVE_FILE, "load_json": load_persistent_json, "save_json": save_persistent_json, "deepl_api_key": st.secrets.get("DEEPL_API_KEY", "")}),
    26: lambda: render_preflight_dtp_screen(st, {"get_current_order_id": get_current_order_id, "update_order_snapshot": update_order_snapshot, "store_order_pdf": store_order_pdf}),
    27: lambda: render_backup_center_screen(st, {"app_root": APP_DIR}),
    29: lambda: render_user_admin_screen(st, globals()),
    30: lambda: render_update_screen(st, {"app_root": APP_DIR}),
    # Moduł 31 używa stałego klucza operacyjnego. Dzięki temu Streamlit i
    # wersja offline korzystają z tego samego rekordu Supabase, niezależnie
    # od ścieżki katalogu na danym komputerze lub serwerze.
    31: lambda: render_bobbin_settlement_screen(st, {"pd": pd, "current_operator": current_operator, "archive_file": os.path.join(APP_DIR, "dane_aplikacji", "rozliczenie_bobin.json"), "load_json": load_operational_json, "save_json": save_operational_json, "storage_error": lambda: getattr(SHARED_STATE_STORE, "last_error", None), "font_regular": FONT_REGULAR, "font_bold": FONT_BOLD}),
    32: lambda: render_warehouse_label_screen(st, {"font_regular": FONT_REGULAR, "font_bold": FONT_BOLD}),
}

selected_renderer = MODULE_RENDERERS.get(selected_module)
if selected_renderer is None:
    st.error("Nie znaleziono widoku wybranego modułu.")
else:
    selected_renderer()


