"""Genera index.html de Participación (voces, banda y sonido) de Northwood a partir de Planning Center.

Lee todos los tipos de servicio y, para cada plan desde el 1 de enero del año pasado hasta hoy,
quién estuvo programado en los equipos de voces, banda y sonido (posición y estado).
Los conteos se hacen en el navegador (template.html) para poder filtrar por periodo,
tipo de evento y equipo sin volver a correr esto.

Credenciales: PCO_APP_ID y PCO_SECRET (Personal Access Token de Planning Center).
Salida: index.html SIN cifrar en PAGE_OUT. El workflow lo cifra antes de publicarlo; nunca se commitea.
"""
import base64, json, os, re, sys, time, urllib.error, urllib.request
from datetime import date, datetime, timedelta, timezone

API = "https://api.planningcenteronline.com/services/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("PAGE_OUT", os.path.join(HERE, "index.html"))
# Equipos que cuentan, por nombre (en cualquier tipo de servicio)
TEAM_KIND = [
    ("V", re.compile(r"^(vocals?|voces|vocal team)$", re.I)),
    ("B", re.compile(r"^(band|banda|musicians|músicos)$", re.I)),
    ("S", re.compile(r"^(sound|sonido|audio)$", re.I)),
]
SUNDAY_HINT = re.compile(r"sunday|domin", re.I)

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
            if e.code in (403, 404) and allow_404:
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


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def main():
    today = datetime.now(timezone(timedelta(hours=-5))).date()
    start = date(today.year - 1, 1, 1)

    # ---- tipos de servicio ----
    st_ids, st_names = [], []
    for page in paginate("/service_types?per_page=100"):
        for s in page["data"]:
            st_ids.append(s["id"])
            st_names.append(s["attributes"]["name"].strip())
    sunday = [i for i, n in enumerate(st_names) if SUNDAY_HINT.search(n)]
    print(f"Tipos de servicio: {st_names} · domingos: {[st_names[i] for i in sunday]}")

    # ---- equipos que cuentan ----
    team_kind = {}
    for page in paginate("/teams?per_page=100"):
        for t in page["data"]:
            name = (t["attributes"].get("name") or "").strip()
            for kind, rx in TEAM_KIND:
                if rx.match(name):
                    team_kind[t["id"]] = kind
    print(f"Equipos de voces/banda/sonido: {len(team_kind)}")

    people, person_index = [], {}
    positions, pos_index = [], {}

    def person_idx(pid, name):
        if pid not in person_index:
            person_index[pid] = len(people)
            people.append(name.strip())
        return person_index[pid]

    def pos_idx(kind, name):
        key = (kind, name)
        if key not in pos_index:
            pos_index[key] = len(positions)
            positions.append([kind, name])
        return pos_index[key]

    plans, assigns = [], []
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
                if d > today:
                    done = True
                    break
                if d < start:
                    continue
                title = (p["attributes"].get("title") or p["attributes"].get("series_title") or "").strip()
                pi_plan = len(plans)
                plans.append([sd, si, title])
                for mp in paginate(f"/service_types/{sid}/plans/{p['id']}/team_members?per_page=100"):
                    for m in mp["data"]:
                        a = m["attributes"]
                        kind = team_kind.get(rel_id(m, "team"))
                        pid = rel_id(m, "person")
                        if not kind or not pid or not a.get("name"):
                            continue
                        st = (a.get("status") or "U")[:1].upper()
                        if st not in "CUD":
                            st = "U"
                        pos = (a.get("team_position_name") or "Sin posición").strip()
                        assigns.append([person_idx(pid, a["name"]), pi_plan, pos_idx(kind, pos), st])
            if done:
                break
        print(f"  {st_names[si]}: {len(plans) - n0} eventos")

    data = {"gen": today.isoformat(), "start": start.isoformat(), "st": st_names, "sunday": sunday,
            "plans": plans, "people": people, "pos": positions, "a": assigns}
    updated = f"{today.day} de {MESES[today.month - 1]} de {today.year}"
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("__UPDATED__", updated).replace(
        "__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html generado: {len(people)} personas, {len(plans)} eventos, {len(assigns)} programaciones, {_calls} consultas.")
    if not people:
        sys.exit("No se encontró a nadie programado: revisa las credenciales o los nombres de los equipos.")


if __name__ == "__main__":
    main()
