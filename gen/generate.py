import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright
from ics import Calendar, Event
from ics.grammar.parse import ContentLine

LOGIN_URL = "https://myschool.centralesupelec.fr/plannings/login"
API_URL = "https://myschool.centralesupelec.fr/plannings/api/events/resources"

PARIS = ZoneInfo("Europe/Paris")

ROOMS = [
    {"id": 436, "slug": "e090", "name": "e.090, Bouygues"},
    {"id": 437, "slug": "e091", "name": "e.091, Bouygues"},
    {"id": 433, "slug": "e008", "name": "e.008, Bouygues"},
    {"id": 434, "slug": "e010", "name": "e.010, Bouygues"},
    {"id": 435, "slug": "e012", "name": "e.012, Bouygues"},
]

def window_myschool(lookback_days: int = 5, horizon_days: int = 10) -> tuple[str, str]:
    now_paris = datetime.now(PARIS)

    # Dates (sans l'heure)
    start_date = (now_paris - timedelta(days=lookback_days)).date()
    end_date   = (now_paris + timedelta(days=horizon_days)).date()

    # Bornes en heure de Paris (début/fin de journée)
    start_paris = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, 0, tzinfo=PARIS)
    end_paris   = datetime(end_date.year,   end_date.month,   end_date.day,   23, 59, 59, 999_000, tzinfo=PARIS)

    # Convert UTC
    start_utc = start_paris.astimezone(timezone.utc)
    end_utc   = end_paris.astimezone(timezone.utc)

    # Format exact MySchool
    date_start = start_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    date_end   = end_utc.strftime("%Y-%m-%dT%H:%M:%S.999Z")

    return date_start, date_end

def login(page, username, password):
    page.goto(LOGIN_URL, wait_until="domcontentloaded")

    page.fill("#username", username)
    page.fill("#password", password)

    page.locator("button[type='submit'], input[type='submit']").click()

    # Attendre un signe de succès : URL qui n'est plus /login
    page.wait_for_function(
        "() => !location.pathname.endsWith('/plannings/login')",
        timeout=120_000
    )

    # Petite stabilisation
    page.wait_for_timeout(1000)

def capture_bearer_from_app(page) -> str:
    page.goto("https://myschool.centralesupelec.fr/plannings/", wait_until="domcontentloaded")

    for _ in range(2):  # goto + reload si besoin
        try:
            with page.expect_request(
                lambda r: (r.headers.get("authorization") or "").startswith("Bearer "),
                timeout=60_000,
            ) as req_info:
                page.reload(wait_until="domcontentloaded")

            req = req_info.value
            return req.headers["authorization"].split(" ", 1)[1]

        except Exception:
            pass

    raise RuntimeError("Aucun Bearer capturé (aucune requête Authorization observée).")

def fetch_json(page, room_id, date_start, date_end, token):
    params = {
        "dateStart": date_start,
        "dateEnd": date_end,
        "expand": "true",
        "withTitle": "true",
        "rooms[]": str(room_id),
    }
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    resp = page.request.get(API_URL, params=params, headers=headers)
    if not resp.ok:
        raise RuntimeError(f"API error {resp.status}: {resp.text()[:200]}")
    return resp.json()

def json_to_ics(payload: dict, cal_name: str, default_location: str) -> Calendar:
    cal = Calendar()
    cal.extra.append(ContentLine(name="X-WR-CALNAME", value=cal_name))

    for ev in payload.get("data", []):
        title = ev.get("name", "Réservation")

        rooms = ev.get("rooms") or []
        location = rooms[0].get("name") if rooms else default_location
        room_link = rooms[0].get("mapwizeLink") if rooms else None

        author = ev.get("author") or {}
        author_name = " ".join(filter(None, [author.get("firstname"), author.get("lastname")]))

        description = f"Réservé par : {author_name}".strip()
        if room_link:
            description += f"\nPlan salle : {room_link}"

        for s in ev.get("sessions", []):
            start_str, end_str = s.get("start"), s.get("end")
            if not start_str or not end_str:
                continue

            e = Event()
            e.name = title
            e.begin = datetime.fromisoformat(start_str)  # gère +01:00
            e.end = datetime.fromisoformat(end_str)
            e.location = location
            e.description = description
            if room_link:
                e.url = room_link

            cal.events.add(e)

    return cal

def main() -> None:
    username = os.environ["MYSCHOOL_USERNAME"]
    password = os.environ["MYSCHOOL_PASSWORD"]
    date_start, date_end = window_myschool(lookback_days=5, horizon_days=10)
    out_dir = Path("calendars"); out_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        login(page, username, password)
        token = capture_bearer_from_app(page)

        for room in ROOMS:
            payload = fetch_json(page, room["id"], date_start, date_end, token)
            cal = json_to_ics(payload, f"{room['name']}", room["name"])
            (out_dir / f"{room['slug']}.ics").write_text(cal.serialize(), encoding="utf-8")

        browser.close()


if __name__ == "__main__":
    main()
