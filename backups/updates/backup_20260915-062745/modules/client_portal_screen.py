"""Moduł 18: administracja dostępem klienta do statusów jego zleceń."""


def _order_customer(record):
    header = record.get("order_header", {}) or {}
    if header.get("client"):
        return str(header["client"]).strip()
    for document in record.get("documents", []) or []:
        recipient = (document.get("metadata", {}) or {}).get("recipient", "")
        if recipient:
            return str(recipient).strip()
    return ""


def render_client_portal_screen(st, deps):
    pd = deps["pd"]
    datetime = deps["datetime"]
    secrets = deps["secrets"]
    load_database = deps["load_database"]
    save_database = deps["save_database"]
    load_document_registry = deps["load_document_registry"]

    st.title("🌐 Portal klienta")
    st.caption("Zarządzaj dostępem klienta i sprawdzaj dokładnie to, co zobaczy w portalu: jego statusy oraz dokumenty, bez danych wewnętrznych.")
    database = load_database()
    profiles = database.setdefault("client_portal_profiles", [])
    if not isinstance(profiles, list):
        profiles = []
        database["client_portal_profiles"] = profiles

    with st.expander("➕ Dodaj dostęp klienta", expanded=True):
        with st.form("add_client_portal_profile", clear_on_submit=True):
            client_name = st.text_input("Nazwa klienta / marki", placeholder="np. Ritual")
            contact_email = st.text_input("E-mail kontaktowy")
            submitted = st.form_submit_button("🔐 Utwórz dostęp", type="primary")
        if submitted:
            if not client_name.strip():
                st.error("Podaj nazwę klienta.")
            elif any(str(profile.get("client", "")).casefold() == client_name.strip().casefold() for profile in profiles):
                st.error("Dostęp dla tego klienta już istnieje.")
            else:
                profiles.append({
                    "client": client_name.strip(), "email": contact_email.strip(), "active": True,
                    "access_code": secrets.token_urlsafe(12), "created_at": datetime.now().isoformat(timespec="seconds"),
                })
                save_database(database)
                st.success("Utworzono dostęp klienta.")
                st.rerun()

    st.markdown("### Dostępy klientów")
    if profiles:
        profile_rows = [{
            "Klient": item.get("client", ""), "E-mail": item.get("email", ""),
            "Status": "aktywny" if item.get("active", True) else "wyłączony",
            "Kod dostępu": item.get("access_code", ""), "Utworzono": item.get("created_at", ""),
        } for item in profiles]
        st.dataframe(pd.DataFrame(profile_rows), width="stretch", hide_index=True)
        profile_names = [item.get("client", "") for item in profiles]
        selected_profile_name = st.selectbox("Zarządzaj dostępem klienta", profile_names)
        selected_profile = next(item for item in profiles if item.get("client") == selected_profile_name)
        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            label = "⛔ Wyłącz dostęp" if selected_profile.get("active", True) else "✅ Włącz dostęp"
            if st.button(label):
                selected_profile["active"] = not selected_profile.get("active", True)
                save_database(database)
                st.rerun()
        with action_col2:
            if st.button("🔄 Wygeneruj nowy kod"):
                selected_profile["access_code"] = secrets.token_urlsafe(12)
                selected_profile["rotated_at"] = datetime.now().isoformat(timespec="seconds")
                save_database(database)
                st.success("Wygenerowano nowy kod dostępu.")
                st.rerun()
        with action_col3:
            delete_confirm = st.checkbox("Potwierdzam usunięcie dostępu")
            if st.button("🗑️ Usuń dostęp", disabled=not delete_confirm):
                database["client_portal_profiles"] = [item for item in profiles if item is not selected_profile]
                save_database(database)
                st.rerun()
    else:
        st.info("Nie utworzono jeszcze dostępu dla żadnego klienta.")

    st.markdown("### 👁️ Podgląd klienta — tylko do odczytu")
    registry = load_document_registry()
    known_customers = sorted({customer for record in registry.values() for customer in [_order_customer(record)] if customer}, key=str.lower)
    preview_customer = st.selectbox("Klient do podglądu", known_customers or ["Brak klientów w zleceniach"])
    preview_rows = []
    if known_customers:
        for order_id, record in registry.items():
            if _order_customer(record).casefold() != preview_customer.casefold():
                continue
            documents = record.get("documents", []) or []
            preview_rows.append({
                "Nr zlecenia": order_id, "Nazwa": record.get("order_name", "") or "—",
                "Status": record.get("order_status", "robocze"),
                "Aktualizacja": record.get("updated_at", record.get("created_at", "")),
                "Dokumenty": ", ".join(str(item.get("type", "")) for item in documents if item.get("type")) or "brak",
            })
    if preview_rows:
        st.dataframe(pd.DataFrame(preview_rows), width="stretch", hide_index=True)
        st.caption("Ten widok nie pokazuje kalkulacji wewnętrznych, danych magazynowych, operatorów ani kosztów.")
    elif known_customers:
        st.info("Ten klient nie ma jeszcze zleceń widocznych w portalu.")

    st.warning("Portal zewnętrzny nie jest jeszcze opublikowany w Internecie. Ten moduł przygotowuje konta i bezpieczny widok danych; publikację oraz osobny ekran logowania można dodać po wyborze hostingu.")
