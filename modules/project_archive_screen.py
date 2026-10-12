"""Startowy widok archiwum projektów graficznych."""


def render_project_archive_screen(st) -> None:
    st.title("🗂️ Archiwum projektów graficznych")
    st.info("Moduł został dodany jako punkt startowy. W kolejnym etapie będzie zawierał pliki projektowe, wersje, podglądy oraz powiązania ze zleceniami i klientami.")
    st.subheader("Planowane elementy")
    st.markdown("- archiwum AI, PDF, PSD, CDR i plików pomocniczych,\n- wersjonowanie oraz osoba wprowadzająca zmianę,\n- wyszukiwanie po kliencie, produkcie i numerze zlecenia.")
