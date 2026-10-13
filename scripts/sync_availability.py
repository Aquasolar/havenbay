#!/usr/bin/env python3
"""Holt die iCal-Kalender von Booking/Airbnb und schreibt availability.json.

Die Feed-URLs stehen NICHT im Repository, sondern als GitHub-Secrets
(ICAL_STUDIO, ICAL_APARTMENT; mehrere URLs durch Leerzeichen/Zeilenumbruch getrennt).
Optional: ICAL_ADMIN (geheime iCal-Adresse des Admin-Kalenders; Direktbuchungen/Blockungen mit
Titel "Studio · Direkt · Name" bzw. "Apartment · Blockiert · Grund" sperren die Einheit) sowie
ICAL_DIRECT_STUDIO / ICAL_DIRECT_APARTMENT.
Ausgegeben werden nur Datumsbereiche [Anreise, Abreise) - keine Gästedaten.
"""
import csv, io, json, os, re, sys, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

UNITS = {"studio": "ICAL_STUDIO", "apartment": "ICAL_APARTMENT"}
DIRECT = {"studio": "ICAL_DIRECT_STUDIO", "apartment": "ICAL_DIRECT_APARTMENT"}  # optional: Direktbuchungen (Google-Kalender)
ROOT = Path(__file__).resolve().parents[1]


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


ADMIN_RE = re.compile(r"^\s*(studio\s*\+\s*apartment|studio|apartment)\s*[·|:\-–]\s*(direkt|blockiert)\b", re.I)


def parse_admin_ical(text):
    """Liest den Admin-Kalender: nur Termine 'Studio|Apartment|Studio + Apartment · Direkt|Blockiert ...'.
    Alle anderen Termine (Airbnb, Booking, Vorbereitung) werden ignoriert. Liefert {unit: [(start, end)]}."""
    out = {"studio": [], "apartment": []}
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfold(text), re.S):
        props = {}
        for line in block.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                props[key.split(";")[0].upper()] = val
        if props.get("STATUS", "").upper() == "CANCELLED":
            continue
        m = ADMIN_RE.match(props.get("SUMMARY", "").replace("\\,", ","))
        start = parse_date(props.get("DTSTART", ""))
        if not m or not start:
            continue
        end = parse_date(props.get("DTEND", ""))
        if not end or end <= start:
            end = start + timedelta(days=1)
        unit = m.group(1).lower().replace(" ", "")
        for u in (("studio", "apartment") if "+" in unit else (unit,)):
            out[u].append((start, end))
    return out


def merge(ranges, today):
    ranges = sorted((s, e) for s, e in ranges if e > today)
    out = []
    for s, e in ranges:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def load_ops():
    p = ROOT / "content" / "operations.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def in_free(d, free_ranges):
    for a, b in free_ranges:
        if date.fromisoformat(a) <= d <= date.fromisoformat(b):
            return True
    return False


def add_cleaning_buffer(ranges, ops, today):
    """Reinigungstag: Endet ein Aufenthalt an einem Werktag (Abreisetag), ist diese Nacht ebenfalls gesperrt,
    außer an freien Tagen (Wochenende, Urlaub mit Lenka vor Ort). Gibt (alle_Sperren, nur_Puffer) zurück."""
    cb = ops.get("cleaning_buffer") or {}
    weekdays = set(cb.get("weekdays", []))
    free = cb.get("free_dates", [])
    buffers = []
    for s, e in ranges:
        if e >= today and e.weekday() in weekdays and not in_free(e, free):
            buffers.append((e, e + timedelta(days=1)))
    return merge(list(ranges) + buffers, today), merge(buffers, today)


def parse_date_any(v):
    v = (v or "").strip()
    if not v:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", v)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", v)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1]))
    raise ValueError("Datum nicht lesbar")


def parse_price_csv(text):
    """Tabelle mit Spalten: von, bis (optional), studio, apartment, bezeichnung (optional).
    Gilt je Nacht von..bis (beide inklusive). Leere Preise werden ignoriert.
    Spalte status: Zeilen mit status=vorschlag werden übersprungen."""
    units = {"studio": {}, "apartment": {}}
    events = []
    rdr = csv.DictReader(io.StringIO(text))
    rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in rdr]
    for r in rows:
        if r.get("status", "").lower() in ("vorschlag", "vorschläge", "entwurf", "draft"):
            continue  # Bot-Vorschläge erscheinen erst nach Freigabe
        a = parse_date_any(r.get("von") or r.get("from") or r.get("datum") or r.get("date"))
        if not a:
            continue
        b = parse_date_any(r.get("bis") or r.get("to")) or a
        label = r.get("bezeichnung") or r.get("label") or ""
        got = False
        for u in units:
            v = r.get(u, "").replace(",", ".").replace("€", "").strip()
            if not v:
                continue
            price = float(v)
            price = int(price) if price == int(price) else price
            d = a
            while d <= b:
                units[u][d.isoformat()] = price
                d += timedelta(days=1)
            got = True
        if got and label:
            events.append({"from": a.isoformat(), "to": b.isoformat(), "label": label})
    return {"units": units, "events": events}


