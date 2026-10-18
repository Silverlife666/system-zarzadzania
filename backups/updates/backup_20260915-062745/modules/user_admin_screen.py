"""Widok wydzielony z app.py; przejściowy most zależności."""

def render_user_admin_screen(st, deps):
    for _bridge_name, _bridge_value in deps.items():
        if not _bridge_name.startswith("__"):
            globals()[_bridge_name] = _bridge_value
    del _bridge_name, _bridge_value
    st.subheader("⚙️ Panel sterowania użytkownikami")
    st.caption("Widok administracyjny: lista kont, przypisane role oraz moduły dostępne dla każdej roli.")
    if role != "Administrator":
        st.error("⛔ Ten panel jest dostępny wyłącznie dla administratora.")
        st.stop()

    user_rows = []
    for username, user_data in sorted(USERS.items(), key=lambda entry: entry[0].casefold()):
        user_role = user_data.get("role", "Brak roli")
        permitted_modules = [
            label for label, config in MODULE_OPTIONS.items()
            if user_role in config.get("roles", [])
        ]
        user_rows.append({
            "Użytkownik": username,
            "Rola": user_role,
            "Dostępne moduły": len(permitted_modules),
            "Uprawnienia": " | ".join(permitted_modules),
        })
    st.dataframe(pd.DataFrame(user_rows), hide_index=True, width="stretch")

    st.markdown("#### Przypisanie roli użytkownikowi")
    all_roles = sorted(set(ROLE_PERMISSIONS) | {data.get("role", "Brak roli") for data in USERS.values()})
    role_user_col, role_value_col, role_action_col = st.columns(3)
    with role_user_col:
        selected_username = st.selectbox("Użytkownik do moderacji", sorted(USERS, key=str.casefold), key="admin_selected_username")
    with role_value_col:
        assigned_role = st.selectbox(
            "Przypisana rola", all_roles,
            index=all_roles.index(USERS[selected_username].get("role", "Brak roli")),
            key="admin_assigned_role",
        )
    with role_action_col:
        st.write("")
        if st.button("💾 Zapisz rolę użytkownika", key="admin_save_user_role"):
            updated_users = {name: dict(data) for name, data in USERS.items()}
            updated_users[selected_username]["role"] = assigned_role
            updated_permissions = {name: set(module_ids) for name, module_ids in ROLE_PERMISSIONS.items()}
            updated_permissions.setdefault(assigned_role, set())
            save_user_access_config(PASS_FILE, updated_users, updated_permissions)
            st.success(f"Rola użytkownika „{selected_username}” została zmieniona na „{assigned_role}”.")
            st.rerun()

    st.markdown("#### Zmiana nazwy użytkownika lub hasła")
    with st.form("admin_edit_account_form"):
        account_col1, account_col2 = st.columns(2)
        with account_col1:
            updated_username = st.text_input(
                "Nazwa użytkownika", value=selected_username, key="admin_updated_username",
            )
        with account_col2:
            updated_password = st.text_input(
                "Nowe hasło (pozostaw puste, aby nie zmieniać)", type="password", key="admin_updated_password",
            )
        submitted_account_edit = st.form_submit_button("💾 Zapisz dane konta")
    if submitted_account_edit:
        try:
            updated_users = update_user_credentials(
                USERS, selected_username, updated_username, updated_password,
            )
            save_user_access_config(PASS_FILE, updated_users, ROLE_PERMISSIONS)
            if st.session_state.get("user_name") == selected_username:
                st.session_state["user_name"] = updated_username.strip()
            st.success("Dane konta zostały zapisane.")
            st.rerun()
        except (KeyError, ValueError) as error:
            st.error(str(error))

    new_role_name = st.text_input("Dodaj nową rolę", key="admin_new_role_name")
    if st.button("➕ Dodaj rolę", key="admin_add_role"):
        normalized_role = new_role_name.strip()
        if not normalized_role:
            st.warning("Podaj nazwę roli.")
        elif normalized_role in ROLE_PERMISSIONS:
            st.warning("Taka rola już istnieje.")
        else:
            updated_permissions = {name: set(module_ids) for name, module_ids in ROLE_PERMISSIONS.items()}
            updated_permissions[normalized_role] = set()
            save_user_access_config(PASS_FILE, USERS, updated_permissions)
            st.success(f"Dodano rolę „{normalized_role}”. Ustaw teraz jej dostęp do modułów.")
            st.rerun()

    st.markdown("#### Dostęp do modułów według roli")
    role_to_edit = st.selectbox("Rola do moderacji", all_roles, key="admin_role_to_edit")
    selected_module_ids = ROLE_PERMISSIONS.get(role_to_edit, set())
    edited_module_ids = set()
    permission_columns = st.columns(2)
    for index, (label, config) in enumerate(MODULE_OPTIONS.items()):
        module_id = config["id"]
        protected_admin_panel = module_id == 14
        with permission_columns[index % 2]:
            allowed = st.checkbox(
                label,
                value=module_id in selected_module_ids,
                key=f"admin_role_module_{role_to_edit}_{module_id}",
                disabled=protected_admin_panel,
                help="Panel użytkowników pozostaje dostępny wyłącznie dla Administratora." if protected_admin_panel else None,
            )
        if allowed or (protected_admin_panel and role_to_edit == "Administrator"):
            edited_module_ids.add(module_id)
    if st.button("💾 Zapisz uprawnienia roli", key="admin_save_role_permissions"):
        updated_permissions = {name: set(module_ids) for name, module_ids in ROLE_PERMISSIONS.items()}
        updated_permissions[role_to_edit] = edited_module_ids
        updated_permissions.setdefault("Administrator", set()).add(14)
        save_user_access_config(PASS_FILE, USERS, updated_permissions)
        st.success(f"Zapisano uprawnienia roli „{role_to_edit}”.")
        st.rerun()

    st.markdown("#### Aktualne uprawnienia według roli")
    permission_rows = [
        {
            "Rola": user_role,
            "Moduły": " | ".join(
                label for label, config in MODULE_OPTIONS.items()
                if user_role in config.get("roles", [])
            ),
        }
        for user_role in all_roles
    ]
    st.dataframe(pd.DataFrame(permission_rows), hide_index=True, width="stretch")
    st.info("Zmiany są zapisywane w .streamlit/pass.toml; przed każdą zmianą aplikacja tworzy kopię .streamlit/pass.toml.bak. Hasła nie są wyświetlane w panelu.")


