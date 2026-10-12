import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.document_safety import document_file_is_ready, is_path_in_directory
from core.email_html import render_email_html
from core.packaging import packaging_level_quantities
from core.vat import normalize_vat_identifier
from core.pallets import layout_for_orientation, mixed_layout_for_orientation, overhang_status
from core.bct import calculate_bct
from core.ppwr import calculate_ppwr_masses, migrate_legacy_order_units
from core.qa import evaluate_qa_metrics, parse_ignored_regions
from core.pallet_optimization import optimize_pallet_layout
from services.order_copy import copy_order_context, create_order_copy_record
from services.document_bundle import build_order_documents_zip, order_document_files
from services.document_storage import clear_pdf_version_history, store_pdf_version
from services.order_context import UNSERIALIZABLE_CONTEXT, deserialize_context_value, serialize_context_value
from services.order_registry import derive_order_lifecycle, generate_short_order_id, new_order_record, register_document_record
from services.storage import SharedStateStore
from services.validation import validate_ean_gtin, validate_required_text
from services.email_service import parse_email_addresses, prepare_email_delivery, use_kdrive_for_attachments
from services.product_catalog import build_catalog_snapshot, ean_conflicts, normalize_product_record
from services.document_generation import bct_document_rows
from services.order_documents import as_positive_int, default_order_header, order_header_pdf_fields, packaging_calculation, selected_ean, validate_base_data
from services.navigation import available_modules, available_navigation_groups, group_for_module_id, group_for_module_label, module_label_for_id
from services.user_access import apply_role_permissions, build_role_permissions, save_user_access_config, update_user_credentials
from services.production_planning import (
    SHIFT_OPTIONS, add_assignment, add_employee, assignments_for_week, empty_production_plan,
    export_plan_for_offline_html, import_plan_from_offline_html, update_assignment, week_dates,
)
from services.production_schedule_pdf import build_production_schedule_pdf
from services.ppwr_documents import (
    format_ppwr_number, ppwr_deepl_translation_overrides, ppwr_table_for_language,
    ppwr_translation_key, ppwr_translation_rows,
)
from services.production_documents import (
    build_eorder_bilingual_pdf,
    build_eorder_pdf,
    build_structured_document_pdf,
    build_worksheet_pdf,
    worksheet_item_data,
)
from services.smtp_message import build_smtp_message
from services.qa_files import inspect_pdf_separations, render_validation_bytes
from services.bct_documents import build_bct_report_pdf, build_bct_text_document_pdf
from services.email_attachments import load_order_pdf_attachments
from services.ppwr_documents import build_ppwr_mass_specification_pdf
from services.order_center_analysis import end_to_end_checks, order_data_quality, order_flow_map
from services.pdf_visual import inspect_pdf_visually
from services.order_requirements import requirement_status
from services.transport_documents import build_transport_order_pdf
from services.packing_documents import build_basic_packing_list_pdf, build_packing_list_pdf
from services.pallet_documents import build_pallet_labels_pdf, decode_qr_bytes
from services.email_presentation import EMAIL_TEMPLATES, default_email_branding, email_template_content, mask_history_addresses
from services.inventory import (
    build_inventory_report_pdf,
    build_stock_comparison_pdf,
    build_tray_labels_pdf,
    build_tray_labels_zpl,
    compare_inventory_to_stock,
    enrich_inventory_records,
    mobile_catalog_rows,
    parse_inventory_csv,
    parse_comparison_inventory_csv,
    parse_stock_csv,
    session_summary,
    stock_comparison_summary,
    normalize_tray_id,
    tray_qr_data,
    tray_qr_payload,
    update_inventory_record,
)
from modules.production_document_actions import (
    generate_bilingual_eorder, generate_eorder, generate_tds_pdf, generate_worksheet,
)
from modules.production_document_form_data import apply_approval_validation, project_file_payload, validate_eorder
from modules.production_document_form_actions import update_production_summary
from modules.production_documents_screen import apply_catalog_selection, prepare_production_documents_state, render_catalog_selector, render_catalog_snapshot_preview, render_production_documents_intro, render_tds_artwork_section, render_tds_form_intro, render_tds_materials_section, render_tds_quantities_section, render_tds_specification_section, restore_production_document_state


