"""Moduł 31: niezależne rozliczenie produkcji bobin."""
from datetime import date, datetime
from datetime import timedelta
from collections import Counter
from io import BytesIO
import copy
import json
import math


def _planning_values(entries, settings, order_name):
    """Ostatni profil użyty w zleceniu albo domyślny profil planowania."""
    matching = [row for row in entries if row.get("order") == order_name]
    source = matching[-1] if matching else settings
    return (float(source.get("bobbin_m", source.get("planning_capacity", 3000)) or 3000),
            float(source.get("roll_length_m", source.get("planning_roll_length", 6)) or 6))


def _report_pdf(order_name, target, rows, font_regular="Helvetica", font_bold="Helvetica-Bold"):
    """Buduje raport PDF bez zapisywania go na dysku serwera."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    produced = sum(float(row.get("produced", 0) or 0) for row in rows)
    waste = sum(float(row.get("waste", 0) or 0) for row in rows)
    remaining = max(float(target or 0) - produced, 0)
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm)
    style = getSampleStyleSheet()
    title = ParagraphStyle("m31title", parent=style["Title"], fontName=font_bold, fontSize=16, textColor=colors.HexColor("#245783"))
    body = ParagraphStyle("m31body", parent=style["Normal"], fontName=font_regular, fontSize=8)
    summary = [["Docelowo", "Wykonano", "Pozostało", "Postęp", "Odpad [szt.]"], [str(int(target or 0)), str(int(produced)), str(int(remaining)), f"{(produced / target * 100) if target else 0:.1f}%", str(int(waste))]]
    details = [["Data", "Bobina", "Pracownik", "Maszyna", "Zmiana", "Pojemność [m]", "Dł. rolki [m]", "Wykonano", "Odpad", "Status"]]
    details += [[str(r.get(k, "")) for k in ("date", "bobbin_index", "employee", "machine", "shift", "bobbin_m", "roll_length_m", "produced", "waste", "completed")] for r in rows]
    story = [Paragraph("RAPORT ROZLICZENIA BOBIN", title), Paragraph(f"Zlecenie: <b>{order_name}</b>", body), Paragraph(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body), Spacer(1, 5*mm)]
    for values in (summary, details):
        table = Table(values, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245783")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), font_bold), ("FONTNAME", (0, 1), (-1, -1), font_regular), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C9D9")), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story.extend([table, Spacer(1, 5*mm)])
    document.build(story)
    return buffer.getvalue()

ROLES = {"admin": "Administrator", "owner": "Właściciel", "operator": "Operator"}
PERMS = {
    "admin": {"entry.add", "entry.edit", "entry.delete", "order.manage", "summary", "export", "config", "data", "log", "remnants", "override", "calc"},
    "owner": {"entry.add", "entry.edit", "entry.delete", "order.manage", "summary", "export", "remnants", "override", "calc"},
    "operator": {"entry.add"},
}
OWNER_PREFIXES = ("darek", "dariusz", "katarzyna")  # konta Właściciela (reszta kont = Operator, "admin" = Administrator)
DN = ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."]


def _identify(deps):
    """Rola wynika z konta zalogowanego w systemie. Nieznane konto = Operator (najmniejsze uprawnienia)."""
    try:
        who = deps["current_operator"]()
    except Exception:
        who = ""
    if isinstance(who, dict):
        who = who.get("name") or who.get("login") or who.get("username") or who.get("operator") or ""
    text = str(who or "").strip()
    low = text.lower()
    if low.startswith("admin"):
        return text, "admin"
    if low.startswith(OWNER_PREFIXES):
        return text, "owner"
    return text or "—", "operator"


def _append_log(data, who, role, act, details=""):
    log = data.setdefault("log", [])
    log.append({"ts": datetime.now().isoformat(timespec="seconds"), "user": who, "role": ROLES.get(role, role), "act": act, "d": details})
    del log[:-3000]


def _desc(e):
    return f"{e.get('date', '')} · {e.get('order', '')} · bob. {e.get('bobbin_index', '—')} · {e.get('machine', '')} zm.{e.get('shift', '')} · {e.get('employee', '')} · wyk. {e.get('produced', 0)}, odpad {e.get('waste', 0)}"


def _diff_log(before, data, who, role):
    """Automatyczny log: porównuje stan sprzed i po zapisie (zlecenia, wpisy, konfiguracja)."""
    L = lambda act, d="": _append_log(data, who, role, act, d)
    key = lambda e: json.dumps(e, sort_keys=True, ensure_ascii=False, default=str)
    bo = {o.get("name"): o for o in before.get("orders", [])}
    ao = {o.get("name"): o for o in data.get("orders", [])}
    for n in ao.keys() - bo.keys():
        L("Zlecenie: dodano", f"{n} ({ao[n].get('target')} szt.)")
    for n in bo.keys() - ao.keys():
        L("Zlecenie: usunięto / zmiana nazwy", n)
    for n in ao.keys() & bo.keys():
        if ao[n] != bo[n]:
            L("Zlecenie: zmiana", f"{n}: docelowo {bo[n].get('target')} → {ao[n].get('target')}, {'zamknięte' if ao[n].get('closed') else 'otwarte'}")
    cb, ca = Counter(map(key, before.get("entries", []))), Counter(map(key, data.get("entries", [])))
    rem, add = [json.loads(x) for x in (cb - ca).elements()], [json.loads(x) for x in (ca - cb).elements()]
    if len(rem) + len(add) > 20:
        L("Zmiana masowa wpisów (import?)", f"+{len(add)} / −{len(rem)}")
    elif len(rem) == 1 and len(add) == 1 and rem[0].get("bobbin_id") == add[0].get("bobbin_id"):
        L("Wpis: edycja", _desc(rem[0]) + "  →  " + _desc(add[0]))
    else:
        for x in rem:
            L("Wpis: usunięto", _desc(x))
        for x in add:
            L("Wpis: dodano", _desc(x))
    if before.get("settings") != data.get("settings"):
        L("Konfiguracja", "zapisano ustawienia")


def _make_saver(raw_save, before, who, role):
    def saver(path, data):
        try:
            _diff_log(before, data, who, role)
        except Exception:
            pass
        raw_save(path, data)
        before.clear(); before.update(copy.deepcopy({k: data.get(k) for k in ("orders", "entries", "settings")}))
    return saver


def _validate(entries, orders, f, override):
    """Zwraca (błędy blokujące, ostrzeżenia do potwierdzenia)."""
    E, W, today = [], [], date.today()
    o = next((x for x in orders if x.get("name") == f["order"]), None)
    if orders and not o:
        E.append("Wybierz zlecenie.")
    elif o and o.get("closed"):
        E.append("Zlecenie jest zamknięte – otwórz je ponownie, aby dodać wpis.")
    if f["day"] > today:
        E.append("Data nie może być z przyszłości.")
    elif (today - f["day"]).days > 7:
        W.append(f"Data wpisu jest starsza niż 7 dni ({f['day'].isoformat()}).")
    if not f["employee"]:
        E.append("Wybierz pracownika.")
    if f["length"] <= 0 or f["cap"] < f["length"]:
        E.append("Błędna pojemność bobiny lub długość rolki.")
    if E:
        return E, W
    if f["produced"] == 0 and f["completed"] == "NIE":
        E.append("Wpis bez produkcji: podaj liczbę wykonanych sztuk albo oznacz bobinę jako zakończoną.")
    auto = int(f["cap"] // f["length"])
    before = sum(float(e.get("produced", 0) or 0) for e in entries if e.get("bobbin_id") == f["bobbin_id"]) if f["resumed"] else 0
    over = before + f["produced"] + (f["waste"] if f["completed"] == "TAK" else 0) - auto
    if over > 0:
        (W if override else E).append(f"Wpis przekracza pojemność bobiny o {int(over)} szt. (maks. {auto} szt.: bobina {f['cap']:g} m, rolka {f['length']:g} m" + (f", już wykonano {int(before)}" if f["resumed"] else "") + ").")
    if o and f["produced"]:
        done = sum(float(e.get("produced", 0) or 0) for e in entries if e.get("order") == f["order"])
        if f["produced"] > float(o.get("target", 0) or 0) - done:
            W.append(f"Wpis przekracza ilość docelową zlecenia o {int(f['produced'] - (float(o.get('target', 0) or 0) - done))} szt.")
    if any(e.get("order") == f["order"] and e.get("date") == f["day"].isoformat() and e.get("machine") == f["machine"] and str(e.get("shift")) == str(f["shift"]) and e.get("employee") == f["employee"] and float(e.get("produced", 0) or 0) == f["produced"] for e in entries):
        W.append("Istnieje już podobny wpis (ta sama data, zlecenie, maszyna, zmiana, osoba i ilość) – czy to nie duplikat?")
    ps = sorted(float(e.get("produced", 0) or 0) for e in entries if e.get("machine") == f["machine"] and float(e.get("produced", 0) or 0) > 0)
    if len(ps) >= 5 and f["produced"] > 3 * ps[len(ps) // 2]:
        W.append(f"Ilość {int(f['produced'])} szt. jest ponad 3× większa niż typowa dla tej maszyny (mediana {ps[len(ps) // 2]:g}).")
    return E, W


def _fc(entries, order, remaining, settings):
    """Prognoza terminu zakończenia na podstawie tempa z ostatnich dni produkcji."""
    if remaining <= 0:
        return "zrealizowane"
    per = {}
    for e in entries:
        if e.get("order") == order:
            per[e.get("date", "")] = per.get(e.get("date", ""), 0) + float(e.get("produced", 0) or 0)
    ks = sorted(per)[-int(settings.get("forecast_days", 7) or 7):]
    pace = sum(per[k] for k in ks) / len(ks) if ks else 0
    if pace <= 0:
        return "brak danych do prognozy"
    n = math.ceil(remaining / pace)
    if n > 2000:
        return "powyżej 5 lat"
    wd, c = int(settings.get("work_days", 5) or 5), date.today()
    if c.isoformat() in per:
        c += timedelta(days=1)
    k = 0
    while True:
        if wd == 7 or c.weekday() < wd:
            k += 1
            if k == n:
                break
        c += timedelta(days=1)
    return f"ok. {c.strftime('%d.%m.%Y')} ({DN[c.weekday()]}) · ~{round(pace)} szt./dzień · {n} dni rob." + (f" · mało danych ({len(ks)} dni)" if len(ks) < 3 else "")


def _remnants_tab(st, deps, data, entries, settings, who, role):
    pd, latest = deps["pd"], {}
    for e in entries:
        if e.get("bobbin_id"):
            latest[e["bobbin_id"]] = e
    rem = sorted([e for e in latest.values() if e.get("completed") != "TAK" and float(e.get("remaining_m", 0) or 0) > 0], key=lambda e: e.get("date", ""))
    stale = int(settings.get("stale_days", 7) or 7)
    def age(e):
        try:
            return (date.today() - date.fromisoformat(e.get("date", ""))).days
        except ValueError:
            return 0
    st.markdown("### Stan resztek bobin")
    for col, (label, value) in zip(st.columns(3), [("Otwarte bobiny", len(rem)), ("Suma resztek [m]", round(sum(float(e.get("remaining_m", 0) or 0) for e in rem), 1)), (f"Nieaktywne > {stale} dni", sum(age(e) > stale for e in rem))]):
        col.metric(label, value)
    if not rem:
        st.info("Brak otwartych bobin z resztką.")
        return
    st.dataframe(pd.DataFrame([{"Zlecenie": e.get("order"), "Maszyna": e.get("machine"), "Bobina": e.get("bobbin_index"), "Pojemność [m]": e.get("bobbin_m"), "Ostatni wpis": e.get("date"), "Dni": age(e), "Resztka [m]": e.get("remaining_m"), "≈ szt.": int(float(e.get("remaining_m", 0) or 0) // (float(e.get("roll_length_m", 0) or 1)))} for e in rem]), hide_index=True, width="stretch")
    st.caption("Resztka = bobina rozpoczęta, ale niezakończona. „Spisz” zamyka bobinę i księguje resztkę jako odpad.")
    pick = st.selectbox("Resztka do spisania", range(len(rem)), format_func=lambda i: f"{rem[i].get('order')} · bobina {rem[i].get('bobbin_index')} z {rem[i].get('date')} · {rem[i].get('remaining_m')} m", key="m31_writeoff")
    if st.button("🗑️ Spisz resztkę jako odpad", key="m31_writeoff_btn"):
        e = rem[pick]; length = float(e.get("roll_length_m", 0) or 1); w = int(float(e.get("remaining_m", 0) or 0) // length)
        entries.append({**e, "date": date.today().isoformat(), "produced": 0, "waste": w, "waste_m": w * length, "completed": "TAK", "remaining_m": 0, "carry_m": 0, "notes": "Spisanie resztki bobiny", "by": who})
        deps["save_json"](deps["archive_file"], data); st.rerun()


def _log_tab(st, deps, data):
    st.markdown("### Dziennik zdarzeń")
    if not data.get("log"):
        st.info("Brak zdarzeń."); return
    df = deps["pd"].DataFrame(data["log"]).rename(columns={"ts": "Czas", "user": "Użytkownik", "role": "Rola", "act": "Zdarzenie", "d": "Szczegóły"})
    c1, c2, c3 = st.columns(3)
    users, acts, q = c1.multiselect("Użytkownik", sorted(df["Użytkownik"].unique())), c2.multiselect("Zdarzenie", sorted(df["Zdarzenie"].unique())), c3.text_input("Szukaj (tekst lub data RRRR-MM-DD)")
    if users: df = df[df["Użytkownik"].isin(users)]
    if acts: df = df[df["Zdarzenie"].isin(acts)]
    if q: df = df[df.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
    st.caption(f"Zdarzeń: {len(df)} (log tylko do odczytu, ostatnie 3000; pokazano do 500 najnowszych)")
    st.dataframe(df.iloc[::-1].head(500), hide_index=True, width="stretch")


def _calc_tab(st, deps, data, entries, orders):
    """Kalkulator kosztu rolki – założenia surowe, wartości przykładowe do zastąpienia własnymi."""
    pd, c = deps["pd"], data.setdefault("calc", {})
    spec = {"price": ("Cena papieru [zł/kg]", 5.0, 0.1), "width": ("Szerokość rolki [cm]", 10.0, 0.5), "gsm": ("Gramatura całkowita [g/m²]", 34.0, 1.0), "length": ("Długość rolki [m]", 20.0, 1.0), "waste": ("Odpad [%]", 3.0, 0.1), "wage": ("Stawka pracownika [zł/h]", 35.0, 1.0), "people": ("Pracowników przy maszynie", 2.0, 1.0), "hours": ("Godzin na zmianę", 8.0, 0.5), "rolls": ("Rolek na zmianę", 4000.0, 100.0), "core": ("Tuleja [zł/szt.]", 0.05, 0.01), "pack": ("Opakowanie [zł/szt.]", 0.10, 0.01), "energy": ("Energia i inne [zł/h]", 40.0, 1.0), "over": ("Koszty ogólne [% narzutu]", 10.0, 1.0), "margin": ("Marża [% od ceny sprzedaży]", 20.0, 1.0)}
    def fill():
        p, w = sum(float(e.get("produced", 0) or 0) for e in entries), sum(float(e.get("waste", 0) or 0) for e in entries if e.get("completed") == "TAK")
        if p + w: st.session_state["m31_c_waste"] = round(w / (p + w) * 100, 1)
        if entries: st.session_state["m31_c_rolls"] = float(round(p / len(entries)))
    st.markdown("### Kalkulator kosztu rolki")
    st.caption("Wartości początkowe są przykładowe – zastąp je własnymi i zapisz. Dostępne tylko dla Właściciela i Administratora.")
    cols, v = st.columns(3), {}
    for i, (k, (label, default, step)) in enumerate(spec.items()):
        v[k] = cols[i % 3].number_input(label, min_value=0.0, value=float(c.get(k, default)), step=step, key=f"m31_c_{k}")
    b1, b2 = st.columns(2)
    b1.button("📊 Podstaw odpad i wydajność z wpisów", on_click=fill, width="stretch")
    if b2.button("💾 Zapisz ustawienia kalkulatora", width="stretch"):
        c.update(v); deps["save_json"](deps["archive_file"], data); st.success("Zapisano.")
    kg = v["length"] * v["width"] / 100 * v["gsm"] / 1000
    w = v["waste"] / 100; paper = kg * v["price"] / (1 - w) if w < 1 else 0
    labor = v["wage"] * v["people"] * v["hours"] / v["rolls"] if v["rolls"] else 0
    other = v["core"] + v["pack"] + (v["energy"] * v["hours"] / v["rolls"] if v["rolls"] else 0)
    sub = paper + labor + other; cost = sub * (1 + v["over"] / 100); m = v["margin"] / 100; price = cost / (1 - m) if m < 1 else 0
    z = lambda x: f"{x:.2f} zł".replace(".", ",")
    st.table(pd.DataFrame([("Masa papieru w rolce", f"{kg * 1000:.1f} g".replace(".", ",")), ("Papier (z odpadem)", z(paper)), ("Robocizna", z(labor)), ("Tuleja + opakowanie + energia", z(other)), ("Koszty ogólne", z(cost - sub)), ("KOSZT 1 ROLKI", z(cost)), (f"Cena sprzedaży przy marży {v['margin']:g}%", z(price)), ("Zysk na rolce", z(price - cost))], columns=["Składnik", "Wartość"]))
    if orders:
        name = st.selectbox("Koszt zlecenia", [o["name"] for o in orders], key="m31_c_order")
        o = next(x for x in orders if x["name"] == name); done = sum(float(e.get("produced", 0) or 0) for e in entries if e.get("order") == name); tgt = float(o.get("target", 0) or 0)
        st.table(pd.DataFrame([(lbl, int(q), z(cost * q), z(price * q), z((price - cost) * q)) for lbl, q in (("Docelowo", tgt), ("Wykonano", done), ("Pozostało", max(tgt - done, 0)))], columns=["Zakres", "Szt.", "Koszt", "Przychód", "Zysk"]))


def render_bobbin_settlement_screen(st, deps):
    data = deps["load_json"](deps["archive_file"], {"orders": [], "entries": [], "settings": {}})
    orders, entries = data.setdefault("orders", []), data.setdefault("entries", [])
    settings = data.setdefault("settings", {})
    employees = settings.setdefault("employees", [])
    capacities = settings.setdefault("capacities", [3000, 5000])
    roll_lengths = settings.setdefault("roll_lengths", [3, 4, 5, 6, 8, 20])
    st.title("Moduł 31 - Rozliczenie produkcji bobin")
    who, role = _identify(deps)
    can = lambda perm: perm in PERMS[role]
    data.setdefault("log", [])
    raw_save = deps["save_json"]
    deps = dict(deps, save_json=_make_saver(raw_save, copy.deepcopy({k: data.get(k) for k in ("orders", "entries", "settings")}), who, role))
    def event(act, details=""):
        _append_log(data, who, role, act, details); raw_save(deps["archive_file"], data)
    if not st.session_state.get("m31_session_logged"):
        st.session_state["m31_session_logged"] = True; event("Wejście do modułu")
    st.caption(f"👤 Zalogowano: {who} · rola w module: {ROLES[role]}")
    spec = [("orders", "Zlecenia", "order.manage"), ("entries", "Wpisy produkcyjne", "entry.add"), ("remnants", "Resztki bobin", "remnants"), ("summary", "Podsumowanie", "summary"), ("calc", "Kalkulator", "calc"), ("settings", "Konfiguracja", "config"), ("transfer", "Import / eksport", "data"), ("log", "Log", "log")]
    visible = [s for s in spec if can(s[2])]
    tabs = dict(zip([s[0] for s in visible], st.tabs([s[1] for s in visible])))
    if "orders" in tabs:
        with tabs["orders"]:
            with st.form("m31_order", clear_on_submit=True):
                name = st.text_input("Nazwa / numer zlecenia")
                target = st.number_input("Ilość docelowa [szt.]", min_value=1, step=1)
                if st.form_submit_button("Dodaj zlecenie") and name.strip():
                    orders.append({"name": name.strip(), "target": target, "closed": False}); deps["save_json"](deps["archive_file"], data); st.rerun()
            if orders:
                st.dataframe(deps["pd"].DataFrame(orders), hide_index=True, width="stretch")
                st.markdown("### Zarządzanie zleceniem")
                selected_name = st.selectbox("Wybierz zlecenie", [order["name"] for order in orders], key="m31_manage_order")
                selected_order = next(order for order in orders if order["name"] == selected_name)
                linked_entries = [entry for entry in entries if entry.get("order") == selected_name]
                with st.expander("✏️ Edytuj nazwę i ilość docelową zlecenia"):
                    with st.form("m31_edit_order"):
                        edit_name = st.text_input("Nazwa / numer zlecenia — edycja", value=selected_order["name"])
                        edit_target = st.number_input("Ilość docelowa [szt.] — edycja", min_value=1, value=int(selected_order.get("target", 1)), step=1)
                        if st.form_submit_button("Zapisz dane zlecenia"):
                            new_name = edit_name.strip()
                            if not new_name:
                                st.error("Podaj nazwę zlecenia.")
                            elif new_name != selected_name and any(order["name"] == new_name for order in orders):
                                st.error("Zlecenie o tej nazwie już istnieje.")
                            else:
                                selected_order.update({"name": new_name, "target": edit_target})
                                for entry in entries:
                                    if entry.get("order") == selected_name:
                                        entry["order"] = new_name
                                deps["save_json"](deps["archive_file"], data); st.rerun()
                manage_a, manage_b = st.columns(2)
                with manage_a:
                    action_label = "↩️ Otwórz ponownie zlecenie" if selected_order.get("closed", False) else "✅ Zamknij zlecenie"
                    if st.button(action_label, width="stretch"):
                        selected_order["closed"] = not selected_order.get("closed", False)
                        deps["save_json"](deps["archive_file"], data); st.rerun()
                with manage_b:
                    if linked_entries:
                        st.caption(f"Zlecenie ma {len(linked_entries)} wpisów; usuń je najpierw w „Wpisy produkcyjne”.")
                    elif st.button("🗑️ Usuń puste zlecenie", width="stretch"):
                        orders.remove(selected_order)
                        deps["save_json"](deps["archive_file"], data); st.rerun()
    if "entries" in tabs:
        with tabs["entries"]:
            choices = [o["name"] for o in orders] or ["Zlecenie niezależne"]
            if True:  # pola pozostają poza formularzem, aby szacowanie reagowało natychmiast
                a,b,c=st.columns(3)
                with a: order=st.selectbox("Zlecenie",choices); employee=st.selectbox("Pracownik",employees or [deps["current_operator"]()]); day=st.date_input("Data",date.today())
                latest_by_bobbin = {}
                for entry in entries:
                    if entry.get("order") == order and entry.get("bobbin_id"):
                        latest_by_bobbin[entry["bobbin_id"]] = entry
                open_bobbins = [entry for entry in latest_by_bobbin.values() if entry.get("completed") != "TAK"]
                used_indices = [int(entry.get("bobbin_index", 0) or 0) for entry in entries if entry.get("order") == order and entry.get("date") == day.isoformat()]
                next_index = max(used_indices, default=0) + 1
                bobbin_choices = ["Nowa bobina — indeks " + str(next_index)] + [f"Wznów: bobina {entry.get('bobbin_index')} z {entry.get('date')} · {entry.get('machine')}" for entry in open_bobbins]
                bobbin_choice = st.selectbox("Numer / wznowienie bobiny", bobbin_choices, help="Nowe bobiny zaczynają numerację od 1 każdego dnia. Wznowienie zachowuje wcześniejszy indeks.")
                resumed_entry = open_bobbins[bobbin_choices.index(bobbin_choice) - 1] if bobbin_choice != bobbin_choices[0] else None
                bobbin_index = int(resumed_entry.get("bobbin_index", 0)) if resumed_entry else next_index
                bobbin_id = resumed_entry.get("bobbin_id") if resumed_entry else f"{order}|{day.isoformat()}|{bobbin_index}"
                st.caption(f"Identyfikator operacyjny: bobina {bobbin_index}" + (" — wznowienie" if resumed_entry else " — nowa"))
                active_machines = [str(row.get("Maszyna", "")).strip() for row in settings.get("machines", []) if row.get("Aktywna", True) and str(row.get("Maszyna", "")).strip()] or ["Nowa", "Stara"]
                with b: machine=st.selectbox("Maszyna",active_machines); shift=st.selectbox("Zmiana",["1","2","3"], index=["1","2","3"].index(str(settings.get("default_shift", "1"))) if str(settings.get("default_shift", "1")) in ["1","2","3"] else 0); bobbin=st.selectbox("Pojemność bobiny [m]",capacities); roll_length=st.selectbox("Długość rolki [m]",roll_lengths)
                expected_auto = int(bobbin // roll_length) if roll_length else 0
                with c: produced=st.number_input("Wykonano [szt.]",min_value=0,step=1); st.caption(f"Szacowanie automatyczne: {expected_auto} szt. ({bobbin} m ÷ {roll_length} m)"); expected=st.number_input("Szacowane [szt.] - korekta",min_value=0,value=expected_auto,step=1); completed=st.selectbox("Bobina zakończona?",["NIE","TAK"]); remaining=st.number_input("Reszta bobiny [m]",min_value=0,step=1); waste_override=st.number_input("Korekta odpadu [szt.]",min_value=0,step=1); st.caption("Odpad [m] jest liczony automatycznie: odpad [szt.] × długość rolki.")
                notes=st.text_area("Uwagi / powód korekty")
                _cap = float(resumed_entry.get("bobbin_m") or bobbin) if resumed_entry else float(bobbin)
                _len = float(resumed_entry.get("roll_length_m") or roll_length) if resumed_entry else float(roll_length)
                errs, warns = _validate(entries, orders, dict(order=order, day=day, employee=employee, machine=machine, shift=shift, cap=_cap, length=_len, produced=produced, waste=waste_override, completed=completed, bobbin_id=bobbin_id, resumed=bool(resumed_entry)), can("override"))
                for _m in errs: st.error(_m)
                for _m in warns: st.warning(_m)
                ack = st.checkbox("Rozumiem ostrzeżenia – zapisz mimo to", key="m31_ack") if warns and not errs else False
                if st.button("Dodaj wpis", key="m31_add_entry", disabled=bool(errs) or (bool(warns) and not ack)):
                    unfinished_pieces = max(expected - produced, 0)
                    waste = (waste_override if waste_override else unfinished_pieces) if completed == "TAK" else 0
                    calculated_remaining = unfinished_pieces * float(roll_length) if completed == "NIE" else remaining
                    entries.append({"date":day.isoformat(),"order":order,"employee":employee,"machine":machine,"shift":shift,"bobbin_id":bobbin_id,"bobbin_index":bobbin_index,"bobbin_m":bobbin,"roll_length_m":roll_length,"produced":produced,"expected":expected,"waste":waste,"waste_m":waste * float(roll_length),"completed":completed,"remaining_m":calculated_remaining,"carry_m":calculated_remaining if completed == "NIE" else 0,"notes":notes,"by":who}); deps["save_json"](deps["archive_file"],data); st.rerun()
            if entries:
                history = [{"Data": item.get("date", ""), "Zlecenie": item.get("order", ""), "Bobina": item.get("bobbin_index", "—"), "Pracownik": item.get("employee", ""), "Maszyna": item.get("machine", ""), "Zmiana": item.get("shift", ""), "Pojemność bobiny [m]": item.get("bobbin_m", ""), "Długość rolki [m]": item.get("roll_length_m", ""), "Wykonano [szt.]": item.get("produced", 0), "Szacowane [szt.]": item.get("expected", 0), "Odpad [szt.]": item.get("waste", 0) if item.get("completed") == "TAK" else 0, "Odpad [m]": (item.get("waste_m") or float(item.get("waste", 0) or 0) * float(item.get("roll_length_m", 0) or 0)) if item.get("completed") == "TAK" else 0, "Status": item.get("completed", ""), "Pozostało do wznowienia [m]": item.get("remaining_m") or (max(float(item.get("expected", 0) or 0) - float(item.get("produced", 0) or 0), 0) * float(item.get("roll_length_m", 0) or 0) if item.get("completed") == "NIE" else 0), "Uwagi": item.get("notes", "")} for item in entries]
                st.dataframe(deps["pd"].DataFrame(history), hide_index=True, width="stretch")
                if can("entry.delete"):
                    delete_index = st.selectbox("Usuń wpis", range(len(entries)), key="m31_delete_entry", format_func=lambda i: f"{entries[i].get('date', '')} · {entries[i].get('order', '')} · bobina {entries[i].get('bobbin_index', '—')}")
                    if st.button("🗑️ Usuń wybrany wpis", key="m31_delete_entry_button"):
                        entries.pop(delete_index); deps["save_json"](deps["archive_file"], data); st.rerun()
                if can("entry.edit"):
                    with st.expander("✏️ Edytuj wcześniejszy wpis"):
                        index = st.selectbox(
                            "Wpis do edycji", range(len(entries)), key="m31_edit_entry_select",
                            format_func=lambda i: f"{entries[i].get('date', '')} · {entries[i].get('order', '')} · bobina {entries[i].get('bobbin_index', '—')} · {entries[i].get('machine', '')} · zmiana {entries[i].get('shift', '')} · {entries[i].get('employee', '')}",
                        )
                        item = entries[index]
                        with st.form("m31_edit_entry"):
                            saved_date = item.get("date", date.today().isoformat())
                            try:
                                saved_date = date.fromisoformat(str(saved_date))
                            except ValueError:
                                saved_date = date.today()
                            edit_a, edit_b, edit_c = st.columns(3)
                            with edit_a:
                                e_date = st.date_input("Data — edycja", value=saved_date)
                            with edit_b:
                                shift_options = ["1", "2", "3"]
                                saved_shift = str(item.get("shift", "1"))
                                e_shift = st.selectbox("Zmiana — edycja", shift_options, index=shift_options.index(saved_shift) if saved_shift in shift_options else 0)
                            with edit_c:
                                e_roll_length = st.selectbox("Długość rolki [m] — edycja", roll_lengths, index=roll_lengths.index(item.get("roll_length_m")) if item.get("roll_length_m") in roll_lengths else 0)
                            e_produced=st.number_input("Wykonano [szt.] — edycja",min_value=0,value=int(item.get("produced",0))); e_expected=st.number_input("Szacowane [szt.] — edycja",min_value=0,value=int(item.get("expected",0))); e_waste=st.number_input("Odpad [szt.] — edycja",min_value=0,value=int(item.get("waste",0))); st.caption("Odpad [m] zostanie przeliczony: odpad [szt.] × długość rolki."); e_completed=st.selectbox("Bobina zakończona? — edycja",["NIE","TAK"],index=0 if item.get("completed")!="TAK" else 1); e_notes=st.text_area("Uwagi — edycja",value=item.get("notes",""))
                            if st.form_submit_button("Zapisz edycję wpisu"):
                                unfinished_after_edit = max(e_expected - e_produced, 0)
                                remaining_after_edit = unfinished_after_edit * float(e_roll_length) if e_completed == "NIE" else 0
                                final_waste = (e_waste if e_waste > 0 else unfinished_after_edit) if e_completed == "TAK" else 0
                                item.update({"date": e_date.isoformat(), "shift": e_shift, "roll_length_m": e_roll_length, "produced":e_produced,"expected":e_expected,"waste":final_waste,"waste_m":final_waste * float(e_roll_length),"completed":e_completed,"remaining_m":remaining_after_edit,"carry_m":remaining_after_edit if e_completed=="NIE" else 0,"notes":e_notes}); deps["save_json"](deps["archive_file"],data); st.rerun()
    if "summary" in tabs:
        with tabs["summary"]:
            if entries:
                frame=deps["pd"].DataFrame(entries)
                for column, default in (("completed", "NIE"), ("remaining_m", 0), ("bobbin_m", 0), ("waste_m", None)):
                    if column not in frame: frame[column] = default
                frame["waste_m"] = frame.apply(lambda row: row["waste_m"] if not deps["pd"].isna(row["waste_m"]) and row["waste_m"] else float(row.get("waste", 0) or 0) * float(row.get("roll_length_m", 0) or 0), axis=1)
                frame.loc[frame["completed"] != "TAK", "waste"] = 0
                frame.loc[frame["completed"] != "TAK", "waste_m"] = 0
                frame["waste_bobbins"] = frame.apply(lambda row: row["waste_m"] / row["bobbin_m"] if row["bobbin_m"] else 0, axis=1)
                st.markdown("### Statystyki produkcji")
                metrics = [("Ilość zmian", len(frame)), ("Ilość wykonanych sztuk", int(frame.produced.sum())), ("Odpad w sztukach", int(frame.waste.sum())), ("Średnia ilość wykonanych sztuk na zmianę", round(frame.produced.mean(), 1)), ("Ilość wykonanych bobin", int((frame.completed == "TAK").sum())), ("Ilość osób", frame.employee.nunique()), ("Odpad w metrach", round(frame.waste_m.sum(), 1)), ("Odpad w bobinach", round(frame.waste_bobbins.sum(), 2))]
                for group in (metrics[:4], metrics[4:]):
                    columns = st.columns(4)
                    for column, (label, value) in zip(columns, group): column.metric(label, value)
                target_map = {o["name"]: float(o.get("target", 0) or 0) for o in orders}
                waste_rate = float(settings.get("waste_rate_pct", 1.0) or 0)
                rows = []
                for order_name, group in frame.groupby("order"):
                    produced = float(group["produced"].sum())
                    target = target_map.get(order_name, 0)
                    remaining = max(target - produced, 0)
                    capacity, length = _planning_values(entries, settings, order_name)
                    effective_pieces = (capacity / length) * (1 - waste_rate / 100) if length else 0
                    forecast = math.ceil(remaining / effective_pieces) if effective_pieces and remaining else 0
                    progress = (produced / target) if target else 0
                    st.markdown(f"#### {order_name}")
                    st.progress(min(progress, 1.0), text=f"Postęp: {int(produced)} z {int(target)} szt. · pozostało {int(remaining)} szt.")
                    st.caption("📅 Prognoza zakończenia: " + _fc(entries, order_name, remaining, settings))
                    st.caption(f"Prognoza: {forecast} bobin do wykonania ({capacity:g} m / {length:g} m, planowany odpad {waste_rate:g}%).")
                    order_metrics = [("Zmiany", len(group)), ("Wykonano [szt.]", int(group["produced"].sum())), ("Odpad [szt.]", int(group["waste"].sum())), ("Średnio / zmianę", round(group["produced"].mean(), 1)), ("Bobiny zakończone", int((group["completed"] == "TAK").sum())), ("Osoby", group["employee"].nunique()), ("Odpad [m]", round(group["waste_m"].sum(), 1)), ("Odpad [bob.]", round(group["waste_bobbins"].sum(), 2))]
                    for metric_group in (order_metrics[:4], order_metrics[4:]):
                        for metric_column, (label, value) in zip(st.columns(4), metric_group):
                            metric_column.metric(label, value)
                    rows.append({"Zlecenie": order_name, "Docelowo": int(target), "Wykonano": int(produced), "Pozostało [szt.]": int(remaining), "Postęp": f"{progress * 100:.1f}%", "Bobiny do wykonania (z odpadem)": forecast, "Odpad planowany": f"{waste_rate:g}%", "Odpad [szt.]": int(group["waste"].sum()), "Odpad [m]": round(group["waste_m"].sum(), 1), "Zmiany": len(group), "Bobiny zakończone": int((group["completed"] == "TAK").sum())})
                summary = deps["pd"].DataFrame(rows)
                st.markdown("### Pełne zestawienie według zlecenia")
                st.dataframe(summary, hide_index=True, width="stretch")
                report_order = st.selectbox("Zlecenie do raportu PDF", list(frame["order"].unique()), key="m31_report_order")
                selected_order = next((o for o in orders if o["name"] == report_order), {"target": 0})
                report_rows = [row for row in entries if row.get("order") == report_order]
                st.download_button("📄 Pobierz raport PDF zlecenia", _report_pdf(report_order, selected_order.get("target", 0), report_rows, deps.get("font_regular", "Helvetica"), deps.get("font_bold", "Helvetica-Bold")), f"Rozliczenie_bobin_{report_order.replace('/', '_')}.pdf", "application/pdf", width="stretch", on_click=lambda: event("Eksport PDF", report_order))
    if "settings" in tabs:
        with tabs["settings"]:
            st.markdown("### Konfigurator produkcji")
            staff_tab, machine_tab, material_tab, rules_tab = st.tabs(["Pracownicy", "Maszyny", "Bobiny i rolki", "Reguły"])
            with staff_tab:
                staff_rows = deps["pd"].DataFrame(settings.get("staff_records") or [{"Pracownik": name, "Aktywny": True, "Stawka/h": 0} for name in employees])
                staff_edit = st.data_editor(staff_rows, num_rows="dynamic", hide_index=True, width="stretch", key="m31_staff_config")
            with machine_tab:
                machine_rows = deps["pd"].DataFrame(settings.get("machines") or [{"Maszyna": "Nowa", "Typ": "Nowa", "Aktywna": True}, {"Maszyna": "Stara", "Typ": "Stara", "Aktywna": True}])
                machine_edit = st.data_editor(machine_rows, num_rows="dynamic", hide_index=True, width="stretch", key="m31_machine_config")
            with material_tab:
                material_rows = deps["pd"].DataFrame(settings.get("bobbin_profiles") or [{"Pojemność bobiny [m]": cap, "Długość rolki [m]": length, "Aktywny": True} for cap in capacities for length in roll_lengths])
                material_edit = st.data_editor(material_rows, num_rows="dynamic", hide_index=True, width="stretch", key="m31_material_config")
            with rules_tab:
                default_shift = st.selectbox("Domyślna zmiana", ["1", "2", "3"], index=["1", "2", "3"].index(str(settings.get("default_shift", "1"))))
                automatic_waste = st.checkbox("Automatycznie licz odpad po zakończeniu bobiny", value=settings.get("automatic_waste", True))
                waste_rate = st.number_input("Planowany odpad do prognozy bobin [%]", min_value=0.0, max_value=100.0, value=float(settings.get("waste_rate_pct", 1.0)), step=0.1)
                planning_capacity = st.selectbox("Domyślna pojemność do planowania [m]", capacities, index=capacities.index(settings.get("planning_capacity", capacities[0])) if settings.get("planning_capacity", capacities[0]) in capacities else 0)
                planning_length = st.selectbox("Domyślna długość rolki do planowania [m]", roll_lengths, index=roll_lengths.index(settings.get("planning_roll_length", roll_lengths[0])) if settings.get("planning_roll_length", roll_lengths[0]) in roll_lengths else 0)
                work_days = st.selectbox("Dni pracy (prognoza terminu)", [5, 6, 7], index=[5, 6, 7].index(int(settings.get("work_days", 5))) if int(settings.get("work_days", 5)) in (5, 6, 7) else 0, help="5 = pn–pt, 6 = pn–sob, 7 = codziennie")
                forecast_days = st.number_input("Prognoza z ostatnich [dni produkcji]", min_value=1, value=int(settings.get("forecast_days", 7)), step=1)
                stale_days = st.number_input("Resztka nieaktywna po [dniach]", min_value=1, value=int(settings.get("stale_days", 7)), step=1)
                st.caption("Gdy bobina nie jest zakończona, reszta jest przenoszona. Prognoza bobin uwzględnia podany procent odpadu.")
            bad_profiles = [r for r in material_edit.to_dict("records") if not (float(r.get("Pojemność bobiny [m]") or 0) > 0 and float(r.get("Długość rolki [m]") or 0) > 0 and float(r.get("Długość rolki [m]") or 0) <= float(r.get("Pojemność bobiny [m]") or 0))]
            if bad_profiles: st.error("Profile bobin: pojemność i długość rolki muszą być > 0, a rolka nie może być dłuższa niż bobina.")
            if st.button("💾 Zapisz konfigurację produkcji", type="primary", width="stretch", disabled=bool(bad_profiles)):
                settings["staff_records"] = staff_edit.to_dict("records"); settings["employees"] = [str(row["Pracownik"]).strip() for row in settings["staff_records"] if str(row.get("Pracownik", "")).strip() and row.get("Aktywny", True)]
                settings["machines"] = machine_edit.to_dict("records"); settings["bobbin_profiles"] = material_edit.to_dict("records"); settings["capacities"] = sorted({int(row["Pojemność bobiny [m]"]) for row in settings["bobbin_profiles"] if row.get("Aktywny", True)}) or [3000]; settings["roll_lengths"] = sorted({float(row["Długość rolki [m]"]) for row in settings["bobbin_profiles"] if row.get("Aktywny", True)}) or [6]; settings["default_shift"] = default_shift; settings["automatic_waste"] = automatic_waste; settings["waste_rate_pct"] = waste_rate; settings["planning_capacity"] = planning_capacity; settings["planning_roll_length"] = planning_length; settings["work_days"] = work_days; settings["forecast_days"] = int(forecast_days); settings["stale_days"] = int(stale_days)
                deps["save_json"](deps["archive_file"], data); st.success("Zapisano konfigurację produkcji.")
    if "transfer" in tabs:
        with tabs["transfer"]:
            st.markdown("### Kopia danych modułu")
            payload = {"format": "system-produkcji/bobbin-settlement", "version": 1, "exported_at": datetime.now().isoformat(timespec="seconds"), "data": {k: v for k, v in data.items() if k != "log"}}
            st.download_button("⬇️ Eksportuj dane JSON", json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "rozliczenie_bobin.json", "application/json", width="stretch", on_click=lambda: event("Eksport JSON", "pełna kopia danych"))
            imported = st.file_uploader("Importuj kopię JSON", type=["json"], key="m31_import")
            if imported:
                try:
                    imported_data = json.loads(imported.getvalue().decode("utf-8")).get("data", {})
                    if not isinstance(imported_data, dict) or not isinstance(imported_data.get("orders", []), list) or not isinstance(imported_data.get("entries", []), list):
                        raise ValueError("Plik nie zawiera danych modułu 31.")
                    st.success(f"Poprawny plik: {len(imported_data['orders'])} zleceń i {len(imported_data['entries'])} wpisów.")
                    if st.button("Wczytaj plik i zastąp bieżące dane", type="primary"):
                        keep_log = data.get("log", []); data.clear(); data.update(imported_data); data["log"] = keep_log; _append_log(data, who, role, "Import danych", f"{len(imported_data.get('orders', []))} zleceń, {len(imported_data.get('entries', []))} wpisów"); data.setdefault("settings", {}); deps["save_json"](deps["archive_file"], data); st.rerun()
                except Exception as exc:
                    st.error(f"Nie można odczytać pliku JSON: {exc}")
    if "remnants" in tabs:
        with tabs["remnants"]:
            _remnants_tab(st, deps, data, entries, settings, who, role)
    if "calc" in tabs:
        with tabs["calc"]:
            _calc_tab(st, deps, data, entries, orders)
    if "log" in tabs:
        with tabs["log"]:
            _log_tab(st, deps, data)
