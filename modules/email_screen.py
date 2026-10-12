"""Widok Centrum komunikacji (moduł 3)."""

from __future__ import annotations

import base64
from io import BytesIO
import os
import re
import smtplib
from datetime import datetime

from services.email_attachments import load_order_pdf_attachments
from services.email_presentation import EMAIL_TEMPLATES, default_email_branding, email_template_content, mask_history_addresses
from services.email_service import prepare_email_delivery
from services.smtp_message import build_smtp_message


def render_email_screen(st, deps):
    """Renderuje moduł e-mail; zależności trwałego zapisu przekazuje router."""
    load_database, save_database = deps["load_database"], deps["save_database"]
    current_operator, get_current_order_id = deps["current_operator"], deps["get_current_order_id"]
    document_files_dir, document_file_is_ready = deps["document_files_dir"], deps["document_file_is_ready"]
    upload_kdrive, register_order_email = deps["upload_kdrive"], deps["register_order_email"]
    render_email_html, secrets = deps["render_email_html"], deps["secrets"]

    st.subheader("📧 Centrum komunikacji")
    st.caption("Hasło SMTP i token kDrive są odczytywane wyłącznie z secrets.toml.")
    mail_db = load_database()
    mail_db.setdefault("email_contacts", [])
    mail_db.setdefault("email_history", [])
    mail_db.setdefault("email_branding", default_email_branding())
    branding = mail_db["email_branding"]

    with st.expander("🎨 Konfiguracja logo, stopki i podpisów", expanded=False):
        if st.session_state.get("user_role") != "Administrator":
            st.info("Konfiguracja firmowa jest dostępna wyłącznie dla administratora.")
        else:
            with st.form("email_branding_form"):
                brand_col1, brand_col2 = st.columns(2)
                with brand_col1:
                    brand_company = st.text_input("Nazwa firmy", value=branding.get("company_name", ""))
                    brand_address = st.text_area("Adres firmy", value=branding.get("address", ""), height=80)
                    brand_phone = st.text_input("Telefon", value=branding.get("phone", ""))
                with brand_col2:
                    brand_website = st.text_input("Strona WWW", value=branding.get("website", ""))
                    brand_logo = st.file_uploader("Logo do e-maili (PNG/JPG)", type=["png", "jpg", "jpeg"], key="email_brand_logo")
                    signature_user = st.text_input("Użytkownik dla podpisu", value=current_operator())
                    signature_text = st.text_area("Podpis użytkownika", value=branding.get("signatures", {}).get(current_operator(), ""), height=80)
                legal_footer = st.text_area("Stopka prawna / RODO", value=branding.get("legal_footer", ""), height=110)
                if st.form_submit_button("💾 Zapisz konfigurację e-mail"):
                    if brand_logo is not None:
                        branding["logo_b64"] = base64.b64encode(brand_logo.getvalue()).decode("ascii")
                        branding["logo_mime"] = brand_logo.type or "image/png"
                    branding.update({"company_name": brand_company.strip(), "address": brand_address.strip(), "phone": brand_phone.strip(), "website": brand_website.strip(), "legal_footer": legal_footer.strip()})
                    branding.setdefault("signatures", {})[signature_user.strip() or current_operator()] = signature_text.strip()
                    mail_db["email_branding"] = branding
                    save_database(mail_db)
                    st.success("Zapisano konfigurację firmową.")
                    st.rerun()

    logo_b64 = branding.get("logo_b64", "")
    logo_mime = branding.get("logo_mime", "image/png")
    user_signature = branding.get("signatures", {}).get(current_operator(), "")
    lang = st.radio("Język", ["Polski", "English"], horizontal=True)
    template_name = st.selectbox("Szablon", list(EMAIL_TEMPLATES))
    product_context = st.session_state.get("pal_calc_result", {}).get("Produkt", st.session_state.get("val_product_name", "produkt"))
    default_subject, default_body = email_template_content(template_name, product_context, lang)

    with st.expander("📇 Książka adresowa i grupy", expanded=False):
        contact_group = st.selectbox("Grupa", ["Klient", "Drukarnia", "Logistyka", "Księgowość", "Pracownik"])
        with st.form("add_email_contact"):
            contact_name, contact_email = st.text_input("Nazwa kontaktu"), st.text_input("Adres e-mail")
            if st.form_submit_button("➕ Zapisz kontakt"):
                if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", contact_email.strip()):
                    mail_db["email_contacts"].append({"name": contact_name.strip(), "email": contact_email.strip().lower(), "group": contact_group})
                    save_database(mail_db)
                    st.rerun()
                else:
                    st.error("Podaj prawidłowy adres e-mail.")
        if mail_db["email_contacts"]:
            st.dataframe(deps["pd"].DataFrame(mail_db["email_contacts"]), hide_index=True)

    known_emails = {item["email"].lower() for item in mail_db["email_contacts"]}
    group_choice = st.selectbox("Dodaj grupę odbiorców", ["—"] + sorted({item["group"] for item in mail_db["email_contacts"]}))
    group_addresses = ", ".join(item["email"] for item in mail_db["email_contacts"] if item["group"] == group_choice)
    with st.form("email_center_form"):
        to_value = st.text_input("Do (adresy oddziel przecinkami)", value=group_addresses)
        cc_value, bcc_value = st.text_input("DW"), st.text_input("UDW")
        subject = st.text_input("Temat", value=default_subject)
        body = st.text_area("Treść wiadomości", value=default_body, height=220)
        html_mode = st.checkbox("Wyślij jako HTML z logo i stopką", value=True)
        attachments = st.file_uploader("Załączniki — przeciągnij pliki tutaj", type=["pdf", "xlsx", "xls", "csv", "png", "jpg", "jpeg", "gif", "docx", "zip"], accept_multiple_files=True)
        order_attachments = _order_attachments(st.session_state.get("email_order_bundle", {}), document_files_dir)
        auto_attachments, auto_attachment = _auto_attachments(st.session_state.get("email_auto_attachment", {}), get_current_order_id(), document_files_dir, document_file_is_ready)
        all_attachments = list(attachments or []) + order_attachments + auto_attachments
        if order_attachments:
            st.info(f"Dodano z Centrum zlecenia: {len(order_attachments)} dokumentów PDF.")
        if auto_attachments:
            st.info(f"Dodano automatycznie z {auto_attachment.get('source', 'modułu')}: {auto_attachments[0].name}.")
        if all_attachments:
            rows = [{"Nazwa": item.name, "Rozmiar": f"{len(item.getvalue()) / 1024 / 1024:.2f} MB"} for item in all_attachments]
            st.dataframe(deps["pd"].DataFrame(rows), hide_index=True)
        attachment_delivery = st.radio("Sposób przekazania załączników", ["Automatycznie (do 25 MB e-mail, powyżej kDrive)", "Dołącz bezpośrednio do e-maila", "Prześlij do kDrive i wstaw link"], horizontal=True)
        mode = st.radio("Tryb", ["Podgląd", "Zapisz roboczą", "Wyślij"], horizontal=True)
        submitted = st.form_submit_button("Wykonaj")

    if submitted:
        _handle_submission(
            st, deps, mail_db, branding, logo_b64, logo_mime, user_signature,
            to_value, cc_value, bcc_value, subject, body, lang, html_mode,
            all_attachments, known_emails, attachment_delivery, mode,
            current_operator, save_database, upload_kdrive, register_order_email,
            render_email_html, secrets,
        )
    with st.expander("🕓 Historia wiadomości", expanded=False):
        if mail_db["email_history"]:
            history = deps["pd"].DataFrame(mask_history_addresses(mail_db["email_history"], is_administrator=st.session_state.get("user_role") == "Administrator"))
            st.dataframe(history.drop(columns=["body"], errors="ignore"), hide_index=True)


