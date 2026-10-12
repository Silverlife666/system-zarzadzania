"""Startowy widok akceptacji artworków przez klienta."""


def render_artwork_approval_screen(st) -> None:
    st.title("✅ Akceptacja artworków przez klienta")
    st.info("Moduł został dodany jako punkt startowy. W kolejnym etapie umożliwi wysłanie podglądu klientowi, zebranie akceptacji oraz zachowanie historii decyzji.")
    st.subheader("Planowane elementy")
    st.markdown("- link do akceptacji bez dostępu do całego systemu,\n- decyzja: zaakceptowano / poprawki wymagane,\n- komentarze, data, osoba akceptująca i wersja pliku.")
