"""Moduł 31: niezależne rozliczenie produkcji bobin."""
from datetime import date, datetime, timezone
from datetime import timedelta
from collections import Counter
from io import BytesIO
import copy
import json
from html import escape as _esc
import math
import os
import time
import urllib.request
import uuid


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
ADMIN_PREFIXES = ("admin", "adrian")  # konta Administratora
OWNER_PREFIXES = ("darek", "dariusz", "katarzyna")  # konta Właściciela (każde inne konto = Operator)
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
    if low.startswith(ADMIN_PREFIXES):
        return text, "admin"
    if low.startswith(OWNER_PREFIXES):
        return text, "owner"
    return text or "—", "operator"


def _append_log(data, who, role, act, details=""):
    log = data.setdefault("log", [])
    log.append({"id": uuid.uuid4().hex, "ts": datetime.now().isoformat(timespec="seconds"), "user": who, "role": ROLES.get(role, role), "act": act, "d": details})
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


def _make_saver(raw_save, before, who, role, st=None):
    def saver(path, data):
        try:
            _diff_log(before, data, who, role)
        except Exception:
            pass
        try:
            _stamp_changes(before, data)
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


# ===================== Synchronizacja z chmurą (npoint.io) =====================
# Ta sama baza JSON co w wersji HTML (index_bobina.html): obie wersje współdzielą zlecenia, wpisy,
# konfigurację i log. Użytkownicy/PIN-y wersji HTML są przepuszczane bez zmian. Brak sieci = praca
# lokalna; zmiany dosyłają się przy następnym zapisie lub odświeżeniu.
NPOINT_URL = "https://api.npoint.io/b34b762a751860b3606a"   # zmienna środowiskowa BOBBIN_NPOINT_URL ma pierwszeństwo
CLOUD_TTL = 15       # s – minimalny odstęp między automatycznymi pobraniami (przycisk „Odśwież z chmury” pomija limit)
CLOUD_TIMEOUT = 8    # s
_CFG_KEYS = ("employees", "capacities", "roll_lengths", "waste_rate_pct", "default_shift", "company", "report_footer", "waste_alert_pct", "pdf_history", "default_machine", "default_capacity", "default_roll_length", "paper_types", "default_paper", "work_days", "fc_window", "stale_days", "idle_min")
_CFG_REV = {"report_footer": "footer", "waste_alert_pct": "waste_alert", "fc_window": "forecast_days"}   # klucz w chmurze -> klucz w module


def _ms():
    return int(time.time() * 1000)


def _url():
    return os.environ.get("BOBBIN_NPOINT_URL") or NPOINT_URL


def _b36(n):
    digits, out = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return out or "0"


