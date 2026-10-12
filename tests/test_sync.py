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

    def test_ical_blocks_no_guest_data(self):
        out = s.ical_blocks([(date(2027, 1, 13), date(2027, 1, 14))], "studio")
        self.assertIn("DTSTART;VALUE=DATE:20270113", out)
        self.assertNotIn("Reserved", out)


if __name__ == "__main__":
    unittest.main()