class PackagingRegressionTests(unittest.TestCase):
    RELATIONS = {"displays_per_mastercase": 4, "boxes_per_display": 2, "pieces_per_box": 3}

    def test_product_quantity_rounds_up_to_display_and_mastercase(self):
        result = packaging_level_quantities(25, "Produkt", self.RELATIONS)
        self.assertEqual(result["produktow"], 25)
        self.assertEqual(result["displayow"], 5)
        self.assertEqual(result["mastercase"], 2)

    def test_display_quantity_calculates_all_levels(self):
        result = packaging_level_quantities(5, "Display", self.RELATIONS)
        self.assertEqual((result["produktow"], result["displayow"], result["mastercase"]), (30, 5, 2))

    def test_mastercase_quantity_calculates_all_levels(self):
        result = packaging_level_quantities(2, "Master Case", self.RELATIONS)
        self.assertEqual((result["produktow"], result["displayow"], result["mastercase"]), (48, 8, 2))

    def test_unknown_level_is_rejected(self):
        with self.assertRaises(ValueError):
            packaging_level_quantities(1, "Paleta", self.RELATIONS)

    def test_clear_pdf_version_history_keeps_current_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            current = os.path.join(directory, "current.pdf")
            versions = os.path.join(directory, "wersje")
            old = os.path.join(versions, "current_v1.pdf")
            os.makedirs(versions)
            Path(current).write_bytes(b"current")
            Path(old).write_bytes(b"old")
            documents = [{"version": 2, "history": [{"previous_file_path": old}]}]
            self.assertEqual(clear_pdf_version_history(documents, [directory]), 1)
            self.assertTrue(os.path.isfile(current))
            self.assertFalse(os.path.exists(versions))
            self.assertEqual((documents[0]["version"], documents[0]["history"]), (1, []))

    def test_production_document_adapters_build_pdfs_and_register_them(self):
        stored = []

        def store_pdf(*args, **kwargs):
            stored.append((args, kwargs))

        tds = generate_tds_pdf(
            {"Dane": {"Produkt": "Test"}}, document_title="TDS", font_regular="Helvetica",
            font_bold="Helvetica-Bold", attachment_image_bytes=None, bct_flowables=(),
            canvasmaker=None, store_pdf=store_pdf, order_id="ORD-1",
        )
        eorder = generate_eorder(
            [{"product_name": "Test", "qty_net": 1}], {"order_no": "ORD-1", "recipient": {}},
            font_regular="Helvetica", font_bold="Helvetica-Bold", logo_path="", canvasmaker=None,
            store_pdf=store_pdf, order_id="ORD-1",
        )
        bilingual = generate_bilingual_eorder(
            [{"product_name": "Test", "qty_net": 1}], {"order_no": "ORD-1", "recipient": {}},
            font_regular="Helvetica", font_bold="Helvetica-Bold", canvasmaker=None,
            store_pdf=store_pdf, order_id="ORD-1",
        )
        worksheet = generate_worksheet(
            [{"product_name": "Test"}], {"order_no": "ORD-1"}, font_regular="Helvetica",
            font_bold="Helvetica-Bold", logo_path="", bct_flowables=(), canvasmaker=None,
            store_pdf=store_pdf, order_id="ORD-1",
        )

        self.assertTrue(all(document.getvalue().startswith(b"%PDF") for document in (tds, eorder, bilingual, worksheet)))
        self.assertEqual([entry[0][0] for entry in stored], ["TDS", "E-Order", "E-Order", "Karta Pracy"])

    def test_production_document_form_validation_is_independent_of_streamlit(self):
        errors, warnings = validate_eorder([], {}, "")
        self.assertIn("E-Order nie zawiera żadnej pozycji.", errors)
        self.assertEqual(apply_approval_validation(errors, ["niezgodność"], "zatwierdzone")[-1], "Zatwierdzenie zablokowane: niezgodność")

    def test_advisory_packaging_warning_does_not_block_approved_document(self):
        errors = []
        apply_approval_validation(errors, ["Pozycja 1: Informacyjnie: Relacja Display → Master Case różni się od kartoteki."], "zatwierdzone")
        self.assertEqual(errors, [])

    def test_project_attachment_payload_versions_changed_files(self):
        class UploadedFile:
            name, type = "projekt.pdf", "application/pdf"

            def getvalue(self):
                return b"version one"

        first = project_file_payload(UploadedFile(), uploaded_by="Tester", uploaded_at="2026-08-24T12:00:00")
        self.assertEqual(project_file_payload(UploadedFile(), first), first)

        class NewUploadedFile(UploadedFile):
            def getvalue(self):
                return b"version two"

        second = project_file_payload(NewUploadedFile(), first, uploaded_by="Tester", uploaded_at="2026-08-24T12:01:00")
        self.assertEqual(len(second["versions"]), 1)
        self.assertEqual(second["versions"][0]["sha256"], first["sha256"])

    def test_production_summary_persists_totals_in_order_registry(self):
        registry = {}
        summary = update_production_summary(
            "ORD-1", {"machine": "M1"}, [{"production_planned": 10, "production_made": 8, "production_waste": 2}],
            load_registry=lambda: registry, save_registry=lambda value: registry.update(value),
            user_name="Tester", saved_at="2026-08-24T12:00:00",
        )
        self.assertEqual((summary["planned"], summary["made"], summary["waste"]), (10, 8, 2))
        self.assertEqual(registry["ORD-1"]["summary"]["production"]["machine"], "M1")

    def test_production_documents_intro_shows_bct_warning_and_summary(self):
        with patch("modules.production_documents_screen.st") as ui:
            render_production_documents_intro(
                bct_for_order={"approval": "do akceptacji"},
                bct_for_tds={"bct": 10, "safe_bct": 8, "max_safe_layers": 2, "approval": "robocze"},
            )
        self.assertTrue(ui.warning.called)
        self.assertTrue(ui.info.called)

    def test_production_documents_state_normalizes_header_and_item_lists(self):
        state = {}
        header = prepare_production_documents_state(
            session_state=state, active_order_id="ORD-1", registry_header={"priority": "unknown", "document_status": "bad", "language": "DE"},
            default_order_header=lambda order_id: {"order_id": order_id, "priority": "normalny", "document_status": "robocze", "language": "PL"},
            priorities=["normalny"], document_statuses=["robocze"], languages=["PL"],
        )
        self.assertEqual((header["priority"], header["document_status"], header["language"]), ("normalny", "robocze", "PL"))
        self.assertEqual((state["e_order_items"], state["work_sheet_items"]), ([], []))

    def test_catalog_selection_populates_tds_session_fields(self):
        state = {}
        snapshot = apply_catalog_selection(
            session_state=state, selected_product="Produkt A", empty_option="—",
            build_snapshot=lambda name: {"Nazwa produktu": name, "Klient": "Klient A"},
            packaging_calculation=lambda *_: {"produktow_w_displayu": 50, "produktow_w_mastercase": 1200},
            order_clients=["Klient A"],
        )
        self.assertEqual(snapshot["Nazwa produktu"], "Produkt A")
        self.assertEqual((state["val_order_channel"], state["val_qty_display_pieces"], state["val_qty_carton"]), ("Klient A", 50, 1200))

    def test_catalog_selector_returns_selected_snapshot_and_packaging_level(self):
        state = {}
        with patch("modules.production_documents_screen.st") as ui:
            ui.selectbox.side_effect = ["Produkt A", "Display"]
            snapshot, level = render_catalog_selector(
                session_state=state, catalog_products={"Produkt A": {}}, order_clients=[],
                build_snapshot=lambda name: {"Nazwa produktu": name},
                packaging_calculation=lambda *_: {"produktow_w_displayu": 1, "produktow_w_mastercase": 1},
                selected_ean=lambda *_: "123",
            )
        self.assertEqual((snapshot["Nazwa produktu"], level), ("Produkt A", "Display"))

    def test_restored_production_document_state_precedes_widgets(self):
        state = {
            "tab9_order_to_restore": {"val_product_name": "Produkt A"},
            "tab9_catalog_snapshot_to_restore": {"Nazwa produktu": "Produkt A"},
            "tab9_project_attachment_to_restore": {"name": "projekt.pdf"},
        }
        restore_production_document_state(state)
        self.assertEqual(state["val_product_name"], "Produkt A")
        self.assertEqual(state["tab9_catalog_applied_name"], "Produkt A")
        self.assertEqual(state["tab9_project_attachment"]["name"], "projekt.pdf")

    def test_tds_form_intro_consumes_one_time_notices(self):
        state = {"tab9_restore_notice": "yes", "tab9_product_notice": "Produkt A"}
        with patch("modules.production_documents_screen.st") as ui:
            render_tds_form_intro(state)
        self.assertEqual(state, {})
        self.assertEqual(ui.success.call_count, 2)

    def test_catalog_snapshot_preview_uses_only_nonempty_values(self):
        class Context:
            def __enter__(self): return self
            def __exit__(self, *_): return False
        with patch("modules.production_documents_screen.st") as ui:
            ui.expander.return_value = Context()
            render_catalog_snapshot_preview({"Produkt": {"SKU": "A", "Pusty": ""}, "Relacje pakowania": {"sztuki": 10}})
        self.assertTrue(ui.dataframe.called)

    def test_tds_material_and_quantity_sections_preserve_field_keys(self):
        class Context:
            def __enter__(self): return self
            def __exit__(self, *_): return False
        fields_seen = []
        def field(*args, **kwargs):
            fields_seen.append(kwargs["key_prefix"])
            return True, kwargs["key_prefix"]
        with patch("modules.production_documents_screen.st") as ui:
            ui.expander.return_value = Context()
            ui.columns.return_value = (Context(), Context())
            materials = render_tds_materials_section(database={key: [] for key in ("products", "other_criteria", "dimensions", "filter_colors", "box_paper_colors", "print_types", "orders_clients")}, render_field=field, render_master_checkbox=Mock())
            quantities = render_tds_quantities_section(render_field=field, render_master_checkbox=Mock())
        self.assertEqual(materials["product_name"], (True, "product_name"))
        self.assertEqual(quantities["qty_net"], (True, "qty_net"))
        self.assertIn("qty_display", fields_seen)

    def test_tds_artwork_section_keeps_attachment_upload_key(self):
        class Context:
            def __enter__(self): return self
            def __exit__(self, *_): return False
        with patch("modules.production_documents_screen.st") as ui:
            ui.expander.return_value = Context()
            ui.file_uploader.return_value = None
            result = render_tds_artwork_section(render_field=lambda *_, **kwargs: (True, kwargs["key_prefix"]), render_master_checkbox=Mock(), existing_attachment={"name": "projekt.pdf", "size": 10})
        self.assertEqual(result[0], (True, "artwork_number"))
        self.assertEqual(ui.file_uploader.call_args.kwargs["key"], "tab9_artwork_source_upload")

    def test_tds_specification_renderer_preserves_legacy_field_keys(self):
        class Context:
            def __enter__(self): return self
            def __exit__(self, *_): return False
        database = {key: [] for key in ("grammages", "print_covers", "color_spaces", "press_combinations", "varnishes", "foil_options", "perforations", "yes_no", "print_types", "display_prints")}
        with patch("modules.production_documents_screen.st") as ui:
            ui.expander.return_value = Context()
            fields = render_tds_specification_section(database=database, render_field=lambda *_, **kwargs: (True, kwargs["key_prefix"]), render_master_checkbox=Mock())
        self.assertEqual(fields["ok_gram"], (True, "ok_gram"))
        self.assertEqual(fields["dsp_wyk"], (True, "dsp_wyk"))
        self.assertEqual(fields["other_notes"], (True, "other_notes"))

    def test_pallet_layout_is_centered_and_overhang_is_detected(self):
        layout = layout_for_orientation(1200, 800, 400, 300)
        self.assertEqual(len(layout), 6)
        self.assertEqual(layout[0][:2], (0.0, 100.0))
        self.assertEqual(overhang_status([(1100, 0, 200, 200)], 1200, 800)[1], 100.0)

    def test_mixed_pallet_layout_beats_uniform_layout_for_ritual_case(self):
        uniform = max(
            len(layout_for_orientation(1200, 800, 470, 200)),
            len(layout_for_orientation(1200, 800, 200, 470)),
        )
        mixed = mixed_layout_for_orientation(1200, 800, 470, 200)
        self.assertEqual(uniform, 8)
        self.assertEqual(len(mixed), 9)
        self.assertEqual(overhang_status(mixed, 1200, 800)[1], 0)

    def test_bct_reports_safe_layers_and_risk(self):
        result = calculate_bct(5, 4, 600, 400, 10, 5)
        self.assertGreater(result["bct"], 0)
        self.assertGreaterEqual(result["max_safe_layers"], 1)
        self.assertIn(result["risk"], {"bezpieczne", "warunkowo bezpieczne", "ryzykowne", "niedopuszczalne"})

    def test_ppwr_excludes_non_packaging_and_keeps_legacy_rows_included(self):
        result = calculate_ppwr_masses([
            {"Komponent opakowania": "Karton", "Materiał główny": "Paper", "Masa jednostkowa (g)": 100, "Ilość / 1 SKU": 1},
            {"Komponent opakowania": "Produkt", "Materiał główny": "Other", "Masa jednostkowa (g)": 50, "Ilość / 1 SKU": 1, "Uwzględniać jako opakowanie PPWR": "false"},
        ], 10, 2)
        self.assertEqual(result["excluded_components_count"], 1)
        self.assertEqual(result["total_sku_g"], 100)
        self.assertEqual(result["total_order_kg"], 2)

    def test_ppwr_uses_exact_order_quantity_for_unit_packaging(self):
        result = calculate_ppwr_masses(
            [{"Komponent opakowania": "Okładka", "Masa jednostkowa (g)": 2.36, "Ilość / 1 SKU": 1}],
            units_per_pallet=24984, pallets_per_order=2, units_per_order=49944,
        )
        self.assertAlmostEqual(result["total_sku_g"], 2.36)
        self.assertAlmostEqual(result["total_order_kg"], 117.86784)

    def test_ppwr_does_not_double_count_equivalent_sku_and_pallet_quantities(self):
        result = calculate_ppwr_masses(
            [{"Komponent opakowania": "Kartonik do rollsa", "Masa jednostkowa (g)": 2.3,
              "Ilość / 1 SKU": 1, "Ilość / 1 paletę": 20736}],
            units_per_pallet=20736, pallets_per_order=2, units_per_order=41472,
        )
        self.assertEqual(result["redundant_pallet_quantities"], ["Kartonik do rollsa"])
        self.assertEqual(result["components"][0]["Ilość / 1 paletę"], 0)
        self.assertAlmostEqual(result["total_order_kg"], 95.3856)

    def test_ppwr_migrates_legacy_display_count_saved_as_sku_quantity(self):
        corrected, migrated = migrate_legacy_order_units(2592, 2592, 16)
        self.assertTrue(migrated)
        self.assertEqual(corrected, 41472)
        unchanged, migrated = migrate_legacy_order_units(41472, 2592, 16)
        self.assertFalse(migrated)
        self.assertEqual(unchanged, 41472)

    def test_qa_status_explains_failed_threshold_and_parses_masks(self):
        assessment = evaluate_qa_metrics(0.97, 2.5, 6, min_ssim=0.98, max_mismatch=2, max_delta_e=5)
        self.assertEqual(assessment["status"], "DO SPRAWDZENIA")
        self.assertEqual(len(assessment["reasons"]), 3)
        regions, invalid = parse_ignored_regions("1,2,30,40; niepoprawne; 5,6,-1,4")
        self.assertEqual(regions, [(1, 2, 30, 40)])
        self.assertEqual(invalid, ["niepoprawne", "5,6,-1,4"])

    def test_pallet_optimizer_selects_variant_and_reports_stability(self):
        def layout(length, width, carton_length, carton_width):
            return [(0, 0, carton_length, carton_width)] if carton_length <= length and carton_width <= width else []
        result = optimize_pallet_layout(
            carton_length=400, carton_width=300, carton_height=200, carton_mass=2,
            pallet={"L": 1200, "W": 800, "H": 144, "WEIGHT": 25}, carton_quantity=10,
            max_height=1600, max_weight=500, can_stack=True, can_rotate_vertical=False,
            layout_standard=layout, layout_mixed=layout, overhang_check=lambda _layout, _l, _w: ("OK", 0),
        )
        self.assertGreater(result["best"]["Pojemność"], 0)
        self.assertEqual(result["pallet_count"], 2)
        self.assertIn(result["stability_text"], {"stabilna", "wymaga zabezpieczenia", "ryzykowna"})