def _js_norm(v):
    """Liczby całkowite zapisane jako float (6.0) -> int, żeby JSON był taki sam jak w JavaScripcie."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, dict):
        return {k: _js_norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_js_norm(x) for x in v]
    return v


def _js_dumps(v):
    return json.dumps(_js_norm(v), ensure_ascii=False, separators=(",", ":"), default=str)


def _js_hash(s):
    """Odpowiednik hash() z wersji HTML (DJB2 po jednostkach UTF-16) – te same wpisy bez uid dostają to samo uid."""
    h, b = 5381, s.encode("utf-16-le", "surrogatepass")
    for i in range(0, len(b), 2):
        h = ((h << 5) + h + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    return _b36(h)


def _uid_of(e):
    return "h" + _js_hash(_js_dumps(e))


def _ensure_uid(e):
    if not e.get("uid"):
        e["uid"] = _uid_of(e)
    if e.get("updated") is None:
        e["updated"] = 0
    return e["uid"]


def _iso_ms(ts):
    if isinstance(ts, (int, float)):
        return int(ts)
    try:
        return int(datetime.fromisoformat(str(ts)).timestamp() * 1000)
    except Exception:
        return 0


def _ms_iso(ms):
    try:
        return datetime.fromtimestamp(float(ms) / 1000).isoformat(timespec="seconds")
    except Exception:
        return str(ms)


def _role_key(label):
    return {v: k for k, v in ROLES.items()}.get(label, label)


def _lm_stamp():
    n = datetime.now()
    return f"{n:%H:%M} ({n:%d.%m})"


def _normalize(data):
    """Dopisuje pola potrzebne do scalania z chmurą (uid wpisów, znaczniki zmian, id logu, listy usunięć)."""
    for k in ("orders", "entries", "log", "deleted_entries", "deleted_orders"):
        data.setdefault(k, [])
    data.setdefault("cfg_updated", 0)
    data.setdefault("last_modified", "—")
    for e in data["entries"]:
        _ensure_uid(e)
    for o in data["orders"]:
        if o.get("updated") is None:
            o["updated"] = 0
    for l in data["log"]:
        if not l.get("id"):
            l["id"] = "l" + _js_hash(_js_dumps(l))


def _strip(x):
    return {k: v for k, v in x.items() if k != "updated"}


def _stamp_changes(before, data):
    """Przed zapisem: nowe wpisy dostają uid, zmienione – nowy znacznik czasu, usunięte trafiają na listę usunięć."""
    now = _ms()
    bo = {e.get("uid"): e for e in before.get("entries") or [] if e.get("uid")}
    seen = set()
    for e in data.get("entries", []):
        u = e.get("uid")
        if not u or u in seen:            # nowy wpis albo kopia istniejącego (np. spisanie resztki) -> nowa tożsamość
            e["uid"] = uuid.uuid4().hex
            e["created"] = now
            e["updated"] = now
        elif u in bo and _strip(bo[u]) != _strip(e):
            e["updated"] = now
        seen.add(e["uid"])
    data["deleted_entries"] = list(dict.fromkeys(list(data.get("deleted_entries", [])) + [u for u in bo if u not in seen]))
    bor = {o.get("name"): o for o in before.get("orders") or []}
    names = {o.get("name") for o in data.get("orders", [])}
    for o in data.get("orders", []):
        old = bor.get(o.get("name"))
        if old is None or _strip(old) != _strip(o):
            o["updated"] = now
    data["deleted_orders"] = [n for n in dict.fromkeys(list(data.get("deleted_orders", [])) + [n for n in bor if n not in names]) if n not in names]
    if before.get("settings") != data.get("settings"):
        data["cfg_updated"] = now


def _unpack(p):
    p = p if isinstance(p, dict) else {}
    d, y = p.get("data") or p, p.get("sync") or {}
    r = {"orders": [o for o in d.get("orders") or [] if isinstance(o, dict)], "entries": [e for e in d.get("entries") or [] if isinstance(e, dict)],
         "settings": d.get("settings") or {}, "users": y.get("users") or [], "log": [l for l in y.get("log") or [] if isinstance(l, dict)],
         "deleted_users": y.get("deleted_users") or [], "deleted_entries": y.get("deleted_entries") or [], "deleted_orders": y.get("deleted_orders") or [],
         "cfg_updated": y.get("cfg_updated") or 0, "last_modified": y.get("last_modified") or "—", "has_settings": bool(d.get("settings"))}
    for e in r["entries"]:
        _ensure_uid(e)
    return r


def _apply_cfg(settings, rs):
    """Konfiguracja z chmury -> ustawienia modułu (klucze o innych nazwach są mapowane, reszta przepuszczana)."""
    old = (settings.get("capacities"), settings.get("roll_lengths"))
    for k, v in rs.items():
        if k != "machines":
            settings[_CFG_REV.get(k, k)] = v
    names = []
    for m in rs.get("machines") or []:
        n = str(m.get("Maszyna", "") if isinstance(m, dict) else m).strip()
        if n and n not in names:
            names.append(n)
    if names:
        local = {str(m.get("Maszyna", "")).strip(): m for m in settings.get("machines") or [] if isinstance(m, dict)}
        settings["machines"] = [{**local.get(n, {"Maszyna": n, "Typ": n}), "Maszyna": n, "Aktywna": True} for n in names] + [{**m, "Aktywna": False} for n, m in local.items() if n and n not in names]
    if "staff_records" in settings and "employees" in rs:
        rows = {str(x.get("Pracownik", "")).strip(): x for x in settings["staff_records"] if isinstance(x, dict)}
        emp = [str(n).strip() for n in rs["employees"] if str(n).strip()]
        settings["staff_records"] = [{**rows.get(n, {"Pracownik": n, "Stawka/h": 0}), "Pracownik": n, "Aktywny": True} for n in emp] + [{**x, "Aktywny": False} for n, x in rows.items() if n and n not in emp]
    if (settings.get("capacities"), settings.get("roll_lengths")) != old:
        settings.pop("bobbin_profiles", None)   # profile bobin zostaną zbudowane od nowa z pojemności × długości


def _cfg_for_cloud(settings, base):
    out = dict(base or {})
    for k in _CFG_KEYS:
        v = settings.get(_CFG_REV.get(k, k))
        if v is not None:
            out[k] = v
    if "machines" in settings:
        out["machines"] = [{"Maszyna": n, "Aktywna": True} for n in (str(m.get("Maszyna", "")).strip() for m in settings["machines"] if isinstance(m, dict) and m.get("Aktywna", True)) if n]
    return _js_norm(out)


def _merge(data, r):
    """Scalanie jak w wersji HTML: wpisy po uid (wygrywa nowszy 'updated'), zlecenia po nazwie, listy usunięć, log, konfiguracja."""
    de = list(dict.fromkeys(list(data["deleted_entries"]) + list(r["deleted_entries"])))
    dord = list(dict.fromkeys(list(data["deleted_orders"]) + list(r["deleted_orders"])))
    em, om = {}, {}
    for e in list(data["entries"]) + list(r["entries"]):
        u = _ensure_uid(e)
        if u not in em or (e.get("updated") or 0) > (em[u].get("updated") or 0):
            em[u] = e
    for o in list(data["orders"]) + list(r["orders"]):
        n = o.get("name")
        if n not in om or (o.get("updated") or 0) > (om[n].get("updated") or 0):
            om[n] = o
    data["deleted_entries"], data["deleted_orders"] = de, dord
    dset, oset = set(de), set(dord)
    data["entries"] = sorted((e for u, e in em.items() if u not in dset), key=lambda e: (e.get("date") or "", e.get("created") or 0))
    data["orders"] = [o for n, o in om.items() if n not in oset]
    for e in data["entries"]:
        if e.get("completed") is None and e.get("done") is not None:
            e["completed"] = e["done"]
    lm = {l["id"]: l for l in data["log"] if l.get("id")}
    for l in r["log"]:
        if l.get("id") and l["id"] not in lm:
            lm[l["id"]] = {"id": l["id"], "ts": _ms_iso(l.get("ts") or 0), "user": l.get("user") or "—", "role": ROLES.get(l.get("role"), l.get("role") or "—"), "act": l.get("act") or "", "d": l.get("d") or ""}
    data["log"] = sorted(lm.values(), key=lambda l: _iso_ms(l.get("ts")))[-3000:]
    if r["cfg_updated"] > data["cfg_updated"] or (r["cfg_updated"] == data["cfg_updated"] == 0 and r["has_settings"]):
        _apply_cfg(data.setdefault("settings", {}), r["settings"])
        data["cfg_updated"] = r["cfg_updated"]


def _needs_push(data, r):
    re_ = {e["uid"]: (e.get("updated") or 0) for e in r["entries"]}
    rn = {o.get("name"): (o.get("updated") or 0) for o in r["orders"]}
    rl = {l.get("id") for l in r["log"]}
    return (any(re_.get(e["uid"], -1) < (e.get("updated") or 0) for e in data["entries"])
            or any(rn.get(o.get("name"), -1) < (o.get("updated") or 0) for o in data["orders"])
            or any(u not in r["deleted_entries"] for u in data["deleted_entries"])
            or any(n not in r["deleted_orders"] for n in data["deleted_orders"])
            or data["cfg_updated"] > r["cfg_updated"]
            or any(l.get("id") not in rl for l in data["log"]))


def _cloud_pack(data, r):
    entries = []
    for e in data["entries"]:
        c = dict(e)
        c.setdefault("done", c.get("completed", "NIE"))   # wersja HTML czyta pole „done”
        entries.append(c)
    log = [{"id": l["id"], "ts": _iso_ms(l.get("ts")), "user": l.get("user") or "—", "role": _role_key(l.get("role")), "act": l.get("act") or "", "d": l.get("d") or ""} for l in data["log"] if l.get("id")]
    return _js_norm({"format": "system-produkcji/bobbin-settlement", "version": 1, "app_version": "module31", "exported_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                     "data": {"orders": data["orders"], "entries": entries, "settings": _cfg_for_cloud(data.get("settings") or {}, r["settings"])},
                     "sync": {"users": r["users"], "log": log, "deleted_users": r["deleted_users"], "deleted_entries": data["deleted_entries"], "deleted_orders": data["deleted_orders"],
                              "cfg_updated": data["cfg_updated"], "last_modified": data["last_modified"]}})


def _cloud_get():
    req = urllib.request.Request(_url() + ("&" if "?" in _url() else "?") + "nocache=" + str(_ms()), headers={"Cache-Control": "no-store", "User-Agent": "bobbin-module31"})
    with urllib.request.urlopen(req, timeout=CLOUD_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _cloud_post(payload):
    req = urllib.request.Request(_url(), data=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"), method="POST", headers={"Content-Type": "application/json", "User-Agent": "bobbin-module31"})
    with urllib.request.urlopen(req, timeout=CLOUD_TIMEOUT) as resp:
        return resp.status


def _cloud_sync(data, raw_save, path):
    """Pobiera chmurę, scala z lokalnymi danymi i – jeśli lokalnie jest coś nowego – wysyła z powrotem. Zwraca komunikat statusu."""
    try:
        _normalize(data)
        r = _unpack(_cloud_get())
        sig = lambda: json.dumps([data["orders"], data["entries"], data.get("settings"), [l.get("id") for l in data["log"]], data["deleted_entries"], data["deleted_orders"]], sort_keys=True, default=str)
        s0 = sig()
        _merge(data, r)
        if sig() != s0:
            if r["last_modified"] not in ("", "—"):
                data["last_modified"] = r["last_modified"]
            raw_save(path, data)
        if _needs_push(data, r):
            data["last_modified"] = _lm_stamp()
            _cloud_post(_cloud_pack(data, r))
            raw_save(path, data)
        return f"☁️ Chmura: zsynchronizowano {datetime.now():%H:%M:%S}"
    except Exception as exc:
        return f"⚠️ Chmura niedostępna ({type(exc).__name__}) – praca lokalna, dane zsynchronizują się przy następnym zapisie lub odświeżeniu"


def _cloud_push(st, data, raw_save, path):
    msg = _cloud_sync(data, raw_save, path)
    if st is not None:
        try:
            st.session_state["m31_cloud"] = msg
            st.session_state["m31_cloud_t"] = time.time()
        except Exception:
            pass


def _cloud_boot(st, deps, data):
    """Kompatybilny no-op po migracji: stan pobiera warstwa Supabase przy load_json."""
    _normalize(data)
    st.session_state["m31_cloud"] = "☁️ Supabase: dane centralne"


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
    df = deps["pd"].DataFrame(data["log"]).drop(columns=["id"], errors="ignore").rename(columns={"ts": "Czas", "user": "Użytkownik", "role": "Rola", "act": "Zdarzenie", "d": "Szczegóły"})
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


# ===================== RAPORT PDF (odpowiednik generatora z wersji offline) =====================
PRESETS = {"Bieżący tydzień": ("w", 0), "Poprzedni tydzień": ("w", 1), "Bieżący miesiąc": ("m", 0), "Poprzedni miesiąc": ("m", 1), "Bieżący kwartał": ("q", 0), "Poprzedni kwartał": ("q", 1), "Cały okres": ("all", 0), "Własny zakres dat": ("custom", 0)}
MONTHS = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]


def _preset_range(kind, entries):
    t, (k, back) = date.today(), kind
    if k == "all":
        ds = sorted(e["date"] for e in entries if e.get("date"))
        return (date.fromisoformat(ds[0]), date.fromisoformat(ds[-1])) if ds else (t, t)
    if k == "w":
        a = t - timedelta(days=t.weekday() + 7 * back); return a, a + timedelta(days=6)
    if k == "m":
        m = t.year * 12 + t.month - 1 - back; a = date(m // 12, m % 12 + 1, 1); n = m + 1
        return a, date(n // 12, n % 12 + 1, 1) - timedelta(days=1)
    if k == "q":
        q = (t.year * 4 + (t.month - 1) // 3) - back; a = date(q // 4, (q % 4) * 3 + 1, 1); n = q + 1
        return a, date(n // 4, (n % 4) * 3 + 1, 1) - timedelta(days=1)
    return t.replace(day=1), t


_fl = lambda x, k: float(x.get(k, 0) or 0)
_done = lambda x: x.get("completed") == "TAK"
_w = lambda x: _fl(x, "waste") if _done(x) else 0.0
_wm = lambda x: (float(x.get("waste_m") or 0) or _fl(x, "waste") * _fl(x, "roll_length_m")) if _done(x) else 0.0
_n = lambda v: str(int(v)) if float(v) == int(float(v)) else f"{float(v):.1f}"
_fd = lambda d: f"{d[8:10]}.{d[5:7]}.{d[:4]}" if d and len(d) >= 10 else (d or "—")
_pct = lambda w, p: f"{(w / (p + w) * 100) if (p + w) else 0:.1f}"
_shifts = lambda es: len({(e.get("date", ""), str(e.get("shift", ""))) for e in es})
_days = lambda es: len({e.get("date", "") for e in es})


def _agg(es, kf):
    m = {}
    for e in es:
        a = m.setdefault(kf(e), {"n": 0, "p": 0.0, "w": 0.0, "d": 0, "b": set(), "s": set(), "dd": set(), "m": 0.0})
        a["n"] += 1; a["p"] += _fl(e, "produced"); a["w"] += _w(e); a["m"] += _wm(e); a["d"] += _done(e)
        a["b"].add(e.get("bobbin_id")); a["s"].add((e.get("date", ""), str(e.get("shift", "")))); a["dd"].add(e.get("date", ""))
    return m


def _ostats(o, entries, settings, a, b):
    all_e = [x for x in entries if x.get("order") == o["name"]]; g = [x for x in all_e if a <= x.get("date", "") <= b]
    p, pall, w = sum(_fl(x, "produced") for x in g), sum(_fl(x, "produced") for x in all_e), sum(_w(x) for x in g)
    target = float(o.get("target", 0) or 0); left = max(target - pall, 0); cap, length = _planning_values(entries, settings, o["name"])
    eff = (cap / length) * (1 - float(settings.get("waste_rate_pct", 1.0) or 0) / 100) if length else 0
    sc = _shifts(g)
    return {"g": g, "p": p, "pall": pall, "w": w, "left": left, "target": target, "forecast": math.ceil(left / eff) if eff and left else 0, "percent": min(100, pall / target * 100) if target else 0, "wastepct": float(_pct(w, p)), "avg": p / sc if sc else 0, "done": sum(_done(x) for x in g), "m": sum(_wm(x) for x in g), "bobw": sum(_wm(x) / _fl(x, "bobbin_m") for x in g if _fl(x, "bobbin_m"))}


def _report_v2(orders, entries, settings, opt, font="Helvetica", bold="Helvetica-Bold"):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas
    C = {k: HexColor(v) for k, v in dict(navy="#123B69", ink="#152238", pale="#EEF4FB", line="#CBD8E6", green="#168253", red="#AE3D3D", grey="#60748A", white="#FFFFFF", zebra="#F6F9FC", soft="#C7DBF0", track="#E3EEF9").items()}
    PW, PH = A4; PM = 36; CW = PW - 2 * PM
    A, B, layout = opt["from"], opt["to"], opt["layout"]; single = len(orders) == 1
    wa, hist = float(settings.get("waste_alert", 5) or 0), settings.get("pdf_history", "TAK") != "NIE"
    foot = (settings.get("footer") or "Rozliczenie produkcji bobin")
    GL = {"emp": ("Pracownik", "employee"), "paper": ("Typ papieru", "paper"), "mach": ("Maszyna", "machine")}.get(layout)
    names = {o["name"] for o in orders}; ents = [x for x in entries if x.get("order") in names and A <= x.get("date", "") <= B]
    act = [o for o in orders if any(x.get("order") == o["name"] for x in ents)]
    kind = {"emp": "pracowników", "paper": "typów papieru", "mach": "maszyn"}.get(layout)
    title = (f"Raport wg {kind}" + (f": {orders[0]['name']}" if single else "")) if GL else (("Raport zbiorczy: " + orders[0]["name"] if single else "Raport zbiorczy zleceń") if layout == "sum" else ("Raport zlecenia: " + orders[0]["name"] if single else "Raport wg zleceń"))

    class NC(canvas.Canvas):
        def __init__(s, *a, **k): super().__init__(*a, **k); s.saved = []
        def showPage(s): s.saved.append(dict(s.__dict__)); s._startPage()
        def save(s):
            n = len(s.saved)
            for i, st_ in enumerate(s.saved):
                s.__dict__.update(st_); s.setStrokeColor(C["line"]); s.setLineWidth(0.6); s.line(PM, 36, PW - PM, 36)
                s.setFillColor(C["grey"]); s.setFont(font, 7); s.drawString(PM, 24, foot[:120]); s.drawRightString(PW - PM, 24, f"Strona {i + 1} / {n}"); super().showPage()
            super().save()
    import io; buf = io.BytesIO(); cv = NC(buf, pagesize=A4); cv.setTitle(title)
    S = {"Y": 0}
    fnt = lambda b_: bold if b_ else font
    tw = lambda s, sz, b_=False: stringWidth(s, fnt(b_), sz)
    def text(x, y, s, sz, b_=False, col=None, al="l"):
        s = " ".join(str(s if s is not None else "").split())
        if not s: return
        cv.setFillColor(col or C["ink"]); cv.setFont(fnt(b_), sz); yy = PH - y
        (cv.drawRightString if al == "r" else cv.drawCentredString if al == "c" else cv.drawString)(x, yy, s)
    def fit(s, sz, b_, mx):
        s = " ".join(str(s).split())
        while len(s) > 1 and tw(s, sz, b_) > mx: s = s[:-2] + "…" if not s.endswith("…") else s[:-2] + "…"
        return s
    def wrap(s, sz, b_, mx):
        words, lines, cur = " ".join(str(s if s is not None else "").split()).split(" "), [], ""
        for w in [x for x in words if x]:
            while tw(w, sz, b_) > mx and len(w) > 1:
                i = 1
                while i < len(w) and tw(w[:i + 1], sz, b_) <= mx: i += 1
                if cur: lines.append(cur); cur = ""
                lines.append(w[:i]); w = w[i:]
            nx = f"{cur} {w}" if cur else w
            if cur and tw(nx, sz, b_) > mx: lines.append(cur); cur = w
            else: cur = nx
        if cur: lines.append(cur)
        return lines or [""]
    def rect(x, y, w, h, col): cv.setFillColor(col); cv.rect(x, PH - y - h, w, h, fill=1, stroke=0)
    def hline(y, col, wd=0.5): cv.setStrokeColor(col); cv.setLineWidth(wd); cv.line(PM, PH - y, PW - PM, PH - y)
    def new_page():
        cv.showPage(); text(PM, 30, fit(f"{title}  ·  {_fd(A)} – {_fd(B)}", 8, False, CW - 60), 8, False, C["grey"]); hline(38, C["line"]); S["Y"] = 54
    def ensure(h):
        if S["Y"] + h > PH - 52: new_page()
    def heading(t, sz=11):
        ensure(40); text(PM, S["Y"] + 12, fit(t, sz, True, CW), sz, True, C["navy"]); S["Y"] += 18; hline(S["Y"], C["line"], 0.8); S["Y"] += 8
    def sub(t): ensure(60); text(PM, S["Y"] + 8, t, 7, True, C["grey"]); S["Y"] += 14
    def tiles(items):
        per, gap, h = 4, 8, 38; w = (CW - gap * (per - 1)) / per
        for i in range(0, len(items), per):
            ensure(h + gap)
            for j, it in enumerate(items[i:i + per]):
                x = PM + j * (w + gap); rect(x, S["Y"], w, h, C["pale"]); text(x + 8, S["Y"] + 13, it[0], 7, True, C["grey"])
                text(x + 8, S["Y"] + 30, fit(str(it[1]), 14, True, w - 14), 14, True, C["red"] if len(it) > 2 and it[2] else C["navy"])
            S["Y"] += h + gap
    def table(cols, rows):
        fixed = sum(k["w"] for k in cols if k["w"] != "*"); ws = [CW - fixed if k["w"] == "*" else k["w"] for k in cols]; fs, lh, pad = 7.5, 9.5, 4
        ax = lambda i, al: ws[i] - pad if al == "r" else ws[i] / 2 if al == "c" else pad
        def head():
            rect(PM, S["Y"], CW, 18, C["navy"]); x = PM
            for i, k in enumerate(cols): text(x + ax(i, k.get("a")), S["Y"] + 12, fit(k["h"], 6.8, True, ws[i] - 2 * pad), 6.8, True, C["white"], k.get("a", "l")); x += ws[i]
            S["Y"] += 18
        ensure(40); head()
        for ri, r in enumerate(rows):
            cells = [dict(v) if isinstance(v, dict) else {"t": v} for v in r]
            for i, z in enumerate(cells): z["lines"] = wrap(z["t"], fs, z.get("b", False), ws[i] - 2 * pad)
            h = max(len(z["lines"]) for z in cells) * lh + 6
            if S["Y"] + h > PH - 52: new_page(); head()
            if ri % 2: rect(PM, S["Y"], CW, h, C["zebra"])
            x = PM
            for i, z in enumerate(cells):
                for k, l in enumerate(z["lines"]): text(x + ax(i, cols[i].get("a")), S["Y"] + 10 + k * lh, l, fs, z.get("b", False), z.get("c"), cols[i].get("a", "l"))
                x += ws[i]
            hline(S["Y"] + h, C["line"], 0.4); S["Y"] += h
        S["Y"] += 10
    sort_h = lambda a: sorted(a, key=lambda x: x.get("date", ""))
    status = lambda x: {"t": "Zakończona", "c": C["green"], "b": True} if _done(x) else "W toku" + (f" ({_n(_fl(x, 'remaining_m'))} m)" if _fl(x, "remaining_m") else "")
    R = lambda *a: [str(v) for v in a]
    def group_table(label, key, es):
        sub(label.upper()); table([{"h": label, "w": "*"}, {"h": "Zmiany", "w": 56, "a": "r"}, {"h": "Wpisy", "w": 56, "a": "r"}, {"h": "Wykonano [szt.]", "w": 90, "a": "r"}, {"h": "Odpad [szt.]", "w": 80, "a": "r"}, {"h": "Bobiny zakończone", "w": 100, "a": "r"}],
            [R(k, len(a["s"]), a["n"], _n(a["p"]), _n(a["w"]), a["d"]) for k, a in sorted(_agg(es, lambda x: x.get(key) or "—").items(), key=lambda kv: -kv[1]["p"])])
    def paper_table(es, nosub=False):
        if not any(x.get("paper") for x in es): return
        if not nosub: sub("TYPY PAPIERU")
        table([{"h": "Typ papieru", "w": "*"}, {"h": "Wpisy", "w": 44, "a": "r"}, {"h": "Bobiny", "w": 44, "a": "r"}, {"h": "Zakończone", "w": 56, "a": "r"}, {"h": "Wykonano [szt.]", "w": 74, "a": "r"}, {"h": "Odpad [szt.]", "w": 66, "a": "r"}, {"h": "Odpad [%]", "w": 52, "a": "r"}],
            [R(k, a["n"], len(a["b"]), a["d"], _n(a["p"]), _n(a["w"]), _pct(a["w"], a["p"]) + "%") for k, a in sorted(_agg(es, lambda x: x.get("paper") or "Nie określono").items(), key=lambda kv: -kv[1]["p"])])
    cnt_cols = lambda lbl: [{"h": lbl, "w": "*"}, {"h": "Dni", "w": 36, "a": "r"}, {"h": "Zmiany", "w": 46, "a": "r"}, {"h": "Wpisy", "w": 42, "a": "r"}, {"h": "Wykonano [szt.]", "w": 74, "a": "r"}, {"h": "Odpad [szt.]", "w": 62, "a": "r"}, {"h": "Odpad [%]", "w": 50, "a": "r"}, {"h": "Bobiny zakoń.", "w": 68, "a": "r"}]
    cnt_rows = lambda m: [R(k, len(a["dd"]), len(a["s"]), a["n"], _n(a["p"]), _n(a["w"]), _pct(a["w"], a["p"]) + "%", a["d"]) for k, a in sorted(m.items(), key=lambda kv: -kv[1]["p"])]
    def hist_table(es, with_order):
        sub("HISTORIA WPISÓW")
        cols = [{"h": "Data", "w": 50}] + ([{"h": "Zlecenie", "w": 84}] if with_order else []) + [{"h": "Bob.", "w": 24, "a": "c"}, {"h": "Pracownik", "w": 70}, {"h": "Maszyna", "w": 48}, {"h": "Zm.", "w": 22, "a": "c"}, {"h": "Wykonano", "w": 46, "a": "r"}, {"h": "Odpad szt.", "w": 46, "a": "r"}, {"h": "Status", "w": 70}] + ([] if with_order else [{"h": "Uwagi", "w": "*"}])
        if with_order: cols[-1]["w"] = "*"
        table(cols, [[_fd(x.get("date"))] + ([x.get("order", "")] if with_order else []) + [str(x.get("bobbin_index") or "—"), x.get("employee", ""), x.get("machine", ""), str(x.get("shift", "")), _n(_fl(x, "produced")), _n(_w(x)), status(x)] + ([] if with_order else [x.get("notes", "")]) for x in sort_h(es)])
    # --- pierwsza strona
    rect(0, 0, PW, 80, C["navy"]); text(PM, 26, fit((settings.get("company") or "Rozliczenie produkcji bobin").upper(), 8, True, CW - 80), 8, True, C["soft"]); text(PW - PM, 26, "Moduł 31", 8, True, C["soft"], "r")
    tsz = 19
    while tw(title, tsz, True) > CW and tsz > 11: tsz -= 1
    text(PM, 54, title, tsz, True, C["white"])
    text(PM, 71, fit(opt["label"] + "  ·  " + {"sum": "zestawienie zbiorcze", "emp": "z podziałem na pracowników", "paper": "z podziałem na typy papieru", "mach": "z podziałem na maszyny"}.get(layout, "z podziałem na zlecenia"), 8.5, False, CW), 8.5, False, C["soft"])
    S["Y"] = 94; rect(PM, S["Y"], CW, 38, C["pale"]); totp = sum(_fl(x, "produced") for x in ents)
    for i, (l, v) in enumerate([("Wygenerowano", datetime.now().strftime("%d.%m.%Y %H:%M")), ("Okres", f"{_fd(A)} – {_fd(B)}"), ("Wpisy produkcyjne", len(ents)), ("Wykonano w okresie", f"{_n(totp)} szt.")]):
        x = PM + i * CW / 4; text(x + 10, S["Y"] + 14, l.upper(), 6.5, True, C["grey"]); text(x + 10, S["Y"] + 29, fit(str(v), 10, True, CW / 4 - 16), 10, True)
    S["Y"] += 54
    wsum = sum(_w(x) for x in ents); wp = float(_pct(wsum, totp)); alt = wa > 0 and wp > wa
    heading("Podsumowanie okresu")
    tiles([("Dni produkcji", _days(ents)), ("Zmiany", _shifts(ents)), ("Wpisy", len(ents)), ("Wykonano [szt.]", _n(totp)), ("Odpad [szt.]", _n(wsum)), ("Odpad [%]", f"{wp:.1f}", alt), ("Średnio / zmianę", f"{totp / _shifts(ents):.1f}" if ents else 0), ("Bobiny zakończone", sum(_done(x) for x in ents)), ("Osoby", len({x.get("employee") for x in ents})), ("Zlecenia w okresie", len(act))])
    if alt: ensure(16); text(PM, S["Y"] + 8, f"UWAGA: odpad {wp:.1f}% przekracza ustalony próg {wa:g}%.", 8.5, True, C["red"]); S["Y"] += 18
    # rozbicie w czasie
    span = (date.fromisoformat(B) - date.fromisoformat(A)).days + 1
    if span <= 10: bname, bkey, blab = "dni", (lambda d: d), (lambda k: DN[date.fromisoformat(k).weekday()] + " " + _fd(k))
    elif span <= 70:
        bname, bkey = "tygodnie", (lambda d: (date.fromisoformat(d) - timedelta(days=date.fromisoformat(d).weekday())).isoformat())
        blab = lambda k: "Tydzień " + _fd(k)[:5] + " – " + _fd((date.fromisoformat(k) + timedelta(days=6)).isoformat())
    else: bname, bkey, blab = "miesiące", (lambda d: d[:7]), (lambda k: MONTHS[int(k[5:7]) - 1] + " " + k[:4])
    bm = _agg([x for x in ents if x.get("date")], lambda x: bkey(x["date"]))
    if len(bm) > 1:
        heading(f"Rozbicie w czasie ({bname})"); table(cnt_cols("Okres"), [R(blab(k), len(a["dd"]), len(a["s"]), a["n"], _n(a["p"]), _n(a["w"]), _pct(a["w"], a["p"]) + "%", a["d"]) for k, a in sorted(bm.items())])
    if len(act) > 1:
        heading("Przegląd zleceń w okresie"); rows = []
        for o in act:
            s = _ostats(o, entries, settings, A, B); al = wa > 0 and s["wastepct"] > wa
            rows.append(R(o["name"], _n(s["target"]), _n(s["p"]), f"{s['percent']:.0f}%", _n(s["w"])) + [{"t": f"{s['wastepct']:.1f}%", "c": C["red"] if al else C["ink"], "b": al}] + R(_n(s["left"]), s["forecast"], "zamknięte" if o.get("closed") else "otwarte"))
        table([{"h": "Zlecenie", "w": "*"}, {"h": "Docelowo", "w": 50, "a": "r"}, {"h": "W okresie [szt.]", "w": 62, "a": "r"}, {"h": "Realizacja", "w": 50, "a": "r"}, {"h": "Odpad szt.", "w": 48, "a": "r"}, {"h": "Odpad %", "w": 44, "a": "r"}, {"h": "Pozostało", "w": 50, "a": "r"}, {"h": "Prognoza bob.", "w": 58, "a": "r"}, {"h": "Status", "w": 52}], rows)
    if GL:
        gl, gk = GL; key = lambda x: x.get(gk) or ("Nie określono" if gk == "paper" else "—"); gm = _agg(ents, key)
        dims = [d for d in (("Typ papieru", "paper"), ("Pracownik", "employee"), ("Maszyna", "machine")) if d[1] != gk]
        heading("Przegląd: " + gl.lower()); table(cnt_cols(gl), cnt_rows(gm))
        for k in sorted(gm, key=lambda z: -gm[z]["p"]):
            es = [x for x in ents if key(x) == k]; p2, w2 = sum(_fl(x, "produced") for x in es), sum(_w(x) for x in es); wp2 = float(_pct(w2, p2)); sc = _shifts(es)
            ensure(210); heading(f"{gl}: {k}")
            tiles([("Dni", _days(es)), ("Zmiany", sc), ("Wpisy", len(es)), ("Wykonano [szt.]", _n(p2)), ("Odpad [szt.]", _n(w2)), ("Odpad [%]", f"{wp2:.1f}", wa > 0 and wp2 > wa), ("Średnio / zmianę", f"{p2 / sc:.1f}" if sc else 0), ("Bobiny zakończone", sum(_done(x) for x in es)), ("Odpad [m]", _n(sum(_wm(x) for x in es))), ("Zlecenia", len({x.get("order") for x in es}))])
            sub("ZLECENIA"); table(cnt_cols("Zlecenie"), cnt_rows(_agg(es, lambda x: x.get("order") or "—")))
            for d in dims: paper_table(es) if d[1] == "paper" else group_table(d[0], d[1], es)
            if hist: hist_table(es, True)
    elif layout == "sum":
        heading("Zestawienie zbiorcze"); paper_table(ents); group_table("Pracownik", "employee", ents); group_table("Maszyna", "machine", ents)
        if hist: hist_table(ents, True)
    else:
        if not single and act: heading("Typy papieru w okresie"); paper_table(ents, True)
        for o in act:
            s = _ostats(o, entries, settings, A, B); al = wa > 0 and s["wastepct"] > wa
            if not single: ensure(210)
            heading(f"Zlecenie: {o['name']}  ·  " + ("zamknięte" if o.get("closed") else "otwarte"), 12 if single else 11)
            ensure(60); rect(PM, S["Y"], CW, 10, C["track"])
            if s["percent"] > 0: rect(PM, S["Y"], CW * s["percent"] / 100, 10, C["green"])
            S["Y"] += 10
            text(PM, S["Y"] + 12, f"okres: {_n(s['p'])} szt.  ·  łącznie: {_n(s['pall'])} / {_n(s['target'])} szt. ({s['percent']:.1f}%)  ·  pozostało: {_n(s['left'])} szt.  ·  prognoza: {s['forecast']} bob. (odpad plan. {float(settings.get('waste_rate_pct', 1.0) or 0):g}%)", 8, False, C["grey"])
            text(PM, S["Y"] + 24, "Prognoza zakończenia: " + _fc(entries, o["name"], s["left"], settings), 8, True, C["navy"]); S["Y"] += 36
            tiles([("Dni", _days(s["g"])), ("Zmiany", _shifts(s["g"])), ("Wpisy", len(s["g"])), ("Wykonano [szt.]", _n(s["p"])), ("Odpad [szt.]", _n(s["w"])), ("Odpad [%]", f"{s['wastepct']:.1f}", al), ("Średnio / zmianę", f"{s['avg']:.1f}" if s["g"] else 0), ("Bobiny zakończone", s["done"]), ("Odpad [m]", _n(s["m"])), ("Odpad [bobiny]", f"{s['bobw']:.2f}")])
            if al: ensure(16); text(PM, S["Y"] + 8, f"UWAGA: odpad {s['wastepct']:.1f}% przekracza ustalony próg {wa:g}%.", 8.5, True, C["red"]); S["Y"] += 18
            paper_table(s["g"]); group_table("Pracownik", "employee", s["g"]); group_table("Maszyna", "machine", s["g"])
            if hist: hist_table(s["g"], False)
    cv.showPage(); cv.save()
    return buf.getvalue()


def _pdf_fonts(deps):
    """Czcionka z polskimi znakami: najpierw ta z systemu, potem folder fonts/, Windows (Arial), Linux, matplotlib."""
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pl = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
    def supports(name):
        try:
            cmap = getattr(getattr(pdfmetrics.getFont(name), "face", None), "charToGlyph", None)
            return bool(cmap) and all(ord(c) in cmap for c in pl)
        except Exception:
            return False
    reg, bold = deps.get("font_regular", "Helvetica"), deps.get("font_bold", "Helvetica-Bold")
    if supports(reg) and supports(bold):
        return reg, bold
    if supports("M31Sans") and supports("M31Sans-Bold"):
        return "M31Sans", "M31Sans-Bold"
    here = Path(__file__).resolve().parent
    dirs = [here / "fonts", here.parent / "fonts"]
    try:
        dirs.append(Path(deps["archive_file"]).resolve().parent.parent / "fonts")
    except Exception:
        pass
    dirs += [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/liberation"), Path("/usr/share/fonts/truetype/dejavu"), Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]
    try:
        import matplotlib
        dirs.append(Path(matplotlib.get_data_path()) / "fonts" / "ttf")
    except Exception:
        pass
    pairs = [("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"), ("arial.ttf", "arialbd.ttf"), ("Arial.ttf", "Arial Bold.ttf"), ("segoeui.ttf", "segoeuib.ttf"), ("calibri.ttf", "calibrib.ttf"), ("tahoma.ttf", "tahomabd.ttf"), ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")]
    for d in dirs:
        for r, b in pairs:
            if (d / r).is_file() and (d / b).is_file():
                try:
                    pdfmetrics.registerFont(TTFont("M31Sans", str(d / r))); pdfmetrics.registerFont(TTFont("M31Sans-Bold", str(d / b)))
                    if supports("M31Sans") and supports("M31Sans-Bold"):
                        return "M31Sans", "M31Sans-Bold"
                except Exception:
                    continue
    return reg, bold


_SUMMARY_CSS = """<style>
.m31-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:4px 0 14px}
.m31-card{background:#eef4fb;border-radius:9px;padding:12px 14px;color:#152238}
.m31-lab{font-size:.68rem;font-weight:800;color:#60738a;letter-spacing:.04em;text-transform:uppercase}
.m31-val{display:block;margin-top:4px;font-size:1.5rem;font-weight:700;color:#123b69}
.m31-prog{height:18px;background:#e3eef9;border-radius:9px;overflow:hidden;margin:2px 0 10px}
.m31-prog i{display:block;background:#16825d;height:100%}
.m31-warn{color:#ae3d3d;font-weight:700;margin:4px 0}
</style>"""


def _cards(items):
    return '<div class="m31-grid">' + "".join(f'<div class="m31-card"><div class="m31-lab">{_esc(str(label))}</div><span class="m31-val">{_esc(str(value))}</span></div>' for label, value in items) + "</div>"


def _nv(v):
    v = float(v or 0)
    return int(v) if v == int(v) else round(v, 1)


def _summary_tab(st, deps, orders, entries, settings, event):
    """Podsumowanie w układzie wersji HTML: kafelki, statystyki wg maszyn, panel każdego zlecenia, raport PDF."""
    st.markdown(_SUMMARY_CSS, unsafe_allow_html=True)
    waste_rate, waste_alert = float(settings.get("waste_rate_pct", 1.0) or 0), float(settings.get("waste_alert", 5) or 0)
    tp, tw, sh = sum(_fl(x, "produced") for x in entries), sum(_w(x) for x in entries), _shifts(entries)
    st.markdown(_cards([
        ("Dni produkcji", _days(entries)), ("Ilość zmian", sh), ("Liczba wpisów", len(entries)), ("Wykonane sztuki", _n(tp)), ("Odpad w sztukach", _n(tw)),
        ("Odpad %", _pct(tw, tp)), ("Średnio / zmianę", f"{tp / sh:.1f}" if sh else 0), ("Wykonane bobiny", sum(_done(x) for x in entries)),
        ("Ilość osób", len({x.get("employee") for x in entries})), ("Odpad w metrach", _n(sum(_wm(x) for x in entries))),
        ("Odpad w bobinach", f"{sum(_wm(x) / _fl(x, 'bobbin_m') for x in entries if _fl(x, 'bobbin_m')):.2f}")]), unsafe_allow_html=True)
    st.markdown("### Statystyki wg maszyn")
    machines = _agg(entries, lambda x: x.get("machine") or "—")
    if machines:
        st.dataframe(deps["pd"].DataFrame([{"Maszyna": k, "Dni": len(a["dd"]), "Zmiany": len(a["s"]), "Wpisy": a["n"], "Wykonano": _nv(a["p"]), "Odpad szt.": _nv(a["w"]), "Odpad %": float(_pct(a["w"], a["p"])), "Bobiny zakończone": a["d"], "Odpad m": _nv(a["m"])}
                                           for k, a in sorted(machines.items(), key=lambda kv: -kv[1]["p"])]), hide_index=True, width="stretch")
    else:
        st.caption("Brak wpisów.")
    st.markdown("### Statystyki, progres i prognoza per zlecenie")
    if not orders:
        st.caption("Brak zleceń.")
    for o in orders:
        s = _ostats(o, entries, settings, "", "9999-12-31"); g = s["g"]
        with st.container(border=True):
            st.markdown(f"#### {o['name']}{' (zamknięte)' if o.get('closed') else ''}")
            st.markdown(f'<div class="m31-prog"><i style="width:{s["percent"]:.4g}%"></i></div>', unsafe_allow_html=True)
            st.markdown(f"{_n(s['p'])} / {_n(s['target'])} szt. · pozostało {_n(s['left'])} szt. · prognoza {s['forecast']} bobin (odpad {_n(waste_rate)}%)")
            st.markdown("**📅 Prognoza zakończenia:** " + ("zamknięte" if o.get("closed") else _fc(entries, o["name"], s["left"], settings)))
            papers = {}
            for x in g:
                if x.get("paper"):
                    papers[x["paper"]] = papers.get(x["paper"], 0) + _fl(x, "produced")
            if papers:
                st.caption("Typy papieru: " + ", ".join(f"{k}: {_n(v)} szt." for k, v in papers.items()))
            if waste_alert > 0 and s["wastepct"] > waste_alert:
                st.markdown(f'<p class="m31-warn">⚠ Odpad {s["wastepct"]:.1f}% przekracza próg {_n(waste_alert)}%</p>', unsafe_allow_html=True)
            st.markdown(_cards([("Dni", _days(g)), ("Zmiany", _shifts(g)), ("Wpisy", len(g)), ("Wykonano", _n(s["p"])), ("Odpad szt.", _n(s["w"])), ("Odpad %", f"{s['wastepct']:.1f}"),
                                ("Średnio / zmianę", f"{s['avg']:.1f}" if g else 0), ("Bobiny zakończone", s["done"]), ("Osoby", len({x.get("employee") for x in g})), ("Odpad m", _n(s["m"])), ("Odpad bob.", f"{s['bobw']:.2f}")]), unsafe_allow_html=True)
    if entries:
        st.markdown("### Raport PDF")
        ra, rb = st.columns(2)
        report_order = ra.selectbox("Zlecenia", ["Wszystkie zlecenia"] + [o["name"] for o in orders], key="m31_report_order")
        preset = rb.selectbox("Okres", list(PRESETS), index=2, key="m31_rep_period")
        pa, pb = _preset_range(PRESETS[preset], entries)
        da, db = st.columns(2)
        rep_from = da.date_input("Od", value=pa, disabled=preset != "Własny zakres dat", key=f"m31_rf_{preset}")
        rep_to = db.date_input("Do", value=pb, disabled=preset != "Własny zakres dat", key=f"m31_rt_{preset}")
        layouts = {"Z podziałem na zlecenia": "split", "Zbiorczy (zlecenia razem)": "sum", "Z podziałem na pracowników": "emp", "Z podziałem na maszyny": "mach"}
        if any(e.get("paper") for e in entries): layouts["Z podziałem na typy papieru"] = "paper"
        layout_label = st.selectbox("Układ raportu", list(layouts), key="m31_rep_layout")
        if st.button("📄 Generuj raport PDF", width="stretch", key="m31_rep_btn"):
            sel_orders = orders if report_order == "Wszystkie zlecenia" else [o for o in orders if o["name"] == report_order]
            sel_names = {o["name"] for o in sel_orders}
            if rep_from > rep_to:
                st.error("Data „Od” jest późniejsza niż „Do”.")
            elif not any(e.get("order") in sel_names and rep_from.isoformat() <= e.get("date", "") <= rep_to.isoformat() for e in entries):
                st.warning("Brak wpisów produkcyjnych w wybranym zakresie dat.")
            else:
                f_reg, f_bold = _pdf_fonts(deps)
                if f_reg.startswith("Helvetica"): st.warning("Nie znaleziono czcionki z polskimi znakami – wgraj folder fonts/ (LiberationSans-Regular.ttf i LiberationSans-Bold.ttf) obok pliku modułu 31.")
                pdf_bytes = _report_v2(sel_orders, entries, settings, {"from": rep_from.isoformat(), "to": rep_to.isoformat(), "layout": layouts[layout_label], "label": preset}, f_reg, f_bold)
                slug = "".join(ch if ch.isalnum() else "_" for ch in (report_order if len(sel_orders) == 1 else "wszystkie")).strip("_") or "zlecenie"
                st.session_state["m31_pdf"] = (pdf_bytes, f"raport_bobiny_{layouts[layout_label]}_{slug}_{rep_from.isoformat()}_{rep_to.isoformat()}.pdf")
                event("Raport PDF", f"{layouts[layout_label]} {rep_from.isoformat()} – {rep_to.isoformat()}")
        if st.session_state.get("m31_pdf"):
            st.download_button("⬇️ Pobierz wygenerowany raport PDF", st.session_state["m31_pdf"][0], st.session_state["m31_pdf"][1], "application/pdf", width="stretch")


def render_bobbin_settlement_screen(st, deps):
    # Rekord Supabase współdzielony z wersją HTML ma zewnętrzne opakowanie
    # ``{data, sync}``. Widok Streamlit pracuje wewnętrznie na rozpakowanym
    # słowniku, ale przy zapisie odtwarza dokładnie ten sam format, aby obie
    # wersje aplikacji widziały identyczne dane.
    stored = deps["load_json"](deps["archive_file"], {"orders": [], "entries": [], "settings": {}})
    cloud_base = _unpack(stored) if isinstance(stored, dict) and ("data" in stored or "sync" in stored) else _unpack({})
    data = _unpack(stored) if isinstance(stored, dict) and ("data" in stored or "sync" in stored) else stored
    if not isinstance(data, dict):
        data = {"orders": [], "entries": [], "settings": {}}
    raw_state_save = deps["save_json"]

    def save_module_state(path, value):
        _normalize(value)
        raw_state_save(path, _cloud_pack(value, cloud_base))

    deps = dict(deps, save_json=save_module_state)
    _cloud_boot(st, deps, data)
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
    deps = dict(deps, save_json=_make_saver(raw_save, copy.deepcopy({k: data.get(k) for k in ("orders", "entries", "settings")}), who, role, st))
    def event(act, details=""):
        _append_log(data, who, role, act, details); raw_save(deps["archive_file"], data)
    if not st.session_state.get("m31_session_logged"):
        st.session_state["m31_session_logged"] = True; event("Wejście do modułu")
    st.caption(f"👤 Zalogowano: {who} · rola w module: {ROLES[role]}")
    _cc1, _cc2 = st.columns([4, 1])
    _cc1.caption(st.session_state.get("m31_cloud", "☁️ Chmura: —"))
    _cc2.button("🔄 Odśwież z chmury", key="m31_cloud_btn", on_click=lambda: st.session_state.__setitem__("m31_cloud_t", 0))
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
            _summary_tab(st, deps, orders, entries, settings, event)
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
                company = st.text_input("Nazwa firmy w raporcie PDF", value=settings.get("company", ""))
                report_footer = st.text_input("Stopka raportu PDF", value=settings.get("footer", ""))
                waste_alert = st.number_input("Próg alarmu odpadu w raporcie [%] (0 = wyłączony)", min_value=0.0, max_value=100.0, value=float(settings.get("waste_alert", 5)), step=0.5)
                pdf_history = st.selectbox("Historia wpisów w raporcie PDF", ["TAK", "NIE"], index=0 if settings.get("pdf_history", "TAK") != "NIE" else 1)
                st.caption("Gdy bobina nie jest zakończona, reszta jest przenoszona. Prognoza bobin uwzględnia podany procent odpadu.")
            bad_profiles = [r for r in material_edit.to_dict("records") if not (float(r.get("Pojemność bobiny [m]") or 0) > 0 and float(r.get("Długość rolki [m]") or 0) > 0 and float(r.get("Długość rolki [m]") or 0) <= float(r.get("Pojemność bobiny [m]") or 0))]
            if bad_profiles: st.error("Profile bobin: pojemność i długość rolki muszą być > 0, a rolka nie może być dłuższa niż bobina.")
            if st.button("💾 Zapisz konfigurację produkcji", type="primary", width="stretch", disabled=bool(bad_profiles)):
                settings["staff_records"] = staff_edit.to_dict("records"); settings["employees"] = [str(row["Pracownik"]).strip() for row in settings["staff_records"] if str(row.get("Pracownik", "")).strip() and row.get("Aktywny", True)]
                settings["machines"] = machine_edit.to_dict("records"); settings["bobbin_profiles"] = material_edit.to_dict("records"); settings["capacities"] = sorted({int(row["Pojemność bobiny [m]"]) for row in settings["bobbin_profiles"] if row.get("Aktywny", True)}) or [3000]; settings["roll_lengths"] = sorted({float(row["Długość rolki [m]"]) for row in settings["bobbin_profiles"] if row.get("Aktywny", True)}) or [6]; settings["default_shift"] = default_shift; settings["automatic_waste"] = automatic_waste; settings["waste_rate_pct"] = waste_rate; settings["planning_capacity"] = planning_capacity; settings["planning_roll_length"] = planning_length; settings["work_days"] = work_days; settings["forecast_days"] = int(forecast_days); settings["stale_days"] = int(stale_days); settings["company"] = company.strip(); settings["footer"] = report_footer.strip(); settings["waste_alert"] = waste_alert; settings["pdf_history"] = pdf_history
                deps["save_json"](deps["archive_file"], data); st.success("Zapisano konfigurację produkcji.")
    if "transfer" in tabs:
        with tabs["transfer"]:
            st.markdown("### Kopia danych modułu")
            payload = {"format": "system-produkcji/bobbin-settlement", "version": 1, "exported_at": datetime.now().isoformat(timespec="seconds"), "data": {k: v for k, v in data.items() if k not in ("log", "deleted_entries", "deleted_orders", "cfg_updated", "last_modified")}}
            st.download_button("⬇️ Eksportuj dane JSON", json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "rozliczenie_bobin.json", "application/json", width="stretch", on_click=lambda: event("Eksport JSON", "pełna kopia danych"))
            imported = st.file_uploader("Importuj kopię JSON", type=["json"], key="m31_import")
            if imported:
                try:
                    imported_data = json.loads(imported.getvalue().decode("utf-8")).get("data", {})
                    if not isinstance(imported_data, dict) or not isinstance(imported_data.get("orders", []), list) or not isinstance(imported_data.get("entries", []), list):
                        raise ValueError("Plik nie zawiera danych modułu 31.")
                    st.success(f"Poprawny plik: {len(imported_data['orders'])} zleceń i {len(imported_data['entries'])} wpisów.")
                    if st.button("Wczytaj plik i zastąp bieżące dane", type="primary"):
                        keep_log = data.get("log", []); data.clear(); data.update(imported_data); data["log"] = keep_log; _append_log(data, who, role, "Import danych", f"{len(imported_data.get('orders', []))} zleceń, {len(imported_data.get('entries', []))} wpisów"); data.setdefault("settings", {}); _normalize(data); deps["save_json"](deps["archive_file"], data); st.rerun(); deps["save_json"](deps["archive_file"], data); st.rerun()
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
