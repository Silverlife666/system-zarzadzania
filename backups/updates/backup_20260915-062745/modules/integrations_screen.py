"""Moduł 20: importy plików i konfiguracja integracji zewnętrznych."""
from io import BytesIO


TARGETS = {
    "Produkty": ["Nazwa", "SKU", "EAN", "Dlugosc", "Szerokosc", "Wysokosc", "Waga", "Klient"],
    "Klienci": ["Nazwa", "E-mail", "Telefon", "NIP", "Adres"],
    "Cenniki": ["Grupa cennika", "Klient", "Produkt / usługa", "SKU / kod", "Jednostka", "Minimalna ilość", "Cena netto", "Waluta", "Ważny do", "Uwagi"],
    "Stany magazynowe": ["Kod materiału", "Materiał", "Ilość", "Jednostka", "Lokacja", "Partia"],
}


def _read_file(pd, uploaded):
    name = uploaded.name.lower()
    content = uploaded.getvalue()
    if name.endswith(".csv"):
        for encoding in ("utf-8-sig", "windows-1250", "utf-8"):
            try:
                return pd.read_csv(BytesIO(content), sep=None, engine="python", encoding=encoding)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(BytesIO(content), sep=None, engine="python")
    return pd.read_excel(BytesIO(content))


def _guess_mapping(columns, fields):
    aliases = {
        "Nazwa": ["nazwa", "towar", "produkt", "name"], "SKU": ["sku", "kod", "indeks"], "EAN": ["ean", "kod kreskowy", "barcode"],
        "Dlugosc": ["dlugosc", "długość", "length"], "Szerokosc": ["szerokosc", "szerokość", "width"], "Wysokosc": ["wysokosc", "wysokość", "height"], "Waga": ["waga", "masa", "weight"],
        "Klient": ["klient", "kontrahent", "odbiorca", "customer"], "E-mail": ["e-mail", "email"], "Telefon": ["telefon", "phone"], "NIP": ["nip", "vat"], "Adres": ["adres", "address"],
        "Grupa cennika": ["grupa", "cennik", "price group"], "Produkt / usługa": ["produkt", "usługa", "towar", "nazwa"], "SKU / kod": ["sku", "kod", "indeks"],
        "Jednostka": ["jednostka", "jm", "unit"], "Minimalna ilość": ["minimum", "minimalna ilość", "min"], "Cena netto": ["cena netto", "cena", "net price"], "Waluta": ["waluta", "currency"], "Ważny do": ["ważny do", "data ważności", "valid to"], "Uwagi": ["uwagi", "notes"],
        "Kod materiału": ["kod materiału", "kod", "sku"], "Materiał": ["materiał", "nazwa", "towar"], "Ilość": ["ilość", "stan", "quantity"], "Lokacja": ["lokacja", "magazyn", "location"], "Partia": ["partia", "lot"],
    }
    normalized = {str(column).strip().casefold(): column for column in columns}
    return {field: next((normalized[alias] for alias in aliases.get(field, []) if alias in normalized), None) for field in fields}


