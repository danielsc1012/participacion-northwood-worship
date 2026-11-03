"""Genera index.html del equipo de alabanza de Northwood (Participación · Disponibilidad · Armar voces).

1. Participación: para cada plan desde el 1 de enero del año pasado, quién estuvo programado en voces,
   banda y sonido (posición y estado). También lee los planes de las próximas ~9 semanas (no cuentan
   como participación; sirven para ver quién ya está programado al armar las voces).
2. Disponibilidad: los miembros de esos equipos (según sus posiciones en Planning Center) y sus
   blockout dates, de 4 semanas atrás a ~6 meses adelante. NO se guarda el motivo del blockout.
3. Armar voces: los niveles de cada voz, guardados como tags de persona en Planning Center Services
   (grupos de tags: Vocals - Range, Vocals - Level, Vocals - Harmony, Vocals - Stage Presence).

Los conteos y vistas se hacen en el navegador (template.html).
Credenciales: PCO_APP_ID y PCO_SECRET (Personal Access Token de Planning Center).
Salida: index.html SIN cifrar en PAGE_OUT. El workflow lo cifra antes de publicarlo; nunca se commitea.
"""
import base64, calendar, json, os, re, sys, time, unicodedata, urllib.error, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

API = "https://api.planningcenteronline.com/services/v2"
TZ = ZoneInfo("America/New_York")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("PAGE_OUT", os.path.join(HERE, "index.html"))
DAYS_BACK, DAYS_AHEAD, FUTURE_PLANS = 28, 183, 63
# Eventos del proyecto "Calendario de Eventos" (repo público). La página los vuelve a leer en vivo al abrirse.
EVENTOS_URL = os.environ.get("EVENTOS_URL", "https://raw.githubusercontent.com/danielsc1012/calendario-northwood/main/eventos.json")
# Equipos que cuentan, por nombre (en cualquier tipo de servicio)
TEAM_KIND = [
    ("V", re.compile(r"^(vocals?|voces|vocal team)$", re.I)),
    ("B", re.compile(r"^(band|banda|musicians|músicos)$", re.I)),
    ("S", re.compile(r"^(sound|sonido|audio)$", re.I)),
]
RISK_EXCLUDE = {"leaders", "pastor"}
SUNDAY_HINT = re.compile(r"sunday|domin", re.I)
LEADER_POS = re.compile(r"worship leader|l[ií]der de alabanza|lead vocal|^l[ií]der$", re.I)
# Grupos de tags de persona en Planning Center Services (se buscan sin importar acentos ni mayúsculas)
LEVEL_FIELDS = {"r": "vocals range", "d": "vocals level", "a": "vocals harmony", "p": "vocals stage presence"}
# Rango: 1 Bass, 2 Baritone, 3 Tenor, 4 Alto, 5 Mezzo Soprano, 6 Soprano (mezzo se revisa antes que soprano)
RANGOS = [(5, "mezzo"), (1, "bass"), (2, "baritone"), (3, "tenor"), (4, "alto"), (6, "soprano")]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

TOKEN = base64.b64encode(f"{os.environ['PCO_APP_ID']}:{os.environ['PCO_SECRET']}".encode()).decode()
_calls = 0


def get(url, allow_404=False):
    global _calls
    if not url.startswith("http"):
        url = API + url
    for attempt in range(8):
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {TOKEN}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                _calls += 1
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", "20")) + 1)
                continue
            if e.code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            if e.code in (401, 403, 404) and allow_404:
                return None
            raise
        except urllib.error.URLError:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"No se pudo leer {url}")


def paginate(path, allow_404=False):
    url = path
    while url:
        j = get(url, allow_404)
        if j is None:
            return
        yield j
        url = j.get("links", {}).get("next")


def rel_id(obj, name):
    return ((((obj.get("relationships") or {}).get(name) or {}).get("data")) or {}).get("id")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9+\s]", " ", s).split())


# ---------- blockouts (misma lógica que Disponibilidad del Equipo) ----------
def parse_dt(s, tz):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(tz)


def hora(dt):
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d} {'am' if dt.hour < 12 else 'pm'}"


