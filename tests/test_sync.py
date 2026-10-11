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

if __name__ == "__main__":
    unittest.main()
