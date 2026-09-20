import json
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
import generate_earnings as earnings
from salary_pending import add_pending_estimates

ROOT = Path(__file__).resolve().parent

class Markup(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.keys = Counter()
        self.badges = Counter()
        self.pending = []
        self.feed(path.read_text(encoding="utf-8"))
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get("class", "").split()
        if "lesson-log-open" in classes:
            self.keys[a["data-log-key"]] += 1
        if "class-id" in classes and "card-course-filter" in classes:
            self.badges[a["data-card-group"]] += 1
        if "pending-course" in classes:
            self.pending.append(a["data-card-group"])

class PendingReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = json.loads((ROOT/"events.json").read_text(encoding="utf-8")) + json.loads((ROOT/"class_context.json").read_text(encoding="utf-8"))
        for event in cls.events:
            event.setdefault("category", "methodist" if "循道" in event["text"] or "MC0106" in event["text"] else "erb")
        cls.context = json.loads((ROOT/"payment_context.json").read_text(encoding="utf-8"))
        cls.report = earnings.build_report({"id":"2026-09-20-V20ap", "label":"V20ap"}, cls.events, cls.context)
    def test_financial_totals_and_ownership(self):
        r = self.report
        self.assertEqual(r["confirmed"]["grand_total"], 148750)
        self.assertEqual(r["confirmed_and_unconfirmed"]["grand_total"], 197200)
        self.assertEqual([(c["lesson_count"],c["hours"],c["amount"]) for c in r["pending_courses"]], [(33,132,39600),(5,17.5,5250),(4,12,3600)])
        self.assertEqual([x["total"] for x in r["confirmed_and_unconfirmed"]["months"]][4:], [37425,34800,25800])
        self.assertEqual(sum(x["total"] for x in r["confirmed_and_unconfirmed"]["months"]),197200)
    def test_confirmed_payments_are_not_promoted(self):
        r = self.report
        self.assertEqual(r["confirmed"]["expected_payments"],r["confirmed_and_unconfirmed"]["expected_payments"])
        self.assertFalse(any("HF8" in x["label"] for x in r["confirmed"]["expected_payments"]["rows"]))
    def test_unknown_rate_is_not_zero(self):
        report={"confirmed":self.report["confirmed"], "notes":[]}
        config={"courses":[{"id":"lms","match":"梨木樹學校","label":"LMS", "hourly_rate":None,"basis":"rate pending"}]}
        with patch("pathlib.Path.read_text",return_value=json.dumps(config)):
            add_pending_estimates(report,self.events,"2026-09-20-V20ap",earnings.event_interval)
        self.assertIsNone(report["pending_courses"][0]["amount"])
        self.assertEqual(report["confirmed_and_unconfirmed"]["grand_total"],148750)
    def test_later_release_keeps_pending_estimates(self):
        report={"confirmed":self.report["confirmed"], "notes":[]}
        add_pending_estimates(report,self.events,"2026-09-21-V20aq",earnings.event_interval)
        self.assertEqual(report["confirmed_and_unconfirmed"]["grand_total"],197200)
    def test_records_and_course_groups_preserved(self):
        old=ROOT/"versions/2026-09-20-V20ao"
        for name in ["events.json","class_context.json"]:
            self.assertEqual((old/name).read_bytes(),(ROOT/name).read_bytes())
        a=Markup(old/"index.html");b=Markup(ROOT/"index.html")
        self.assertEqual(a.keys,b.keys)
        self.assertEqual(set(b.pending),{"g27","g29","g30"})
        self.assertEqual(b.badges["g27"],8)
        self.assertEqual(b.badges["g30"],10)

if __name__ == "__main__":
    unittest.main()
