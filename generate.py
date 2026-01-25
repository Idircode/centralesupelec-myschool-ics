from __future__ import annotations

import requests
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from dateutil import parser as dtparser
from ics import Calendar, Event
from ics.grammar.parse import ContentLine


API_URL = "https://myschool.centralesupelec.fr/plannings/api/events/resources"
PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True)
class Room:
    id: int
    slug: str
    name: str


# ✅ Mets ici toutes les salles
ROOMS: list[Room] = [
    Room(id=436, slug="e090", name="e.090, Bouygues"),
    # Room(id=437, slug="e091", name="e.091, Bouygues"),
    # ...
]


def to_myschool_z(dt: datetime, end: bool = False) -> str:
    """
    MySchool aime bien des timestamps comme Chrome:
      - start: ...SS.000Z
      - end:   ...SS.999Z
    """
    dt = dt.astimezone(timezone.utc)
    if end:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.999Z")
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def week_window_paris(n_weeks: int = 2) -> tuple[datetime, datetime]:
    """
    Fenêtre alignée sur les semaines (heure Paris) :
    start = lundi 00:00 Paris
    end   = dimanche 23:59:59.999 Paris (sur n_weeks)
    """
    now_paris = datetime.now(PARIS)
    monday = (now_paris - timedelta(days=now_paris.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_paris = monday
    end_paris = monday + timedelta(days=7 * n_weeks) - timedelta(milliseconds=1)

    return start_paris.astimezone(timezone.utc), end_paris.astimezone(timezone.utc)


def fetch_events(room_id: int, start_utc: datetime, end_utc: datetime) -> dict:
    params = {
        "dateStart": to_myschool_z(start_utc, end=False),
        "dateEnd": to_myschool_z(end_utc, end=True),
        "expand": "true",
        "withTitle": "true",
        "rooms[]": str(room_id),
    }
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def build_calendar_from_payload(payload: dict, cal_name: str, default_location: str) -> Calendar:
    cal = Calendar()
    cal.extra.append(ContentLine(name="X-WR-CALNAME", value=cal_name))

    for ev in payload.get("data", []):
        name = ev.get("name", "Réservation")
        rooms = ev.get("rooms", [])
        location = rooms[0]["name"] if rooms else default_location
        ev_id = ev.get("id", "unknown")

        # Ton format: sessions[]
        for s in ev.get("sessions", []):
            start_str = s.get("start")
            end_str = s.get("end")
            if not start_str or not end_str:
                continue

            e = Event()
            e.name = name
            e.begin = dtparser.isoparse(start_str)
            e.end = dtparser.isoparse(end_str)
            e.location = location
            e.uid = f"myschool-{ev_id}-{start_str}"  # stable
            cal.events.add(e)

    return cal


def write_calendar(cal: Calendar, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cal.serialize(), encoding="utf-8")


def main() -> None:
    if not ROOMS:
        raise SystemExit("Aucune salle définie dans ROOMS.")

    start_utc, end_utc = week_window_paris(n_weeks=2)
    print("Window UTC:", to_myschool_z(start_utc), "->", to_myschool_z(end_utc, end=True))

    out_dir = Path("calendars")
    all_cal = Calendar()
    all_cal.extra.append(ContentLine(name="X-WR-CALNAME", value="MySchool – Music Rooms (ALL)"))

    total_vevents = 0

    for room in ROOMS:
        payload = fetch_events(room.id, start_utc, end_utc)
        meta_title = (payload.get("meta") or {}).get("title")

        cal = build_calendar_from_payload(
            payload=payload,
            cal_name=f"MySchool – {room.name}",
            default_location=room.name,
        )

        room_path = out_dir / f"{room.slug}.ics"
        write_calendar(cal, room_path)

        # merge ALL
        for e in cal.events:
            all_cal.events.add(e)

        total_vevents += len(cal.events)
        print(f"[{room.slug}] meta.title={meta_title} | data={len(payload.get('data', []))} | vevents={len(cal.events)}")

    write_calendar(all_cal, out_dir / "ALL.ics")
    print(f"✅ Done: {len(ROOMS)} rooms + ALL. Total VEVENTs={total_vevents}")


if __name__ == "__main__":
    main()
