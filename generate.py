from __future__ import annotations

import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests
import yaml
from dateutil import parser as dtparser
from ics import Calendar, Event
from ics.grammar.parse import ContentLine


API_URL = "https://myschool.centralesupelec.fr/plannings/api/events/resources"


def fetch_room_events(room_id: int, start_utc: datetime, end_utc: datetime) -> dict:
    params = {
        "dateStart": start_utc.isoformat().replace("+00:00", "Z"),
        "dateEnd": end_utc.isoformat().replace("+00:00", "Z"),
        "expand": "true",
        "withTitle": "true",
        "rooms[]": str(room_id),
    }
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def stable_uid(*parts: str) -> str:
    h = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"myschool-{h}"


def json_to_calendar(payload: dict, cal_name: str) -> Calendar:
    cal = Calendar()
    cal.extra.append(ContentLine(name="X-WR-CALNAME", value=cal_name))

    for item in payload.get("data", []):
        event_name = item.get("name") or "Réservation"
        rooms = item.get("rooms") or []
        location = rooms[0].get("name") if rooms else payload.get("meta", {}).get("title", "")

        # Certains items ont sessions[], sinon start/end directement
        sessions = item.get("sessions")
        if sessions:
            iter_sessions = sessions
        else:
            iter_sessions = [item]

        for s in iter_sessions:
            start_str = s.get("start")
            end_str = s.get("end")
            if not start_str or not end_str:
                continue

            start = dtparser.isoparse(start_str)
            end = dtparser.isoparse(end_str)

            e = Event()
            e.name = event_name
            e.begin = start
            e.end = end
            e.location = location

            # UID stable pour que Google fasse les updates correctement
            base_id = str(item.get("id", ""))
            e.uid = stable_uid(base_id, start_str, end_str, location, event_name)

            cal.events.add(e)

    return cal


def main() -> None:
    root = Path(__file__).parent
    cfg = yaml.safe_load((root / "rooms.yaml").read_text(encoding="utf-8"))

    horizon_days = int(cfg.get("horizon_days", 45))
    lookback_days = int(cfg.get("lookback_days", 2))
    tz_name = cfg.get("timezone", "Europe/Paris")

    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(days=lookback_days)
    end_utc = now_utc + timedelta(days=horizon_days)

    out_dir = root / "calendars"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_cal = Calendar()
    all_cal.extra.append(ContentLine(name="X-WR-CALNAME", value="MySchool – Music Rooms (ALL)"))

    rooms = cfg.get("rooms", [])
    if not rooms:
        raise SystemExit("rooms.yaml: aucune salle définie.")

    for room in rooms:
        room_id = int(room["id"])
        slug = room["slug"]
        room_name = room["name"]

        payload = fetch_room_events(room_id, start_utc, end_utc)
        cal = json_to_calendar(payload, cal_name=f"MySchool – {room_name}")

        # Write per-room file
        (out_dir / f"{slug}.ics").write_text(cal.serialize(), encoding="utf-8")

        # Merge into ALL calendar
        for ev in cal.events:
            all_cal.events.add(ev)

    (out_dir / "ALL.ics").write_text(all_cal.serialize(), encoding="utf-8")

    print(f"OK: ICS générés dans {out_dir} (timezone ref: {tz_name}).")


if __name__ == "__main__":
    main()