def segment(s, e, tz):
    """[fecha_inicio, fecha_fin (inclusive), hora_salida o '', hora_regreso o ''] en hora local."""
    s, e = parse_dt(s, tz), parse_dt(e, tz)
    full_start = s.hour == 0 and s.minute == 0
    if e > s and e.hour == 0 and e.minute == 0:
        e_eff, full_end = e - timedelta(seconds=1), True
    else:
        e_eff, full_end = e, (e.hour == 23 and e.minute >= 59)
    if e_eff < s:
        e_eff = s
    return [s.date().isoformat(), e_eff.date().isoformat(), "" if full_start else hora(s), "" if full_end else hora(e)]


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    if d.day > calendar.monthrange(y, m)[1]:
        return None
    return d.replace(year=y, month=m)


def expand(a, tz, limit):
    """Respaldo por si Planning Center no da las fechas de un blockout que se repite."""
    s, e = parse_dt(a["starts_at"], tz).replace(tzinfo=None), parse_dt(a["ends_at"], tz).replace(tzinfo=None)
    m = re.search(r"(\d+)", a.get("repeat_frequency") or "")
    n = int(m.group(1)) if m else 1
    period = (a.get("repeat_period") or "week").lower().rstrip("s")
    until = a.get("repeat_until")
    stop = min(limit, date.fromisoformat(until[:10])) if until else limit
    dur, out, k = e - s, [], 0
    while k < 1000:
        if period.startswith("day"):
            cur = s + timedelta(days=n * k)
        elif period.startswith("month"):
            cur = add_months(s, n * k)
        elif period.startswith("year"):
            cur = add_months(s, 12 * n * k)
        else:
            cur = s + timedelta(weeks=n * k)
        k += 1
        if cur is None:
            continue
        if cur.date() > stop:
            break
        out.append((cur.replace(tzinfo=tz).isoformat(), (cur + dur).replace(tzinfo=tz).isoformat()))
    return out


def blockouts(pid, start, end):
    segs = []
    for page in paginate(f"/people/{pid}/blockouts?per_page=100", allow_404=True):
        for b in page["data"]:
            a = b["attributes"]
            if not a.get("starts_at") or not a.get("ends_at"):
                continue
            try:
                tz = ZoneInfo(a.get("time_zone") or "America/New_York")
            except Exception:
                tz = TZ
            freq = (a.get("repeat_frequency") or "no_repeat").lower()
            if freq in ("no_repeat", "none", ""):
                occ = [(a["starts_at"], a["ends_at"])]
            else:
                occ = []
                for dp in paginate(f"/people/{pid}/blockouts/{b['id']}/blockout_dates?per_page=100", allow_404=True):
                    for x in dp["data"]:
                        xa = x["attributes"]
                        if xa.get("starts_at") and xa.get("ends_at"):
                            occ.append((xa["starts_at"], xa["ends_at"]))
                if not occ:
                    occ = expand(a, tz, end)
            for s, e in occ:
                seg = segment(s, e, tz)
                if seg[1] >= start.isoformat() and seg[0] <= end.isoformat():
                    segs.append(seg)
    return [list(x) for x in sorted({tuple(x) for x in segs})]


REHEARSAL = re.compile(r"ensamble|rehearsal|ensayo", re.I)


def rehearsals(sid, plan_id):
    """Ensayos del plan ("Ensamble (Northwood Worship)" u otro tiempo de tipo rehearsal): [[fecha, hora, nombre], ...]."""
    out = []
    for page in paginate(f"/service_types/{sid}/plans/{plan_id}/plan_times?per_page=100", allow_404=True):
        for t in page["data"]:
            a = t["attributes"]
            name = (a.get("name") or "").strip()
            if not a.get("starts_at") or not ((a.get("time_type") or "") == "rehearsal" or REHEARSAL.search(name)):
                continue
            dt = parse_dt(a["starts_at"], TZ)
            out.append([dt.date().isoformat(), hora(dt), name or "Ensayo"])
    # primero los que se llaman "Ensamble"
    return sorted(out, key=lambda x: (0 if "ensamble" in norm(x[2]) else 1, x[0], x[1]))


def load_events():
    try:
        with urllib.request.urlopen(urllib.request.Request(EVENTOS_URL, headers={"Accept": "application/json"}), timeout=30) as r:
            j = json.load(r)
        keep = ("nombre", "inicio", "fin", "publico", "grupo", "tentativo")
        evs = [{k: e[k] for k in keep if k in e} for e in j.get("eventos", []) if e.get("inicio")]
        print(f"Eventos del Calendario de Eventos: {len(evs)}")
        return evs, j.get("actualizado", "")
    except Exception as e:
        print(f"aviso · no se pudieron leer los eventos ({EVENTOS_URL}): {e}")
        return [], ""