class DocumentSafetyRegressionTests(unittest.TestCase):
    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(is_path_in_directory(os.path.join(root, "..", "outside.pdf"), root))

    def test_ready_document_requires_existing_file_inside_order_directory(self):
        with tempfile.TemporaryDirectory() as root:
            file_path = os.path.join(root, "document.pdf")
            self.assertFalse(document_file_is_ready(file_path, root))
            with open(file_path, "wb") as stream:
                stream.write(b"%PDF-test")
            self.assertTrue(document_file_is_ready(file_path, root))


class EmailAndVatRegressionTests(unittest.TestCase):
    def test_email_preview_escapes_user_html(self):
        html = render_email_html("<script>alert(1)</script>", "", "Firma", "", "")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_vat_normalization_accepts_prefixed_and_unprefixed_number(self):
        self.assertEqual(normalize_vat_identifier("NL 988009596B01"), ("NL", "988009596B01"))
        self.assertEqual(normalize_vat_identifier("  123-456-78-90 "), ("PL", "1234567890"))

    def test_email_presentation_keeps_templates_branding_and_masks_addresses(self):
        self.assertIn("Packing List", EMAIL_TEMPLATES)
        self.assertIn("legal_footer", default_email_branding())
        subject, body = email_template_content("Raport paletyzacji", "Ritual", "English")
        self.assertIn("Ritual", subject)
        self.assertIn("Dear", body)
        masked = mask_history_addresses([{"to": "anna@example.com", "cc": ""}], is_administrator=False)
        self.assertNotEqual(masked[0]["to"], "anna@example.com")


class OrderCopyRegressionTests(unittest.TestCase):
    def test_copy_clears_documents_and_retains_audit_reference(self):
        source = {
            "documents": [{"type": "TDS", "file_name": "tds.pdf", "version": 2}],
            "order_header": {"order_number": "ZL-10", "document_version": "v2"},
        }
        copied = create_order_copy_record("ORD-1", source, "ORD-2", "2026-08-23T12:00:00", "admin")
        self.assertEqual(copied["documents"], [])
        self.assertEqual(copied["source_order_id"], "ORD-1")
        self.assertEqual(copied["source_documents"][0]["source_file_name"], "tds.pdf")
        self.assertEqual(copied["order_header"]["order_id"], "ORD-2")

    def test_reprint_increments_version_and_context_reference(self):
        source = {"documents": [], "order_header": {"order_number": "ZL-10", "document_version": "v2"}}
        copied = create_order_copy_record("ORD-1", source, "ORD-2", "2026-08-23T12:00:00", is_reprint=True)
        contexts = {"ORD-1": {"data": {"order_id": "ORD-1"}}}
        copied_contexts = copy_order_context(contexts, "ORD-1", "ORD-2", copied, "2026-08-23T12:00:00")
        self.assertEqual(copied["order_header"]["document_version"], "v3")
        self.assertEqual(copied["order_header"]["priority"], "reprint")
        self.assertEqual(copied_contexts["ORD-2"]["data"]["order_id"], "ORD-2")


class DocumentBundleRegressionTests(unittest.TestCase):
    def test_bundle_ignores_paths_outside_order_and_makes_unique_names(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            first = os.path.join(root, "report.pdf")
            second = os.path.join(root, "another.pdf")
            foreign = os.path.join(outside, "secret.pdf")
            for path, data in ((first, b"one"), (second, b"two"), (foreign, b"secret")):
                with open(path, "wb") as stream:
                    stream.write(data)
            files = order_document_files([
                {"file_path": first, "file_name": "report.pdf"},
                {"file_path": second, "file_name": "report.pdf"},
                {"file_path": foreign, "file_name": "secret.pdf"},
            ], root)
            self.assertEqual([item["file_name"] for item in files], ["report.pdf", "report_2.pdf"])
            with zipfile.ZipFile(__import__("io").BytesIO(build_order_documents_zip(files))) as archive:
                self.assertEqual(archive.namelist(), ["report.pdf", "report_2.pdf"])


class DocumentStorageRegressionTests(unittest.TestCase):
    def test_identical_pdf_does_not_create_a_new_version_but_changed_pdf_does(self):
        with tempfile.TemporaryDirectory() as directory:
            documents = []
            documents, path, changed = store_pdf_version(
                documents, "TDS", b"first", "tds.pdf", directory, timestamp="2026-08-23T12:00:00"
            )
            self.assertTrue(changed)
            documents, same_path, changed = store_pdf_version(
                documents, "TDS", b"first", "tds.pdf", directory, timestamp="2026-08-23T12:00:01"
            )
            self.assertFalse(changed)
            self.assertEqual(path, same_path)
            self.assertEqual(documents[0]["version"], 1)
            documents[0]["status"] = "zatwierdzony"
            documents, _, changed = store_pdf_version(
                documents, "TDS", b"second", "tds.pdf", directory, timestamp="2026-08-23T12:01:00"
            )
            self.assertTrue(changed)
            self.assertEqual(documents[0]["version"], 2)
            self.assertEqual(documents[0]["status"], "wygenerowany")
            self.assertTrue(os.path.isfile(documents[0]["history"][-1]["previous_file_path"]))


class OrderRegistryRegressionTests(unittest.TestCase):
    def test_short_order_id_uses_date_and_skips_collisions(self):
        token_values = iter(["beef", "cafe"])
        order_id = generate_short_order_id("260824", {"EMBURN-260824-BEEF"}, lambda _size: next(token_values))
        self.assertEqual(order_id, "EMBURN-260824-CAFE")

    def test_new_order_and_document_update_keep_one_document_entry(self):
        record = new_order_record("2026-08-23T12:00:00", "operator")
        self.assertEqual(record["order_name"], "")
        documents = register_document_record(record["documents"], "QA", "2026-08-23T12:01:00", file_name="qa.pdf")
        documents = register_document_record(documents, "QA", "2026-08-23T12:02:00", file_name="qa.pdf", status="zatwierdzony")
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["version"], 2)
        self.assertEqual(documents[0]["status"], "zatwierdzony")

    def test_lifecycle_is_determined_without_streamlit(self):
        self.assertEqual(derive_order_lifecycle("robocze", False, ["QA"], False)[0], "robocze")
        self.assertEqual(derive_order_lifecycle("robocze", True, [], False)[0], "gotowe do wysyłki")
        self.assertEqual(derive_order_lifecycle("robocze", True, ["QA"], True)[0], "wysłane")


