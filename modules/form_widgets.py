"""Wspólne elementy formularzy Streamlit używane przez moduły dokumentów."""

from __future__ import annotations

import streamlit as st


def render_includable_field(label, widget_type, options=None, default_value="", key_prefix=""):
    """Pole formularza aktywowane własnym przełącznikiem „Uwzględnij”."""
    col_chk, col_widget = st.columns([1, 4])
    with col_chk:
        include = st.checkbox("Uwzględnij", value=True, key=f"chk_{key_prefix}")
    with col_widget:
        if widget_type == "text":
            value = st.text_input(label, value=default_value, disabled=not include, key=f"val_{key_prefix}")
        elif widget_type == "number":
            value = st.number_input(label, value=default_value, disabled=not include, key=f"val_{key_prefix}")
        elif widget_type == "select":
            value = st.selectbox(label, options=options or [], disabled=not include, key=f"val_{key_prefix}")
        elif widget_type == "area":
            value = st.text_area(label, value=default_value, disabled=not include, key=f"val_{key_prefix}")
        else:
            raise ValueError(f"Nieobsługiwany typ pola: {widget_type}")
    return include, value


def render_section_master_checkbox(label, keys_list, master_key):
    """Checkbox sterujący wszystkimi polami wskazanej podsekcji."""
    if master_key not in st.session_state:
        st.session_state[master_key] = True
    previous_key = f"prev_{master_key}"
    if previous_key not in st.session_state:
        st.session_state[previous_key] = True
    master_value = st.checkbox(label, key=master_key)
    if master_value != st.session_state[previous_key]:
        st.session_state[previous_key] = master_value
        for field_key in keys_list:
            st.session_state[f"chk_{field_key}"] = master_value
    return master_value


def render_existing_includable_field(label, widget_type, *, value, key, options=None):
    """Dodaje „Uwzględnij” do istniejącego pola, zachowując jego klucz sesji."""
    check_col, field_col = st.columns([1, 4])
    with check_col:
        include = st.checkbox("Uwzględnij", value=True, key=f"include_{key}")
    with field_col:
        if widget_type == "text":
            result = st.text_input(label, value=str(value or ""), key=key, disabled=not include)
        elif widget_type == "number":
            result = st.number_input(label, value=value or 0, key=key, disabled=not include)
        elif widget_type == "select":
            options = options or []
            index = options.index(value) if value in options else 0
            result = st.selectbox(label, options, index=index, key=key, disabled=not include)
        else:
            raise ValueError(f"Nieobsługiwany typ pola: {widget_type}")
    return include, result