# ---------- niveles de voces (tags de persona en Planning Center Services) ----------
def parse_level(v):
    """In Progress = 1, Good = 2, Strong = 3."""
    n = norm(v)
    if "strong" in n:
        return 3
    if "good" in n:
        return 2
    if "progress" in n:
        return 1
    return 0


def parse_harmony(v):
    """Bits: First = 1, Second = 2, Third = 4 (el grupo es de selección múltiple)."""
    n = norm(v)
    return 4 if "third" in n else 2 if "second" in n else 1 if "first" in n else 0


def parse_rango(v):
    n = norm(v)
    for k, r in RANGOS:
        if r in n.split():
            return k
    return 0


def load_levels(pids):
    """{pid: [rango, level, armonía (bits), stage presence]} (0 = sin dato) y un aviso si algo falló.

    Los niveles son tags de persona en Planning Center Services, en cuatro grupos de tags:
    Vocals - Range, Vocals - Level, Vocals - Harmony (selección múltiple) y Vocals - Stage Presence.
    Si alguien tiene dos tags de Range, Level o Stage Presence, se usa el más alto (en Range, el primero) y se avisa.
    """
    # mapa tag -> grupo, leído de todos los grupos de tags de Services (no depende de "include" por persona)
    tag_group, grupos = {}, []
    for page in paginate("/tag_groups?include=tags&per_page=100", allow_404=True):
        tags_inc = {x["id"]: x for x in page.get("included", []) if x.get("type") == "Tag"}
        for g in page["data"]:
            gname = norm(g["attributes"].get("name"))
            grupos.append(g["attributes"].get("name"))
            ids = [t["id"] for t in (((g.get("relationships") or {}).get("tags") or {}).get("data") or [])]
            if not ids:
                for tp in paginate(f"/tag_groups/{g['id']}/tags?per_page=100", allow_404=True):
                    ids += [t["id"] for t in tp["data"]]
            for tid in ids:
                tag_group[tid] = gname
    print(f"Grupos de tags en Services: {grupos}")
    grupos_vistos, out, dobles = set(), {}, []
    for pid in pids:
        vals = {}
        for page in paginate(f"/people/{pid}/tags?include=tag_group&per_page=100", allow_404=True):
            groups = {x["id"]: norm(x["attributes"].get("name")) for x in page.get("included", []) if x.get("type") == "TagGroup"}
            for t in page["data"]:
                gname = groups.get(rel_id(t, "tag_group")) or tag_group.get(t["id"], "")
                for k, want in LEVEL_FIELDS.items():
                    if gname == want or gname.startswith(want):
                        grupos_vistos.add(k)
                        vals.setdefault(k, []).append(t["attributes"].get("name") or "")
        if not vals:
            continue

        def best(k, f):
            xs = [x for x in (f(v) for v in vals.get(k, [])) if x]
            if len(xs) > 1:
                dobles.append(pid)
            return (xs[0] if k == "r" else max(xs)) if xs else 0
        harm = 0
        for v in vals.get("a", []):
            harm |= parse_harmony(v)
        out[pid] = [best("r", parse_rango), best("d", parse_level), harm, best("p", parse_level)]
    aviso = ""
    if not grupos_vistos:
        aviso = "Nadie tiene todavía tags de voces (Vocals - Range, Level, Harmony, Stage Presence) en Planning Center Services."
    if dobles:
        aviso += f" {len(set(dobles))} persona(s) tienen dos tags en Range, Level o Stage Presence; se usó el más alto."
    return out, aviso.strip()


def person_name(attrs):
    n = (attrs.get("full_name") or attrs.get("name") or "").strip()
    if not n:
        n = f"{attrs.get('first_name') or ''} {attrs.get('last_name') or ''}".strip()
    return n