def render_integrations_screen(st, deps):
    pd = deps["pd"]
    datetime = deps["datetime"]
    secrets = deps["secrets"]
    load_database = deps["load_database"]
    save_database = deps["save_database"]
    load_products = deps["load_products"]
    save_product = deps["save_product"]

    st.title("🔌 Integracje")
    st.caption("Importuj dane z Excel/CSV, zapisuj mapowania pól i zarządzaj integracjami zewnętrznymi.")
    database = load_database()
    mappings = database.setdefault("integration_field_mappings", {})
    logs = database.setdefault("integration_logs", [])
    import_tab, mapping_tab, globkurier_tab, log_tab = st.tabs(["📥 Import Excel/CSV i Subiekt", "🧩 Mapowanie pól", "🚚 Globkurier", "🕘 Dziennik"])

    with import_tab:
        target = st.selectbox("Importuj do", list(TARGETS))
        st.caption("Dla pliku z Subiekta wybierz „Produkty” - nazwa, kod, EAN i masa zostaną rozpoznane automatycznie.")
        uploaded = st.file_uploader("Wgraj plik Excel lub CSV", type=["csv", "xls", "xlsx"], key="integration_file")
        if uploaded is not None:
            try:
                frame = _read_file(pd, uploaded)
                frame.columns = [str(column).strip() for column in frame.columns]
                st.success(f"Wczytano {len(frame)} wierszy i {len(frame.columns)} kolumn.")
                st.dataframe(frame.head(25), width="stretch", hide_index=True)
                guessed = _guess_mapping(frame.columns, TARGETS[target])
                active_mapping = mappings.get(target, {})
                options = ["— nie mapuj —"] + list(frame.columns)
                mapping = {}
                with st.expander("🧩 Mapowanie pól importu", expanded=True):
                    columns = st.columns(2)
                    for index, field in enumerate(TARGETS[target]):
                        suggested = active_mapping.get(field) or guessed.get(field)
                        with columns[index % 2]:
                            choice = st.selectbox(field, options, index=options.index(suggested) if suggested in options else 0, key=f"integration_map_{target}_{field}")
                            mapping[field] = None if choice == options[0] else choice
                if st.button("💾 Zapisz mapowanie pól"):
                    mappings[target] = mapping
                    save_database(database)
                    st.success("Mapowanie zapisano.")
                if st.button("🚀 Wykonaj import", type="primary"):
                    rows = frame.where(pd.notna(frame), "").to_dict(orient="records")
                    imported = 0
                    skipped = []
                    if target == "Produkty":
                        existing = load_products()
                        for row in rows:
                            name = str(row.get(mapping.get("Nazwa"), "")).strip() if mapping.get("Nazwa") else ""
                            if not name:
                                skipped.append("brak nazwy produktu"); continue
                            base = dict(existing.get(name, {}))
                            for field in ("SKU", "EAN", "Klient"):
                                if mapping.get(field): base[field] = str(row.get(mapping[field], "")).strip()
                            for field in ("Dlugosc", "Szerokosc", "Wysokosc", "Waga"):
                                if mapping.get(field):
                                    try: base[field] = float(str(row.get(mapping[field], "")).replace(",", "."))
                                    except ValueError: pass
                            try:
                                save_product(name, base); imported += 1
                            except Exception as error:
                                skipped.append(f"{name}: {error}")
                    elif target == "Klienci":
                        clients = database.setdefault("integration_clients", [])
                        for row in rows:
                            name = str(row.get(mapping.get("Nazwa"), "")).strip() if mapping.get("Nazwa") else ""
                            if not name: skipped.append("brak nazwy klienta"); continue
                            clients = [client for client in clients if client.get("Nazwa") != name]
                            clients.append({field: str(row.get(source, "")).strip() if source else "" for field, source in mapping.items()})
                            imported += 1
                        database["integration_clients"] = clients
                        database["orders_clients"] = sorted(set(database.get("orders_clients", [])) | {row.get("Nazwa", "") for row in clients if row.get("Nazwa")})
                    elif target == "Cenniki":
                        prices = database.setdefault("client_price_lists", [])
                        for row in rows:
                            product = str(row.get(mapping.get("Produkt / usługa"), "")).strip() if mapping.get("Produkt / usługa") else ""
                            client = str(row.get(mapping.get("Klient"), "")).strip() if mapping.get("Klient") else ""
                            if not product or not client: skipped.append("brak klienta lub produktu w cenniku"); continue
                            item = {field: str(row.get(source, "")).strip() if source else "" for field, source in mapping.items()}
                            item.update({"id": secrets.token_hex(6), "Grupa cennika": item.get("Grupa cennika") or client, "Status": "Aktywny", "Zmieniono": datetime.now().isoformat(timespec="seconds")})
                            prices.append(item); imported += 1
                    else:
                        stock = database.setdefault("integration_stock_levels", [])
                        stock.extend([{field: str(row.get(source, "")).strip() if source else "" for field, source in mapping.items()} for row in rows])
                        imported = len(rows)
                    logs.append({"at": datetime.now().isoformat(timespec="seconds"), "source": uploaded.name, "target": target, "imported": imported, "skipped": len(skipped)})
                    save_database(database)
                    st.success(f"Zaimportowano: {imported}; pominięto: {len(skipped)}.")
                    if skipped: st.dataframe(pd.DataFrame({"Pominięte": skipped}), width="stretch", hide_index=True)
            except Exception as error:
                st.error(f"Nie udało się odczytać pliku: {error}")

    with mapping_tab:
        st.subheader("Zapisane mapowania pól")
        if mappings:
            rows = [{"Typ importu": target, "Pole systemu": field, "Kolumna źródłowa": source or "—"} for target, mapping in mappings.items() for field, source in mapping.items()]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.info("Nie zapisano jeszcze mapowań.")

    with globkurier_tab:
        st.subheader("Integracja Globkurier")
        st.info("Globkurier udostępnia REST API do wyszukiwania usług, tworzenia przesyłek, etykiet i śledzenia. Konfigurację poświadczeń należy przechowywać w secrets.toml, nie w bazie aplikacji.")
        environment = st.selectbox("Środowisko", ["Testowe", "Produkcyjne"])
        base_url = "https://test.api.globkurier.pl/v1" if environment == "Testowe" else "https://api.globkurier.pl/v1"
        st.code(base_url, language=None)
        has_credentials = bool(st.secrets.get("GLOBKURIER_EMAIL", "") and st.secrets.get("GLOBKURIER_PASSWORD", ""))
        st.success("Poświadczenia Globkurier są dostępne w secrets.toml.") if has_credentials else st.warning("Brak GLOBKURIER_EMAIL i GLOBKURIER_PASSWORD w secrets.toml. Po ich dodaniu można wdrożyć autoryzację i tworzenie przesyłek.")
        st.markdown("Plan połączenia: pobranie ofert przewoźników → utworzenie przesyłki z danych modułu Transport → pobranie etykiety PDF → śledzenie statusu.")
        st.markdown("Dokumentacja: https://developer.globkurier.pl/")

    with log_tab:
        _logs = list(reversed(logs))
        if _logs: st.dataframe(pd.DataFrame(_logs), width="stretch", hide_index=True)
        else: st.info("Brak wykonanych importów.")