def _order_attachments(order_bundle, document_files_dir):
    order_id = str(order_bundle.get("order_id", "")).strip()
    directory = os.path.join(document_files_dir, order_id) if order_id else ""
    return load_order_pdf_attachments(order_bundle.get("documents", []), directory)


def _auto_attachments(auto_attachment, active_order_id, document_files_dir, document_file_is_ready):
    attachments = []
    if not isinstance(auto_attachment, dict) or auto_attachment.get("order_id", active_order_id) != active_order_id:
        return attachments, auto_attachment
    path = auto_attachment.get("file_path", "")
    if document_file_is_ready(path, os.path.join(document_files_dir, active_order_id)):
        with open(path, "rb") as stream:
            payload = BytesIO(stream.read())
        payload.name = auto_attachment.get("name") or os.path.basename(path)
        payload.type = "application/pdf"
        attachments.append(payload)
    else:
        data = auto_attachment.get("data")
        data = data.getvalue() if isinstance(data, BytesIO) else data
        if isinstance(data, (bytes, bytearray)):
            payload = BytesIO(bytes(data))
            payload.name, payload.type = auto_attachment.get("name") or "packing_list.pdf", "application/pdf"
            attachments.append(payload)
    return attachments, auto_attachment


def _handle_submission(st, deps, mail_db, branding, logo_b64, logo_mime, user_signature, to_value, cc_value, bcc_value, subject, body, lang, html_mode, attachments, known_emails, delivery_mode, mode, current_operator, save_database, upload_kdrive, register_order_email, render_email_html, secrets):
    total_size = sum(len(item.getvalue()) for item in attachments)
    attachment_names = [item.name for item in attachments]
    delivery = prepare_email_delivery(to_value, cc_value, bcc_value, subject, body, attachment_names, total_size, delivery_mode, mode)
    if delivery["errors"]:
        st.error("\n".join(delivery["errors"]))
        return
    if delivery["attachment_notice"]:
        st.warning(delivery["attachment_notice"])
        return
    external = sorted(set(delivery["addresses"]) - known_emails)
    if external:
        st.warning("Adresy spoza książki kontaktów: " + ", ".join(external))
    company_html = " · ".join(item for item in [branding.get("company_name", ""), branding.get("address", ""), branding.get("phone", ""), branding.get("website", "")] if item)
    logo_html = "<img src='cid:logo' alt='Logo firmy' style='max-width:180px;max-height:70px;margin-bottom:16px;'>" if logo_b64 else ""
    rendered_html = render_email_html(body, user_signature, company_html, branding.get("legal_footer", ""), logo_html)
    record = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "user": current_operator(), "to": to_value, "cc": cc_value, "bcc": bcc_value, "subject": subject, "body": body, "attachments": attachment_names, "size": total_size, "status": delivery["status"], "language": lang}
    if mode == "Podgląd":
        st.markdown("#### Podgląd desktop / mobile")
        st.markdown(rendered_html, unsafe_allow_html=True)
        st.caption("Na telefonie wiadomość jest wyświetlana jednokolumnowo; przetestuj rzeczywistego klienta pocztowego przed wysyłką.")
        return
    if mode == "Zapisz roboczą":
        mail_db["email_history"].append(record)
        save_database(mail_db)
        st.success("Zapisano wiadomość roboczą.")
        return
    sender, password = secrets.get("SENDER_EMAIL", ""), secrets.get("SENDER_PASSWORD", "")
    if not sender or not password:
        record.update({"status": "błąd", "note": "Brak konfiguracji SMTP w secrets.toml."})
        mail_db["email_history"].append(record)
        save_database(mail_db)
        st.error(record["note"])
        return
    try:
        if delivery["use_kdrive"]:
            kdrive_file = upload_kdrive(attachments)
            record["kdrive"] = kdrive_file
            plain_body = body + f"\n\nPobierz załączniki: {kdrive_file['url']}"
            html_body = rendered_html.replace("</body>", f"<p><a href='{kdrive_file['url']}'>Pobierz załączniki</a></p></body>") if html_mode else ""
        else:
            if delivery["direct_large_warning"]:
                st.warning("Wybrano bezpośredni e-mail mimo rozmiaru powyżej 25 MB. Serwer odbiorcy może odrzucić wiadomość.")
                record["note"] = "Wysłano bezpośrednio mimo rozmiaru przekraczającego 25 MB."
            plain_body, html_body = body, rendered_html if html_mode else ""
        message = build_smtp_message(subject, sender, to_value, cc_value, plain_body, html_body=html_body, logo_bytes=base64.b64decode(logo_b64) if html_mode and logo_b64 else None, logo_mime=logo_mime, attachments=() if delivery["use_kdrive"] else attachments)
        with smtplib.SMTP_SSL(secrets.get("SMTP_SERVER", "smtp.gmail.com"), int(secrets.get("SMTP_PORT", 465))) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message, to_addrs=delivery["addresses"])
        if delivery["use_kdrive"]:
            record["body"] = plain_body
        mail_db["email_history"].append(record)
        save_database(mail_db)
        register_order_email("wysłana", to_value, subject, attachment_names)
        st.success("Plik przesłano do kDrive, a e-mail zawiera link do pobrania." if delivery["use_kdrive"] else "Wiadomość została wysłana.")
    except Exception as error:
        record.update({"status": "błąd", "note": str(error)})
        mail_db["email_history"].append(record)
        save_database(mail_db)
        register_order_email("błąd", to_value, subject, attachment_names)
        st.error(f"Błąd wysyłki: {error}")