class OrderContextRegressionTests(unittest.TestCase):
    def test_dataframe_roundtrip_and_upload_like_object_omission(self):
        original = __import__("pandas").DataFrame([{"SKU": "A-1", "Ilość": 3}])
        encoded = serialize_context_value({"table": original, "skip": object()})
        self.assertNotIn("skip", encoded)
        decoded = deserialize_context_value(encoded)
        self.assertEqual(decoded["table"].to_dict("records"), [{"SKU": "A-1", "Ilość": 3}])

    def test_date_roundtrip_keeps_a_date_json_safe(self):
        original = __import__("datetime").date(2026, 8, 24)
        encoded = serialize_context_value({"week": original})
        self.assertEqual(encoded["week"], {"__context_type__": "date", "value": "2026-08-24"})
        self.assertEqual(deserialize_context_value(encoded)["week"], original)

    def test_dataframe_with_date_is_json_safe(self):
        original = __import__("pandas").DataFrame([{"data": __import__("datetime").date(2026, 8, 24)}])
        encoded = serialize_context_value(original)
        __import__("json").dumps(encoded)
        self.assertEqual(deserialize_context_value(encoded).iloc[0]["data"], __import__("datetime").date(2026, 8, 24))

    def test_image_bytes_roundtrip_for_ppwr_appendix(self):
        original = b"\x89PNG\r\n\x1a\nexample"
        encoded = serialize_context_value({"ppwr_appendix_image": original})
        __import__("json").dumps(encoded)
        self.assertEqual(deserialize_context_value(encoded)["ppwr_appendix_image"], original)


class SharedServicesRegressionTests(unittest.TestCase):
    def test_storage_roundtrip_preserves_json_mirror_and_sqlite_state(self):
        with tempfile.TemporaryDirectory() as directory:
            mirror = os.path.join(directory, "state.json")
            store = SharedStateStore(os.path.join(directory, "state.db"), directory)
            store.save("sample", mirror, {"order_id": "ORD-1"})
            self.assertEqual(store.load("sample", mirror, {}), {"order_id": "ORD-1"})

    def test_validation_email_catalogue_and_bct_helpers(self):
        self.assertEqual(validate_ean_gtin("5901234123457"), (True, ""))
        self.assertFalse(validate_ean_gtin("5901234123458")[0])
        self.assertFalse(validate_required_text("<script>", "Nazwa")[0])
        addresses, invalid = parse_email_addresses("one@example.com, wrong", "two@example.com")
        self.assertEqual(addresses, ["one@example.com", "wrong", "two@example.com"])
        self.assertEqual(invalid, ["wrong"])
        self.assertTrue(use_kdrive_for_attachments("Automatycznie (do 25 MB e-mail, powyżej kDrive)", 30 * 1024 * 1024))
        plan = prepare_email_delivery(
            "one@example.com", "", "", "Dokumenty", "W załączeniu raport.", [], 0,
            "Dołącz bezpośrednio do e-maila", "Wyślij",
        )
        self.assertEqual(plan["attachment_notice"], "Treść wskazuje załącznik, ale nie dodano pliku.")
        self.assertEqual(plan["status"], "wysłana")
        conflicts = ean_conflicts(
            "Nowy", {"Produkt": {"EAN": "5901234123457"}},
            {"Istniejący": {"Produkt": {"EAN": "5901234123457"}}},
        )
        self.assertEqual(conflicts, {"Istniejący": ["5901234123457"]})
        self.assertEqual(bct_document_rows({"bct": 12, "safe_bct": 9})[1], ["BCT nominalne", "12.0 kg"])
        normalized = normalize_product_record({"Dlugosc": 100, "EAN": "5901234123457"})
        self.assertEqual(normalized["Produkt"]["Dlugosc"], 100)
        self.assertEqual(normalized["MasterCase"]["Dlugosc_zewnetrzna"], 100)
        snapshot = build_catalog_snapshot("Ritual", {"Ritual": normalized})
        self.assertEqual(snapshot["Produkt"]["EAN produktu"], "5901234123457")


class OrderDocumentsRegressionTests(unittest.TestCase):
    def test_ean_and_header_are_consistent_for_every_packaging_level(self):
        snapshot = {
            "Produkt": {"EAN produktu": "5901000000001"},
            "Display": {"EAN displaya": "5901000000002"},
            "Master Case": {"EAN Master Case": "5901000000003"},
        }
        self.assertEqual(selected_ean(snapshot, "Display"), "5901000000002")
        header = default_order_header("ORD-123")
        self.assertEqual(header["document_status"], "robocze")
        self.assertEqual(order_header_pdf_fields(header)["Order ID"], "ORD-123")

    def test_base_validation_identifies_the_exact_invalid_field(self):
        errors = validate_base_data("Produkt", "Klient", 0, location="E-Order → pozycja 2")
        self.assertEqual(errors, ["E-Order → pozycja 2 → pole „Ilość netto” musi być większe od zera."])
        self.assertEqual(validate_base_data("Produkt", "", 1, require_client=False), [])
        self.assertEqual(as_positive_int("12.9"), 12)
        self.assertEqual(as_positive_int("nie liczba"), 0)

    def test_packaging_calculation_keeps_all_document_levels_consistent(self):
        result = packaging_calculation({"Relacje pakowania": {
            "Sztuk w pudełku": 2, "Pudełek w displayu": 3, "Displayów w Master Case": 4,
        }}, "Display", 5, cartons_per_pallet=2)
        self.assertEqual(result["ilosc_ekwiwalent_produktu"], 30)
        self.assertEqual(result["mastercase"], 2)
        self.assertEqual(result["palet"], 1)


class NavigationRegressionTests(unittest.TestCase):
    def test_role_filters_modules_and_keeps_correct_group_for_shortcuts(self):
        modules = {
            "Produkty": {"id": 1, "roles": ["Administrator"]},
            "PPWR": {"id": 10, "roles": ["Administrator", "Manager"]},
        }
        groups = {"Dane": [1], "Zgodność": [10]}
        available = available_modules(modules, "Manager")
        self.assertEqual(available, {"PPWR": 10})
        filtered_groups = available_navigation_groups(groups, available)
        self.assertEqual(filtered_groups, {"Zgodność": ["PPWR"]})
        self.assertEqual(group_for_module_label(filtered_groups, "brak"), "Zgodność")
        self.assertEqual(module_label_for_id(modules, 10), "PPWR")
        self.assertEqual(group_for_module_id(groups, 10), "Zgodność")

    def test_user_panel_is_visible_only_to_administrator(self):
        modules = {"Panel użytkowników": {"id": 14, "roles": ["Administrator"]}}
        self.assertEqual(available_modules(modules, "Administrator"), {"Panel użytkowników": 14})
        self.assertEqual(available_modules(modules, "Manager"), {})
        self.assertEqual(available_modules(modules, "Użytkownik"), {})

    def test_user_role_permissions_are_applied_and_saved_with_backup(self):
        users = {"admin": {"password": "secret", "role": "Administrator"}, "worker": {"password": "x", "role": "Operator"}}
        modules = {"Produkty": {"id": 1, "roles": ["Administrator"]}, "Panel": {"id": 14, "roles": ["Administrator"]}}
        permissions = build_role_permissions(users, modules, {"Operator": {"modules": [1]}})
        effective = apply_role_permissions(modules, permissions)
        self.assertEqual(effective["Produkty"]["roles"], ["Administrator", "Operator"])
        self.assertEqual(effective["Panel"]["roles"], ["Administrator"])
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "pass.toml"
            config_path.write_text("[users.admin]\npassword = 'old'\nrole = 'Administrator'\n", encoding="utf-8")
            save_user_access_config(config_path, users, permissions)
            self.assertTrue(config_path.with_suffix(".toml.bak").exists())
            import tomllib
            saved = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["users"]["worker"]["role"], "Operator")
            self.assertEqual(saved["role_permissions"]["Operator"]["modules"], [1])

    def test_admin_can_rename_user_and_change_password_without_losing_role(self):
        users = {"worker": {"password": "old", "role": "Operator"}}
        changed = update_user_credentials(users, "worker", "operator", "new-password")
        self.assertNotIn("worker", changed)
        self.assertEqual(changed["operator"], {"password": "new-password", "role": "Operator"})
        with self.assertRaises(ValueError):
            update_user_credentials(changed, "operator", "", "")


class EndToEndCoreWorkflowRegressionTests(unittest.TestCase):
    def test_order_data_flows_consistently_from_product_to_quality_documents(self):
        snapshot = {
            "Produkt": {"EAN produktu": "5901000000001"},
            "Display": {"EAN displaya": "5901000000002"},
            "Master Case": {"EAN Master Case": "5901000000003"},
            "Relacje pakowania": {
                "Sztuk w pudełku": 2, "Pudełek w displayu": 3, "Displayów w Master Case": 4,
            },
        }
        order = default_order_header("ORD-REG-1")
        calculation = packaging_calculation(snapshot, "Master Case", 2, cartons_per_pallet=2)
        self.assertEqual(selected_ean(snapshot, "Master Case"), "5901000000003")
        self.assertEqual(calculation["ilosc_ekwiwalent_produktu"], 48)
        self.assertEqual(calculation["palet"], 1)

        bct = calculate_bct(5, 4, 600, 400, 10, calculation["mastercase"])
        self.assertGreater(bct["safe_bct"], 0)
        ppwr = calculate_ppwr_masses([
            {"Komponent opakowania": "Master Case", "Materiał główny": "Paper", "Masa jednostkowa (g)": 300, "Ilość / 1 SKU": 1},
            {"Komponent opakowania": "Paleta", "Materiał główny": "Wood", "Masa jednostkowa (g)": 25000, "Ilość / 1 paletę": 1},
        ], 48, calculation["palet"])
        self.assertGreater(ppwr["total_order_kg"], 0)
        self.assertEqual(evaluate_qa_metrics(0.995, 0.1, 1)["status"], "ZATWIERDZONE")

        record = new_order_record("2026-08-24T10:00:00", "tester")
        record["order_header"] = order
        documents = register_document_record(record["documents"], "Raport PPWR", "2026-08-24T10:01:00", file_name="ppwr.pdf")
        documents = register_document_record(documents, "Raport QA drukarni", "2026-08-24T10:02:00", file_name="qa.pdf")
        self.assertEqual(len(documents), 2)
        self.assertEqual(derive_order_lifecycle("robocze", True, ["Raport QA drukarni"], True)[0], "wysłane")


