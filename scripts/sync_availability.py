#!/usr/bin/env python3
"""Holt die iCal-Kalender von Booking/Airbnb und schreibt availability.json.

Die Feed-URLs stehen NICHT im Repository, sondern als GitHub-Secrets
(ICAL_STUDIO, ICAL_APARTMENT; mehrere URLs durch Leerzeichen/Zeilenumbruch getrennt).
Ausgegeben werden nur Datumsbereiche [Anreise, Abreise) - keine Gästedaten.
"""
import json, os, re, sys, urllib.request
from datetime import date, datetime, timedelta, timezone

UNITS = {"studio": "ICAL_STUDIO", "apartment": "ICAL_APARTMENT"}


def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def parse_date(value):
    value = value.strip()
    m = re.match(r"(\d{4})(\d{2})(\d{2})", value)
    if not m:
        return None
    return date(int(m[1]), int(m[2]), int(m[3]))


def parse_ical(text):
    """Liefert Liste (start, end) mit exklusivem Ende; stornierte Events werden ignoriert."""
    ranges = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfold(text), re.S):
        props = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            props[key.split(";")[0].upper()] = val
        if props.get("STATUS", "").upper() == "CANCELLED":
            continue
        start = parse_date(props.get("DTSTART", ""))
        end = parse_date(props.get("DTEND", ""))
        if not start:
            continue
        if not end or end <= start:
            end = start + timedelta(days=1)
        ranges.append((start, end))
    return ranges


def merge(ranges, today):
    ranges = sorted((s, e) for s, e in ranges if e > today)
    out = []
    for s, e in ranges:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "havenbay-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main(out_path):
    today = date.today()
    result = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "units": {}}
    failed = False
    for unit, env in UNITS.items():
        urls = os.environ.get(env, "").split()
        if not urls:
            print(f"FEHLER: Secret {env} fehlt oder ist leer.", file=sys.stderr)
            failed = True
            continue
        all_ranges = []
        for i, url in enumerate(urls, 1):
            try:
                all_ranges += parse_ical(fetch(url))
            except Exception as exc:  # URL nie ausgeben
                print(f"FEHLER: {unit} Feed {i} nicht ladbar ({type(exc).__name__}).", file=sys.stderr)
                failed = True
        result["units"][unit] = [[s.isoformat(), e.isoformat()] for s, e in merge(all_ranges, today)]
    if failed:
        return 1
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("availability.json geschrieben:", {k: len(v) for k, v in result["units"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "build/availability.json"))
