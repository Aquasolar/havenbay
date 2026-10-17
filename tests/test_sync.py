import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_availability as s

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE:20270110
DTEND;VALUE=DATE:20270114
SUMMARY:CLOSED - Not available
END:VEVENT
BEGIN:VEVENT
DTSTART:20270114T000000Z
DTEND:20270117T000000Z
SUMMARY:Reserved
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20270201
DTEND;VALUE=DATE:20270205
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20200101
DTEND;VALUE=DATE:20200105
END:VEVENT
END:VCALENDAR
"""

class T(unittest.TestCase):
    def test_parse_merge(self):
        r = s.merge(s.parse_ical(ICS), date(2026, 10, 11))
        self.assertEqual(r, [(date(2027, 1, 10), date(2027, 1, 17))])
    def test_no_end(self):
        r = s.parse_ical("BEGIN:VEVENT\nDTSTART;VALUE=DATE:20270301\nEND:VEVENT")
        self.assertEqual(r, [(date(2027, 3, 1), date(2027, 3, 2))])



class T2(unittest.TestCase):
    def test_buffer_weekday_only(self):
        # Abreise Mittwoch 2027-01-13 -> Puffer; Abreise Samstag 2027-01-16 -> kein Puffer
        ops = {"cleaning_buffer": {"weekdays": [0, 1, 2, 3, 4], "free_dates": []}}
        r = [(date(2027, 1, 10), date(2027, 1, 13)), (date(2027, 1, 20), date(2027, 1, 23))]
        blocked, buf = s.add_cleaning_buffer(r, ops, date(2026, 10, 11))
        self.assertIn((date(2027, 1, 10), date(2027, 1, 14)), blocked)
        self.assertIn((date(2027, 1, 20), date(2027, 1, 23)), blocked)
        self.assertEqual(buf, [(date(2027, 1, 13), date(2027, 1, 14))])

    def test_buffer_free_dates(self):
        ops = {"cleaning_buffer": {"weekdays": [0, 1, 2, 3, 4], "free_dates": [["2027-08-01", "2027-08-31"]]}}
        blocked, buf = s.add_cleaning_buffer([(date(2027, 8, 10), date(2027, 8, 12))], ops, date(2026, 10, 11))
        self.assertEqual(buf, [])

    def test_price_csv(self):
        txt = "von,bis,studio,apartment,bezeichnung\n13.08.2027,15.08.2027,150,\"190,5\",Lada Marathon\n2027-09-01,,99,,\n"
        d = s.parse_price_csv(txt)
        self.assertEqual(d["units"]["studio"]["2027-08-14"], 150)
        self.assertEqual(d["units"]["apartment"]["2027-08-15"], 190.5)
        self.assertEqual(d["units"]["studio"]["2027-09-01"], 99)
        self.assertNotIn("2027-09-01", d["units"]["apartment"])
        self.assertEqual(d["events"], [{"from": "2027-08-13", "to": "2027-08-15", "label": "Lada Marathon"}])

    def test_price_csv_skips_proposals(self):
        txt = "von,bis,studio,apartment,bezeichnung,status\n2027-05-01,,70,80,,vorschlag\n2027-05-02,,71,81,,freigegeben\n"
        d = s.parse_price_csv(txt)
        self.assertNotIn("2027-05-01", d["units"]["studio"])
        self.assertEqual(d["units"]["studio"]["2027-05-02"], 71)

    def test_admin_calendar_only_direct_and_blocked(self):
        def ev(summary, a, b):
            return f"BEGIN:VEVENT\nDTSTART;VALUE=DATE:{a}\nDTEND;VALUE=DATE:{b}\nSUMMARY:{summary}\nEND:VEVENT\n"
        txt = ("BEGIN:VCALENDAR\n" + ev("Studio · Direkt · Müller", "20270803", "20270814")
               + ev("Apartment - Blockiert - Reparatur", "20270820", "20270830")
               + ev("Studio + Apartment · direkt · Familie", "20271001", "20271004")
               + ev("Studio · Booking · Eva G. · 2 Nächte", "20270101", "20270103")
               + ev("Vorbereitung · Studio", "20270105", "20270106") + "END:VCALENDAR\n")
        r = s.parse_admin_ical(txt)
        self.assertEqual(r["studio"], [(date(2027, 8, 3), date(2027, 8, 14)), (date(2027, 10, 1), date(2027, 10, 4))])
        self.assertEqual(r["apartment"], [(date(2027, 8, 20), date(2027, 8, 30)), (date(2027, 10, 1), date(2027, 10, 4))])

    def test_ical_blocks_no_guest_data(self):
        out = s.ical_blocks([(date(2027, 1, 13), date(2027, 1, 14))], "studio")
        self.assertIn("DTSTART;VALUE=DATE:20270113", out)
        self.assertNotIn("Reserved", out)

    def test_feed_down_keeps_last_state(self):
        """K5: fällt ein Feed aus, bricht der Abgleich ab (alte Seite bleibt online), nichts wird geschrieben, keine URL im Protokoll."""
        import io, os, tempfile, contextlib
        from unittest import mock
        secret = "https://example.invalid/geheim-token-123.ics"
        def fake_fetch(url):
            if url == secret:
                raise OSError("down")
            return ICS
        env = {"ICAL_STUDIO": secret, "ICAL_APARTMENT": "https://example.invalid/ok.ics", "ICAL_ADMIN": "", "PRICES_CSV_URL": ""}
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, env), mock.patch.object(s, "fetch", fake_fetch):
            out = os.path.join(d, "availability.json")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = s.main(out)
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(out))
            self.assertNotIn("geheim", err.getvalue())


if __name__ == "__main__":
    unittest.main()