def ical_blocks(ranges, name):
    """iCal-Datei nur mit Datumsbereichen (keine Gästedaten)."""
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Haven Bay//Blocks//EN", "CALSCALE:GREGORIAN"]
    for i, (s, e) in enumerate(ranges):
        out += ["BEGIN:VEVENT", f"UID:hb-{name}-{s.isoformat()}-{i}@havenbay.eu",
                f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART;VALUE=DATE:{s.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{e.strftime('%Y%m%d')}",
                "SUMMARY:Blocked", "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "havenbay-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main(out_path):
    today = date.today()
    ops = load_ops()
    outdir = os.path.dirname(out_path) or "."
    result = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "units": {}}
    exports = {}
    failed = False
    admin = {"studio": [], "apartment": []}
    admin_url = os.environ.get("ICAL_ADMIN", "").strip()
    if admin_url:  # optional: geheime iCal-Adresse des Kalenders "Haven Bay Admin"
        try:
            admin = parse_admin_ical(fetch(admin_url))
        except Exception as exc:
            print(f"FEHLER: Admin-Kalender nicht ladbar ({type(exc).__name__}).", file=sys.stderr)
            failed = True
    for unit, env in UNITS.items():
        urls = os.environ.get(env, "").split()
        if not urls:
            print(f"FEHLER: Secret {env} fehlt oder ist leer.", file=sys.stderr)
            failed = True
            continue
        platform_ranges = []
        for i, url in enumerate(urls, 1):
            try:
                platform_ranges += parse_ical(fetch(url))
            except Exception as exc:  # URL nie ausgeben
                print(f"FEHLER: {unit} Feed {i} nicht ladbar ({type(exc).__name__}).", file=sys.stderr)
                failed = True
        direct_ranges = list(admin[unit])
        for i, url in enumerate(os.environ.get(DIRECT[unit], "").split(), 1):
            try:
                direct_ranges += parse_ical(fetch(url))
            except Exception as exc:
                print(f"FEHLER: {unit} Direktkalender {i} nicht ladbar ({type(exc).__name__}).", file=sys.stderr)
                failed = True
        everything = merge(platform_ranges + direct_ranges, today)
        blocked, buffers = add_cleaning_buffer(everything, ops, today)
        result["units"][unit] = [[s.isoformat(), e.isoformat()] for s, e in blocked]
        # Export für Plattformen: nur Direktbuchungen und Reinigungstage (nie deren eigene Buchungen zurückspielen)
        exports[unit] = merge(direct_ranges + buffers, today)
    # Tagespreise aus veröffentlichter Google-Tabelle (optional)
    daily = {"updated": result["updated"], "units": {"studio": {}, "apartment": {}}, "events": []}
    csv_url = os.environ.get("PRICES_CSV_URL", "").strip()
    if csv_url:
        try:
            parsed = parse_price_csv(fetch(csv_url))
            daily["units"], daily["events"] = parsed["units"], parsed["events"]
        except Exception as exc:
            print(f"FEHLER: Preistabelle nicht lesbar ({type(exc).__name__}).", file=sys.stderr)
            failed = True
    if failed:
        return 1
    os.makedirs(outdir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(os.path.join(outdir, "daily-prices.json"), "w", encoding="utf-8") as f:
        json.dump(daily, f, ensure_ascii=False, indent=1)
    token = os.environ.get("ICAL_EXPORT_TOKEN", "").strip()
    if token:
        d = os.path.join(outdir, "ical", token)
        os.makedirs(d, exist_ok=True)
        for unit, rng in exports.items():
            with open(os.path.join(d, f"{unit}.ics"), "w", encoding="utf-8", newline="") as f:
                f.write(ical_blocks(rng, unit))
    print("availability.json geschrieben:", {k: len(v) for k, v in result["units"].items()},
          "| Tagespreise:", {k: len(v) for k, v in daily["units"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "build/availability.json"))
