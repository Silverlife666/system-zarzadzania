"""Widok modułu 26: kontrola PDF przed przekazaniem do druku."""
from __future__ import annotations

from services.preflight_dtp import PROFILES, analyze_pdf, build_preflight_html, build_preflight_pdf


def render_preflight_dtp_screen(st, deps):
    order_id = deps["get_current_order_id"]()
    st.title("🖨️ Preflight DTP")
    st.caption(f"Automatyczna kontrola techniczna PDF przed drukiem · aktywne zlecenie: {order_id}")
    st.info("MVP obsługuje PDF. AI, EPS i SVG wymagają osobnego parsera i będą dodane później.")
    profile_key = st.selectbox("Profil kontroli", list(PROFILES), format_func=lambda key: PROFILES[key]["label"])
    upload = st.file_uploader("Wgraj plik PDF do kontroli", type=["pdf"], key="preflight_dtp_upload")
    if upload is not None and upload.size > 100 * 1024 * 1024:
        st.error("Plik jest większy niż 100 MB."); return
    if upload is not None and st.button("🔍 Analizuj plik", type="primary", width="stretch"):
        report = analyze_pdf(upload.getvalue(), upload.name, profile_key)
        st.session_state["preflight_dtp_report"] = report
        deps["update_order_snapshot"]("preflight_dtp", report, order_id=order_id)
        st.success("Wynik kontroli zapisano przy aktywnym zleceniu.")
    report = st.session_state.get("preflight_dtp_report")
    if not report:
        st.info("Wgraj PDF i uruchom analizę."); return
    if report.get("overall_status") == "blokada": st.error("⨯ WYMAGA POPRAWY — wykryto blokady.")
    elif report.get("overall_status") == "ostrzezenia": st.warning("⚠ OSTRZEŻENIA — plik wymaga świadomej weryfikacji.")
    else: st.success("✓ GOTOWY — nie wykryto blokad ani ostrzeżeń.")
    summary = report.get("summary", {}); one, two, three = st.columns(3); one.metric("Blokady", summary.get("blockers", 0)); two.metric("Ostrzeżenia", summary.get("warnings", 0)); three.metric("Informacje", summary.get("info", 0))
    st.subheader("Wyniki kontroli")
    st.dataframe([{"Ważność": f["severity"], "Strona": f.get("page") or "—", "Kontrola": f["code"], "Wynik": f["message"]} for f in report.get("findings", [])], width="stretch", hide_index=True)
    metrics = report.get("metrics", {})
    with st.expander("Format i spad"):
        st.write(metrics.get("boxes", []))
    with st.expander("Kolory i obrazy"):
        st.write({"RGB": metrics.get("has_rgb"), "Pantone / spot": metrics.get("spots", []), "obrazy": metrics.get("images", [])})
    with st.expander("Fonty, tekst i wektory"):
        st.write({"fonty osadzone": f"{metrics.get('embedded_fonts', 0)} / {metrics.get('fonts', 0)}", "tekst edytowalny": metrics.get("has_text"), "wektory": metrics.get("has_vectors")})
    left, middle, right = st.columns(3); safe_name = report.get("file_name", "raport").rsplit(".", 1)[0]
    with left: st.download_button("⬇️ Pobierz raport HTML", build_preflight_html(report), f"preflight_{safe_name}.html", "text/html", width="stretch")
    pdf = build_preflight_pdf(report)
    with middle: st.download_button("📄 Pobierz raport PDF", pdf, f"preflight_{safe_name}.pdf", "application/pdf", width="stretch")
    with right:
        if st.button("💾 Zapisz raport PDF w Centrum", width="stretch"):
            deps["store_order_pdf"]("Raport Preflight DTP", pdf, "raport_preflight_dtp.pdf", {"source": "Preflight DTP", "status": report.get("overall_status"), "file": report.get("file_name")}, order_id=order_id)
            st.success("Raport zapisano w dokumentach aktywnego zlecenia.")
    st.caption("Automatyczna kontrola techniczna nie zastępuje preflightu RIP ani akceptacji drukarni.")