def main():
    today = datetime.now(TZ).date()
    start = date(today.year - 1, 1, 1)
    fut_end = today + timedelta(days=FUTURE_PLANS)

    # ---- tipos de servicio ----
    st_ids, st_names = [], []
    for page in paginate("/service_types?per_page=100"):
        for s in page["data"]:
            st_ids.append(s["id"])
            st_names.append(s["attributes"]["name"].strip())
    sunday = [i for i, n in enumerate(st_names) if SUNDAY_HINT.search(n)]
    print(f"Tipos de servicio: {st_names} · domingos: {[st_names[i] for i in sunday]}")

    # ---- equipos que cuentan ----
    team_kind, team_name = {}, {}
    for page in paginate("/teams?per_page=100"):
        for t in page["data"]:
            name = (t["attributes"].get("name") or "").strip()
            team_name[t["id"]] = name or "Equipo"
            for kind, rx in TEAM_KIND:
                if rx.match(name):
                    team_kind[t["id"]] = kind
    print(f"Equipos de voces/banda/sonido: {len(team_kind)}")

    people, person_index, pids = [], {}, []
    positions, pos_index = [], {}

    def person_idx(pid, name):
        if pid not in person_index:
            person_index[pid] = len(people)
            people.append(name.strip())
            pids.append(pid)
        return person_index[pid]

    def pos_idx(kind, name):
        key = (kind, name)
        if key not in pos_index:
            pos_index[key] = len(positions)
            positions.append([kind, name])
        return pos_index[key]

    # ---- planes (pasados = participación; próximas semanas = ya programados) ----
    plans, assigns = [], []
    others = []  # programaciones en otros ministerios (para el riesgo); se filtran a los miembros al final
    for si, sid in enumerate(st_ids):
        url = f"/service_types/{sid}/plans?filter=after&after={start.isoformat()}&order=sort_date&per_page=100"
        n0 = len(plans)
        for page in paginate(url, allow_404=True):
            done = False
            for p in page["data"]:
                sd = (p["attributes"].get("sort_date") or "")[:10]
                if not sd:
                    continue
                d = date.fromisoformat(sd)
                if d > fut_end:
                    done = True
                    break
                if d < start:
                    continue
                title = (p["attributes"].get("title") or p["attributes"].get("series_title") or "").strip()
                pi_plan = len(plans)
                plans.append([sd, si, title, rehearsals(sid, p["id"]) if d >= today - timedelta(days=DAYS_BACK) else []])
                for mp in paginate(f"/service_types/{sid}/plans/{p['id']}/team_members?per_page=100"):
                    for m in mp["data"]:
                        a = m["attributes"]
                        tid = rel_id(m, "team")
                        kind = team_kind.get(tid)
                        pid = rel_id(m, "person")
                        if not pid or not a.get("name"):
                            continue
                        st = (a.get("status") or "U")[:1].upper()
                        if st not in "CUD":
                            st = "U"
                        if not kind:
                            # mismas reglas que el Portal de Voluntarios: "Pastor"/"Leaders" son placeholders;
                            # en el equipo Leaders solo cuenta Preacher (que no cuenta para el límite de equipos)
                            posl = (a.get("team_position_name") or "").strip().lower()
                            tname = team_name.get(tid, "Equipo")
                            if posl in RISK_EXCLUDE or (tname.strip().lower() == "leaders" and posl != "preacher"):
                                continue
                            others.append([pid, pi_plan, "Preacher" if posl == "preacher" else tname, st])
                            continue
                        pos = (a.get("team_position_name") or "Sin posición").strip()
                        assigns.append([person_idx(pid, a["name"]), pi_plan, pos_idx(kind, pos), st])
            if done:
                break
        print(f"  {st_names[si]}: {len(plans) - n0} eventos (incluye próximas {FUTURE_PLANS // 7} semanas), "
              f"{sum(1 for x in plans[n0:] if x[3])} con ensamble")

    # ---- miembros de cada equipo (por sus posiciones en Planning Center) ----
    member = {}  # pid -> {"k": set(kinds), "lead": bool}
    for tid, kind in team_kind.items():
        n_team = 0
        for tp_page in paginate(f"/teams/{tid}/team_positions?per_page=100", allow_404=True):
            for tp in tp_page["data"]:
                pos_name = (tp["attributes"].get("name") or "").strip()
                for ap in paginate(f"/teams/{tid}/team_positions/{tp['id']}/person_team_position_assignments?include=person&per_page=100", allow_404=True):
                    inc = {x["id"]: x["attributes"] for x in ap.get("included", []) if x.get("type") == "Person"}
                    for asg in ap["data"]:
                        pid = rel_id(asg, "person")
                        at = inc.get(pid, {})
                        if not pid or at.get("archived") or at.get("archived_at") or (at.get("status") or "").lower() == "inactive":
                            continue
                        name = person_name(at)
                        if not name:
                            continue
                        person_idx(pid, name)
                        m = member.setdefault(pid, {"k": set(), "lead": False})
                        m["k"].add(kind)
                        if kind == "V" and LEADER_POS.search(pos_name):
                            m["lead"] = True
                        n_team += 1
        print(f"  equipo {tid} ({kind}): {n_team} asignaciones de posición")
    # respaldo: si un equipo no tiene posiciones asignadas, usar a quien sirvió ahí en los últimos 12 meses
    recent = (today - timedelta(days=365)).isoformat()
    kinds_found = {k for m in member.values() for k in m["k"]}
    for pi, pl, po, st in assigns:
        kind, pos = positions[po]
        sd = plans[pl][0]
        if st != "C" or not (recent <= sd <= today.isoformat()):
            continue
        pid = pids[pi]
        if kind not in kinds_found:
            member.setdefault(pid, {"k": set(), "lead": False})["k"].add(kind)
    # "Dirige" = solo quien tiene una posición de líder en el equipo de voces en Planning Center (decisión de Daniel, 2026-11-03)
    if not member:
        sys.exit("No se encontraron miembros de voces, banda ni sonido.")
    print(f"Pueden dirigir (posición de líder en voces): {sum(1 for m in member.values() if m['lead'])}")
    print(f"Miembros: {len(member)} (voces {sum('V' in m['k'] for m in member.values())}, "
          f"banda {sum('B' in m['k'] for m in member.values())}, sonido {sum('S' in m['k'] for m in member.values())})")

    # ---- blockouts ----
    events, ev_upd = load_events()
    d_start, d_end = today - timedelta(days=DAYS_BACK), today + timedelta(days=DAYS_AHEAD)
    roster = []
    for pid, m in member.items():
        b = blockouts(pid, d_start, d_end)
        roster.append({"i": person_index[pid], "k": "".join(k for k in "VBS" if k in m["k"]), "lead": int(m["lead"]), "b": b})
    print(f"Blockouts leídos: {sum(len(r['b']) for r in roster)} en {sum(1 for r in roster if r['b'])} personas")

    # ---- niveles de las voces ----
    vocal_pids = [pids[r["i"]] for r in roster if "V" in r["k"]]
    levels, lv_warn = load_levels(vocal_pids)
    for r in roster:
        lv = levels.get(pids[r["i"]])
        if lv and any(lv):
            r["lv"] = lv
    print(f"Niveles: {sum(1 for r in roster if r.get('lv'))}/{len(vocal_pids)} voces con datos" + (f" · aviso: {lv_warn}" if lv_warn else ""))

    # ---- otros ministerios de los miembros (para la pestaña Riesgo) ----
    ot_names, ot_idx, ro, seen = [], {}, [], set()
    for pid, pl, tname, st in others:
        if pid not in member:
            continue
        if tname not in ot_idx:
            ot_idx[tname] = len(ot_names)
            ot_names.append(tname)
        key = (pid, pl, tname)
        if key in seen:
            continue
        seen.add(key)
        ro.append([person_index[pid], pl, ot_idx[tname], st])
    print(f"Otros ministerios de los miembros: {len(ro)} programaciones en {len(ot_names)} equipos")

    data = {"gen": today.isoformat(), "start": start.isoformat(), "st": st_names, "sunday": sunday,
            "plans": plans, "people": people, "pid": pids, "pos": positions, "a": assigns,
            "roster": roster, "dstart": d_start.isoformat(), "dend": d_end.isoformat(),
            "ev": events, "evUpd": ev_upd, "evUrl": EVENTOS_URL, "lvWarn": lv_warn,
            "ro": ro, "otn": ot_names, "nolimit": ["preacher"]}
    updated = f"{today.day} de {MESES[today.month - 1]} de {today.year}"
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("__UPDATED__", updated).replace(
        "__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html generado: {len(people)} personas, {len(plans)} eventos, {len(assigns)} programaciones, "
          f"{len(roster)} miembros, {_calls} consultas.")
    if not people:
        sys.exit("No se encontró a nadie programado: revisa las credenciales o los nombres de los equipos.")


if __name__ == "__main__":
    main()