class ProductionPlanningRegressionTests(unittest.TestCase):
    def test_ppwr_number_uses_space_as_thousands_separator(self):
        self.assertEqual(format_ppwr_number(49944, 2), "49 944.00")

    def test_ppwr_en_export_translates_component_values_without_changing_source(self):
        pandas = __import__("pandas")
        source = pandas.DataFrame([{
            "Komponent opakowania": "Okładka", "Poziom opakowania": "Opakowanie jednostkowe",
            "Materiał główny": "Papier", "Surowiec": "Tektura gładka / lita (PAP 21)",
            "Kolor / druk / uwagi": "brak",
        }])
        translated = ppwr_table_for_language(source, "en")
        self.assertEqual(translated.iloc[0]["Komponent opakowania"], "Cover")
        self.assertEqual(translated.iloc[0]["Poziom opakowania"], "Primary packaging")
        self.assertEqual(translated.iloc[0]["Surowiec"], "Solid board (PAP 21)")
        self.assertEqual(source.iloc[0]["Komponent opakowania"], "Okładka")

    def test_ppwr_manual_translation_overrides_custom_component_name(self):
        pandas = __import__("pandas")
        source = pandas.DataFrame([{"Komponent opakowania": "Zgrzewany pakiet displayów"}])
        key = ppwr_translation_key("Komponent opakowania", "Zgrzewany pakiet displayów")
        translated = ppwr_table_for_language(source, "en", {key: "Heat-sealed display bundle"})
        self.assertEqual(translated.iloc[0]["Komponent opakowania"], "Heat-sealed display bundle")
        self.assertEqual(ppwr_translation_rows(source, {key: "Heat-sealed display bundle"})[0]["English version"], "Heat-sealed display bundle")

    @patch("services.ppwr_documents._deepl_translate_texts")
    def test_ppwr_deepl_translates_only_values_without_manual_override(self, translate):
        pandas = __import__("pandas")
        source = pandas.DataFrame([{"Komponent opakowania": "Pakiet 3 displayów"}])
        key = ppwr_translation_key("Komponent opakowania", "Pakiet 3 displayów")
        translate.return_value = {"Pakiet 3 displayów": "Bundle of 3 displays"}
        result = ppwr_deepl_translation_overrides(source, "test-key")
        self.assertEqual(result[key], "Bundle of 3 displays")
        translate.assert_called_once()
        preserved = ppwr_deepl_translation_overrides(source, "test-key", {key: "Manual bundle"})
        self.assertEqual(preserved[key], "Manual bundle")

    def test_schedule_pdf_generator_returns_a_pdf_for_a_single_day(self):
        pdf_bytes = build_production_schedule_pdf(
            [{"date": "2026-08-24", "shift": SHIFT_OPTIONS[0], "employee": "Judyta", "task": "Kręcenie", "notes": "", "order_id": "ORD-1"}],
            title="Harmonogram", period_label="Poniedziałek · 24.08.2026",
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_two_shift_assignment_is_saved_and_filtered_by_week(self):
        plan = add_employee(empty_production_plan(), "Judyta")
        plan = add_assignment(plan, {
            "date": "2026-08-24", "shift": SHIFT_OPTIONS[0], "employee": "Judyta", "task": "Kręcenie Rolls Ritual",
            "order_id": "ORD-1",
        })
        self.assertEqual(week_dates("2026-08-26")[0].isoformat(), "2026-08-24")
        rows = assignments_for_week(plan, "2026-08-26", SHIFT_OPTIONS[0])
        self.assertEqual(rows[0]["task"], "Kręcenie Rolls Ritual")
        self.assertEqual(rows[0]["order_id"], "ORD-1")

    def test_assignment_can_be_edited_without_changing_its_identifier(self):
        plan = add_employee(empty_production_plan(), "Judyta")
        plan = add_assignment(plan, {
            "date": "2026-08-24", "shift": SHIFT_OPTIONS[0], "employee": "Judyta",
            "task": "Kręcenie", "order_id": "ORD-1",
        })
        assignment_id = plan["assignments"][0]["id"]
        edited = update_assignment(plan, assignment_id, {
            "date": "2026-08-25", "shift": SHIFT_OPTIONS[1], "employee": "Judyta",
            "task": "Pakowanie", "notes": "Priorytet", "order_id": "ORD-2",
        })
        self.assertEqual(edited["assignments"][0]["id"], assignment_id)
        self.assertEqual(edited["assignments"][0]["task"], "Pakowanie")
        self.assertEqual(edited["assignments"][0]["order_id"], "ORD-2")

    def test_schedule_pdf_generator_returns_a_pdf_for_a_week(self):
        pdf_bytes = build_production_schedule_pdf(
            [
                {"date": "2026-08-24", "shift": SHIFT_OPTIONS[0], "employee": "Judyta", "task": "Kręcenie", "notes": "", "order_id": "ORD-1"},
                {"date": "2026-08-24", "shift": SHIFT_OPTIONS[1], "employee": "Marek", "task": "Pakowanie", "notes": "Pilne", "order_id": "ORD-2"},
            ],
            title="HARMONOGRAM PRODUKCJI - TYDZIEŃ", period_label="24.08.2026–30.08.2026",
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_offline_html_export_and_import_round_trip(self):
        plan = add_employee(empty_production_plan(), "Judyta")
        plan = add_assignment(plan, {
            "date": "2026-08-24", "shift": SHIFT_OPTIONS[0], "employee": "Judyta",
            "task": "Kręcenie", "notes": "", "order_id": "ORD-1",
        })
        exported = export_plan_for_offline_html(plan)
        self.assertEqual(exported["format"], "plan-produkcji-html-v1")
        self.assertEqual(exported["assignments"][0]["shift"], "1")
        exported["assignments"][0]["task"] = "Pakowanie"
        exported["assignments"][0]["order"] = "ORD-2"
        imported, count = import_plan_from_offline_html(plan, exported)
        self.assertEqual(count, 1)
        self.assertEqual(imported["assignments"][0]["task"], "Pakowanie")
        self.assertEqual(imported["assignments"][0]["order_id"], "ORD-2")


class ProductionDocumentsRegressionTests(unittest.TestCase):
    def test_printer_copy_excludes_internal_tds_sections_and_packaging_calculation(self):
        from services.production_documents import printer_copy_data, printer_copy_data_en

        source = {
            "Nagłówek zlecenia": {"Numer": "ORD-1"},
            "TDS: identyfikacja": {"SKU": "SKU-1"},
            "TDS: Produkt": {"EAN": "5901"},
            "TDS: Display": {"EAN": "5902"},
            "TDS: Master Case": {"EAN": "5903"},
            "TDS: Paleta": {"Typ": "EURO"},
            "TDS: relacje pakowania": {"Sztuk w pudełku": 20},
            "Przeliczenie pozycji: Produkt → Display → Master Case → Paleta": {"Palety": 2},
            "Sekcja I": {"Produkt": "Rolls Ritual"},
        }

        self.assertEqual(printer_copy_data(source), {"Sekcja I": {"Produkt": "Rolls Ritual"}})
        self.assertEqual(printer_copy_data_en(source), {"Sekcja I": {"Product": "Rolls Ritual"}})
        self.assertEqual(source["Nagłówek zlecenia"]["Numer"], "ORD-1")

    @patch("services.production_documents.requests.post")
    def test_printer_copy_uses_deepl_for_custom_printing_descriptions(self, post):
        response = Mock()
        response.json.return_value = {"translations": [{"text": "Spot UV varnish on the logo"}]}
        post.return_value = response
        from services.production_documents import printer_copy_data_en

        result = printer_copy_data_en(
            {"SEKCJA IV: INNE ISTOTNE INFORMACJE": {"Uwagi do zamówienia": "Lakier wybiórczy UV na logo"}},
            "test-key:fx",
        )

        self.assertEqual(result["Section IV: Additional requirements"]["Order notes"], "Spot UV varnish on the logo")
        self.assertIn("printing terminology", post.call_args.kwargs["data"]["context"])

    @patch("services.production_documents.requests.post")
    def test_printer_copy_uses_saved_manual_translation_without_calling_deepl(self, post):
        from services.production_documents import printer_copy_data_en, printer_copy_translation_rows

        source = {"SEKCJA IV: INNE ISTOTNE INFORMACJE": {"Uwagi do zamówienia": "Lakier wybiórczy UV na logo"}}
        rows = printer_copy_translation_rows(source)
        result = printer_copy_data_en(
            source,
            "test-key:fx",
            {rows[0]["key"]: "Spot UV varnish on the logo"},
        )

        self.assertEqual(result["Section IV: Additional requirements"]["Order notes"], "Spot UV varnish on the logo")
        post.assert_not_called()

    def test_structured_document_generator_returns_a_real_pdf_and_escapes_text(self):
        pdf_bytes = build_structured_document_pdf(
            {"Dane": {"Produkt": "Rolls <Ritual>"}}, document_title="TDS <test>",
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 500)

    def test_worksheet_item_data_keeps_identifiers_and_production_values(self):
        row = worksheet_item_data({"product_name": "Ritual", "sku": "SKU-1", "ean_selected": "5901", "lot_number": "LOT-7", "production_made": 9})
        self.assertIn("SKU: SKU-1", row["product_label"])
        self.assertEqual(row["production_values"][1], 9)

    def test_worksheet_item_data_hides_fields_not_included_in_document(self):
        row = worksheet_item_data({
            "product_name": "Ritual", "order_channel": "Klient", "qty_net": 9,
            "production_made": 4,
            "included_fields": {"product_name": False, "order_channel": False, "qty_net": False, "production_made": False},
        })
        self.assertEqual(row["product_label"], "")
        self.assertEqual(row["order_values"][0], "")
        self.assertEqual(row["order_values"][6], "")
        self.assertEqual(row["production_values"][1], "")

    def test_single_language_eorder_and_worksheet_generators_return_real_pdfs(self):
        items = [{"product_name": "Rolls Ritual", "qty_net": 5, "sku": "R-1", "ean_selected": "5901234123457"}]
        meta = {"order_no": "ORD-1", "recipient": {"company": "Klient"}}
        self.assertTrue(build_eorder_pdf(items, meta).startswith(b"%PDF"))
        self.assertTrue(build_worksheet_pdf(items, meta).startswith(b"%PDF"))

    def test_worksheet_generator_accepts_header_include_flags(self):
        pdf_bytes = build_worksheet_pdf(
            [{"product_name": "Ritual"}],
            {
                "order_no": "EMBURN-1", "order_date": "24.08.2026",
                "included_fields": {"order_no": False, "order_date": False},
                "production_meta": {"machine": "Linia A", "included_fields": {"machine": False}},
            },
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


class SmtpMessageRegressionTests(unittest.TestCase):
    def test_smtp_message_contains_headers_html_logo_and_binary_attachment(self):
        attachment = __import__("io").BytesIO(b"%PDF-test")
        attachment.name, attachment.type = "raport.pdf", "application/pdf"
        message = build_smtp_message(
            "Raport", "nadawca@example.com", "odbiorca@example.com", "kopia@example.com", "Tekst",
            html_body="<p>Tekst</p>", logo_bytes=b"logo", attachments=[attachment],
        )
        self.assertEqual(message["Cc"], "kopia@example.com")
        self.assertIn("raport.pdf", [part.get_filename() for part in message.iter_attachments()])


class QaFileRegressionTests(unittest.TestCase):
    def test_raster_image_and_pdf_separation_inspection_are_independent_of_streamlit(self):
        image = __import__("PIL.Image", fromlist=["Image"]).new("RGB", (3, 2), "red")
        buffer = __import__("io").BytesIO()
        image.save(buffer, format="PNG")
        raster = render_validation_bytes(buffer.getvalue(), "projekt.png", 1, 300)
        self.assertEqual(raster.shape, (2, 3, 3))
        self.assertEqual(inspect_pdf_separations(b"/DeviceCMYK /Separation /PANTONE_123_C", "projekt.pdf")["pantone"], ["PANTONE_123_C"])


class BctDocumentsRegressionTests(unittest.TestCase):
    def test_bct_documents_are_valid_pdfs_for_all_document_languages(self):
        self.assertTrue(build_bct_report_pdf({"bct": 12, "safe_bct": 9, "language": "PL/EN"}).startswith(b"%PDF"))
        self.assertTrue(build_bct_text_document_pdf("Kontrola", ["Wiersz 1"]).startswith(b"%PDF"))


class PpwrDocumentsRegressionTests(unittest.TestCase):
    def test_ppwr_pdf_contains_component_and_material_tables(self):
        pandas = __import__("pandas")
        components = pandas.DataFrame([{
            "Komponent opakowania": "Karton", "Poziom opakowania": "Sprzedażowe", "Materiał główny": "Paper",
            "Surowiec": "Tektura", "Masa jednostkowa (g)": 100, "Ilość / 1 SKU": 1,
            "Ilość / 1 paletę": 0, "Masa / zamówienie (kg)": 2, "Kolor / druk / uwagi": "CMYK",
        }])
        materials = pandas.DataFrame([{
            "Materiał główny": "Paper", "Masa / 1 SKU (g)": 100, "Udział / 1 SKU (%)": 100,
            "Masa / 1 paletę (kg)": 1, "Masa / zamówienie (kg)": 2,
        }])
        pdf_bytes = build_ppwr_mass_specification_pdf(
            {"product_name": "Ritual", "sku": "R-1", "pallets_per_order": 2},
            components, materials, language="pl",
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_ppwr_pdf_lists_goods_excluded_from_calculations(self):
        pandas = __import__("pandas")
        source_name = "Tuleja do nawijania rolls"
        translated_name = "Roll winding core"
        pdf_bytes = build_ppwr_mass_specification_pdf(
            {
                "report_requirement_keys": ["excluded_goods"],
                "excluded_components": [{
                    "Komponent opakowania": source_name, "Poziom opakowania": "Opakowanie jednostkowe",
                    "Materiał główny": "Papier",
                }],
                "ppwr_translation_overrides": {
                    ppwr_translation_key("Komponent opakowania", source_name): translated_name,
                },
            }, pandas.DataFrame(), pandas.DataFrame(), language="en"
        )
        reader = __import__("pypdf").PdfReader(__import__("io").BytesIO(pdf_bytes))
        self.assertIn("Goods and shipments excluded", reader.pages[-1].extract_text())
        self.assertIn(translated_name, reader.pages[-1].extract_text())
        self.assertIn("Primary packaging", reader.pages[-1].extract_text())
        self.assertIn("Paper", reader.pages[-1].extract_text())

    def test_ppwr_pdf_places_component_diagram_on_final_page(self):
        image = __import__("PIL.Image", fromlist=["Image"]).new("RGB", (20, 10), "red")
        image_buffer = __import__("io").BytesIO()
        image.save(image_buffer, format="PNG")
        components = __import__("pandas").DataFrame()
        materials = __import__("pandas").DataFrame()
        pdf_bytes = build_ppwr_mass_specification_pdf(
            {"appendix_image": image_buffer.getvalue()}, components, materials, language="en"
        )
        reader = __import__("pypdf").PdfReader(__import__("io").BytesIO(pdf_bytes))
        self.assertIn("Packaging component diagram", reader.pages[-1].extract_text())

    def test_ppwr_process_diagram_supports_sixteen_numbered_stages(self):
        pandas = __import__("pandas")
        components = pandas.DataFrame([{
            "Komponent opakowania": f"Etap {index}", "Poziom opakowania": "Transportowe",
            "Materiał główny": "Paper", "Surowiec": "PAP 20", "Masa jednostkowa (g)": 1,
            "Ilość / 1 SKU": 1, "Ilość / 1 paletę": 1, "Masa / zamówienie (kg)": 1,
            "Kolor / druk / uwagi": "",
        } for index in range(1, 17)])
        pdf_bytes = build_ppwr_mass_specification_pdf(
            {"report_requirement_keys": ["diagram"]}, components, pandas.DataFrame(), language="pl"
        )
        reader = __import__("pypdf").PdfReader(__import__("io").BytesIO(pdf_bytes))
        self.assertIn("Diagram procesu pakowania", reader.pages[-1].extract_text())

    def test_ppwr_process_diagram_fits_thirty_stages_on_one_page(self):
        pandas = __import__("pandas")
        components = pandas.DataFrame([{
            "Komponent opakowania": f"Etap {index}", "Poziom opakowania": "Transportowe",
            "Materiał główny": "Paper", "Surowiec": "PAP 20", "Masa jednostkowa (g)": 1,
            "Ilość / 1 SKU": 1, "Ilość / 1 paletę": 1, "Masa / zamówienie (kg)": 1,
            "Kolor / druk / uwagi": "",
        } for index in range(1, 31)])
        pdf_bytes = build_ppwr_mass_specification_pdf(
            {"report_requirement_keys": ["diagram"]}, components, pandas.DataFrame(), language="pl"
        )
        reader = __import__("pypdf").PdfReader(__import__("io").BytesIO(pdf_bytes))
        diagram_text = reader.pages[-1].extract_text()
        self.assertIn("Etap 21", diagram_text)
        self.assertIn("Etap 30", diagram_text)
        self.assertNotIn("dalszy", diagram_text)

    def test_ppwr_process_diagram_keeps_excluded_goods_without_ppwr_number(self):
        pandas = __import__("pandas")
        all_positions = [
            {"Komponent opakowania": "Towar gotowy", "Uwzględniać jako opakowanie PPWR": False},
            {"Komponent opakowania": "Karton", "Uwzględniać jako opakowanie PPWR": True},
        ]
        included = pandas.DataFrame([all_positions[1]])
        pdf_bytes = build_ppwr_mass_specification_pdf(
            {"report_requirement_keys": ["diagram"], "diagram_positions": all_positions},
            included, pandas.DataFrame(), language="en"
        )
        reader = __import__("pypdf").PdfReader(__import__("io").BytesIO(pdf_bytes))
        diagram_text = reader.pages[-1].extract_text()
        self.assertIn("Towar gotowy", diagram_text)
        self.assertIn("Karton", diagram_text)


class OrderCenterAnalysisRegressionTests(unittest.TestCase):
    def test_quality_and_flow_checks_explain_cross_module_problems(self):
        record = {"order_header": {"order_number": "ORD-1"}, "documents": [{"type": "Raport PPWR", "file_path": "missing.pdf"}]}
        context = {
            "packing_document": {"items": [{"Poziom opakowania": "Display", "EAN displaya": "5902", "EAN/GTIN": "5901", "LOT": ""}]},
            "e_order_items": [{"catalog_snapshot": {"Display": {"EAN displaya": "5902"}}, "packaging_level": "Display", "ean_selected": "5901", "qty_shipping": 0}],
        }
        selected = lambda snapshot, _level: snapshot.get("Display", {}).get("EAN displaya", "")
        issues = order_data_quality(record, context, selected_ean=selected, positive_int=int, file_exists=lambda _path: False)
        self.assertTrue(any(row["Obszar"] == "Packing List" for row in issues))
        self.assertTrue(any(row["Obszar"] == "E-Order" for row in issues))
        flow = order_flow_map({"sections": {"paletyzacja": {}}}, record["documents"], {})
        self.assertEqual(flow[1]["Status"], "✅")

    def test_end_to_end_check_marks_foreign_reprint_file(self):
        results = end_to_end_checks(
            "ORD-2", {"order_header": {"order_number": "ORD-2"}, "source_order_id": "ORD-1", "documents": [{"file_path": "foreign.pdf"}]},
            [], ["ppwr"], {"ppwr": False}, {"ppwr": "Raport PPWR"}, own_file=lambda _path: False,
            selected_ean=lambda _snapshot, _level: "",
        )
        self.assertEqual(results[2]["Wynik"], "BŁĄD")


class PdfVisualRegressionTests(unittest.TestCase):
    def test_visual_check_explains_missing_file_and_missing_renderer(self):
        self.assertFalse(inspect_pdf_visually("missing.pdf")["ok"])
        with tempfile.TemporaryDirectory() as directory:
            pdf = os.path.join(directory, "sample.pdf")
            with open(pdf, "wb") as stream:
                stream.write(b"%PDF-test")
            result = inspect_pdf_visually(pdf, which=lambda _name: None)
            self.assertFalse(result["ok"])
            self.assertIn("pdftoppm", result["message"])


class OrderRequirementsRegressionTests(unittest.TestCase):
    def test_bct_requires_approval_and_documents_use_injected_readiness(self):
        record = {"required_documents": ["bct", "ppwr"], "documents": [{"type": "Raport PPWR", "metadata": {}}]}
        requirements, checks = requirement_status(
            record, {"bct_last_result": {"approval": "roboczy"}}, ["ppwr"],
            document_ready=lambda key, _documents: key == "ppwr",
        )
        self.assertEqual(requirements, ["bct", "ppwr"])
        self.assertFalse(checks["bct"])
        self.assertTrue(checks["ppwr"])
        _, approved = requirement_status(
            record, {"bct_last_result": {"approval": "zatwierdzony"}}, ["ppwr"],
            document_ready=lambda _key, _documents: False,
        )
        self.assertTrue(approved["bct"])


class TransportDocumentsRegressionTests(unittest.TestCase):
    def test_transport_order_generator_returns_pdf_for_incomplete_numeric_values(self):
        pdf_bytes = build_transport_order_pdf({
            "number": "TR/1", "carrier": "Raben", "dimensions_cm": [120, "x"],
            "requirements": {"tail_lift": True}, "notes": "Nie piętrować",
        })
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


class PackingDocumentsRegressionTests(unittest.TestCase):
    def test_packing_list_generator_keeps_ean_levels_and_returns_pdf(self):
        document = {"number": "PL/1", "language": "PL/EN", "items": [{
            "Produkt": "Ritual", "SKU": "RR-1", "EAN produktu": "5901", "EAN displaya": "5902",
            "EAN Master Case": "5903", "Poziom opakowania": "Master Case", "EAN/GTIN": "5903", "LOT": "L-1",
        }], "summary": {"pallets": 1}}
        self.assertTrue(build_packing_list_pdf(document).startswith(b"%PDF"))

    def test_basic_packing_list_generator_returns_pdf_for_empty_and_regular_table(self):
        pandas = __import__("pandas")
        self.assertTrue(build_basic_packing_list_pdf(pandas.DataFrame([{ "Produkt": "Ritual", "Ilość": 2 }])).startswith(b"%PDF"))
        self.assertTrue(build_basic_packing_list_pdf(pandas.DataFrame()).startswith(b"%PDF"))


class PalletDocumentsRegressionTests(unittest.TestCase):
    def test_pallet_label_generator_creates_one_or_more_label_pdf(self):
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        pdf_bytes = build_pallet_labels_pdf({"Liczba palet": 1, "Produkt": "Ritual", "Paleta": "EURO"}, "5901", "Warszawa", canvas=canvas, colors=colors, mm=mm, qr_widget=QrCodeWidget, drawing_class=Drawing, render_pdf=renderPDF)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_qr_decoder_returns_message_for_unreadable_image(self):
        class FakeNumpy:
            uint8 = object()
            @staticmethod
            def frombuffer(_data, dtype=None):
                return object()
        class FakeCv2:
            IMREAD_COLOR = 1
            @staticmethod
            def imdecode(_data, _mode):
                return None
        value, error = decode_qr_bytes(b"not an image", cv2_module=FakeCv2, numpy_module=FakeNumpy)
        self.assertIsNone(value)
        self.assertIn("Nie udało", error)


class InventoryRegressionTests(unittest.TestCase):
    PRODUCTS = {
        "Ritual Rolls": {
            "SKU": "RIT-01", "pcs_in_box": 8,
            "Produkt": {"EAN": "5901234567890"},
            "Display": {"EAN": "5901234567897"},
            "MasterCase": {"EAN": "5901234567894"},
        },
    }

    def test_csv_import_recognizes_product_and_detects_duplicate_tray(self):
        payload = (
            "data/czas;operator;EAN/GTIN;ID tacki;ilość rzeczywista\n"
            "2026-08-27 10:00;Ala;5901234567890;TRAY|000145;7\n"
            "2026-08-27 10:01;Ala;5901234567890;000145;8\n"
        ).encode("utf-8")
        records = enrich_inventory_records(parse_inventory_csv(payload), self.PRODUCTS)
        self.assertEqual(records[0]["product_name"], "Ritual Rolls")
        self.assertEqual(records[0]["difference"], -1)
        self.assertTrue(records[0]["duplicate_tray"])
        self.assertTrue(records[1]["duplicate_tray"])

    def test_summary_and_mobile_catalog(self):
        records = enrich_inventory_records([
            {"tray_id": "000001", "ean": "5901234567890", "actual_quantity": 10, "nominal_quantity": 8},
            {"tray_id": "000002", "ean": "999", "actual_quantity": 3, "nominal_quantity": 0},
        ], self.PRODUCTS)
        summary = session_summary(records)
        self.assertEqual((summary["trays"], summary["sku"], summary["pieces"], summary["difference"]), (2, 1, 13, 5))
        self.assertEqual(summary["unknown_products"], 1)
        catalog = mobile_catalog_rows(self.PRODUCTS)
        self.assertEqual(len(catalog), 3)
        self.assertEqual(catalog[0]["Nazwa produktu"], "Ritual Rolls")

    def test_editing_imported_record_recalculates_session(self):
        records = enrich_inventory_records([
            {"tray_id": "000001", "ean": "5901234567890", "actual_quantity": 8, "nominal_quantity": 8},
            {"tray_id": "000002", "ean": "5901234567890", "actual_quantity": 7, "nominal_quantity": 8},
        ], self.PRODUCTS)
        updated = update_inventory_record(records, 1, {
            "tray_id": "TRAY|000003", "actual_quantity": 9, "operator": "Ala",
        }, self.PRODUCTS)
        self.assertEqual(updated[1]["tray_id"], "000003")
        self.assertEqual(updated[1]["actual_quantity"], 9)
        self.assertEqual(updated[1]["difference"], 1)
        self.assertEqual(session_summary(updated)["difference"], 1)

    def test_inventory_report_pdf_is_generated(self):
        payload = build_inventory_report_pdf({
            "name": "Test", "created_at": "2026-08-30 12:00", "operator": "Ala",
            "records": [{"tray_id": "000001", "product_name": "Ritual Rolls", "actual_quantity": 8, "nominal_quantity": 8, "difference": 0}],
        })
        self.assertTrue(payload.startswith(b"%PDF"))

    def test_tray_labels_pdf_uses_one_4x6cm_page_per_tray(self):
        from io import BytesIO
        from pypdf import PdfReader
        payload = build_tray_labels_pdf([{"tray_id": "000001"}, {"tray_id": "000002"}])
        reader = PdfReader(BytesIO(payload))
        self.assertEqual(len(reader.pages), 2)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 40 / 25.4 * 72, places=1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.height), 60 / 25.4 * 72, places=1)

    def test_stock_comparison_reports_match_surplus_and_shortage(self):
        stock = parse_stock_csv(
            "EAN/GTIN;Nazwa produktu;Ilość rzeczywista\n5901;A;8\n5902;B;5\n5903;C;4\n".encode("utf-8")
        )
        comparison = compare_inventory_to_stock([
            {"ean": "5901", "product_name": "A", "actual_quantity": 8},
            {"ean": "5902", "product_name": "B", "actual_quantity": 7},
            {"ean": "5904", "product_name": "D", "actual_quantity": 2},
        ], stock)
        by_ean = {item["ean"]: item for item in comparison}
        self.assertEqual(by_ean["5901"]["status"], "Zgodne")
        self.assertEqual(by_ean["5902"]["status"], "Nadwyżka")
        self.assertEqual(by_ean["5903"]["status"], "Brak")
        self.assertEqual(by_ean["5904"]["status"], "Nadwyżka")
        self.assertEqual(stock_comparison_summary(comparison), {"items": 4, "matching": 1, "surpluses": 2, "shortages": 1})
        self.assertTrue(build_stock_comparison_pdf(comparison).startswith(b"%PDF"))

    def test_comparison_accepts_simple_inventory_csv_and_zebra_zpl(self):
        simple = parse_comparison_inventory_csv("EAN/GTIN;Nazwa produktu;Ilość rzeczywista\n5901;A;7\n".encode("utf-8"))
        self.assertEqual(simple[0]["ean"], "5901")
        zpl = build_tray_labels_zpl([{"tray_id": "000001", "product_name": "A"}], 203)
        self.assertIn(b"^XA", zpl)
        self.assertIn(b"TRAY-000001", zpl)

    def test_qr_payload_carries_tray_label_data_and_keeps_identifier(self):
        payload = tray_qr_payload({
            "tray_id": "TRAY|000145", "product_name": "Ritual Rolls",
            "nominal_quantity": 667, "actual_quantity": 667, "operator": "Ala",
        })
        self.assertEqual(normalize_tray_id(payload), "000145")
        data = tray_qr_data(payload)
        self.assertEqual(data["product_name"], "Ritual Rolls")
        self.assertEqual(data["actual_quantity"], 667)


class ArchitectureRegressionTests(unittest.TestCase):
    def test_extracted_layers_do_not_import_the_streamlit_entrypoint(self):
        root = Path(__file__).resolve().parents[1]
        prohibited = ("import app", "from app import")
        for directory in ("core", "services", "modules"):
            for path in (root / directory).glob("*.py"):
                source = path.read_text(encoding="utf-8")
                self.assertFalse(any(marker in source for marker in prohibited), f"{path.name} imports app.py")

    def test_architecture_document_describes_layer_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        document = (root / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn("`core/`", document)
        self.assertIn("`services/`", document)
        self.assertIn("`modules/`", document)

    def test_router_uses_extracted_active_screens(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "app.py").read_text(encoding="utf-8")
        self.assertIn("from modules.transport_screen import render_transport_screen", source)
        self.assertIn("from modules.pallet_optimization_screen import render_pallet_optimization_screen", source)
        self.assertIn("MODULE_RENDERERS = {", source)
        self.assertIn("4: _render_module_4,", source)
        self.assertIn("5: _render_module_5,", source)
        self.assertIn("selected_renderer = MODULE_RENDERERS.get(selected_module)", source)
        self.assertNotIn("if selected_module ==", source)


class EmailAttachmentRegressionTests(unittest.TestCase):
    def test_email_only_loads_existing_pdf_belonging_to_order(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            allowed = os.path.join(directory, "tds.pdf")
            forbidden = os.path.join(outside, "foreign.pdf")
            for path in (allowed, forbidden):
                with open(path, "wb") as stream:
                    stream.write(b"%PDF-test")
            attachments = load_order_pdf_attachments([
                {"file_path": allowed, "file_name": "TDS.pdf"}, {"file_path": forbidden, "file_name": "foreign.pdf"},
            ], directory)
            self.assertEqual([item.name for item in attachments], ["TDS.pdf"])

    def test_bilingual_eorder_generator_returns_a_real_pdf(self):
        pdf_bytes = build_eorder_bilingual_pdf([{"product_name": "Rolls Ritual", "qty_net": 5}], {"order_no": "ORD-1"})
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


class IntegrationWorkflowRegressionTests(unittest.TestCase):
    """Przepływy między usługami, zawsze na katalogu tymczasowym."""

    def test_order_context_pdf_versions_and_zip_roundtrip(self):
        order_id = "EMBURN-260827-TEST"
        record = new_order_record("2026-08-27T10:00:00", "tester")
        context = {
            "order_id": order_id,
            "data": serialize_context_value({"product": "Ritual", "quantity": 120, "attachment": b"sample"}),
        }

        # To odpowiada zapisowi i ponownemu odczytowi rejestru oraz kontekstu zlecenia.
        restored_context = json.loads(json.dumps(context))
        self.assertEqual(deserialize_context_value(restored_context["data"])["attachment"], b"sample")

        with tempfile.TemporaryDirectory() as directory:
            documents, _, changed = store_pdf_version(
                record["documents"], "TDS", b"%PDF-tds-v1", "tds.pdf", directory,
                operator="tester", timestamp="2026-08-27T10:01:00",
            )
            self.assertTrue(changed)
            documents, _, changed = store_pdf_version(
                documents, "TDS", b"%PDF-tds-v2", "tds.pdf", directory,
                operator="tester", timestamp="2026-08-27T10:02:00",
            )
            self.assertTrue(changed)
            self.assertEqual(documents[0]["version"], 2)
            self.assertTrue(os.path.isfile(documents[0]["history"][-1]["previous_file_path"]))

            # Drugi dokument sprawdza komplet ZIP dla jednego order_id.
            documents, _, _ = store_pdf_version(
                documents, "E-Order", b"%PDF-eorder", "e-order.pdf", directory,
                operator="tester", timestamp="2026-08-27T10:03:00",
            )
            files = order_document_files(documents, directory)
            with zipfile.ZipFile(__import__("io").BytesIO(build_order_documents_zip(files))) as archive:
                self.assertEqual(set(archive.namelist()), {"tds.pdf", "e-order.pdf"})

            # Usunięcie zamówienia jest testowane na artefaktach tymczasowych.
            registry, contexts = {order_id: record}, {order_id: context}
            for item in order_document_files(documents, directory):
                os.remove(item["path"])
            registry.pop(order_id)
            contexts.pop(order_id)
            self.assertNotIn(order_id, registry)
            self.assertNotIn(order_id, contexts)
            self.assertEqual(order_document_files(documents, directory), [])

    def test_pdf_generators_register_outputs_in_one_order_workflow(self):
        stored = []
        store_pdf = lambda document_type, pdf_bytes, file_name, *_args, **_kwargs: stored.append(
            (document_type, pdf_bytes.getvalue() if hasattr(pdf_bytes, "getvalue") else pdf_bytes, file_name)
        )
        documents = [
            ("TDS", generate_tds_pdf({"Dane": {"Produkt": "Ritual"}}, document_title="TDS", font_regular="Helvetica", font_bold="Helvetica-Bold", attachment_image_bytes=None, bct_flowables=(), canvasmaker=None, store_pdf=store_pdf, order_id="EMBURN-TEST")),
            ("E-Order", generate_eorder([{"product_name": "Ritual", "qty_net": 10}], {"order_no": "EMBURN-TEST", "recipient": {}}, font_regular="Helvetica", font_bold="Helvetica-Bold", logo_path="", canvasmaker=None, store_pdf=store_pdf, order_id="EMBURN-TEST")),
            ("Karta Pracy", generate_worksheet([{"product_name": "Ritual"}], {"order_no": "EMBURN-TEST"}, font_regular="Helvetica", font_bold="Helvetica-Bold", logo_path="", bct_flowables=(), canvasmaker=None, store_pdf=store_pdf, order_id="EMBURN-TEST")),
        ]
        self.assertTrue(all(bytes_.getvalue().startswith(b"%PDF") for _, bytes_ in documents))
        self.assertEqual([entry[0] for entry in stored], [name for name, _ in documents])

    def test_email_message_is_built_without_network_delivery(self):
        attachment = {"name": "raport.pdf", "mime": "application/pdf", "data": b"%PDF-report"}
        message = build_smtp_message(
            "Dokumenty EMBURN", "system@example.com", "client@example.com", "",
            "W załączeniu raport.", html_body="<p>Raport</p>", attachments=[attachment],
        )
        self.assertEqual(message["To"], "client@example.com")
        self.assertEqual(message["Subject"], "Dokumenty EMBURN")
        self.assertEqual(len(list(message.iter_attachments())), 1)


if __name__ == "__main__":
    unittest.main()
